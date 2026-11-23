"""
Comprehensive Test Suite for Audit Logging Middleware and Admin Audit Log API (Issue #115)
============================================================================================
Validates:
1. HTTP Methods (POST, PUT, PATCH, DELETE are audited; GET, HEAD, OPTIONS are bypassed).
2. HTTP Status Code capture (200, 201, 204, 400, 401, 403, 404, 422, 500).
3. Authenticated User ID extraction and spoofing prevention (X-User-ID, query params ignored).
4. Route and Path extraction (simple, nested, path params, query string exclusion).
5. Client IP resolution and anti-spoofing defense.
6. UTC timestamp generation and timezone awareness.
7. Asynchronous persistence via asyncio.to_thread and resilience against database failure.
8. Role-based authorization for GET /api/admin/audit-logs (admin 200, developer 403, PM 403, unauthenticated 401).
9. Safe response serialization (ObjectId, datetime, valid JSON).
10. Security checks (no passwords, tokens, or secrets leaked into audit logs).
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch
import pymongo

# Set test environment variables before module imports
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-audit-tests-32-chars-long")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/test_project_health")
os.environ.setdefault("MONGO_DATABASE", "test_project_health")

_original_mongo_client = pymongo.MongoClient

def _mock_mongo_factory(*args, **kwargs):
    mock = MagicMock()
    mock.admin.command.return_value = {"ok": 1}
    return mock

pymongo.MongoClient = _mock_mongo_factory

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pytest
from bson import ObjectId
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from Backend.audit.audit_middleware import (
    STATE_CHANGING_METHODS,
    AuditMiddleware,
    extract_authenticated_user_id,
    get_client_ip,
)
from Backend.auth.roles import Role
from Backend.auth.security import create_access_token
from Backend.main import app
from Backend.persistence import DatabaseError


# ---------------------------------------------------------------------------
# Fixtures and Test App Setup
# ---------------------------------------------------------------------------

@pytest.fixture
def audit_sink() -> List[Dict[str, Any]]:
    """Capture audit log records in-memory during test execution."""
    sink: List[Dict[str, Any]] = []
    return sink


@pytest.fixture
def mock_persistence(monkeypatch, audit_sink):
    """Mock create_audit_log and get_audit_logs to capture in audit_sink."""
    def _fake_create_audit_log(entry: Dict[str, Any]) -> str:
        record = dict(entry)
        record["_id"] = str(ObjectId())
        audit_sink.append(record)
        return record["_id"]

    def _fake_get_audit_logs(limit: int = 100) -> List[Dict[str, Any]]:
        # Sort descending by createdAt or timestamp
        sorted_records = sorted(
            audit_sink,
            key=lambda r: r.get("createdAt") or r.get("timestamp") or datetime.min,
            reverse=True,
        )
        # Deepcopy and serialize for API response
        result = []
        for r in sorted_records[:limit]:
            doc = dict(r)
            for k, v in doc.items():
                if isinstance(v, datetime):
                    doc[k] = v.isoformat()
            result.append(doc)
        return result

    monkeypatch.setattr("Backend.persistence.create_audit_log", _fake_create_audit_log)
    monkeypatch.setattr("Backend.persistence.get_audit_logs", _fake_get_audit_logs)
    monkeypatch.setattr("Backend.routers.admin_router.get_audit_logs", _fake_get_audit_logs)
    return audit_sink


@pytest.fixture
def test_app(mock_persistence) -> FastAPI:
    """Create an isolated test FastAPI application with AuditMiddleware and sample test routes."""
    app_instance = FastAPI()

    @app_instance.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(status_code=500, content={"error": "internal_server_error"})

    app_instance.add_middleware(AuditMiddleware)

    # State-changing test routes
    @app_instance.post("/api/test-post")
    def post_route(request: Request):
        return {"status": "created", "received": True}

    @app_instance.put("/api/test-put/{item_id}")
    def put_route(item_id: str):
        return {"item_id": item_id, "updated": True}

    @app_instance.patch("/api/test-patch/{item_id}")
    def patch_route(item_id: str):
        return {"item_id": item_id, "patched": True}

    @app_instance.delete("/api/test-delete/{item_id}")
    def delete_route(item_id: str):
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Non-state-changing test routes
    @app_instance.get("/api/test-get")
    def get_route():
        return {"data": "read_only"}

    # Status-code trigger routes
    @app_instance.post("/api/status/{code}")
    def status_route(code: int):
        if code == 400:
            raise HTTPException(status_code=400, detail="Bad Request Triggered")
        if code == 401:
            raise HTTPException(status_code=401, detail="Unauthorized Triggered")
        if code == 403:
            raise HTTPException(status_code=403, detail="Forbidden Triggered")
        if code == 404:
            raise HTTPException(status_code=404, detail="Not Found Triggered")
        if code == 422:
            raise HTTPException(status_code=422, detail="Unprocessable Triggered")
        if code == 500:
            raise RuntimeError("Internal Server Error Triggered")
        return JSONResponse(status_code=code, content={"code": code})

    # Include official admin router containing canonical GET /api/admin/audit-logs
    from Backend.routers.admin_router import router as admin_router
    app_instance.include_router(admin_router)

    return app_instance


@pytest.fixture
def client(test_app) -> TestClient:
    return TestClient(test_app, raise_server_exceptions=False)


def make_auth_headers(user_id: str = "507f1f77bcf86cd799439011", role: str = "developer") -> Dict[str, str]:
    """Helper to generate valid JWT Authorization headers."""
    token = create_access_token({"sub": user_id, "role": role})
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# 1. HTTP Methods Tests
# ===========================================================================

class TestAuditHttpMethods:
    def test_state_changing_methods_are_audited(self, client, audit_sink):
        """POST, PUT, PATCH, and DELETE are strictly intercepted and audited."""
        # 1. POST
        res_post = client.post("/api/test-post", json={"hello": "world"})
        assert res_post.status_code == 200
        assert len(audit_sink) == 1
        assert audit_sink[0]["method"] == "POST"
        assert audit_sink[0]["route"] == "/api/test-post"

        # 2. PUT
        res_put = client.put("/api/test-put/item123", json={"name": "updated"})
        assert res_put.status_code == 200
        assert len(audit_sink) == 2
        assert audit_sink[1]["method"] == "PUT"
        assert audit_sink[1]["route"] == "/api/test-put/item123"

        # 3. PATCH
        res_patch = client.patch("/api/test-patch/item456", json={"flag": True})
        assert res_patch.status_code == 200
        assert len(audit_sink) == 3
        assert audit_sink[2]["method"] == "PATCH"
        assert audit_sink[2]["route"] == "/api/test-patch/item456"

        # 4. DELETE
        res_delete = client.delete("/api/test-delete/item789")
        assert res_delete.status_code == 204
        assert len(audit_sink) == 4
        assert audit_sink[3]["method"] == "DELETE"
        assert audit_sink[3]["route"] == "/api/test-delete/item789"
        assert audit_sink[3]["status_code"] == 204

    def test_read_only_methods_are_not_audited(self, client, audit_sink):
        """GET, HEAD, and OPTIONS requests must NEVER generate audit log records."""
        # GET
        res_get = client.get("/api/test-get")
        assert res_get.status_code == 200

        # HEAD
        res_head = client.head("/api/test-get")
        assert res_head.status_code in (200, 405)

        # OPTIONS
        res_options = client.options("/api/test-get")
        assert res_options.status_code in (200, 405)

        # Audit sink must remain empty
        assert len(audit_sink) == 0


# ===========================================================================
# 2. HTTP Status Code Capture Tests
# ===========================================================================

class TestAuditStatusCodeCapture:
    @pytest.mark.parametrize("status_code", [200, 201, 204, 400, 401, 403, 404, 422, 500])
    def test_audit_captures_exact_status_code(self, client, audit_sink, status_code):
        """Middleware captures the final HTTP status code for both successes and errors."""
        res = client.post(f"/api/status/{status_code}")
        assert res.status_code == status_code
        assert len(audit_sink) == 1
        assert audit_sink[0]["status_code"] == status_code
        assert audit_sink[0]["method"] == "POST"


# ===========================================================================
# 3. Authenticated User ID Integrity & Anti-Spoofing Tests
# ===========================================================================

class TestAuthenticatedUserExtraction:
    def test_authenticated_user_id_captured_from_valid_jwt(self, client, audit_sink):
        """Legitimate user ID embedded in signed JWT token is captured."""
        real_user_id = "507f1f77bcf86cd799439011"
        headers = make_auth_headers(user_id=real_user_id)

        res = client.post("/api/test-post", headers=headers, json={"action": "test"})
        assert res.status_code == 200
        assert len(audit_sink) == 1
        assert audit_sink[0]["user_id"] == real_user_id
        assert audit_sink[0]["actor_id"] == real_user_id

    def test_unauthenticated_request_has_none_user_id(self, client, audit_sink):
        """Unauthenticated requests record user_id as None without fabricating identities."""
        res = client.post("/api/test-post", json={"action": "guest"})
        assert res.status_code == 200
        assert len(audit_sink) == 1
        assert audit_sink[0]["user_id"] is None
        assert audit_sink[0]["actor_id"] is None

    def test_anti_spoofing_ignores_x_user_id_and_query_params(self, client, audit_sink):
        """Client cannot spoof identity via X-User-ID, query params, or body user_id."""
        spoofed_headers = {
            "X-User-ID": "malicious_spoofed_admin",
            "X-Actor-ID": "attacker_id",
        }
        res = client.post(
            "/api/test-post?user_id=attacker_query",
            headers=spoofed_headers,
            json={"user_id": "attacker_body"},
        )
        assert res.status_code == 200
        assert len(audit_sink) == 1
        # Spoofed identity must be completely ignored
        assert audit_sink[0]["user_id"] is None

    def test_invalid_and_expired_jwt_records_none_user(self, client, audit_sink):
        """Invalid or expired JWTs do not authenticate the user in the audit record."""
        # 1. Tampered / invalid token
        res_invalid = client.post(
            "/api/test-post",
            headers={"Authorization": "Bearer totally_invalid_jwt_token_value"},
        )
        assert res_invalid.status_code == 200
        assert audit_sink[0]["user_id"] is None

        # 2. Expired token
        expired_token = create_access_token(
            {"sub": "expired_user"},
            expires_delta=timedelta(minutes=-10),
        )
        res_expired = client.post(
            "/api/test-post",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert res_expired.status_code == 200
        assert audit_sink[1]["user_id"] is None


# ===========================================================================
# 4. Route and Path Extraction Tests
# ===========================================================================

class TestRouteAndPathExtraction:
    def test_nested_route_and_query_string_exclusion(self, client, audit_sink):
        """Route captures the clean URL path; query parameters are excluded from route."""
        res = client.post("/api/test-post?filter=active&sort=desc", json={"test": 1})
        assert res.status_code == 200
        assert len(audit_sink) == 1
        assert audit_sink[0]["route"] == "/api/test-post"
        assert audit_sink[0]["path"] == "/api/test-post"
        assert "filter" not in audit_sink[0]["route"]


# ===========================================================================
# 5. Client IP Resolution & Anti-Spoofing Tests
# ===========================================================================

class TestClientIpResolution:
    def test_direct_client_ip_recorded(self, client, audit_sink):
        """Default behavior records the actual TCP connection IP."""
        res = client.post("/api/test-post")
        assert res.status_code == 200
        assert len(audit_sink) == 1
        assert audit_sink[0]["client_ip"] in ("testclient", "127.0.0.1", "localhost", "unknown")

    def test_anti_spoofing_ignores_x_forwarded_for_by_default(self, client, audit_sink, monkeypatch):
        """Untrusted X-Forwarded-For headers are ignored by default."""
        monkeypatch.delenv("TRUST_FORWARDED_FOR", raising=False)
        headers = {"X-Forwarded-For": "203.0.113.195, 198.51.100.1"}
        res = client.post("/api/test-post", headers=headers)
        assert res.status_code == 200
        assert len(audit_sink) == 1
        # Spoofed IP must NOT be accepted
        assert audit_sink[0]["client_ip"] != "203.0.113.195"

    def test_trusted_proxy_header_resolution(self, client, audit_sink, monkeypatch):
        """When TRUST_FORWARDED_FOR is explicitly enabled, the forwarded IP is resolved."""
        monkeypatch.setenv("TRUST_FORWARDED_FOR", "true")
        headers = {"X-Forwarded-For": "198.51.100.42, 10.0.0.1"}
        res = client.post("/api/test-post", headers=headers)
        assert res.status_code == 200
        assert len(audit_sink) == 1
        assert audit_sink[0]["client_ip"] == "198.51.100.42"


# ===========================================================================
# 6. UTC Timestamp Verification Tests
# ===========================================================================

class TestTimestampVerification:
    def test_utc_timezone_aware_timestamp(self, client, audit_sink):
        """Audit record timestamp is timezone-aware UTC and close to the current time."""
        now_before = datetime.now(timezone.utc)
        res = client.post("/api/test-post")
        now_after = datetime.now(timezone.utc)

        assert res.status_code == 200
        assert len(audit_sink) == 1
        record = audit_sink[0]

        ts = record["timestamp"]
        assert isinstance(ts, datetime)
        assert ts.tzinfo is not None
        assert ts.tzinfo == timezone.utc
        assert now_before <= ts <= now_after


# ===========================================================================
# 7. Asynchronous Persistence & Resilience to Database Failures
# ===========================================================================

class TestPersistenceAndResilience:
    def test_audit_persistence_failure_does_not_break_api_request(self, client, monkeypatch, caplog):
        """Database errors during audit write do NOT fail the original API request."""
        # 1. Force DatabaseError
        def _failing_create_db_error(entry):
            raise DatabaseError("Simulated MongoDB connection drop")

        monkeypatch.setattr("Backend.persistence.create_audit_log", _failing_create_db_error)

        res_db = client.post("/api/test-post", json={"data": "important"})
        # Original business request MUST still succeed with 200
        assert res_db.status_code == 200
        assert res_db.json()["received"] is True

        # 2. Force generic Exception
        def _failing_create_generic(entry):
            raise RuntimeError("Unexpected memory fault in persistence")

        monkeypatch.setattr("Backend.persistence.create_audit_log", _failing_create_generic)

        res_gen = client.post("/api/test-post", json={"data": "vital"})
        assert res_gen.status_code == 200

    def test_exactly_one_audit_record_per_state_change(self, client, audit_sink):
        """No duplicate audit records are created for a single state-changing request."""
        res = client.post("/api/test-post", json={"msg": "single"})
        assert res.status_code == 200
        assert len(audit_sink) == 1

        # Additional request creates exactly one more
        res2 = client.put("/api/test-put/item1", json={"msg": "update"})
        assert res2.status_code == 200
        assert len(audit_sink) == 2


# ===========================================================================
# 8. Admin Endpoint Authorization Tests (GET /api/admin/audit-logs)
# ===========================================================================

class TestAdminAuditLogEndpoint:
    def test_admin_role_can_retrieve_audit_logs(self, client, audit_sink, monkeypatch):
        """Admin users receive 200 OK and valid audit log records."""
        admin_id = str(ObjectId())
        # Populate mock user in persistence and dependencies
        monkeypatch.setattr(
            "Backend.auth.dependencies.get_user",
            lambda uid: {"_id": admin_id, "role": "admin"} if uid == admin_id else None,
        )
        monkeypatch.setattr(
            "Backend.persistence.get_user",
            lambda uid: {"_id": admin_id, "role": "admin"} if uid == admin_id else None,
        )

        # Generate some audit events first
        client.post("/api/test-post", json={"a": 1})
        client.put("/api/test-put/42", json={"b": 2})

        headers = make_auth_headers(user_id=admin_id, role="admin")
        res = client.get("/api/admin/audit-logs", headers=headers)
        assert res.status_code == 200

        data = res.json()
        assert isinstance(data, list)
        assert len(data) == 2
        actions = [d["action"] for d in data]
        assert "POST /api/test-post" in actions
        assert "PUT /api/test-put/42" in actions
        assert data[0]["id"]
        assert data[0]["created_at"]

    def test_developer_role_gets_403_forbidden(self, client, monkeypatch):
        """Developer role is rejected with 403 Forbidden."""
        dev_id = str(ObjectId())
        monkeypatch.setattr(
            "Backend.auth.dependencies.get_user",
            lambda uid: {"_id": dev_id, "role": "developer"} if uid == dev_id else None,
        )
        monkeypatch.setattr(
            "Backend.persistence.get_user",
            lambda uid: {"_id": dev_id, "role": "developer"} if uid == dev_id else None,
        )
        headers = make_auth_headers(user_id=dev_id, role="developer")
        res = client.get("/api/admin/audit-logs", headers=headers)
        assert res.status_code == 403
        assert "permission" in res.json()["detail"].lower()

    def test_project_manager_role_gets_403_forbidden(self, client, monkeypatch):
        """Project manager role is rejected with 403 Forbidden."""
        pm_id = str(ObjectId())
        monkeypatch.setattr(
            "Backend.auth.dependencies.get_user",
            lambda uid: {"_id": pm_id, "role": "project_manager"} if uid == pm_id else None,
        )
        monkeypatch.setattr(
            "Backend.persistence.get_user",
            lambda uid: {"_id": pm_id, "role": "project_manager"} if uid == pm_id else None,
        )
        headers = make_auth_headers(user_id=pm_id, role="project_manager")
        res = client.get("/api/admin/audit-logs", headers=headers)
        assert res.status_code == 403

    def test_unauthenticated_request_gets_401_unauthorized(self, client):
        """Request without Authorization header receives 401 Unauthorized."""
        res = client.get("/api/admin/audit-logs")
        assert res.status_code == 401

    def test_invalid_token_gets_401_unauthorized(self, client):
        """Request with invalid Bearer token receives 401 Unauthorized."""
        res = client.get("/api/admin/audit-logs", headers={"Authorization": "Bearer bad_token"})
        assert res.status_code == 401

    def test_audit_logs_query_limit_parameter(self, client, audit_sink, monkeypatch):
        """Respects limit query parameter and bounds."""
        admin_id = str(ObjectId())
        monkeypatch.setattr(
            "Backend.auth.dependencies.get_user",
            lambda uid: {"_id": admin_id, "role": "admin"} if uid == admin_id else None,
        )
        monkeypatch.setattr(
            "Backend.persistence.get_user",
            lambda uid: {"_id": admin_id, "role": "admin"} if uid == admin_id else None,
        )
        headers = make_auth_headers(user_id=admin_id, role="admin")

        # Create 5 events
        for i in range(5):
            client.post("/api/test-post", json={"i": i})

        # Query with limit=2
        res = client.get("/api/admin/audit-logs?limit=2", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 2

        # Enforce bounds (ge=1, le=500)
        res_below = client.get("/api/admin/audit-logs?limit=0", headers=headers)
        assert res_below.status_code == 422
        res_above = client.get("/api/admin/audit-logs?limit=501", headers=headers)
        assert res_above.status_code == 422


# ===========================================================================
# 9. Security Audit & Secret Leakage Prevention
# ===========================================================================

class TestAuditSecurityAndSecretLeakage:
    def test_no_sensitive_secrets_stored_in_audit_records(self, client, audit_sink):
        """Audit records never capture passwords, bearer tokens, or API secrets."""
        headers = make_auth_headers()
        res = client.post(
            "/api/test-post",
            headers=headers,
            json={
                "password": "SUPER_SECRET_USER_PASSWORD_123",
                "api_key": "sk-real-secret-key-abcdef",
                "secret": "confidential_token",
            },
        )
        assert res.status_code == 200
        assert len(audit_sink) == 1
        record = audit_sink[0]

        # Convert entire record dictionary to string for comprehensive search
        record_str = str(record)
        assert "SUPER_SECRET_USER_PASSWORD_123" not in record_str
        assert "sk-real-secret-key-abcdef" not in record_str
        assert headers["Authorization"] not in record_str
        assert "Bearer" not in record_str


# ===========================================================================
# 10. Main FastAPI Application Integration Tests
# ===========================================================================

class TestMainAppIntegration:
    def test_main_app_has_audit_middleware_and_admin_route(self, monkeypatch):
        """Validates that the main app in Backend.main has AuditMiddleware and /api/admin/audit-logs registered."""
        from Backend.main import app as main_app

        # a. Verify the main app contains AuditMiddleware
        middleware_types = [m.cls for m in main_app.user_middleware]
        assert AuditMiddleware in middleware_types

        # b. Verify /api/admin/audit-logs is registered exactly once
        admin_audit_routes = [
            route for route in main_app.routes
            if getattr(route, "path", None) == "/api/admin/audit-logs"
        ]
        assert len(admin_audit_routes) == 1

        # c. Verify an authenticated admin can retrieve at least one mocked audit record matching AuditLogOut
        client = TestClient(main_app)
        admin_id = str(ObjectId())
        target_id = str(ObjectId())
        mock_log = {
            "_id": str(ObjectId()),
            "action": "role_change",
            "actor_id": admin_id,
            "target_id": target_id,
            "detail": "Role changed from 'developer' to 'admin'.",
            "createdAt": "2026-11-22T23:00:00Z",
        }

        monkeypatch.setattr(
            "Backend.auth.dependencies.get_user",
            lambda uid: {"_id": admin_id, "role": "admin"} if uid == admin_id else None,
        )
        monkeypatch.setattr(
            "Backend.persistence.get_user",
            lambda uid: {"_id": admin_id, "role": "admin"} if uid == admin_id else None,
        )
        monkeypatch.setattr(
            "Backend.routers.admin_router.get_audit_logs",
            lambda limit=100: [mock_log],
        )
        monkeypatch.setattr(
            "Backend.persistence.get_audit_logs",
            lambda limit=100: [mock_log],
        )

        headers = make_auth_headers(user_id=admin_id, role="admin")
        res = client.get("/api/admin/audit-logs", headers=headers)
        assert res.status_code == 200
        logs = res.json()
        assert len(logs) >= 1
        assert logs[0]["id"] == str(mock_log["_id"])
        assert logs[0]["action"] == "role_change"
        assert logs[0]["actor_id"] == admin_id
        assert logs[0]["target_id"] == target_id
        assert logs[0]["detail"] == "Role changed from 'developer' to 'admin'."
        assert logs[0]["created_at"] == "2026-11-22T23:00:00Z"
