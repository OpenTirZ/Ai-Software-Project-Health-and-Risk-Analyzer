"""
Audit Logs Persistence Layer (Sub-DAO) — AI Software Project Health & Risk Analyzer
-----------------------------------------------------------------------------------
Task: Model audit_logs collection in MongoDB Atlas with fast append-only writes,
compound index, and 90-day retention policy compliance.

Enforces:
  - Immutable, append-only log ingestion (no updates or deletes permitted).
  - Explicit schema: _id, userId, userRole, action, resourceType, resourceId,
    timestamp, ipAddress, status, details.
  - Compound indexing on (timestamp: -1, resourceType: 1).
  - Optional TTL index on timestamp for 90-day retention.
  - Robust exception mapping to DatabaseError.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from bson import ObjectId
from pymongo.errors import PyMongoError

from Backend.database import audit_logs_collection
from Backend.persistence import DatabaseError, serialize_document, to_object_id

logger = logging.getLogger(__name__)

# Valid audit status values
VALID_AUDIT_STATUSES = {"SUCCESS", "FAILURE", "PENDING", "WARNING", "INFO"}


def _normalize_audit_entry(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize raw audit dictionary fields to the required schema:
    _id, userId, userRole, action, resourceType, resourceId, timestamp, ipAddress, status, details.

    Supports both camelCase and snake_case inputs gracefully.
    """
    action = str(data.get("action") or "").strip()
    if not action:
        raise ValueError("Audit log entry requires a non-empty 'action'.")

    resource_type = str(
        data.get("resourceType") or data.get("resource_type") or ""
    ).strip()
    if not resource_type:
        raise ValueError("Audit log entry requires a non-empty 'resourceType'.")

    # Extract user information
    user_id = data.get("userId") or data.get("user_id")
    user_id_str = str(user_id).strip() if user_id is not None else None

    user_role = data.get("userRole") or data.get("user_role")
    user_role_str = str(user_role).strip().lower() if user_role is not None else None

    # Extract resource identifier
    resource_id = data.get("resourceId") or data.get("resource_id")
    resource_id_str = str(resource_id).strip() if resource_id is not None else None

    # Extract IP address
    ip_address = data.get("ipAddress") or data.get("ip_address")
    ip_address_str = str(ip_address).strip() if ip_address is not None else None

    # Status
    raw_status = str(data.get("status") or "SUCCESS").strip().upper()
    status = raw_status if raw_status in VALID_AUDIT_STATUSES else "INFO"

    # Details (metadata payload)
    raw_details = data.get("details")
    if raw_details is None:
        raw_details = data.get("detail")
    details: Union[Dict[str, Any], str]
    if isinstance(raw_details, dict):
        details = raw_details
    elif raw_details is not None:
        details = str(raw_details)
    else:
        details = {}

    # Timestamp handling: guarantee timezone-aware UTC datetime
    raw_timestamp = data.get("timestamp") or data.get("createdAt")
    if isinstance(raw_timestamp, datetime):
        if raw_timestamp.tzinfo is None:
            timestamp = raw_timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = raw_timestamp.astimezone(timezone.utc)
    elif isinstance(raw_timestamp, str):
        try:
            # ISO formatted string parse
            dt = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
            timestamp = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            timestamp = datetime.now(timezone.utc)
    else:
        timestamp = datetime.now(timezone.utc)

    entry: Dict[str, Any] = {
        "userId": user_id_str,
        "userRole": user_role_str,
        "action": action,
        "resourceType": resource_type,
        "resourceId": resource_id_str,
        "timestamp": timestamp,
        "ipAddress": ip_address_str,
        "status": status,
        "details": details,
    }

    # Preserve explicit _id if supplied
    if "_id" in data and data["_id"]:
        entry["_id"] = to_object_id(data["_id"])

    return entry


# ---------------------------------------------------------------------------
# Append-Only Write APIs (High Performance)
# ---------------------------------------------------------------------------

def log_audit_event(
    action: str,
    resource_type: str,
    user_id: Optional[str] = None,
    user_role: Optional[str] = None,
    resource_id: Optional[str] = None,
    status: str = "SUCCESS",
    details: Optional[Union[Dict[str, Any], str]] = None,
    ip_address: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> str:
    """
    Fast, append-only insertion of an individual audit log entry.

    Parameters:
        action: The performed operation (e.g. 'role_change', 'login', 'sync_commits').
        resource_type: Domain classification ('user', 'project', 'repository', 'report').
        user_id: ID of the user performing or initiating the action.
        user_role: Role of the actor ('admin', 'developer', 'project_manager').
        resource_id: ID of the entity acted upon.
        status: Operation outcome ('SUCCESS', 'FAILURE', 'WARNING', 'INFO').
        details: Supplemental key-value metadata or description.
        ip_address: Originating client IP address.
        timestamp: Explicit UTC datetime, or None for current UTC timestamp.

    Returns:
        String hex representation of the inserted MongoDB document ID.

    Raises:
        ValueError: If mandatory fields are missing.
        DatabaseError: If insertion into MongoDB Atlas fails.
    """
    entry_dict = {
        "action": action,
        "resourceType": resource_type,
        "userId": user_id,
        "userRole": user_role,
        "resourceId": resource_id,
        "status": status,
        "details": details,
        "ipAddress": ip_address,
        "timestamp": timestamp,
    }
    normalized = _normalize_audit_entry(entry_dict)

    try:
        result = audit_logs_collection.insert_one(normalized)
        return str(result.inserted_id)
    except PyMongoError as exc:
        logger.error("Failed to append audit log entry: %s", exc)
        raise DatabaseError(f"Audit log write failed: {exc}") from exc


def create_audit_log(entry: Dict[str, Any]) -> str:
    """
    Append an audit log document passed as a dictionary.
    Provides drop-in compatibility with existing callers.

    Returns:
        String hex ID of the inserted document.
    """
    normalized = _normalize_audit_entry(entry)
    try:
        result = audit_logs_collection.insert_one(normalized)
        return str(result.inserted_id)
    except PyMongoError as exc:
        logger.error("Failed to append audit log entry: %s", exc)
        raise DatabaseError(f"Audit log write failed: {exc}") from exc


def log_audit_events_batch(events: List[Dict[str, Any]]) -> List[str]:
    """
    High-throughput bulk append-only insertion of multiple audit records.
    Uses insert_many for minimal network round-trips.

    Returns:
        List of inserted document string IDs in order of insertion.
    """
    if not events:
        return []

    normalized_docs = [_normalize_audit_entry(item) for item in events]

    try:
        result = audit_logs_collection.insert_many(normalized_docs, ordered=True)
        return [str(_id) for _id in result.inserted_ids]
    except PyMongoError as exc:
        logger.error("Failed to bulk append audit log entries: %s", exc)
        raise DatabaseError(f"Bulk audit log write failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Query APIs (Indexed Reads)
# ---------------------------------------------------------------------------

def get_audit_logs(
    limit: int = 100,
    skip: int = 0,
    resource_type: Optional[str] = None,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    status: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve audit log records sorted newest-first (timestamp DESC).
    Utilizes the compound index (timestamp: -1, resourceType: 1).

    Parameters:
        limit: Maximum number of records to return (capped at 1,000).
        skip: Number of records to skip for pagination.
        resource_type: Filter by target resourceType.
        user_id: Filter by actor userId.
        action: Filter by action name.
        status: Filter by outcome status.
        start_time: Earliest timestamp filter.
        end_time: Latest timestamp filter.

    Returns:
        List of serialized audit records with string IDs.
    """
    safe_limit = max(1, min(limit, 1000))
    safe_skip = max(0, skip)

    filter_query: Dict[str, Any] = {}

    if resource_type:
        filter_query["resourceType"] = resource_type.strip()
    if user_id:
        filter_query["userId"] = str(user_id).strip()
    if action:
        filter_query["action"] = action.strip()
    if status:
        filter_query["status"] = status.strip().upper()

    # Time range filtering
    time_filter: Dict[str, Any] = {}
    if start_time:
        time_filter["$gte"] = start_time
    if end_time:
        time_filter["$lte"] = end_time
    if time_filter:
        filter_query["timestamp"] = time_filter

    try:
        cursor = (
            audit_logs_collection.find(filter_query)
            .sort("timestamp", -1)
            .skip(safe_skip)
            .limit(safe_limit)
        )
        return [serialize_document(doc) for doc in cursor]
    except PyMongoError as exc:
        logger.error("Failed to query audit logs: %s", exc)
        raise DatabaseError(f"Failed to query audit logs: {exc}") from exc


def get_audit_log_by_id(log_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a specific audit log by its unique ObjectId.
    """
    try:
        oid = to_object_id(log_id)
        doc = audit_logs_collection.find_one({"_id": oid})
        return serialize_document(doc) if doc else None
    except ValueError:
        return None
    except PyMongoError as exc:
        logger.error("Failed to fetch audit log by ID '%s': %s", log_id, exc)
        raise DatabaseError(f"Failed to fetch audit log: {exc}") from exc


def count_audit_logs(
    resource_type: Optional[str] = None,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    status: Optional[str] = None,
) -> int:
    """
    Fast count of audit logs matching specified filter criteria.
    """
    filter_query: Dict[str, Any] = {}
    if resource_type:
        filter_query["resourceType"] = resource_type.strip()
    if user_id:
        filter_query["userId"] = str(user_id).strip()
    if action:
        filter_query["action"] = action.strip()
    if status:
        filter_query["status"] = status.strip().upper()

    try:
        return audit_logs_collection.count_documents(filter_query)
    except PyMongoError as exc:
        logger.error("Failed to count audit logs: %s", exc)
        raise DatabaseError(f"Failed to count audit logs: {exc}") from exc
