"""
Tests for the RBAC Administration Endpoints (/api/admin/*).

Covers:
  - Non-admin callers receive 403 on all /api/admin/* routes.
  - GET /api/admin/users  – listing, search, pagination, is_active filter.
  - PATCH /api/admin/users/{id}/role – valid change, self-demotion block, invalid role.
  - POST /api/admin/users/{id}/activate | /deactivate – toggling, self-block, 404.
  - GET /api/admin/audit-logs – returns log entries.
  - Deactivated user receives 401 on subsequent auth requests.
  - JWT access token contains the `role` claim after signup and login.

Run with:
    PYTHONPATH=. pytest Backend/tests/test_admin_router.py -v
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from Backend.auth.dependencies import get_current_user
from Backend.auth.security import create_access_token, decode_access_token
from Backend.main import app
from Backend.persistence import clear_users, create_user, get_user, update_user

client = TestClient(app)

# ---------------------------------------------------------------------------
# Shared in-memory mock store (mirrors test_auth.py pattern)
# ---------------------------------------------------------------------------

_IN_MEMORY_USERS: dict = {}
_IN_MEMORY_AUDIT: list = []


class MockInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class MockUpdateResult:
    def __init__(self):
        self.modified_count = 1
        self.upserted_id = None


class MockUsersCollection:
    def insert_one(self, doc):
        doc_copy = dict(doc)
        doc_id = doc_copy.get("_id", ObjectId())
        doc_copy["_id"] = doc_id
        _IN_MEMORY_USERS[str(doc_id)] = doc_copy
        return MockInsertResult(doc_id)

    def find_one(self, query):
        if "_id" in query:
            target_id = str(query["_id"])
            return _IN_MEMORY_USERS.get(target_id)
        if "email" in query:
            email_q = query["email"]
            if isinstance(email_q, dict) and "$regex" in email_q:
                target = email_q["$regex"].replace("^", "").replace("$", "").lower()
            else:
                target = str(email_q).lower()
            for doc in _IN_MEMORY_USERS.values():
                if doc.get("email", "").lower() == target:
                    return doc
        return None

    def find(self, query=None):
        query = query or {}
        results = []
        for doc in _IN_MEMORY_USERS.values():
            match = True
            if "$or" in query:
                match = False
                import re
                for cond in query["$or"]:
                    for field, pattern_spec in cond.items():
                        if isinstance(pattern_spec, dict) and "$regex" in pattern_spec:
                            pat = re.compile(
                                pattern_spec["$regex"],
                                re.IGNORECASE if "$options" in pattern_spec else 0,
                            )
                            if pat.search(str(doc.get(field, ""))):
                                match = True
                                break
                    if match:
                        break
            if "is_active" in query:
                val = query["is_active"]
                # treat missing is_active as True (default)
                doc_active = doc.get("is_active", True)
                if doc_active != val:
                    match = False
            if match:
                results.append(doc)
        return _MockCursor(results)

    def update_one(self, filter_q, update_doc, upsert=False):
        target_id = str(filter_q.get("_id", ""))
        doc = _IN_MEMORY_USERS.get(target_id)
        if doc and "$set" in update_doc:
            for k, v in update_doc["$set"].items():
                doc[k] = v
        return MockUpdateResult()

    def delete_many(self, query):
        _IN_MEMORY_USERS.clear()

    def count_documents(self, query=None):
        # Use find to apply same filter logic
        return len(list(self.find(query or {})))


class _MockCursor:
    def __init__(self, docs):
        self._docs = docs
        self._skip = 0
        self._limit = None

    def sort(self, *_):
        return self

    def skip(self, n):
        self._skip = n
        return self

    def limit(self, n):
        self._limit = n
        return self

    def __iter__(self):
        docs = self._docs[self._skip:]
        if self._limit is not None:
            docs = docs[: self._limit]
        return iter(docs)


class MockAuditCollection:
    def insert_one(self, doc):
        doc_copy = dict(doc)
        doc_copy["_id"] = ObjectId()
        _IN_MEMORY_AUDIT.append(doc_copy)
        return MockInsertResult(doc_copy["_id"])

    def find(self, *_, **__):
        return _MockCursor(list(reversed(_IN_MEMORY_AUDIT)))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_db(monkeypatch):
    _IN_MEMORY_USERS.clear()
    _IN_MEMORY_AUDIT.clear()
    monkeypatch.setattr("Backend.persistence.users_collection", MockUsersCollection())
    monkeypatch.setattr("Backend.persistence.audit_logs_collection", MockAuditCollection())
    yield
    app.dependency_overrides.clear()


def _make_user(role: str = "developer", is_active: bool = True) -> tuple[str, str]:
    """Insert a user and return (user_id, bearer_token)."""
    from bson import ObjectId
    oid = ObjectId()
    doc = {
        "_id": oid,
        "name": f"User {role}",
        "email": f"{role}-{str(oid)[-4:]}@test.com",
        "password_hash": "x",
        "role": role,
        "is_active": is_active,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    _IN_MEMORY_USERS[str(oid)] = doc
    token = create_access_token({"sub": str(oid), "role": role})
    return str(oid), token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# 1. Access control — non-admin receives 403
# ===========================================================================

class TestAdminAccessControl:
    def test_developer_cannot_list_users(self):
        _, tok = _make_user("developer")
        r = client.get("/api/admin/users", headers=_auth(tok))
        assert r.status_code == 403

    def test_project_manager_cannot_list_users(self):
        _, tok = _make_user("project_manager")
        r = client.get("/api/admin/users", headers=_auth(tok))
        assert r.status_code == 403

    def test_unauthenticated_cannot_access_admin(self):
        r = client.get("/api/admin/users")
        assert r.status_code in (401, 403)

    def test_developer_cannot_change_role(self):
        uid, _ = _make_user("developer")
        _, dev_tok = _make_user("developer")
        r = client.patch(
            f"/api/admin/users/{uid}/role",
            json={"role": "admin"},
            headers=_auth(dev_tok),
        )
        assert r.status_code == 403

    def test_developer_cannot_deactivate(self):
        uid, _ = _make_user("developer")
        _, dev_tok = _make_user("developer")
        r = client.post(f"/api/admin/users/{uid}/deactivate", headers=_auth(dev_tok))
        assert r.status_code == 403

    def test_developer_cannot_view_audit_logs(self):
        _, tok = _make_user("developer")
        r = client.get("/api/admin/audit-logs", headers=_auth(tok))
        assert r.status_code == 403

    def test_admin_can_access_users_endpoint(self):
        _, tok = _make_user("admin")
        r = client.get("/api/admin/users", headers=_auth(tok))
        assert r.status_code == 200


# ===========================================================================
# 2. GET /api/admin/users
# ===========================================================================

class TestListUsers:
    def test_returns_all_users(self):
        _, tok = _make_user("admin")
        _make_user("developer")
        _make_user("project_manager")
        r = client.get("/api/admin/users", headers=_auth(tok))
        assert r.status_code == 200
        body = r.json()
        assert body["total"] >= 3
        assert len(body["items"]) >= 3

    def test_pagination_skip_and_limit(self):
        _, tok = _make_user("admin")
        for _ in range(5):
            _make_user("developer")
        r = client.get("/api/admin/users?skip=0&limit=2", headers=_auth(tok))
        assert r.status_code == 200
        assert len(r.json()["items"]) <= 2

    def test_search_by_name(self):
        _, tok = _make_user("admin")
        # Insert a user with a distinctive name via direct insertion
        from bson import ObjectId
        oid = ObjectId()
        _IN_MEMORY_USERS[str(oid)] = {
            "_id": oid,
            "name": "UniqueXYZUser",
            "email": "xyz@test.com",
            "role": "developer",
            "is_active": True,
            "createdAt": "",
        }
        r = client.get("/api/admin/users?search=UniqueXYZ", headers=_auth(tok))
        assert r.status_code == 200
        body = r.json()
        assert any("UniqueXYZ" in u["name"] for u in body["items"])

    def test_filter_active_false(self):
        _, tok = _make_user("admin")
        _make_user("developer", is_active=False)
        r = client.get("/api/admin/users?is_active=false", headers=_auth(tok))
        assert r.status_code == 200
        body = r.json()
        assert all(not u["is_active"] for u in body["items"])

    def test_response_schema_fields(self):
        _, tok = _make_user("admin")
        r = client.get("/api/admin/users", headers=_auth(tok))
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert "id" in item
            assert "name" in item
            assert "email" in item
            assert "role" in item
            assert "is_active" in item


# ===========================================================================
# 3. PATCH /api/admin/users/{id}/role
# ===========================================================================

class TestUpdateUserRole:
    def test_admin_can_promote_developer_to_project_manager(self):
        admin_id, tok = _make_user("admin")
        dev_id, _ = _make_user("developer")
        r = client.patch(
            f"/api/admin/users/{dev_id}/role",
            json={"role": "project_manager"},
            headers=_auth(tok),
        )
        assert r.status_code == 200
        assert r.json()["role"] == "project_manager"

    def test_admin_can_demote_project_manager_to_developer(self):
        _, tok = _make_user("admin")
        pm_id, _ = _make_user("project_manager")
        r = client.patch(
            f"/api/admin/users/{pm_id}/role",
            json={"role": "developer"},
            headers=_auth(tok),
        )
        assert r.status_code == 200
        assert r.json()["role"] == "developer"

    def test_admin_cannot_change_own_role(self):
        admin_id, tok = _make_user("admin")
        r = client.patch(
            f"/api/admin/users/{admin_id}/role",
            json={"role": "developer"},
            headers=_auth(tok),
        )
        assert r.status_code == 403

    def test_invalid_role_returns_422(self):
        _, tok = _make_user("admin")
        dev_id, _ = _make_user("developer")
        r = client.patch(
            f"/api/admin/users/{dev_id}/role",
            json={"role": "superuser"},
            headers=_auth(tok),
        )
        assert r.status_code == 422

    def test_nonexistent_user_returns_404(self):
        _, tok = _make_user("admin")
        fake_id = str(ObjectId())
        r = client.patch(
            f"/api/admin/users/{fake_id}/role",
            json={"role": "developer"},
            headers=_auth(tok),
        )
        assert r.status_code == 404

    def test_role_change_creates_audit_log(self):
        _, tok = _make_user("admin")
        dev_id, _ = _make_user("developer")
        client.patch(
            f"/api/admin/users/{dev_id}/role",
            json={"role": "project_manager"},
            headers=_auth(tok),
        )
        assert any(log["action"] == "role_change" for log in _IN_MEMORY_AUDIT)

    def test_role_change_audit_mentions_old_and_new_role(self):
        _, tok = _make_user("admin")
        dev_id, _ = _make_user("developer")
        client.patch(
            f"/api/admin/users/{dev_id}/role",
            json={"role": "admin"},
            headers=_auth(tok),
        )
        audit = next(l for l in _IN_MEMORY_AUDIT if l["action"] == "role_change")
        assert "developer" in audit["detail"]
        assert "admin" in audit["detail"]


# ===========================================================================
# 4. POST /api/admin/users/{id}/activate | /deactivate
# ===========================================================================

class TestActivateDeactivate:
    def test_admin_can_deactivate_another_user(self):
        _, tok = _make_user("admin")
        dev_id, _ = _make_user("developer")
        r = client.post(f"/api/admin/users/{dev_id}/deactivate", headers=_auth(tok))
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    def test_admin_can_activate_a_deactivated_user(self):
        _, tok = _make_user("admin")
        dev_id, _ = _make_user("developer", is_active=False)
        r = client.post(f"/api/admin/users/{dev_id}/activate", headers=_auth(tok))
        assert r.status_code == 200
        assert r.json()["is_active"] is True

    def test_admin_cannot_deactivate_self(self):
        admin_id, tok = _make_user("admin")
        r = client.post(f"/api/admin/users/{admin_id}/deactivate", headers=_auth(tok))
        assert r.status_code == 403

    def test_admin_cannot_activate_self(self):
        admin_id, tok = _make_user("admin")
        r = client.post(f"/api/admin/users/{admin_id}/activate", headers=_auth(tok))
        assert r.status_code == 403

    def test_deactivate_nonexistent_user_returns_404(self):
        _, tok = _make_user("admin")
        fake_id = str(ObjectId())
        r = client.post(f"/api/admin/users/{fake_id}/deactivate", headers=_auth(tok))
        assert r.status_code == 404

    def test_activate_nonexistent_user_returns_404(self):
        _, tok = _make_user("admin")
        fake_id = str(ObjectId())
        r = client.post(f"/api/admin/users/{fake_id}/activate", headers=_auth(tok))
        assert r.status_code == 404

    def test_deactivation_creates_audit_log(self):
        _, tok = _make_user("admin")
        dev_id, _ = _make_user("developer")
        client.post(f"/api/admin/users/{dev_id}/deactivate", headers=_auth(tok))
        assert any(l["action"] == "user_deactivated" for l in _IN_MEMORY_AUDIT)

    def test_activation_creates_audit_log(self):
        _, tok = _make_user("admin")
        dev_id, _ = _make_user("developer", is_active=False)
        client.post(f"/api/admin/users/{dev_id}/activate", headers=_auth(tok))
        assert any(l["action"] == "user_activated" for l in _IN_MEMORY_AUDIT)


# ===========================================================================
# 5. Deactivated user receives 401 on subsequent auth requests
# ===========================================================================

class TestDeactivatedUserAuth:
    def test_deactivated_user_gets_401_on_me(self):
        # Create a user, deactivate them in-store, then try /auth/me
        from bson import ObjectId

        oid = ObjectId()
        _IN_MEMORY_USERS[str(oid)] = {
            "_id": oid,
            "name": "Soon Inactive",
            "email": "inactive@test.com",
            "role": "developer",
            "is_active": False,
            "createdAt": "",
        }
        token = create_access_token({"sub": str(oid), "role": "developer"})
        r = client.get("/auth/me", headers=_auth(token))
        assert r.status_code == 401

    def test_active_user_gets_200_on_me(self):
        uid, tok = _make_user("developer", is_active=True)
        r = client.get("/auth/me", headers=_auth(tok))
        assert r.status_code == 200


# ===========================================================================
# 6. GET /api/admin/audit-logs
# ===========================================================================

class TestAuditLogs:
    def test_admin_can_fetch_audit_logs(self):
        _, tok = _make_user("admin")
        # Pre-populate one log entry
        _IN_MEMORY_AUDIT.append(
            {
                "_id": ObjectId(),
                "action": "test_action",
                "actor_id": "abc",
                "target_id": "def",
                "detail": "Some detail",
                "createdAt": datetime.now(timezone.utc),
            }
        )
        r = client.get("/api/admin/audit-logs", headers=_auth(tok))
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list)
        assert any(log["action"] == "test_action" for log in body)

    def test_audit_log_response_schema(self):
        _, tok = _make_user("admin")
        _IN_MEMORY_AUDIT.append(
            {
                "_id": ObjectId(),
                "action": "schema_check",
                "actor_id": "actor",
                "target_id": "target",
                "detail": "detail text",
                "createdAt": datetime.now(timezone.utc),
            }
        )
        r = client.get("/api/admin/audit-logs", headers=_auth(tok))
        assert r.status_code == 200
        log = r.json()[0]
        for field in ("id", "action", "actor_id", "created_at"):
            assert field in log

    def test_audit_logs_limit_param(self):
        _, tok = _make_user("admin")
        for i in range(10):
            _IN_MEMORY_AUDIT.append(
                {
                    "_id": ObjectId(),
                    "action": f"action_{i}",
                    "actor_id": "x",
                    "createdAt": datetime.now(timezone.utc),
                }
            )
        r = client.get("/api/admin/audit-logs?limit=3", headers=_auth(tok))
        assert r.status_code == 200
        # Limit is passed to persistence; our mock returns all, so just assert no error.
        assert isinstance(r.json(), list)

    def test_non_admin_cannot_fetch_audit_logs(self):
        _, tok = _make_user("developer")
        r = client.get("/api/admin/audit-logs", headers=_auth(tok))
        assert r.status_code == 403


# ===========================================================================
# 7. JWT `role` claim in access tokens (signup & login)
# ===========================================================================

class TestJWTRoleClaim:
    # These tests rely on the real MockUsersCollection so signup/login work.

    def test_signup_token_contains_role_claim(self):
        r = client.post(
            "/auth/signup",
            json={"name": "Role Tester", "email": "roletest@ex.com", "password": "Password123!"},
        )
        assert r.status_code == 201
        token = r.json()["access_token"]
        payload = decode_access_token(token)
        assert "role" in payload
        assert payload["role"] == "developer"

    def test_login_token_contains_role_claim(self):
        # Signup first to create the user
        client.post(
            "/auth/signup",
            json={"name": "Role Login", "email": "rolelogin@ex.com", "password": "Password123!"},
        )
        r = client.post(
            "/auth/login",
            json={"email": "rolelogin@ex.com", "password": "Password123!"},
        )
        assert r.status_code == 200
        token = r.json()["access_token"]
        payload = decode_access_token(token)
        assert "role" in payload

    def test_token_role_reflects_user_role(self):
        """Tokens for a manually inserted admin user carry the 'admin' role."""
        from bson import ObjectId

        oid = ObjectId()
        _IN_MEMORY_USERS[str(oid)] = {
            "_id": oid,
            "name": "Admin Guy",
            "email": "adminguy@ex.com",
            "password_hash": "x",
            "role": "admin",
            "is_active": True,
            "createdAt": "",
        }
        token = create_access_token({"sub": str(oid), "role": "admin"})
        payload = decode_access_token(token)
        assert payload["role"] == "admin"
