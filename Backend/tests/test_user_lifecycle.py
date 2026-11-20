"""
Unit and integration tests for User Lifecycle Management (Account Deactivation).
---------------------------------------------------------------------------------
Covers:
  1. POST /api/users/{id}/deactivate (Admin authorization).
  2. Role rejection: non-admin (developer, project_manager) gets 403 Forbidden.
  3. Unauthenticated request gets 401 Unauthorized.
  4. Invalid user ID returns 400 Bad Request.
  5. Non-existent user returns 404 Not Found.
  6. Database errors return 503 Service Unavailable.
  7. get_current_user dependency immediately rejects deactivated users (is_active=False).
  8. Active users (is_active=True or missing field) are accepted normally.
  9. Session invalidation on protected endpoints when user is deactivated.
"""

import os

# Set required environment variables before Backend imports
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-lifecycle-tests-32-chars")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/test_project_health")
os.environ.setdefault("MONGO_DATABASE", "test_project_health")

from unittest.mock import MagicMock, patch
from bson import ObjectId
import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

# Mock pymongo.MongoClient before Backend imports to avoid connecting to real DB
import pymongo
_original_mongo_client = pymongo.MongoClient


def _mock_mongo_factory(*args, **kwargs):
    mock = MagicMock()
    mock.admin.command.return_value = {"ok": 1}
    return mock


pymongo.MongoClient = _mock_mongo_factory


@pytest.fixture(autouse=True, scope="module")
def isolate_mongo_client():
    with patch("pymongo.MongoClient", side_effect=_mock_mongo_factory):
        yield
    pymongo.MongoClient = _original_mongo_client


from Backend.auth.dependencies import get_current_user
from Backend.auth.lifecycle import router as lifecycle_router
from Backend.auth.roles import Role
from Backend.auth.router import router as auth_router
from Backend.auth.security import create_access_token
from Backend.persistence import DatabaseError

app = FastAPI()
app.include_router(lifecycle_router)
app.include_router(auth_router)

client = TestClient(app)

# ---------------------------------------------------------------------------
# Fixture Users
# ---------------------------------------------------------------------------

ADMIN_ID = str(ObjectId())
DEV_ID = str(ObjectId())
PM_ID = str(ObjectId())
TARGET_USER_ID = str(ObjectId())

ADMIN_USER = {
    "_id": ADMIN_ID,
    "name": "Admin User",
    "email": "admin@example.com",
    "role": "admin",
    "is_active": True,
}

DEV_USER = {
    "_id": DEV_ID,
    "name": "Dev User",
    "email": "dev@example.com",
    "role": "developer",
    "is_active": True,
}

PM_USER = {
    "_id": PM_ID,
    "name": "PM User",
    "email": "pm@example.com",
    "role": "project_manager",
    "is_active": True,
}

TARGET_USER = {
    "_id": TARGET_USER_ID,
    "name": "Target Developer",
    "email": "target@example.com",
    "role": "developer",
    "is_active": True,
}


# ===========================================================================
# 1. POST /api/users/{id}/deactivate Endpoint Tests
# ===========================================================================

class TestUserDeactivationEndpoint:
    @patch("Backend.auth.lifecycle.update_user", return_value=True)
    @patch("Backend.auth.lifecycle.get_user")
    def test_admin_successfully_deactivates_user(self, mock_get_user, mock_update_user):
        mock_get_user.return_value = TARGET_USER
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER

        response = client.post(f"/api/users/{TARGET_USER_ID}/deactivate")
        assert response.status_code == 200

        data = response.json()
        assert data["user_id"] == TARGET_USER_ID
        assert data["is_active"] is False
        assert "deactivated successfully" in data["message"].lower()

        # Verify persistence call
        mock_update_user.assert_called_once()
        args, kwargs = mock_update_user.call_args
        assert args[0] == TARGET_USER_ID
        assert args[1]["is_active"] is False

    @patch("Backend.auth.lifecycle.get_user")
    def test_developer_forbidden_from_deactivating(self, mock_get_user):
        mock_get_user.return_value = TARGET_USER
        app.dependency_overrides[get_current_user] = lambda: DEV_USER

        response = client.post(f"/api/users/{TARGET_USER_ID}/deactivate")
        assert response.status_code == 403

    @patch("Backend.auth.lifecycle.get_user")
    def test_project_manager_forbidden_from_deactivating(self, mock_get_user):
        mock_get_user.return_value = TARGET_USER
        app.dependency_overrides[get_current_user] = lambda: PM_USER

        response = client.post(f"/api/users/{TARGET_USER_ID}/deactivate")
        assert response.status_code == 403

    def test_unauthenticated_request_rejected(self):
        app.dependency_overrides.clear()
        response = client.post(f"/api/users/{TARGET_USER_ID}/deactivate")
        assert response.status_code == 401

    def test_invalid_user_id_format_returns_400(self):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER

        response = client.post("/api/users/not-a-valid-id/deactivate")
        assert response.status_code == 400
        assert "Invalid user ID format" in response.json()["detail"]

    @patch("Backend.auth.lifecycle.get_user", return_value=None)
    def test_nonexistent_user_returns_404(self, mock_get_user):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER

        non_existent_id = str(ObjectId())
        response = client.post(f"/api/users/{non_existent_id}/deactivate")
        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    @patch("Backend.auth.lifecycle.get_user", side_effect=DatabaseError("DB read failure"))
    def test_database_error_on_get_user_returns_503(self, mock_get_user):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER

        response = client.post(f"/api/users/{TARGET_USER_ID}/deactivate")
        assert response.status_code == 503

    @patch("Backend.auth.lifecycle.update_user", side_effect=DatabaseError("DB write failure"))
    @patch("Backend.auth.lifecycle.get_user")
    def test_database_error_on_update_user_returns_503(self, mock_get_user, mock_update_user):
        mock_get_user.return_value = TARGET_USER
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER

        response = client.post(f"/api/users/{TARGET_USER_ID}/deactivate")
        assert response.status_code == 503


# ===========================================================================
# 2. get_current_user Session Invalidation Tests
# ===========================================================================

class TestGetCurrentUserDeactivation:
    @patch("Backend.auth.dependencies.get_user")
    def test_active_user_authenticates_successfully(self, mock_get_user):
        mock_get_user.return_value = TARGET_USER
        token = create_access_token({"sub": TARGET_USER_ID})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        user = get_current_user(credentials)
        assert user["_id"] == TARGET_USER_ID
        assert user["email"] == "target@example.com"

    @patch("Backend.auth.dependencies.get_user")
    def test_legacy_user_without_is_active_flag_authenticates(self, mock_get_user):
        legacy_user = dict(TARGET_USER)
        legacy_user.pop("is_active", None)
        mock_get_user.return_value = legacy_user

        token = create_access_token({"sub": TARGET_USER_ID})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        user = get_current_user(credentials)
        assert user["_id"] == TARGET_USER_ID

    @patch("Backend.auth.dependencies.get_user")
    def test_deactivated_user_session_immediately_invalidated(self, mock_get_user):
        deactivated_user = dict(TARGET_USER)
        deactivated_user["is_active"] = False
        mock_get_user.return_value = deactivated_user

        token = create_access_token({"sub": TARGET_USER_ID})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials)

        assert exc_info.value.status_code == 401
        assert "deactivated" in exc_info.value.detail.lower()

    @patch("Backend.auth.dependencies.get_user")
    def test_deactivated_user_blocked_on_protected_endpoint(self, mock_get_user):
        app.dependency_overrides.clear()
        deactivated_user = dict(TARGET_USER)
        deactivated_user["is_active"] = False
        mock_get_user.return_value = deactivated_user

        token = create_access_token({"sub": TARGET_USER_ID})
        headers = {"Authorization": f"Bearer {token}"}

        # Test against protected /auth/me endpoint
        response = client.get("/auth/me", headers=headers)
        assert response.status_code == 401
        assert "deactivated" in response.json()["detail"].lower()
