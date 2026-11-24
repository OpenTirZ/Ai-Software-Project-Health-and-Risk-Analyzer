"""
B1 Regression & Unit Tests: Email Normalization and Regex Matching Fix.

Covers:
  1. Helper-level tests for normalize_email()
  2. Schema-level validation and normalization tests for SignupRequest & LoginRequest
  3. Persistence-level regex escaping and case-insensitivity tests for get_user_by_email()
  4. API endpoint integration tests for signup, login, and duplicate pre-check
"""
import re
import pytest
from bson import ObjectId
from pydantic import ValidationError

# Root conftest.py sets env vars and patches pymongo.MongoClient before this
# module is imported — no additional global patches needed here.

from Backend import persistence
from Backend.auth.normalization import normalize_email
from Backend.auth.schemas import LoginRequest, SignupRequest
from Backend.auth.security import hash_password
from Backend.auth.router import signup, login
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# In-memory users collection for persistence testing
# ---------------------------------------------------------------------------

class MockInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class InMemoryUsersCollection:
    def __init__(self):
        self.users = {}

    def insert_one(self, doc):
        doc_copy = dict(doc)
        doc_id = doc_copy.get("_id", ObjectId())
        doc_copy["_id"] = doc_id
        self.users[str(doc_id)] = doc_copy
        return MockInsertResult(doc_id)

    def find_one(self, query):
        if "_id" in query:
            target_id = str(query["_id"])
            return self.users.get(target_id)
        if "email" in query:
            email_q = query["email"]
            if isinstance(email_q, dict) and "$regex" in email_q:
                regex_pat = email_q["$regex"]
                flags = re.IGNORECASE if "i" in email_q.get("$options", "") else 0
                pattern = re.compile(regex_pat, flags)
                for doc in self.users.values():
                    if pattern.search(doc.get("email", "")):
                        return doc
            else:
                target = str(email_q).strip().lower()
                for doc in self.users.values():
                    if doc.get("email", "").strip().lower() == target:
                        return doc
        return None

    def delete_many(self, query):
        self.users.clear()


@pytest.fixture(autouse=True)
def setup_mock_db(monkeypatch):
    mock_coll = InMemoryUsersCollection()
    monkeypatch.setattr(persistence, "users_collection", mock_coll)
    yield mock_coll


# ============================================================================
# 1. HELPER & PERSISTENCE TESTS (Regex escaping, normalization, backward compat)
# ============================================================================

class TestEmailNormalizationHelper:
    def test_normalize_email_strips_whitespace(self):
        assert normalize_email("  user@example.com  ") == "user@example.com"
        assert normalize_email("\tuser@example.com\n") == "user@example.com"

    def test_normalize_email_lowercases(self):
        assert normalize_email("User.Name@Example.COM") == "user.name@example.com"
        assert normalize_email("OM+TEST@EXAMPLE.COM") == "om+test@example.com"

    def test_normalize_email_handles_empty_and_none(self):
        assert normalize_email(None) == ""
        assert normalize_email("") == ""
        assert normalize_email("   ") == ""


class TestPersistenceEmailLookup:
    def test_lookup_succeeds_for_email_with_plus(self, setup_mock_db):
        """Lookup succeeds for om+test@example.com."""
        setup_mock_db.insert_one({
            "name": "Plus User",
            "email": "om+test@example.com",
            "password_hash": "hash123",
            "role": "developer",
        })
        user = persistence.get_user_by_email("om+test@example.com")
        assert user is not None
        assert user["email"] == "om+test@example.com"

    def test_lookup_succeeds_for_email_with_dot(self, setup_mock_db):
        """Lookup succeeds for first.last@example.com."""
        setup_mock_db.insert_one({
            "name": "Dot User",
            "email": "first.last@example.com",
            "password_hash": "hash123",
            "role": "developer",
        })
        user = persistence.get_user_by_email("first.last@example.com")
        assert user is not None
        assert user["email"] == "first.last@example.com"

    def test_plus_character_is_interpreted_literally(self, setup_mock_db):
        """Plus is not a regex quantifier; omtest does NOT match om+test."""
        setup_mock_db.insert_one({
            "name": "Literal User",
            "email": "omtest@example.com",
            "password_hash": "hash123",
            "role": "developer",
        })
        # Searching for om+test should NOT match omtest
        user = persistence.get_user_by_email("om+test@example.com")
        assert user is None

        # Searching for ommtest should NOT match om+test
        setup_mock_db.insert_one({
            "name": "Multi M User",
            "email": "ommtest@example.com",
            "password_hash": "hash123",
            "role": "developer",
        })
        user = persistence.get_user_by_email("om+test@example.com")
        assert user is None

    def test_dot_character_is_interpreted_literally(self, setup_mock_db):
        """Dot is not a regex wildcard; firstXlast does NOT match first.last."""
        setup_mock_db.insert_one({
            "name": "X User",
            "email": "firstXlast@example.com",
            "password_hash": "hash123",
            "role": "developer",
        })
        user = persistence.get_user_by_email("first.last@example.com")
        assert user is None

    def test_regex_metacharacters_cannot_alter_pattern(self, setup_mock_db):
        """Regex metacharacters are safely escaped and queried literally."""
        setup_mock_db.insert_one({
            "name": "Complex User",
            "email": "user(tag)[test]*@example.com",
            "password_hash": "hash123",
            "role": "developer",
        })
        user = persistence.get_user_by_email("user(tag)[test]*@example.com")
        assert user is not None
        assert user["email"] == "user(tag)[test]*@example.com"

        # Partial or wild variations should not match
        assert persistence.get_user_by_email("user*@example.com") is None

    def test_email_lookup_remains_case_insensitive(self, setup_mock_db):
        """Lookup remains case-insensitive."""
        setup_mock_db.insert_one({
            "name": "Case User",
            "email": "alex.johnson@example.com",
            "password_hash": "hash123",
            "role": "developer",
        })
        user = persistence.get_user_by_email("ALEX.JOHNSON@EXAMPLE.COM")
        assert user is not None
        assert user["name"] == "Case User"

    def test_existing_accounts_with_mixed_case_stored_emails_remain_accessible(self, setup_mock_db):
        """Existing mixed-case records in DB remain accessible."""
        setup_mock_db.insert_one({
            "name": "Legacy Mixed",
            "email": "Legacy.User@Example.COM",
            "password_hash": "hash123",
            "role": "developer",
        })
        user = persistence.get_user_by_email("legacy.user@example.com")
        assert user is not None
        assert user["email"] == "Legacy.User@Example.COM"

    def test_existing_accounts_with_surrounding_whitespace_remain_accessible(self, setup_mock_db):
        """Stored emails with legacy surrounding whitespace remain accessible."""
        setup_mock_db.insert_one({
            "name": "Padded Legacy",
            "email": "  legacy.padded@example.com  ",
            "password_hash": "hash123",
            "role": "developer",
        })
        user = persistence.get_user_by_email("legacy.padded@example.com")
        assert user is not None
        assert user["name"] == "Padded Legacy"

    def test_lookup_empty_or_none_returns_none(self):
        assert persistence.get_user_by_email("") is None
        assert persistence.get_user_by_email(None) is None
        assert persistence.get_user_by_email("   ") is None


# ============================================================================
# 2. SCHEMA VALIDATION TESTS (Ingress normalization & strict validation)
# ============================================================================

class TestSchemasEmailNormalization:
    def test_signup_request_normalizes_email(self):
        req = SignupRequest(name="John", email="  John.Doe+Tag@EXAMPLE.COM  ", password="password123")
        assert req.email == "john.doe+tag@example.com"

    def test_login_request_normalizes_email(self):
        req = LoginRequest(email="  First.Last@EXAMPLE.COM  ", password="password123")
        assert req.email == "first.last@example.com"

    def test_invalid_email_formats_rejected_by_emailstr(self):
        """Ensure EmailStr validation is NOT weakened."""
        invalid_emails = [
            "not-an-email",
            "@missinguser.com",
            "user@",
            "spaces in@example.com",
            "user@.com",
        ]
        for bad in invalid_emails:
            with pytest.raises(ValidationError):
                SignupRequest(name="Test", email=bad, password="password123")
            with pytest.raises(ValidationError):
                LoginRequest(email=bad, password="password123")


# ============================================================================
# 3. ENDPOINT INTEGRATION TESTS (Signup, Login, Duplicate pre-check)
# ============================================================================

class TestAuthEndpointsB1:
    def test_signup_and_login_with_plus_in_email(self):
        """Signup followed by login works for emails containing '+'."""
        email = "om+test@example.com"
        password = "SecurePassword123!"

        signup_req = SignupRequest(name="Plus User", email=email, password=password)
        signup_res = signup(signup_req)
        assert signup_res.access_token is not None
        assert signup_res.user.email == email

        login_req = LoginRequest(email=email, password=password)
        login_res = login(login_req)
        assert login_res.access_token is not None
        assert login_res.user.email == email

    def test_signup_and_login_with_dot_in_email(self):
        """Signup followed by login works for emails containing '.'."""
        email = "first.last@example.com"
        password = "SecurePassword123!"

        signup_req = SignupRequest(name="Dot User", email=email, password=password)
        signup_res = signup(signup_req)
        assert signup_res.access_token is not None
        assert signup_res.user.email == email

        login_req = LoginRequest(email=email, password=password)
        login_res = login(login_req)
        assert login_res.access_token is not None
        assert login_res.user.email == email

    def test_duplicate_email_precheck_with_case_and_whitespace(self):
        """Existing duplicate-email pre-check works with normalized input."""
        email = "alex.johnson+dev@example.com"
        password = "SecurePassword123!"

        signup_req = SignupRequest(name="Alex", email=email, password=password)
        signup(signup_req)

        # Attempt to sign up with uppercase and surrounding whitespace
        dup_req = SignupRequest(
            name="Alex Duplicate",
            email="  ALEX.JOHNSON+DEV@EXAMPLE.COM  ",
            password="OtherPassword123!",
        )
        with pytest.raises(HTTPException) as exc_info:
            signup(dup_req)
        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail.lower()

    def test_signup_distinct_emails_do_not_conflict(self):
        """om+test@example.com and omtest@example.com are separate accounts."""
        password = "SecurePassword123!"

        # Register omtest@example.com
        signup(SignupRequest(name="User Base", email="omtest@example.com", password=password))

        # Register om+test@example.com should succeed without duplicate conflict
        res = signup(SignupRequest(name="User Plus", email="om+test@example.com", password=password))
        assert res.user.email == "om+test@example.com"
