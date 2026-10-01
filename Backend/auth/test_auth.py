"""
Comprehensive unit and integration test suite for Authentication & Authorization.
Contains 60 test cases covering security utilities, Pydantic schemas, FastAPI endpoints,
and dependency injection.

Run with:
    PYTHONPATH=. pytest Backend/auth/test_auth.py -v
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from pydantic import ValidationError

from Backend.auth.dependencies import get_current_user
from Backend.auth.schemas import (
    LoginRequest,
    MessageResponse,
    SignupRequest,
    TokenResponse,
    UserOut,
)
from Backend.auth.security import (
    _ALGORITHM,
    _SECRET_KEY,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from Backend.main import app
from Backend.persistence import clear_users, create_user, get_user

client = TestClient(app)

VALID_SIGNUP_DATA = {
    "name": "Alex Johnson",
    "email": "alex.johnson@example.com",
    "password": "SecurePassword123!",
}


@pytest.fixture(autouse=True)
def reset_db():
    """Clear in-memory user database before every test."""
    clear_users()


# ============================================================================
# 1. SECURITY UTILITIES TESTS (14 Test Cases)
# ============================================================================

class TestSecurityUtilities:
    def test_hash_password_returns_string(self):
        hashed = hash_password("mysecretpassword")
        assert isinstance(hashed, str)

    def test_hash_password_starts_with_bcrypt_prefix(self):
        hashed = hash_password("mysecretpassword")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_hash_password_unique_salts(self):
        pw = "same_password"
        hash1 = hash_password(pw)
        hash2 = hash_password(pw)
        assert hash1 != hash2

    def test_verify_password_correct(self):
        pw = "Password123"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("Password123")
        assert verify_password("WrongPassword", hashed) is False

    def test_verify_password_empty_plain_password(self):
        hashed = hash_password("Password123")
        assert verify_password("", hashed) is False

    def test_verify_password_empty_hashed_password(self):
        assert verify_password("Password123", "") is False

    def test_verify_password_malformed_hash(self):
        # Should return False without throwing exceptions / 500 error
        assert verify_password("Password123", "not_a_valid_hash") is False

    def test_verify_password_unicode_characters(self):
        pw = "P@$$wørd_🔑_123"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed) is True

    def test_create_and_decode_access_token_valid(self):
        payload = {"sub": "user_id_123", "role": "admin"}
        token = create_access_token(payload)
        decoded = decode_access_token(token)
        assert decoded["sub"] == "user_id_123"
        assert decoded["role"] == "admin"
        assert "exp" in decoded

    def test_create_access_token_custom_expiry(self):
        delta = timedelta(minutes=15)
        token = create_access_token({"sub": "user_1"}, expires_delta=delta)
        decoded = decode_access_token(token)
        exp_time = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        assert (exp_time - now).total_seconds() <= 900 + 5

    def test_decode_access_token_expired(self):
        # Create token that expired 10 minutes ago
        past_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        token = jwt.encode({"sub": "user_1", "exp": past_time}, _SECRET_KEY, algorithm=_ALGORITHM)
        with pytest.raises(Exception):
            decode_access_token(token)

    def test_decode_access_token_tampered_signature(self):
        token = create_access_token({"sub": "user_1"})
        tampered_token = token[:-5] + "XXXXX"
        with pytest.raises(Exception):
            decode_access_token(tampered_token)

    def test_decode_access_token_wrong_secret(self):
        token = jwt.encode({"sub": "user_1"}, "WRONG_SECRET", algorithm=_ALGORITHM)
        with pytest.raises(Exception):
            decode_access_token(token)


# ============================================================================
# 2. SCHEMAS VALIDATION TESTS (10 Test Cases)
# ============================================================================

class TestSchemasValidation:
    def test_signup_request_valid(self):
        obj = SignupRequest(name="John Doe", email="john@example.com", password="password123")
        assert obj.name == "John Doe"
        assert obj.email == "john@example.com"

    def test_signup_request_empty_name_raises(self):
        with pytest.raises(ValidationError):
            SignupRequest(name="", email="john@example.com", password="password123")

    def test_signup_request_name_too_long_raises(self):
        long_name = "A" * 101
        with pytest.raises(ValidationError):
            SignupRequest(name=long_name, email="john@example.com", password="password123")

    def test_signup_request_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            SignupRequest(name="John", email="not-an-email", password="password123")

    def test_signup_request_password_too_short_raises(self):
        with pytest.raises(ValidationError):
            SignupRequest(name="John", email="john@example.com", password="short")

    def test_login_request_valid(self):
        obj = LoginRequest(email="john@example.com", password="password123")
        assert obj.email == "john@example.com"

    def test_login_request_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="invalidemail", password="password123")

    def test_user_out_schema_valid(self):
        obj = UserOut(
            id="507f1f77bcf86cd799439011",
            name="Alice",
            email="alice@example.com",
            role="member",
            created_at="2026-01-01T00:00:00Z",
        )
        assert obj.id == "507f1f77bcf86cd799439011"

    def test_token_response_schema_default_bearer(self):
        user_out = UserOut(
            id="123", name="Alice", email="alice@example.com", role="member", created_at=""
        )
        resp = TokenResponse(access_token="abc.def.ghi", user=user_out)
        assert resp.token_type == "bearer"

    def test_message_response_schema(self):
        msg = MessageResponse(message="Success")
        assert msg.message == "Success"


# ============================================================================
# 3. SIGNUP ENDPOINT TESTS (10 Test Cases)
# ============================================================================

class TestSignupEndpoint:
    def test_signup_new_user_returns_201_and_token(self):
        res = client.post("/auth/signup", json=VALID_SIGNUP_DATA)
        assert res.status_code == 201
        body = res.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["user"]["email"] == VALID_SIGNUP_DATA["email"]
        assert body["user"]["name"] == VALID_SIGNUP_DATA["name"]

    def test_signup_creates_user_in_persistence(self):
        res = client.post("/auth/signup", json=VALID_SIGNUP_DATA)
        user_id = res.json()["user"]["id"]
        db_user = get_user(user_id)
        assert db_user is not None
        assert db_user["email"] == VALID_SIGNUP_DATA["email"]

    def test_signup_duplicate_email_returns_409(self):
        client.post("/auth/signup", json=VALID_SIGNUP_DATA)
        res = client.post("/auth/signup", json=VALID_SIGNUP_DATA)
        assert res.status_code == 409
        assert "already exists" in res.json()["detail"]

    def test_signup_duplicate_email_case_insensitive(self):
        client.post("/auth/signup", json=VALID_SIGNUP_DATA)
        uppercase_signup = {**VALID_SIGNUP_DATA, "email": VALID_SIGNUP_DATA["email"].upper()}
        res = client.post("/auth/signup", json=uppercase_signup)
        assert res.status_code == 409

    def test_signup_password_not_in_response(self):
        res = client.post("/auth/signup", json=VALID_SIGNUP_DATA)
        assert VALID_SIGNUP_DATA["password"] not in res.text

    def test_signup_short_password_returns_422(self):
        bad_data = {**VALID_SIGNUP_DATA, "password": "pass"}
        res = client.post("/auth/signup", json=bad_data)
        assert res.status_code == 422

    def test_signup_invalid_email_returns_422(self):
        bad_data = {**VALID_SIGNUP_DATA, "email": "plainaddress"}
        res = client.post("/auth/signup", json=bad_data)
        assert res.status_code == 422

    def test_signup_missing_name_returns_422(self):
        bad_data = {"email": "a@b.com", "password": "password123"}
        res = client.post("/auth/signup", json=bad_data)
        assert res.status_code == 422

    def test_signup_missing_password_returns_422(self):
        bad_data = {"name": "Alex", "email": "a@b.com"}
        res = client.post("/auth/signup", json=bad_data)
        assert res.status_code == 422

    def test_signup_empty_body_returns_422(self):
        res = client.post("/auth/signup", json={})
        assert res.status_code == 422


# ============================================================================
# 4. LOGIN ENDPOINT TESTS (8 Test Cases)
# ============================================================================

class TestLoginEndpoint:
    def test_login_success_returns_200_and_token(self):
        client.post("/auth/signup", json=VALID_SIGNUP_DATA)
        login_data = {
            "email": VALID_SIGNUP_DATA["email"],
            "password": VALID_SIGNUP_DATA["password"],
        }
        res = client.post("/auth/login", json=login_data)
        assert res.status_code == 200
        body = res.json()
        assert "access_token" in body
        assert body["user"]["email"] == VALID_SIGNUP_DATA["email"]

    def test_login_wrong_password_returns_401(self):
        client.post("/auth/signup", json=VALID_SIGNUP_DATA)
        login_data = {
            "email": VALID_SIGNUP_DATA["email"],
            "password": "WrongPassword123!",
        }
        res = client.post("/auth/login", json=login_data)
        assert res.status_code == 401
        assert "Invalid email or password" in res.json()["detail"]

    def test_login_nonexistent_email_returns_401(self):
        login_data = {
            "email": "nonexistent@example.com",
            "password": "Password123!",
        }
        res = client.post("/auth/login", json=login_data)
        assert res.status_code == 401

    def test_login_case_insensitive_email(self):
        client.post("/auth/signup", json=VALID_SIGNUP_DATA)
        login_data = {
            "email": VALID_SIGNUP_DATA["email"].upper(),
            "password": VALID_SIGNUP_DATA["password"],
        }
        res = client.post("/auth/login", json=login_data)
        assert res.status_code == 200

    def test_login_empty_body_returns_422(self):
        res = client.post("/auth/login", json={})
        assert res.status_code == 422

    def test_login_missing_password_returns_422(self):
        res = client.post("/auth/login", json={"email": "a@b.com"})
        assert res.status_code == 422

    def test_login_missing_email_returns_422(self):
        res = client.post("/auth/login", json={"password": "password123"})
        assert res.status_code == 422

    def test_login_invalid_email_format_returns_422(self):
        res = client.post("/auth/login", json={"email": "bademail", "password": "pass"})
        assert res.status_code == 422


# ============================================================================
# 5. GET /auth/me ENDPOINT TESTS (7 Test Cases)
# ============================================================================

class TestMeEndpoint:
    def test_me_valid_token_returns_profile(self):
        signup_res = client.post("/auth/signup", json=VALID_SIGNUP_DATA)
        token = signup_res.json()["access_token"]

        res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        body = res.json()
        assert body["email"] == VALID_SIGNUP_DATA["email"]
        assert body["name"] == VALID_SIGNUP_DATA["name"]

    def test_me_missing_auth_header_returns_403(self):
        res = client.get("/auth/me")
        assert res.status_code in (401, 403)

    def test_me_invalid_token_returns_401(self):
        res = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.str"})
        assert res.status_code == 401

    def test_me_expired_token_returns_401(self):
        token = create_access_token({"sub": "507f1f77bcf86cd799439011"}, timedelta(seconds=-10))
        res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401

    def test_me_user_deleted_returns_401(self):
        signup_res = client.post("/auth/signup", json=VALID_SIGNUP_DATA)
        token = signup_res.json()["access_token"]
        clear_users()  # Simulate user being deleted from DB

        res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401

    def test_me_invalid_object_id_in_sub_returns_401(self):
        token = create_access_token({"sub": "not_an_object_id"})
        res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401

    def test_me_malformed_auth_header_prefix(self):
        token = create_access_token({"sub": "507f1f77bcf86cd799439011"})
        res = client.get("/auth/me", headers={"Authorization": f"Basic {token}"})
        assert res.status_code in (401, 403)


# ============================================================================
# 6. POST /auth/logout ENDPOINT TESTS (5 Test Cases)
# ============================================================================

class TestLogoutEndpoint:
    def test_logout_valid_token_returns_200(self):
        signup_res = client.post("/auth/signup", json=VALID_SIGNUP_DATA)
        token = signup_res.json()["access_token"]

        res = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert "Logged out successfully" in res.json()["message"]

    def test_logout_missing_auth_header_returns_403(self):
        res = client.post("/auth/logout")
        assert res.status_code in (401, 403)

    def test_logout_invalid_token_returns_401(self):
        res = client.post("/auth/logout", headers={"Authorization": "Bearer badtoken"})
        assert res.status_code == 401

    def test_logout_expired_token_returns_401(self):
        token = create_access_token({"sub": "507f1f77bcf86cd799439011"}, timedelta(seconds=-5))
        res = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401

    def test_logout_user_deleted_returns_401(self):
        signup_res = client.post("/auth/signup", json=VALID_SIGNUP_DATA)
        token = signup_res.json()["access_token"]
        clear_users()

        res = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401


# ============================================================================
# 7. DEPENDENCY DIRECT INVOCATION TESTS (6 Test Cases)
# ============================================================================

class TestAuthDependencies:
    def test_get_current_user_direct_success(self):
        user_id = create_user({"name": "Test", "email": "test@ex.com"})
        token = create_access_token({"sub": user_id})
        credentials = patch("fastapi.security.HTTPAuthorizationCredentials").start()
        credentials.credentials = token

        user = get_current_user(credentials)
        assert user["_id"] == user_id

    def test_get_current_user_missing_sub(self):
        token = create_access_token({"other": "claim"})
        credentials = patch("fastapi.security.HTTPAuthorizationCredentials").start()
        credentials.credentials = token

        with pytest.raises(Exception) as exc_info:
            get_current_user(credentials)
        assert exc_info.value.status_code == 401

    def test_get_current_user_invalid_jwt(self):
        credentials = patch("fastapi.security.HTTPAuthorizationCredentials").start()
        credentials.credentials = "invalid.jwt.token"

        with pytest.raises(Exception) as exc_info:
            get_current_user(credentials)
        assert exc_info.value.status_code == 401

    def test_get_current_user_expired_jwt(self):
        token = create_access_token({"sub": "507f1f77bcf86cd799439011"}, timedelta(seconds=-10))
        credentials = patch("fastapi.security.HTTPAuthorizationCredentials").start()
        credentials.credentials = token

        with pytest.raises(Exception) as exc_info:
            get_current_user(credentials)
        assert exc_info.value.status_code == 401

    def test_get_current_user_invalid_object_id(self):
        token = create_access_token({"sub": "invalid_id_format"})
        credentials = patch("fastapi.security.HTTPAuthorizationCredentials").start()
        credentials.credentials = token

        with pytest.raises(Exception) as exc_info:
            get_current_user(credentials)
        assert exc_info.value.status_code == 401

    def test_get_current_user_nonexistent_user(self):
        token = create_access_token({"sub": "507f1f77bcf86cd799439011"})
        credentials = patch("fastapi.security.HTTPAuthorizationCredentials").start()
        credentials.credentials = token

        with pytest.raises(Exception) as exc_info:
            get_current_user(credentials)
        assert exc_info.value.status_code == 401
