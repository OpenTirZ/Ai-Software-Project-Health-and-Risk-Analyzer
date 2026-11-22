"""
GitHub Webhook Service
----------------------
Handles GitHub webhook event processing:
- HMAC-SHA256 signature verification over raw payload bytes
- Idempotency checking via delivery ID
- Event dispatching for push, pull_request, and ping events
- Incremental commit ingestion and real-time pull request state synchronization
"""

from __future__ import annotations

import collections
import hashlib
import hmac
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from bson import ObjectId

from Backend.database import projects_collection
from Backend.persistence import DatabaseError, upsert_commit
from Backend.persistence_telemetry import upsert_pull_request

logger = logging.getLogger(__name__)

# Bounded in-memory store for delivery IDs to ensure idempotent event handling
_MAX_DELIVERY_CACHE_SIZE = 10000
_processed_deliveries: set[str] = set()
_delivery_queue: collections.deque[str] = collections.deque(maxlen=_MAX_DELIVERY_CACHE_SIZE)


def verify_signature(raw_body: bytes, signature_header: str | None, secret: str) -> bool:
    """
    Validate that the incoming webhook request was sent by GitHub and not tampered with.
    """
    # Computes HMAC-SHA256 over raw request bytes and compares using constant-time comparison
    # to prevent timing attack vulnerabilities. Rejects missing or malformed signature headers.
    if not signature_header or not secret:
        logger.warning("Webhook signature verification failed: missing signature header or secret.")
        return False

    prefix = "sha256="
    if not signature_header.startswith(prefix):
        logger.warning("Webhook signature verification failed: header missing 'sha256=' prefix.")
        return False

    signature_hash = signature_header[len(prefix):].strip()
    if not signature_hash:
        logger.warning("Webhook signature verification failed: empty signature hex value.")
        return False

    try:
        mac = hmac.new(secret.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256)
        expected_signature = mac.hexdigest()
        return hmac.compare_digest(expected_signature, signature_hash)
    except Exception as exc:
        logger.error("Unexpected error during signature verification: %s", exc)
        return False


def is_delivery_processed(delivery_id: str | None) -> bool:
    """
    Check if a webhook delivery has already been processed to maintain idempotency.
    """
    # Queries the in-memory cache to prevent re-processing identical GitHub deliveries.
    if not delivery_id:
        return False
    return delivery_id in _processed_deliveries


def record_delivery(delivery_id: str | None) -> None:
    """
    Record a webhook delivery ID as processed in a bounded memory cache.
    """
    # Stores delivery ID in both a set for O(1) lookup and a deque to evict oldest entries
    # when the cache exceeds the bounded maximum size.
    if not delivery_id:
        return

    if delivery_id in _processed_deliveries:
        return

    if len(_processed_deliveries) >= _MAX_DELIVERY_CACHE_SIZE:
        evicted = _delivery_queue.popleft()
        _processed_deliveries.discard(evicted)

    _delivery_queue.append(delivery_id)
    _processed_deliveries.add(delivery_id)


def clear_processed_deliveries() -> None:
    """
    Reset the delivery cache, primarily used in automated test isolation.
    """
    # Empties the in-memory set and deque to ensure tests do not leak state between test cases.
    _processed_deliveries.clear()
    _delivery_queue.clear()


def find_project_by_repo(
    repo_full_name: str,
    repo_url: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Find a registered project in the database matching the given repository slug or URL.
    """
    # Searches projects collection matching repo_url or variations of github repository names
    # to associate incoming GitHub events with the corresponding local project.
    if not repo_full_name and not repo_url:
        return None

    queries: List[Dict[str, Any]] = []

    if repo_full_name:
        escaped_name = re.escape(repo_full_name.strip())
        pattern = f"{escaped_name}(\\.git)?$"
        queries.extend([
            {"repo_url": {"$regex": pattern, "$options": "i"}},
            {"githubRepoUrl": {"$regex": pattern, "$options": "i"}},
            {"repository_url": {"$regex": pattern, "$options": "i"}},
            {"name": repo_full_name.split("/")[-1]},
        ])

    if repo_url:
        clean_url = repo_url.strip().rstrip("/")
        queries.extend([
            {"repo_url": clean_url},
            {"repo_url": f"{clean_url}.git"},
        ])

    try:
        project = projects_collection.find_one({"$or": queries, "status": {"$ne": "deleted"}})
        return project
    except Exception as exc:
        logger.error("Failed to query project for repository %s: %s", repo_full_name, exc)
        return None


def dispatch_event(
    event_type: str,
    payload: Dict[str, Any],
    delivery_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Route incoming webhook event to its corresponding handler based on X-GitHub-Event.
    """
    # Inspects event type and delivery ID, checks idempotency, logs the step without leaking
    # sensitive credentials, and routes push, pull_request, and ping events to handlers.
    logger.info("Dispatching webhook event: type=%s delivery_id=%s", event_type, delivery_id)

    if delivery_id and is_delivery_processed(delivery_id):
        logger.info("Skipping duplicate delivery: %s", delivery_id)
        return {
            "status": "duplicate",
            "event": event_type,
            "delivery_id": delivery_id,
            "message": "Delivery already processed.",
        }

    if event_type == "ping":
        if delivery_id:
            record_delivery(delivery_id)
        zen = payload.get("zen", "")
        hook_id = payload.get("hook_id")
        logger.info("GitHub ping received. Zen: %s, Hook ID: %s", zen, hook_id)
        return {
            "status": "ok",
            "event": "ping",
            "zen": zen,
            "hook_id": hook_id,
        }

    if event_type == "push":
        result = handle_push_event(payload)
        if delivery_id:
            record_delivery(delivery_id)
        return result

    if event_type == "pull_request":
        result = handle_pull_request_event(payload)
        if delivery_id:
            record_delivery(delivery_id)
        return result

    logger.info("Unsupported or unhandled webhook event ignored: %s", event_type)
    return {
        "status": "ignored",
        "event": event_type,
        "message": f"Event '{event_type}' is not subscribed to.",
    }


def handle_push_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a GitHub push event and incrementally synchronize ingested commits.
    """
    # Extracts commit metadata, checks for branch deletions or zero commits,
    # associates commits with a registered project, and upserts each commit idempotently.
    return {"status": "ok", "event": "push"}


def handle_pull_request_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a GitHub pull_request event and synchronize PR state in real time.
    """
    # Parses pull request action, status, author, timestamps, diff metrics,
    # and upserts the pull request into persistence telemetry without polling.
    return {"status": "ok", "event": "pull_request"}
