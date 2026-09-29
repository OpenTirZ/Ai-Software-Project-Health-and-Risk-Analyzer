"""
Unit + integration tests for auth endpoints.

Run with:
    pytest Backend/auth/test_auth.py -v
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from Backend.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

VALID_SIGNUP = {
    "name": "Test User",
    "email": "testuser@example.com",
    "password": "securepassword123",
}

HASHED_PW = "$2b$12$KIXfakehashedpasswordfortest"


def _mock_user(user_id="507f1f77bcf86cd799439011"):
    """Return a serialized user document as persistence would return it."""
    return {
        "_id": user_id,
        "name": "Test User",
        "email": "testuser@example.com",
        "password_hash": HASHED_PW,
        "role": "member",
        "createdAt": "2026-01-01T00:00:00+00:00",
        "updatedAt": "2026-01-01T00:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# POST /auth/signup
# ---------------------------------------------------------------------------

class TestSignup:
    def test_signup_new_user_returns_201_and_token(self):
        with (
            patch("Backend.auth.router.get_user_by_email", return_value=None),
            patch("Backend.auth.router.create_user", return_value="507f1f77bcf86cd799439011"),
        ):
            response = client.post("/auth/signup", json=VALID_SIGNUP)

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == VALID_SIGNUP["email"]

    def test_signup_duplicate_email_returns_409(self):
        with patch("Backend.auth.router.get_user_by_email", return_value=_mock_user()):
            response = client.post("/auth/signup", json=VALID_SIGNUP)

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_signup_password_not_in_response(self):
        with (
            patch("Backend.auth.router.get_user_by_email", return_value=None),
            patch("Backend.auth.router.create_user", return_value="507f1f77bcf86cd799439011"),
        ):
            response = client.post("/auth/signup", json=VALID_SIGNUP)

        body = response.text
        assert VALID_SIGNUP["password"] not in body

    def test_signup_short_password_returns_422(self):
        payload = {**VALID_SIGNUP, "password": "short"}
        response = client.post("/auth/signup", json=payload)
        assert response.status_code == 422

    def test_signup_invalid_email_returns_422(self):
        payload = {**VALID_SIGNUP, "email": "not-an-email"}
        response = client.post("/auth/signup", json=payload)
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

class TestLogin:
    def test_login_valid_credentials_returns_200_and_token(self):
        from Backend.auth.security import hash_password

        user = _mock_user()
        user["password_hash"] = hash_password(VALID_SIGNUP["password"])

        with patch("Backend.auth.router.get_user_by_email", return_value=user):
            response = client.post(
                "/auth/login",
                json={"email": VALID_SIGNUP["email"], "password": VALID_SIGNUP["password"]},
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == VALID_SIGNUP["email"]

    def test_login_wrong_password_returns_401(self):
        from Backend.auth.security import hash_password

        user = _mock_user()
        user["password_hash"] = hash_password("correct_password")

        with patch("Backend.auth.router.get_user_by_email", return_value=user):
            response = client.post(
                "/auth/login",
                json={"email": VALID_SIGNUP["email"], "password": "wrong_password"},
            )

        assert response.status_code == 401

    def test_login_nonexistent_user_returns_401(self):
        with patch("Backend.auth.router.get_user_by_email", return_value=None):
            response = client.post(
                "/auth/login",
                json={"email": "nobody@example.com", "password": "whatever"},
            )

        assert response.status_code == 401

    def test_login_missing_fields_returns_422(self):
        response = client.post("/auth/login", json={"email": "a@b.com"})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

class TestMe:
    def _get_token(self):
        from Backend.auth.security import create_access_token
        return create_access_token({"sub": "507f1f77bcf86cd799439011"})

    def test_me_with_valid_token_returns_user(self):
        token = self._get_token()
        with patch("Backend.auth.dependencies.get_user", return_value=_mock_user()):
            response = client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        assert response.json()["email"] == "testuser@example.com"

    def test_me_without_token_returns_403(self):
        response = client.get("/auth/me")
        assert response.status_code in (401, 403)

    def test_me_with_invalid_token_returns_401(self):
        response = client.get(
            "/auth/me",
            headers={"Authorization": "Bearer totally.invalid.token"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------

class TestLogout:
    def _get_token(self):
        from Backend.auth.security import create_access_token
        return create_access_token({"sub": "507f1f77bcf86cd799439011"})

    def test_logout_with_valid_token_returns_200(self):
        token = self._get_token()
        with patch("Backend.auth.dependencies.get_user", return_value=_mock_user()):
            response = client.post(
                "/auth/logout",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        assert "Logged out" in response.json()["message"]

    def test_logout_without_token_returns_403(self):
        response = client.post("/auth/logout")
        assert response.status_code in (401, 403)
