"""HTTP regression tests for admin permissions, account lifecycle and project access."""
from datetime import datetime, timedelta, timezone

import mongomock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from Backend import persistence
from Backend.auth.security import create_access_token, decode_access_token
from Backend.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db(monkeypatch):
    db = mongomock.MongoClient().rbac_tests
    monkeypatch.setattr(persistence, "users_collection", db.users)
    monkeypatch.setattr(persistence, "projects_collection", db.projects)
    monkeypatch.setattr(persistence, "audit_logs_collection", db.audit_logs)
    monkeypatch.setattr(app, "dependency_overrides", {})


def _make_user(
    role: str = "developer", is_active: bool = True, name: str | None = None,
) -> tuple[str, str]:
    """Persist an account and issue a token for its initial role."""
    uid = persistence.create_user({
        "name": name or f"User {role}",
        "email": f"{ObjectId()}@example.com",
        "password_hash": "unused",
        "role": role,
        "is_active": is_active,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    })
    return uid, create_access_token({"sub": uid, "role": role})


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# Give the mutating endpoints a real target in the opposite activation state.
ADMIN_ACTIONS = [
    pytest.param("GET", "/api/admin/users", None, id="list-users"),
    pytest.param("GET", "/api/admin/audit-logs", None, id="audit-logs"),
    pytest.param("PATCH", "/api/admin/users/{uid}/role", {"role": "admin"}, id="assign-role"),
    pytest.param("POST", "/api/admin/users/{uid}/activate", None, id="activate"),
    pytest.param("POST", "/api/admin/users/{uid}/deactivate", None, id="deactivate"),
]


class TestAdminAccessControl:
    @pytest.mark.parametrize("method,path,payload", ADMIN_ACTIONS)
    @pytest.mark.parametrize("headers", [
        pytest.param({}, id="missing"),
        pytest.param({"Authorization": "Basic invalid"}, id="wrong-scheme"),
        pytest.param(_auth("invalid-token"), id="malformed-bearer"),
    ])
    def test_admin_actions_require_valid_bearer(self, method, path, payload, headers):
        uid, _ = _make_user(is_active=not path.endswith("/activate"))
        before = persistence.get_user(uid)
        response = client.request(method, path.format(uid=uid), headers=headers, json=payload)
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert persistence.get_user(uid) == before

    def test_expired_admin_token_is_rejected(self):
        admin_id, _ = _make_user("admin")
        expired = create_access_token({"sub": admin_id, "role": "admin"}, timedelta(minutes=-1))
        response = client.get("/api/admin/users", headers=_auth(expired))
        assert response.status_code == 401

    @pytest.mark.parametrize("role", ["developer", "project_manager"])
    @pytest.mark.parametrize("method,path,payload", ADMIN_ACTIONS)
    def test_non_admin_actions_are_forbidden(self, role, method, path, payload):
        _, token = _make_user(role)
        uid, _ = _make_user(is_active=not path.endswith("/activate"))
        before = persistence.get_user(uid)
        response = client.request(method, path.format(uid=uid), headers=_auth(token), json=payload)
        assert response.status_code == 403
        assert persistence.get_user(uid) == before

    @pytest.mark.parametrize("role", ["developer", "project_manager"])
    def test_non_admin_cannot_promote_self(self, role):
        uid, token = _make_user(role)
        headers = _auth(token)
        response = client.patch(f"/api/admin/users/{uid}/role", json={"role": "admin"}, headers=headers)
        assert response.status_code == 403
        assert persistence.get_user(uid)["role"] == role
        assert client.get("/api/admin/users", headers=headers).status_code == 403


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
        assert body["total"] == 3
        assert {u["role"] for u in body["items"]} == {"admin", "developer", "project_manager"}

    def test_pagination_skip_and_limit(self):
        _, tok = _make_user("admin")
        for _ in range(5):
            _make_user("developer")
        r = client.get("/api/admin/users?skip=0&limit=2", headers=_auth(tok))
        assert r.status_code == 200
        assert len(r.json()["items"]) == 2

    def test_search_by_name(self):
        _, tok = _make_user("admin")
        _make_user(name="UniqueXYZUser")
        r = client.get("/api/admin/users?search=UniqueXYZ", headers=_auth(tok))
        assert r.status_code == 200
        body = r.json()
        assert any("UniqueXYZ" in u["name"] for u in body["items"])

    def test_filter_active_false(self):
        _, tok = _make_user("admin")
        inactive_id, _ = _make_user("developer", is_active=False)
        r = client.get("/api/admin/users?is_active=false", headers=_auth(tok))
        assert r.status_code == 200
        body = r.json()
        assert [u["id"] for u in body["items"]] == [inactive_id]
        assert body["items"][0]["is_active"] is False

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
        _, tok = _make_user("admin")
        dev_id, _ = _make_user("developer")
        r = client.patch(
            f"/api/admin/users/{dev_id}/role",
            json={"role": "project_manager"},
            headers=_auth(tok),
        )
        assert r.status_code == 200
        assert r.json()["role"] == "project_manager"
        assert persistence.get_user(dev_id)["role"] == "project_manager"

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

    @pytest.mark.parametrize("new_role", ["developer", "project_manager"])
    def test_admin_cannot_demote_self(self, new_role):
        admin_id, tok = _make_user("admin")
        r = client.patch(
            f"/api/admin/users/{admin_id}/role",
            json={"role": new_role},
            headers=_auth(tok),
        )
        assert r.status_code == 400
        assert persistence.get_user(admin_id)["role"] == "admin"

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
        assert any(log["action"] == "role_change" for log in persistence.get_audit_logs())

    def test_role_change_audit_mentions_old_and_new_role(self):
        _, tok = _make_user("admin")
        dev_id, _ = _make_user("developer")
        client.patch(
            f"/api/admin/users/{dev_id}/role",
            json={"role": "admin"},
            headers=_auth(tok),
        )
        audit = next(l for l in persistence.get_audit_logs() if l["action"] == "role_change")
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

    @pytest.mark.parametrize("prefix", ["/api/admin/users", "/api/users", "/users"])
    def test_admin_cannot_deactivate_self(self, prefix):
        admin_id, tok = _make_user("admin")
        r = client.post(f"{prefix}/{admin_id}/deactivate", headers=_auth(tok))
        assert r.status_code == 400
        assert persistence.get_user(admin_id)["is_active"] is True

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
        assert any(l["action"] == "user_deactivated" for l in persistence.get_audit_logs())

    def test_activation_creates_audit_log(self):
        _, tok = _make_user("admin")
        dev_id, _ = _make_user("developer", is_active=False)
        client.post(f"/api/admin/users/{dev_id}/activate", headers=_auth(tok))
        assert any(l["action"] == "user_activated" for l in persistence.get_audit_logs())


# ===========================================================================
# 5. Deactivated user receives 401 on subsequent auth requests
# ===========================================================================

class TestDeactivatedUserAuth:
    @pytest.mark.parametrize("role", ["developer", "admin"])
    def test_deactivation_rejects_an_existing_session(self, role):
        _, acting_admin = _make_user("admin")
        uid, token = _make_user(role)
        headers = _auth(token)
        assert client.get("/auth/me", headers=headers).status_code == 200

        response = client.post(f"/api/admin/users/{uid}/deactivate", headers=_auth(acting_admin))
        assert response.status_code == 200
        assert persistence.get_user(uid)["is_active"] is False
        assert client.get("/auth/me", headers=headers).status_code == 401
        assert client.get("/api/admin/users", headers=headers).status_code == 401

    def test_deactivated_account_cannot_start_a_new_session(self):
        credentials = {"email": "inactive@example.com", "password": "Password123!"}
        signup = client.post("/auth/signup", json={"name": "Developer", **credentials})
        assert signup.status_code == 201
        uid = signup.json()["user"]["id"]
        _, admin_token = _make_user("admin")
        deactivated = client.post(f"/api/admin/users/{uid}/deactivate", headers=_auth(admin_token))
        assert deactivated.status_code == 200

        login = client.post("/auth/login", json=credentials)
        assert login.status_code == 401
        assert "access_token" not in login.json()


# ===========================================================================
# 6. GET /api/admin/audit-logs
# ===========================================================================

class TestAuditLogs:
    def test_admin_can_fetch_audit_logs(self):
        _, tok = _make_user("admin")
        # Pre-populate one log entry
        persistence.create_audit_log(
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
        persistence.create_audit_log(
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
            persistence.create_audit_log(
                {
                    "_id": ObjectId(),
                    "action": f"action_{i}",
                    "actor_id": "x",
                    "createdAt": datetime.now(timezone.utc),
                }
            )
        r = client.get("/api/admin/audit-logs?limit=3", headers=_auth(tok))
        assert r.status_code == 200
        assert len(r.json()) == 3

# ===========================================================================
# 7. JWT `role` claim in access tokens (signup & login)
# ===========================================================================

class TestJWTRoleClaim:
    def test_signup_cannot_choose_admin_role(self):
        r = client.post(
            "/auth/signup",
            json={
                "name": "Role Tester", "email": "roletest@ex.com",
                "password": "Password123!", "role": "admin",
            },
        )
        assert r.status_code == 201
        token = r.json()["access_token"]
        payload = decode_access_token(token)
        assert payload["role"] == "developer"
        assert persistence.get_user(payload["sub"])["role"] == "developer"
        assert client.get("/api/admin/users", headers=_auth(token)).status_code == 403

    def test_login_token_reflects_updated_role(self):
        credentials = {"email": "rolelogin@ex.com", "password": "Password123!"}
        signup = client.post("/auth/signup", json={"name": "Role Login", **credentials})
        assert signup.status_code == 201
        uid = signup.json()["user"]["id"]
        _, admin_token = _make_user("admin")
        promoted = client.patch(
            f"/api/admin/users/{uid}/role",
            headers=_auth(admin_token),
            json={"role": "admin"},
        )
        assert promoted.status_code == 200
        login = client.post("/auth/login", json=credentials)
        assert login.status_code == 200
        assert decode_access_token(login.json()["access_token"])["role"] == "admin"

    def test_demoted_admin_loses_access_with_existing_token(self):
        _, acting_admin = _make_user("admin")
        uid, token = _make_user("admin")
        headers = _auth(token)
        assert client.get("/api/admin/users", headers=headers).status_code == 200

        response = client.patch(
            f"/api/admin/users/{uid}/role",
            headers=_auth(acting_admin),
            json={"role": "developer"},
        )
        assert response.status_code == 200
        assert client.get("/auth/me", headers=headers).json()["role"] == "developer"
        assert client.get("/api/admin/users", headers=headers).status_code == 403


@pytest.mark.parametrize("role", ["admin", "project_manager", "developer"])
def test_project_access_for_non_member(role):
    owner_id, owner_token = _make_user("project_manager")
    created = client.post("/api/projects", json={"name": "Private project"}, headers=_auth(owner_token))
    assert created.status_code == 201
    project_id = created.json()["id"]
    path = f"/api/projects/{project_id}"

    _, token = _make_user(role)
    headers = _auth(token)
    listing = client.get("/api/projects", headers=headers)
    assert listing.status_code == 200
    detail = client.get(path, headers=headers)
    update = client.patch(path, json={"name": "Updated project"}, headers=headers)

    if role == "admin":
        assert [p["id"] for p in listing.json()] == [project_id]
        assert detail.status_code == 200
        assert detail.json()["ownerId"] == owner_id
        assert update.status_code == 200
        assert persistence.get_project(project_id)["name"] == "Updated project"
    else:
        assert listing.json() == []
        assert detail.status_code == 403
        assert update.status_code == 403
        assert persistence.get_project(project_id)["name"] == "Private project"
