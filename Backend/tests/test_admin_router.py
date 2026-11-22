"""HTTP regression tests for platform roles and user lifecycle protections."""

from datetime import datetime, timedelta, timezone

import mongomock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from Backend import persistence
from Backend.auth.security import create_access_token, decode_access_token
from Backend.main import app


@pytest.fixture(autouse=True)
def db(monkeypatch):
    with mongomock.MongoClient() as mongo:
        database = mongo.rbac
        monkeypatch.setattr(persistence, "users_collection", database.users)
        monkeypatch.setattr(persistence, "projects_collection", database.projects)
        monkeypatch.setattr(persistence, "audit_logs_collection", database.audit_logs)
        yield database


@pytest.fixture
def client():
    with TestClient(app) as http:
        yield http


def make_user(role="developer", *, active=True, name=None):
    user_id = ObjectId()
    persistence.create_user(
        {
            "_id": user_id,
            "name": name or f"User {role}",
            "email": f"{user_id}@example.com",
            "password_hash": "fixture-only",
            "role": role,
            "is_active": active,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
    )
    token = create_access_token({"sub": str(user_id), "role": role})
    return str(user_id), {"Authorization": f"Bearer {token}"}


ADMIN_ACTIONS = [
    pytest.param("GET", "/api/admin/users", None, id="list"),
    pytest.param("GET", "/api/admin/audit-logs", None, id="audit"),
    pytest.param("PATCH", "/api/admin/users/{id}/role", {"role": "admin"}, id="role"),
    pytest.param("POST", "/api/admin/users/{id}/activate", None, id="activate"),
    pytest.param("POST", "/api/admin/users/{id}/deactivate", None, id="deactivate"),
]


@pytest.mark.parametrize("method,path,body", ADMIN_ACTIONS)
@pytest.mark.parametrize(
    "authorization",
    [None, "Basic abc", "Bearer invalid"],
    ids=["missing", "wrong-scheme", "malformed"],
)
def test_admin_actions_require_valid_bearer(client, method, path, body, authorization):
    target, _ = make_user()
    headers = {} if authorization is None else {"Authorization": authorization}
    response = client.request(
        method, path.format(id=target), headers=headers, json=body
    )
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_expired_admin_session_is_unauthorized(client):
    user_id, _ = make_user("admin")
    expired = create_access_token(
        {"sub": user_id, "role": "admin"}, timedelta(minutes=-1)
    )
    response = client.get(
        "/api/admin/users", headers={"Authorization": f"Bearer {expired}"}
    )
    assert response.status_code == 401


@pytest.mark.parametrize("role", ["developer", "project_manager"])
@pytest.mark.parametrize("method,path,body", ADMIN_ACTIONS)
def test_non_admin_cannot_administer_other_users(client, db, role, method, path, body):
    _, headers = make_user(role)
    # Each attempted mutation would change the target if the guard were removed.
    target, _ = make_user(active=not path.endswith("/activate"))
    before = persistence.get_user(target)
    response = client.request(
        method, path.format(id=target), headers=headers, json=body
    )
    assert response.status_code == 403
    assert persistence.get_user(target) == before
    assert (
        db.audit_logs.count_documents(
            {"action": {"$in": ["role_change", "user_activated", "user_deactivated"]}}
        )
        == 0
    )


@pytest.mark.parametrize("role", ["developer", "project_manager"])
def test_cannot_grant_self_admin(client, role):
    user_id, headers = make_user(role)
    response = client.patch(
        f"/api/admin/users/{user_id}/role", headers=headers, json={"role": "admin"}
    )
    assert response.status_code == 403
    assert persistence.get_user(user_id)["role"] == role
    assert client.get("/api/admin/users", headers=headers).status_code == 403


def test_admin_directory_and_filters(client):
    admin_id, headers = make_user("admin")
    dev_id, _ = make_user(name="Directory Example")
    pm_id, _ = make_user("project_manager", active=False)

    response = client.get("/api/admin/users", headers=headers)
    assert response.status_code == 200
    directory = response.json()
    assert directory["total"] == 3
    assert {user["id"] for user in directory["items"]} == {admin_id, dev_id, pm_id}
    for user in directory["items"]:
        assert set(user) == {"id", "name", "email", "role", "is_active", "created_at"}

    for filters, expected in [
        ({"search": "directory"}, dev_id),
        ({"is_active": False}, pm_id),
    ]:
        response = client.get("/api/admin/users", headers=headers, params=filters)
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert [user["id"] for user in response.json()["items"]] == [expected]

    page = client.get(
        "/api/admin/users", headers=headers, params={"skip": 1, "limit": 1}
    )
    assert page.status_code == 200
    assert page.json() == {
        "total": 3,
        "skip": 1,
        "limit": 1,
        "items": directory["items"][1:2],
    }


def test_role_changes_take_effect_on_existing_sessions(client):
    actor, admin = make_user("admin")
    target, session = make_user()
    role_path = f"/api/admin/users/{target}/role"
    for role, expected_access in [
        ("project_manager", 403),
        ("admin", 200),
        ("developer", 403),
    ]:
        response = client.patch(role_path, headers=admin, json={"role": role})
        assert response.status_code == 200
        assert response.json()["role"] == persistence.get_user(target)["role"] == role
        assert (
            client.get("/api/admin/users", headers=session).status_code
            == expected_access
        )

    logs = client.get("/api/admin/audit-logs", headers=admin)
    assert logs.status_code == 200
    entries = logs.json()
    assert len(entries) == 3
    for entry in entries:
        assert entry["id"] and entry["created_at"]
        assert (entry["action"], entry["actor_id"], entry["target_id"]) == (
            "role_change",
            actor,
            target,
        )
    assert any(
        "admin" in entry["detail"] and "developer" in entry["detail"]
        for entry in entries
    )
    limited = client.get("/api/admin/audit-logs", headers=admin, params={"limit": 2})
    assert limited.status_code == 200
    assert len(limited.json()) == 2


def test_demoted_admin_cannot_use_previously_issued_admin_token(client):
    _, admin = make_user("admin")
    target, old_admin_session = make_user("admin")
    path = f"/api/admin/users/{target}/role"
    assert client.get("/api/admin/users", headers=old_admin_session).status_code == 200
    assert (
        client.patch(path, headers=admin, json={"role": "developer"}).status_code == 200
    )
    assert client.get("/api/admin/users", headers=old_admin_session).status_code == 403
    assert (
        client.patch(
            path, headers=old_admin_session, json={"role": "admin"}
        ).status_code
        == 403
    )
    assert persistence.get_user(target)["role"] == "developer"


@pytest.mark.parametrize("role", ["developer", "project_manager"])
def test_admin_cannot_demote_self(client, db, role):
    actor, admin = make_user("admin")
    response = client.patch(
        f"/api/admin/users/{actor}/role", headers=admin, json={"role": role}
    )
    assert response.status_code == 400
    assert persistence.get_user(actor)["role"] == "admin"
    assert db.audit_logs.count_documents({"action": "role_change"}) == 0


@pytest.mark.parametrize("prefix", ["/api/admin/users", "/api/users", "/users"])
def test_admin_cannot_deactivate_self(client, db, prefix):
    actor, admin = make_user("admin")
    response = client.post(f"{prefix}/{actor}/deactivate", headers=admin)
    assert response.status_code == 400
    assert persistence.get_user(actor)["is_active"] is True
    assert db.audit_logs.count_documents({"action": "user_deactivated"}) == 0
    assert client.get("/api/admin/users", headers=admin).status_code == 200


def test_admin_cannot_activate_self(client):
    actor, admin = make_user("admin")
    assert (
        client.post(f"/api/admin/users/{actor}/activate", headers=admin).status_code
        == 403
    )


@pytest.mark.parametrize(
    "method,suffix,body",
    [
        ("PATCH", "role", {"role": "developer"}),
        ("POST", "activate", None),
        ("POST", "deactivate", None),
    ],
)
def test_missing_target_returns_404(client, method, suffix, body):
    _, admin = make_user("admin")
    response = client.request(
        method, f"/api/admin/users/{ObjectId()}/{suffix}", headers=admin, json=body
    )
    assert response.status_code == 404


def test_unknown_role_is_rejected(client):
    _, admin = make_user("admin")
    target, _ = make_user()
    response = client.patch(
        f"/api/admin/users/{target}/role", headers=admin, json={"role": "unknown"}
    )
    assert response.status_code == 422
    assert persistence.get_user(target)["role"] == "developer"


@pytest.mark.parametrize("role", ["developer", "admin"])
def test_deactivation_rejects_a_previously_working_session(client, db, role):
    actor, admin = make_user("admin")
    target, session = make_user(role)
    protected = "/api/admin/users" if role == "admin" else "/auth/me"
    assert client.get(protected, headers=session).status_code == 200

    response = client.post(f"/api/admin/users/{target}/deactivate", headers=admin)
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert persistence.get_user(target)["is_active"] is False
    assert client.get(protected, headers=session).status_code == 401
    assert client.get("/api/projects", headers=session).status_code == 401

    response = client.post(f"/api/admin/users/{target}/activate", headers=admin)
    assert response.status_code == 200
    assert response.json()["is_active"] is True
    assert persistence.get_user(target)["is_active"] is True
    assert {
        log["action"]
        for log in db.audit_logs.find({"actor_id": actor, "target_id": target})
    } == {"user_deactivated", "user_activated"}


def test_signup_and_login_respect_stored_role_and_account_status(client):
    _, admin = make_user("admin")
    credentials = {"email": "new.user@example.com", "password": "FixturePassword1!"}
    signup = client.post(
        "/auth/signup", json={**credentials, "name": "New User", "role": "admin"}
    )
    assert signup.status_code == 201
    account = signup.json()
    user_id = account["user"]["id"]
    assert (
        account["user"]["role"] == persistence.get_user(user_id)["role"] == "developer"
    )
    assert decode_access_token(account["access_token"])["role"] == "developer"

    promoted = client.patch(
        f"/api/admin/users/{user_id}/role", headers=admin, json={"role": "admin"}
    )
    assert promoted.status_code == 200
    login = client.post("/auth/login", json=credentials)
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert decode_access_token(token)["role"] == "admin"
    session = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/admin/users", headers=session).status_code == 200

    assert (
        client.post(f"/api/admin/users/{user_id}/deactivate", headers=admin).status_code
        == 200
    )
    assert client.get("/api/admin/users", headers=session).status_code == 401
    denied = client.post("/auth/login", json=credentials)
    assert denied.status_code == 401
    assert "access_token" not in denied.json()


@pytest.mark.parametrize("role", ["admin", "project_manager", "developer"])
def test_cross_project_access_requires_global_admin(client, role):
    _, owner = make_user("project_manager")
    created = client.post(
        "/api/projects", headers=owner, json={"name": "Private project"}
    )
    assert created.status_code == 201
    project_id = created.json()["id"]
    path = f"/api/projects/{project_id}"
    _, outsider = make_user(role)

    listing = client.get("/api/projects", headers=outsider)
    assert listing.status_code == 200
    expected = 200 if role == "admin" else 403
    assert [p["id"] for p in listing.json()] == (
        [project_id] if role == "admin" else []
    )
    assert client.get(path, headers=outsider).status_code == expected
    assert client.get(f"{path}/thresholds", headers=outsider).status_code == expected
    assert (
        client.patch(path, headers=outsider, json={"name": "Renamed"}).status_code
        == expected
    )
    assert persistence.get_project(project_id)["name"] == (
        "Renamed" if role == "admin" else "Private project"
    )
