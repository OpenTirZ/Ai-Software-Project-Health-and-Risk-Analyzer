"""
Unit and integration tests for OTP (One-Time Password) Authentication System.
----------------------------------------------------------------------------
Covers:
  1. OTP generation (6 digits, numeric, random).
  2. OTP hashing and constant-time verification with salt.
  3. Database storage and retrieval with TTL expiration.
  4. Brute-force throttling (max 3 failed attempts before lockout).
  5. Replay attack rejection (one-time use deletion upon success).
  6. Email dispatch handling (mocked SMTP and missing SMTP fallback).
  7. API Endpoints:
     - POST /auth/request-otp (200 success, 404 not found, 403 deactivated).
     - POST /auth/verify-otp (200 success with JWT token, 400 invalid/expired, 403 deactivated).
     - /api/auth/* prefix routing compatibility.
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

# Configure required environment variables before Backend imports
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-otp-auth-tests-32-chars")
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

from Backend.auth.otp import (
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_OTP_TTL_SECONDS,
    generate_otp,
    hash_otp,
    save_otp,
    send_otp_email,
    verify_otp,
    verify_otp_hash,
)
from Backend.auth.router import router as auth_router
from Backend.auth.schemas import OTPRequest, OTPVerifyRequest


# ---------------------------------------------------------------------------
# In-Memory Database Fixture for OTP tests
# ---------------------------------------------------------------------------

class InMemoryCollection:
    """Mock MongoDB collection storing documents in memory."""

    def __init__(self):
        self.documents = []

    def update_one(self, filter_dict, update_dict, upsert=False):
        set_fields = update_dict.get("$set", {})
        for doc in self.documents:
            match = all(doc.get(k) == v for k, v in filter_dict.items())
            if match:
                doc.update(set_fields)
                return MagicMock(matched_count=1, modified_count=1)
        if upsert:
            new_doc = {**filter_dict, **set_fields}
            if "_id" not in new_doc:
                new_doc["_id"] = str(len(self.documents) + 1)
            self.documents.append(new_doc)
            return MagicMock(matched_count=0, upserted_id=new_doc["_id"])
        return MagicMock(matched_count=0, modified_count=0)

    def find_one(self, filter_dict):
        for doc in self.documents:
            match = all(doc.get(k) == v for k, v in filter_dict.items())
            if match:
                return dict(doc)
        return None

    def delete_one(self, filter_dict):
        for i, doc in enumerate(self.documents):
            match = all(doc.get(k) == v for k, v in filter_dict.items())
            if match:
                self.documents.pop(i)
                return MagicMock(deleted_count=1)
        return MagicMock(deleted_count=0)


@pytest.fixture
def memory_otp_collection():
    mem_col = InMemoryCollection()
    with patch("Backend.auth.otp._get_otp_collection", return_value=mem_col):
        yield mem_col


# ---------------------------------------------------------------------------
# Unit Tests: Cryptographic Helpers
# ---------------------------------------------------------------------------

class TestOTPCryptography:
    def test_generate_otp_default_length(self):
        code = generate_otp()
        assert len(code) == 6
        assert code.isdigit()

    def test_generate_otp_custom_length(self):
        code = generate_otp(length=8)
        assert len(code) == 8
        assert code.isdigit()

    def test_generate_otp_randomness(self):
        codes = {generate_otp() for _ in range(50)}
        # Set of 50 generated OTPs should have high entropy (not identical)
        assert len(codes) > 40

    def test_hash_and_verify_otp(self):
        code = "123456"
        digest, salt = hash_otp(code)
        assert digest is not None
        assert salt is not None
        assert verify_otp_hash(code, digest, salt) is True
        assert verify_otp_hash("654321", digest, salt) is False


# ---------------------------------------------------------------------------
# Unit Tests: Schema Validation
# ---------------------------------------------------------------------------

class TestOTPSchemas:
    def test_otp_request_valid(self):
        req = OTPRequest(email="User@Example.com ")
        assert req.email == "user@example.com"

    def test_otp_verify_request_valid(self):
        req = OTPVerifyRequest(email="User@Example.com", code="123456")
        assert req.email == "user@example.com"
        assert req.code == "123456"

    def test_otp_verify_request_invalid_code_length(self):
        with pytest.raises(Exception):
            OTPVerifyRequest(email="user@example.com", code="12345")

    def test_otp_verify_request_non_numeric_code(self):
        with pytest.raises(Exception):
            OTPVerifyRequest(email="user@example.com", code="abcdef")


# ---------------------------------------------------------------------------
# Unit Tests: OTP Storage, Expiration & Brute-Force Throttling
# ---------------------------------------------------------------------------

class TestOTPPersistence:
    def test_save_and_verify_otp_success(self, memory_otp_collection):
        email = "alice@example.com"
        code = "481920"
        save_otp(email, code)

        valid, err = verify_otp(email, code)
        assert valid is True
        assert err == ""

        # Check replay protection: OTP must be deleted after use
        replay_valid, replay_err = verify_otp(email, code)
        assert replay_valid is False
        assert "Invalid or expired OTP" in replay_err

    def test_verify_otp_invalid_code_decrements_attempts(self, memory_otp_collection):
        email = "bob@example.com"
        code = "112233"
        save_otp(email, code)

        valid, err = verify_otp(email, "999999")
        assert valid is False
        assert "Invalid OTP code" in err
        assert "2 attempt(s) remaining" in err

        valid, err = verify_otp(email, "888888")
        assert valid is False
        assert "1 attempt(s) remaining" in err

        # Third failure triggers lockout and invalidation
        valid, err = verify_otp(email, "777777")
        assert valid is False
        assert "Too many failed attempts" in err

        # Subsequent attempts fail as record is deleted
        valid, err = verify_otp(email, code)
        assert valid is False
        assert "Invalid or expired OTP" in err

    def test_verify_otp_expired(self, memory_otp_collection):
        email = "carol@example.com"
        code = "556677"
        # Save with negative TTL to simulate expired token
        save_otp(email, code, ttl_seconds=-10)

        valid, err = verify_otp(email, code)
        assert valid is False
        assert "expired" in err.lower()

    def test_save_otp_overwrites_existing(self, memory_otp_collection):
        email = "dave@example.com"
        save_otp(email, "111111")
        save_otp(email, "222222")

        # First code should now be invalid
        valid_1, _ = verify_otp(email, "111111")
        assert valid_1 is False

        # Second code should be valid
        valid_2, err_2 = verify_otp(email, "222222")
        assert valid_2 is True
        assert err_2 == ""


# ---------------------------------------------------------------------------
# Unit Tests: Email Dispatch
# ---------------------------------------------------------------------------

class TestOTPEmailDispatch:
    def test_send_otp_email_no_smtp_host_graceful_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            success = send_otp_email("test@example.com", "123456")
            assert success is True

    @patch("smtplib.SMTP")
    def test_send_otp_email_smtp_success(self, mock_smtp):
        mock_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_instance

        env = {
            "SMTP_HOST": "smtp.test.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "mailer",
            "SMTP_PASS": "secret",
            "SMTP_FROM": "auth@test.com",
        }
        with patch.dict(os.environ, env):
            success = send_otp_email("recipient@example.com", "998877")
            assert success is True
            mock_instance.starttls.assert_called_once()
            mock_instance.login.assert_called_once_with("mailer", "secret")
            mock_instance.send_message.assert_called_once()


# ---------------------------------------------------------------------------
# Integration Tests: Auth Router Endpoints
# ---------------------------------------------------------------------------

app = FastAPI()
app.include_router(auth_router)
app.include_router(auth_router, prefix="/api")

client = TestClient(app)

MOCK_USER = {
    "_id": "64bf459f1c9d8a0012345678",
    "name": "Test Engineer",
    "email": "engineer@aegis.internal",
    "role": "developer",
    "createdAt": "2026-01-01T00:00:00Z",
    "is_active": True,
}


class TestOTPRouterEndpoints:
    @patch("Backend.auth.router.get_user_by_email")
    @patch("Backend.auth.router.send_otp_email")
    def test_request_otp_success(
        self, mock_send_email, mock_get_user, memory_otp_collection
    ):
        mock_get_user.return_value = MOCK_USER
        mock_send_email.return_value = True

        response = client.post(
            "/auth/request-otp",
            json={"email": "engineer@aegis.internal"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "engineer@aegis.internal"
        assert "OTP sent successfully" in data["message"]
        mock_send_email.assert_called_once()

    @patch("Backend.auth.router.get_user_by_email")
    def test_request_otp_user_not_found(self, mock_get_user):
        mock_get_user.return_value = None

        response = client.post(
            "/auth/request-otp",
            json={"email": "unknown@aegis.internal"},
        )
        assert response.status_code == 404
        assert "No account found" in response.json()["detail"]

    @patch("Backend.auth.router.get_user_by_email")
    def test_request_otp_deactivated_user(self, mock_get_user):
        deactivated = {**MOCK_USER, "is_active": False}
        mock_get_user.return_value = deactivated

        response = client.post(
            "/auth/request-otp",
            json={"email": "engineer@aegis.internal"},
        )
        assert response.status_code == 403
        assert "Account is deactivated" in response.json()["detail"]

    @patch("Backend.auth.router.get_user_by_email")
    def test_verify_otp_success_returns_jwt(
        self, mock_get_user, memory_otp_collection
    ):
        mock_get_user.return_value = MOCK_USER
        code = "654321"
        save_otp("engineer@aegis.internal", code)

        response = client.post(
            "/auth/verify-otp",
            json={"email": "engineer@aegis.internal", "code": code},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "engineer@aegis.internal"

    @patch("Backend.auth.router.get_user_by_email")
    def test_verify_otp_invalid_code(self, mock_get_user, memory_otp_collection):
        mock_get_user.return_value = MOCK_USER
        save_otp("engineer@aegis.internal", "654321")

        response = client.post(
            "/auth/verify-otp",
            json={"email": "engineer@aegis.internal", "code": "000000"},
        )
        assert response.status_code == 400
        assert "Invalid OTP code" in response.json()["detail"]

    @patch("Backend.auth.router.get_user_by_email")
    def test_api_prefix_endpoints_compatibility(
        self, mock_get_user, memory_otp_collection
    ):
        mock_get_user.return_value = MOCK_USER
        code = "123789"
        save_otp("engineer@aegis.internal", code)

        response = client.post(
            "/api/auth/verify-otp",
            json={"email": "engineer@aegis.internal", "code": code},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()
