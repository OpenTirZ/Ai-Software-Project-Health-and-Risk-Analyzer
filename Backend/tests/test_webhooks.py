"""
Unit and Integration Tests for GitHub Webhook Listener
------------------------------------------------------
Covers:
- HMAC-SHA256 signature verification over raw request body
- Fails closed when GITHUB_WEBHOOK_SECRET is not configured
- Event routing: ping, push, pull_request, and unsupported events
- Pull request actions: opened, closed (merged vs unmerged), reopened, synchronize
- Push event edge cases: zero commits, deleted branch, incremental commit sync
- Delivery idempotency using X-GitHub-Delivery
- Rejection of invalid JSON, tampered payloads, and malformed signature headers
"""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch
import pytest
from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Backend.externalservies import webhook_service
from Backend.routers.webhook_router import router as webhook_router

TEST_SECRET = "super-secret-test-webhook-key-123"
MOCK_PROJECT_ID = str(ObjectId())


def compute_signature(secret: str, raw_body: bytes) -> str:
    """Helper to compute valid GitHub HMAC-SHA256 signature header for test payloads."""
    # Computes standard sha256=<hex> signature using the specified webhook secret.
    mac = hmac.new(secret.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


@pytest.fixture(autouse=True)
def clean_delivery_cache():
    """Ensure delivery cache is reset before and after every test."""
    webhook_service.clear_processed_deliveries()
    yield
    webhook_service.clear_processed_deliveries()


@pytest.fixture
def webhook_app():
    """Create a test FastAPI application hosting the webhook router."""
    app = FastAPI()
    app.include_router(webhook_router)
    return app


@pytest.fixture
def client(webhook_app):
    """Create a TestClient with test secret configured in environment."""
    with patch.dict("os.environ", {"GITHUB_WEBHOOK_SECRET": TEST_SECRET}):
        with TestClient(webhook_app) as tc:
            yield tc


# ---------------------------------------------------------------------------
# 1. Unit Tests: Signature Verification
# ---------------------------------------------------------------------------

def test_verify_signature_valid():
    """Valid signature matches raw body bytes."""
    raw_body = b'{"action": "ping"}'
    sig = compute_signature(TEST_SECRET, raw_body)
    assert webhook_service.verify_signature(raw_body, sig, TEST_SECRET) is True


def test_verify_signature_tampered_body():
    """Altered body fails signature verification."""
    original_body = b'{"action": "ping"}'
    sig = compute_signature(TEST_SECRET, original_body)
    tampered_body = b'{"action": "ping", "hacked": true}'
    assert webhook_service.verify_signature(tampered_body, sig, TEST_SECRET) is False


def test_verify_signature_wrong_secret():
    """Signature generated with a different secret fails verification."""
    raw_body = b'{"action": "ping"}'
    sig = compute_signature("wrong-secret", raw_body)
    assert webhook_service.verify_signature(raw_body, sig, TEST_SECRET) is False


def test_verify_signature_missing_header():
    """Missing signature header returns False."""
    assert webhook_service.verify_signature(b"body", None, TEST_SECRET) is False
    assert webhook_service.verify_signature(b"body", "", TEST_SECRET) is False


def test_verify_signature_malformed_header():
    """Header without sha256= prefix or empty hash returns False."""
    assert webhook_service.verify_signature(b"body", "invalid_format", TEST_SECRET) is False
    assert webhook_service.verify_signature(b"body", "sha256=", TEST_SECRET) is False
    assert webhook_service.verify_signature(b"body", "sha1=abcdef", TEST_SECRET) is False


def test_verify_signature_missing_secret():
    """Missing secret configuration returns False."""
    assert webhook_service.verify_signature(b"body", "sha256=abcdef", "") is False


# ---------------------------------------------------------------------------
# 2. Integration Tests: Secret Configuration (Fail-Closed)
# ---------------------------------------------------------------------------

def test_secret_not_configured_fails_closed(webhook_app):
    """When GITHUB_WEBHOOK_SECRET is not set, endpoint fails closed with 500."""
    with patch.dict("os.environ", {}, clear=True):
        client_no_secret = TestClient(webhook_app)
        raw_body = b'{"action": "ping"}'
        sig = compute_signature("test", raw_body)
        headers = {
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "ping",
            "Content-Type": "application/json",
        }
        response = client_no_secret.post("/api/webhooks/github", content=raw_body, headers=headers)
        assert response.status_code == 500
        assert "not configured" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 3. Integration Tests: Signature Validation via Router
# ---------------------------------------------------------------------------

def test_missing_signature_header_rejected(client):
    """Requests missing X-Hub-Signature-256 are rejected with 401."""
    raw_body = b'{"action": "ping"}'
    headers = {
        "X-GitHub-Event": "ping",
        "Content-Type": "application/json",
    }
    response = client.post("/api/webhooks/github", content=raw_body, headers=headers)
    assert response.status_code == 401
    assert "missing" in response.json()["detail"].lower()


def test_invalid_signature_rejected(client):
    """Requests with incorrect signature are rejected with 401."""
    raw_body = b'{"action": "ping"}'
    headers = {
        "X-Hub-Signature-256": "sha256=0000000000000000000000000000000000000000000000000000000000000000",
        "X-GitHub-Event": "ping",
        "Content-Type": "application/json",
    }
    response = client.post("/api/webhooks/github", content=raw_body, headers=headers)
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


def test_malformed_signature_rejected(client):
    """Requests with malformed signature prefix are rejected with 401."""
    raw_body = b'{"action": "ping"}'
    headers = {
        "X-Hub-Signature-256": "sha1=abcdef123456",
        "X-GitHub-Event": "ping",
        "Content-Type": "application/json",
    }
    response = client.post("/api/webhooks/github", content=raw_body, headers=headers)
    assert response.status_code == 401


def test_invalid_json_payload_rejected(client):
    """Invalid JSON payload with valid signature rejected with 400."""
    raw_body = b"not valid json {"
    sig = compute_signature(TEST_SECRET, raw_body)
    headers = {
        "X-Hub-Signature-256": sig,
        "X-GitHub-Event": "push",
        "Content-Type": "application/json",
    }
    response = client.post("/api/webhooks/github", content=raw_body, headers=headers)
    assert response.status_code == 400
    assert "invalid json" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 4. Integration Tests: Event Handlers
# ---------------------------------------------------------------------------

def test_ping_event_happy_path(client):
    """Ping event returns 200 with pong response."""
    payload = {"zen": "Keep it logically awesome.", "hook_id": 98765}
    raw_body = json.dumps(payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, raw_body)
    headers = {
        "X-Hub-Signature-256": sig,
        "X-GitHub-Event": "ping",
        "X-GitHub-Delivery": "delivery-ping-1",
        "Content-Type": "application/json",
    }
    response = client.post("/api/webhooks/github", content=raw_body, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["zen"] == "Keep it logically awesome."


def test_unsupported_event_ignored(client):
    """Unsupported event returns 200 with status ignored."""
    payload = {"action": "created", "check_run": {"id": 123}}
    raw_body = json.dumps(payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, raw_body)
    headers = {
        "X-Hub-Signature-256": sig,
        "X-GitHub-Event": "check_run",
        "X-GitHub-Delivery": "delivery-unsupported-1",
        "Content-Type": "application/json",
    }
    response = client.post("/api/webhooks/github", content=raw_body, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ignored"
    assert data["event"] == "check_run"


def test_idempotency_duplicate_delivery(client):
    """Duplicate delivery ID returns 200 without reprocessing."""
    payload = {"zen": "Mindful communication."}
    raw_body = json.dumps(payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, raw_body)
    headers = {
        "X-Hub-Signature-256": sig,
        "X-GitHub-Event": "ping",
        "X-GitHub-Delivery": "delivery-dup-test",
        "Content-Type": "application/json",
    }

    # First delivery
    res1 = client.post("/api/webhooks/github", content=raw_body, headers=headers)
    assert res1.status_code == 200
    assert res1.json()["status"] == "ok"

    # Second delivery with same delivery ID
    res2 = client.post("/api/webhooks/github", content=raw_body, headers=headers)
    assert res2.status_code == 200
    assert res2.json()["status"] == "duplicate"


# ---------------------------------------------------------------------------
# 5. Push Event Tests
# ---------------------------------------------------------------------------

@patch("Backend.externalservies.webhook_service.find_project_by_repo")
@patch("Backend.externalservies.webhook_service.upsert_commit")
def test_push_event_happy_path(mock_upsert_commit, mock_find_project, client):
    """Valid push event ingests commits incrementally into project."""
    mock_find_project.return_value = {
        "_id": ObjectId(MOCK_PROJECT_ID),
        "name": "Health Analyzer",
        "repo_url": "https://github.com/org/repo",
        "default_branch": "main",
    }

    payload = {
        "ref": "refs/heads/main",
        "before": "sha-old",
        "after": "sha-new-2",
        "repository": {
            "full_name": "org/repo",
            "html_url": "https://github.com/org/repo",
            "default_branch": "main",
        },
        "commits": [
            {
                "id": "sha-new-1",
                "message": "fix: update risk calculations",
                "timestamp": "2026-11-22T10:00:00Z",
                "author": {"name": "Om Patel", "username": "ompatel"},
                "added": ["file1.py"],
                "removed": [],
                "modified": ["file2.py"],
            },
            {
                "id": "sha-new-2",
                "message": "feat: webhook listener implementation",
                "timestamp": "2026-11-22T10:05:00Z",
                "author": {"name": "Om Patel", "username": "ompatel"},
                "added": ["webhook.py"],
                "removed": [],
                "modified": [],
            },
        ],
    }

    raw_body = json.dumps(payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, raw_body)
    headers = {
        "X-Hub-Signature-256": sig,
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": "delivery-push-1",
        "Content-Type": "application/json",
    }

    response = client.post("/api/webhooks/github", content=raw_body, headers=headers)
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"

    # Verify background execution upserted commits
    assert mock_upsert_commit.call_count == 2
    first_call_args = mock_upsert_commit.call_args_list[0]
    assert first_call_args[0][0] == MOCK_PROJECT_ID
    assert first_call_args[0][1]["sha"] == "sha-new-1"
    assert first_call_args[0][1]["author"] == "Om Patel"


@patch("Backend.externalservies.webhook_service.upsert_commit")
def test_push_event_zero_commits(mock_upsert_commit, client):
    """Push event with zero commits is safely skipped."""
    payload = {
        "ref": "refs/heads/main",
        "before": "sha-old",
        "after": "sha-new",
        "repository": {"full_name": "org/repo"},
        "commits": [],
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, raw_body)
    headers = {
        "X-Hub-Signature-256": sig,
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": "delivery-push-zero",
        "Content-Type": "application/json",
    }

    response = client.post("/api/webhooks/github", content=raw_body, headers=headers)
    assert response.status_code == 202
    assert mock_upsert_commit.call_count == 0


@patch("Backend.externalservies.webhook_service.upsert_commit")
def test_push_event_branch_deletion(mock_upsert_commit, client):
    """Branch deletion push event is safely skipped."""
    payload = {
        "ref": "refs/heads/feature-branch",
        "before": "sha-old",
        "after": "0000000000000000000000000000000000000000",
        "deleted": True,
        "repository": {"full_name": "org/repo"},
        "commits": [],
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, raw_body)
    headers = {
        "X-Hub-Signature-256": sig,
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": "delivery-push-del",
        "Content-Type": "application/json",
    }

    response = client.post("/api/webhooks/github", content=raw_body, headers=headers)
    assert response.status_code == 202
    assert mock_upsert_commit.call_count == 0


# ---------------------------------------------------------------------------
# 6. Pull Request Event Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "action,merged,expected_state",
    [
        ("opened", False, "open"),
        ("reopened", False, "open"),
        ("synchronize", False, "open"),
        ("closed", True, "merged"),
        ("closed", False, "closed"),
    ],
)
@patch("Backend.externalservies.webhook_service.find_project_by_repo")
@patch("Backend.externalservies.webhook_service.upsert_pull_request")
def test_pull_request_event_states(
    mock_upsert_pr,
    mock_find_project,
    client,
    action,
    merged,
    expected_state,
):
    """Pull request events accurately update PR states across lifecycle actions."""
    mock_find_project.return_value = {
        "_id": ObjectId(MOCK_PROJECT_ID),
        "name": "Health Analyzer",
        "repo_url": "https://github.com/org/repo",
    }
    mock_upsert_pr.return_value = "mock_pr_doc_id"

    payload = {
        "action": action,
        "repository": {
            "full_name": "org/repo",
            "html_url": "https://github.com/org/repo",
        },
        "pull_request": {
            "number": 42,
            "title": "Add Webhook Listener Endpoint",
            "state": "closed" if action == "closed" else "open",
            "merged": merged,
            "draft": False,
            "user": {"login": "ompatel"},
            "base": {"ref": "main"},
            "head": {"ref": "Om_Patel"},
            "created_at": "2026-11-22T08:00:00Z",
            "updated_at": "2026-11-22T08:30:00Z",
            "closed_at": "2026-11-22T09:00:00Z" if action == "closed" else None,
            "merged_at": "2026-11-22T09:00:00Z" if merged else None,
            "additions": 150,
            "deletions": 10,
            "changed_files": 4,
            "html_url": "https://github.com/org/repo/pull/42",
        },
    }

    raw_body = json.dumps(payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, raw_body)
    delivery_id = f"delivery-pr-{action}-{merged}"
    headers = {
        "X-Hub-Signature-256": sig,
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": delivery_id,
        "Content-Type": "application/json",
    }

    response = client.post("/api/webhooks/github", content=raw_body, headers=headers)
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"

    # Verify upsert_pull_request was invoked with expected values
    assert mock_upsert_pr.call_count == 1
    call_args = mock_upsert_pr.call_args[0]
    assert call_args[0] == MOCK_PROJECT_ID
    pr_data = call_args[1]
    assert pr_data["number"] == 42
    assert pr_data["state"] == expected_state
    assert pr_data["merged"] is merged
    assert pr_data["author"] == "ompatel"
    assert pr_data["additions"] == 150
    assert pr_data["deletions"] == 10


def test_tampered_body_rejected_by_router(client):
    """Router rejects request when body bytes do not match signature."""
    raw_body = b'{"action": "ping", "data": "original"}'
    sig = compute_signature(TEST_SECRET, raw_body)
    tampered_body = b'{"action": "ping", "data": "tampered"}'
    headers = {
        "X-Hub-Signature-256": sig,
        "X-GitHub-Event": "ping",
        "Content-Type": "application/json",
    }
    response = client.post("/api/webhooks/github", content=tampered_body, headers=headers)
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


@patch("Backend.externalservies.webhook_service.find_project_by_repo")
@patch("Backend.externalservies.webhook_service.upsert_commit")
def test_push_non_default_branch_ignored(mock_upsert_commit, mock_find_project, client):
    """Pushes to a non-default branch are ignored when project specifies a default branch."""
    mock_find_project.return_value = {
        "_id": ObjectId(MOCK_PROJECT_ID),
        "name": "Health Analyzer",
        "default_branch": "main",
    }

    payload = {
        "ref": "refs/heads/feature-branch",
        "before": "sha-old",
        "after": "sha-new",
        "repository": {"full_name": "org/repo", "default_branch": "main"},
        "commits": [{"id": "sha-feat-1", "message": "feat work"}],
    }

    raw_body = json.dumps(payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, raw_body)
    headers = {
        "X-Hub-Signature-256": sig,
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": "delivery-non-default-branch",
        "Content-Type": "application/json",
    }

    response = client.post("/api/webhooks/github", content=raw_body, headers=headers)
    assert response.status_code == 202
    assert mock_upsert_commit.call_count == 0


@patch("Backend.externalservies.webhook_service.find_project_by_repo")
@patch("Backend.externalservies.webhook_service.upsert_commit")
def test_push_unlinked_repo_handled_cleanly(mock_upsert_commit, mock_find_project, client):
    """Push event for unlinked repository does not error and does not upsert commits."""
    mock_find_project.return_value = None

    payload = {
        "ref": "refs/heads/main",
        "before": "sha-old",
        "after": "sha-new",
        "repository": {"full_name": "unlinked/repo", "default_branch": "main"},
        "commits": [{"id": "sha-unlinked-1", "message": "some work"}],
    }

    raw_body = json.dumps(payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, raw_body)
    headers = {
        "X-Hub-Signature-256": sig,
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": "delivery-unlinked-repo",
        "Content-Type": "application/json",
    }

    response = client.post("/api/webhooks/github", content=raw_body, headers=headers)
    assert response.status_code == 202
    assert mock_upsert_commit.call_count == 0


@pytest.mark.parametrize(
    "action",
    [
        "ready_for_review",
        "converted_to_draft",
        "labeled",
        "unlabeled",
        "assigned",
        "edited",
    ],
)
@patch("Backend.externalservies.webhook_service.find_project_by_repo")
@patch("Backend.externalservies.webhook_service.upsert_pull_request")
def test_pull_request_additional_actions(mock_upsert_pr, mock_find_project, client, action):
    """PR lifecycle actions like labeled, assigned, ready_for_review upsert PR data."""
    mock_find_project.return_value = {
        "_id": ObjectId(MOCK_PROJECT_ID),
        "name": "Health Analyzer",
    }

    payload = {
        "action": action,
        "repository": {"full_name": "org/repo"},
        "pull_request": {
            "number": 101,
            "title": f"Action test for {action}",
            "state": "open",
            "merged": False,
            "draft": (action == "converted_to_draft"),
            "user": {"login": "ompatel"},
        },
    }

    raw_body = json.dumps(payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, raw_body)
    headers = {
        "X-Hub-Signature-256": sig,
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": f"delivery-action-{action}",
        "Content-Type": "application/json",
    }

    response = client.post("/api/webhooks/github", content=raw_body, headers=headers)
    assert response.status_code == 202
    assert mock_upsert_pr.call_count == 1
    call_args = mock_upsert_pr.call_args[0]
    assert call_args[1]["number"] == 101
    assert call_args[1]["action"] == action


def test_delivery_cache_bounded_eviction():
    """Delivery cache discards the oldest entry when exceeding maximum capacity."""
    # Temporarily set max cache to a tiny number to test eviction
    with patch("Backend.externalservies.webhook_service._MAX_DELIVERY_CACHE_SIZE", 3):
        webhook_service.record_delivery("del-1")
        webhook_service.record_delivery("del-2")
        webhook_service.record_delivery("del-3")
        assert webhook_service.is_delivery_processed("del-1") is True

        webhook_service.record_delivery("del-4")
        # del-1 should be evicted
        assert webhook_service.is_delivery_processed("del-1") is False
        assert webhook_service.is_delivery_processed("del-2") is True
        assert webhook_service.is_delivery_processed("del-3") is True
        assert webhook_service.is_delivery_processed("del-4") is True

