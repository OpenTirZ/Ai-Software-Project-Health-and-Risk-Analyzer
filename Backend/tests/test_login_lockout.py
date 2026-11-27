"""
Unit and integration tests for Password Login Rate Limiting & Account Lockout.
-----------------------------------------------------------------------------
Covers:
  1. Failed password attempt increments user's failure counter.
  2. 401 response specifies remaining attempts before lockout.
  3. 5th consecutive failed attempt triggers 15-minute temporary lockout (HTTP 423).
  4. Locked account rejects login even if valid password is provided (HTTP 423).
  5. Expired lockout automatically permits authentication and resets counters.
  6. Successful authentication clears any previous failed attempts.
  7. Non-existent and deactivated users return standard 401 without updating lockout.
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-lockout-tests-32-chars")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/test_project_health")
os.environ.setdefault("MONGO_DATABASE", "test_project_health")

import pymongo
_original_mongo_client = pymongo.MongoClient


def _mock_mongo_factory(*args, **kwargs):
    mock = MagicMock()
    mock.admin.command.return_value = {"ok": 1}
    return mock


pymongo.MongoClient = _mock_mongo_factory

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Backend.auth.router import router as auth_router
from Backend.auth.security import hash_password

app = FastAPI()
app.include_router(auth_router)
client = TestClient(app)

TEST_PASSWORD = "CorrectPassword123!"
HASHED_PASSWORD = hash_password(TEST_PASSWORD)


def _build_test_user(failed_attempts=0, locked_until=None, is_active=True):
    return {
        "_id": "64bf459f1c9d8a0012345678",
        "name": "Lockout Test User",
        "email": "lockout_user@example.com",
        "password_hash": HASHED_PASSWORD,
        "role": "developer",
        "createdAt": "2026-01-01T00:00:00Z",
        "is_active": is_active,
        "failed_login_attempts": failed_attempts,
        "locked_until": locked_until,
    }


class TestLoginBruteForceLockout:
    @patch("Backend.auth.router.update_user")
    @patch("Backend.auth.router.get_user_by_email")
    def test_wrong_password_increments_counter_and_returns_remaining(
        self, mock_get_user, mock_update_user
    ):
        mock_get_user.return_value = _build_test_user(failed_attempts=0)

        response = client.post(
            "/auth/login",
            json={"email": "lockout_user@example.com", "password": "WrongPassword!"},
        )
        assert response.status_code == 401
        assert "4 attempt(s) remaining" in response.json()["detail"]
        mock_update_user.assert_called_once_with(
            "64bf459f1c9d8a0012345678", {"failed_login_attempts": 1}
        )

    @patch("Backend.auth.router.update_user")
    @patch("Backend.auth.router.get_user_by_email")
    def test_fifth_failed_attempt_triggers_15_minute_lockout(
        self, mock_get_user, mock_update_user
    ):
        mock_get_user.return_value = _build_test_user(failed_attempts=4)

        response = client.post(
            "/auth/login",
            json={"email": "lockout_user@example.com", "password": "WrongPassword!"},
        )
        assert response.status_code == 423
        assert "temporarily locked for 15 minutes" in response.json()["detail"]
        assert mock_update_user.call_count == 1
        update_args = mock_update_user.call_args[0][1]
        assert update_args["failed_login_attempts"] == 5
        assert "locked_until" in update_args

    @patch("Backend.auth.router.get_user_by_email")
    def test_locked_account_rejects_even_correct_password(self, mock_get_user):
        lock_time = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        mock_get_user.return_value = _build_test_user(
            failed_attempts=5, locked_until=lock_time
        )

        response = client.post(
            "/auth/login",
            json={"email": "lockout_user@example.com", "password": TEST_PASSWORD},
        )
        assert response.status_code == 423
        assert "temporarily locked due to multiple failed login attempts" in response.json()["detail"]

    @patch("Backend.auth.router.update_user")
    @patch("Backend.auth.router.get_user_by_email")
    def test_expired_lockout_permits_login_and_clears_lock(
        self, mock_get_user, mock_update_user
    ):
        # Lockout was 20 minutes ago (expired)
        expired_lock = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        mock_get_user.return_value = _build_test_user(
            failed_attempts=5, locked_until=expired_lock
        )

        response = client.post(
            "/auth/login",
            json={"email": "lockout_user@example.com", "password": TEST_PASSWORD},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()
        # Verify reset update was called
        mock_update_user.assert_called_with(
            "64bf459f1c9d8a0012345678", {"failed_login_attempts": 0, "locked_until": None}
        )

    @patch("Backend.auth.router.update_user")
    @patch("Backend.auth.router.get_user_by_email")
    def test_successful_login_resets_prior_failed_attempts(
        self, mock_get_user, mock_update_user
    ):
        mock_get_user.return_value = _build_test_user(failed_attempts=2)

        response = client.post(
            "/auth/login",
            json={"email": "lockout_user@example.com", "password": TEST_PASSWORD},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()
        mock_update_user.assert_called_once_with(
            "64bf459f1c9d8a0012345678", {"failed_login_attempts": 0, "locked_until": None}
        )

    @patch("Backend.auth.router.update_user")
    @patch("Backend.auth.router.get_user_by_email")
    def test_deactivated_user_rejected_without_mutating_lockout(
        self, mock_get_user, mock_update_user
    ):
        mock_get_user.return_value = _build_test_user(is_active=False)

        response = client.post(
            "/auth/login",
            json={"email": "lockout_user@example.com", "password": "AnyPassword!"},
        )
        assert response.status_code == 401
        mock_update_user.assert_not_called()

    @patch("Backend.auth.router.update_user")
    @patch("Backend.auth.router.get_user_by_email")
    def test_nonexistent_user_returns_401_without_mutating_lockout(
        self, mock_get_user, mock_update_user
    ):
        mock_get_user.return_value = None

        response = client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "AnyPassword!"},
        )
        assert response.status_code == 401
        mock_update_user.assert_not_called()
