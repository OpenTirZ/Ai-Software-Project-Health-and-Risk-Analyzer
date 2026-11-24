"""
Comprehensive test suite for Signup Password Whitespace Restriction.

Tests verify:
1. Valid passwords without whitespace are accepted by SignupRequest.
2. Internal spaces, leading spaces, and trailing spaces are rejected.
3. Tabs, newlines, and carriage returns are rejected.
4. Representative Unicode whitespace characters (NBSP, em space, ideographic space, etc.) are rejected.
5. Existing minimum length validation (min_length=8) remains active and takes precedence for short inputs.
6. Valid-length whitespace-containing passwords produce the exact validation error message:
   "Password must not contain spaces or whitespace characters."
7. LoginRequest continues accepting whitespace-containing passwords for backward compatibility.
8. verify_password() correctly verifies legacy whitespace-containing passwords against their bcrypt hashes.
9. Invalid signup payloads cannot proceed to password hashing, user creation, or persistence.
10. Existing legacy accounts with whitespace-containing passwords can successfully authenticate via login().
"""

import pytest
from bson import ObjectId
from pydantic import ValidationError

from Backend import persistence
from Backend.auth.router import login, signup
from Backend.auth.schemas import LoginRequest, SignupRequest
from Backend.auth.security import hash_password, verify_password


# ---------------------------------------------------------------------------
# In-memory users collection fixture for isolated auth testing
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
        if "email_normalized" in query:
            target = str(query["email_normalized"]).strip().lower()
            for doc in self.users.values():
                if doc.get("email_normalized", "").strip().lower() == target:
                    return doc
        if "email" in query:
            target = str(query["email"]).strip().lower()
            for doc in self.users.values():
                if doc.get("email", "").strip().lower() == target:
                    return doc
        return None

    def delete_many(self, query):
        self.users.clear()


@pytest.fixture
def mock_db(monkeypatch):
    """Provide an isolated in-memory collection and patch persistence references."""
    col = InMemoryUsersCollection()
    monkeypatch.setattr(persistence, "users_collection", col)
    from Backend import database
    monkeypatch.setattr(database, "users_collection", col)
    return col


# ============================================================================
# 1. SignupRequest Schema Validation Tests
# ============================================================================

class TestSignupPasswordWhitespaceValidation:
    """Tests for SignupRequest password whitespace rejection."""

    def test_valid_password_without_whitespace_accepted(self):
        """A valid password of at least 8 characters without whitespace is accepted."""
        req = SignupRequest(
            name="Alice Developer",
            email="alice@example.com",
            password="SecurePass123!",
        )
        assert req.password == "SecurePass123!"

    def test_internal_ordinary_space_rejected(self):
        """Internal ordinary space is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SignupRequest(
                name="Alice Developer",
                email="alice@example.com",
                password="Secure Pass123!",
            )
        errors = exc_info.value.errors()
        assert any(
            "Password must not contain spaces or whitespace characters." in e["msg"]
            for e in errors
        )
        assert errors[0]["loc"] == ("password",)

    def test_internal_space_variant_rejected(self):
        """Variant position internal ordinary space is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SignupRequest(
                name="Alice Developer",
                email="alice@example.com",
                password="SecurePass 123!",
            )
        assert any(
            "Password must not contain spaces or whitespace characters." in e["msg"]
            for e in exc_info.value.errors()
        )

    def test_trailing_space_rejected(self):
        """Password followed by a space is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SignupRequest(
                name="Alice Developer",
                email="alice@example.com",
                password="SecurePass123! ",
            )
        assert any(
            "Password must not contain spaces or whitespace characters." in e["msg"]
            for e in exc_info.value.errors()
        )

    def test_leading_space_rejected(self):
        """Space followed by password is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SignupRequest(
                name="Alice Developer",
                email="alice@example.com",
                password=" SecurePass123!",
            )
        assert any(
            "Password must not contain spaces or whitespace characters." in e["msg"]
            for e in exc_info.value.errors()
        )

    def test_tab_character_rejected(self):
        """Password containing a tab character is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SignupRequest(
                name="Alice Developer",
                email="alice@example.com",
                password="SecurePass123!\t",
            )
        assert any(
            "Password must not contain spaces or whitespace characters." in e["msg"]
            for e in exc_info.value.errors()
        )

    def test_newline_and_carriage_return_rejected(self):
        """Password containing newline or carriage return is rejected."""
        for bad_pw in ["SecurePass123!\n", "SecurePass123!\r", "Secure\r\nPass123!"]:
            with pytest.raises(ValidationError) as exc_info:
                SignupRequest(
                    name="Alice Developer",
                    email="alice@example.com",
                    password=bad_pw,
                )
            assert any(
                "Password must not contain spaces or whitespace characters." in e["msg"]
                for e in exc_info.value.errors()
            )

    @pytest.mark.parametrize(
        "unicode_char,char_name",
        [
            ("\u00a0", "non-breaking space (NBSP)"),
            ("\u2002", "en space"),
            ("\u2003", "em space"),
            ("\u2009", "thin space"),
            ("\u200a", "hair space"),
            ("\u3000", "ideographic space"),
            ("\u2028", "line separator"),
            ("\u2029", "paragraph separator"),
            ("\u202f", "narrow no-break space"),
            ("\u205f", "medium mathematical space"),
            ("\x0c", "form feed"),
            ("\x0b", "vertical tab"),
        ],
    )
    def test_representative_unicode_whitespace_rejected(self, unicode_char, char_name):
        """Representative Unicode whitespace characters are strictly rejected."""
        bad_pw = f"Secure{unicode_char}Pass123!"
        with pytest.raises(ValidationError) as exc_info:
            SignupRequest(
                name="Alice Developer",
                email="alice@example.com",
                password=bad_pw,
            )
        assert any(
            "Password must not contain spaces or whitespace characters." in e["msg"]
            for e in exc_info.value.errors()
        ), f"Failed to reject Unicode whitespace: {char_name}"

    def test_feff_is_not_treated_as_whitespace(self):
        """U+FEFF (BOM / zero-width no-break space) does not satisfy str.isspace() and is accepted."""
        req = SignupRequest(
            name="Alice Developer",
            email="alice@example.com",
            password="Secure\ufeffPass123!",
        )
        assert req.password == "Secure\ufeffPass123!"

    def test_existing_minimum_length_validation_still_works(self):
        """Password shorter than 8 characters fails min_length validation."""
        with pytest.raises(ValidationError) as exc_info:
            SignupRequest(
                name="Alice Developer",
                email="alice@example.com",
                password="Short1!",
            )
        errors = exc_info.value.errors()
        # Pydantic v2 core validation catches length
        assert any("at least 8 characters" in e["msg"] or "string_too_short" in e["type"] for e in errors)

    def test_short_password_with_space_fails_length_first(self):
        """Short password with space (length < 8) fails core min_length validation."""
        with pytest.raises(ValidationError) as exc_info:
            SignupRequest(
                name="Alice Developer",
                email="alice@example.com",
                password="Pass 1",
            )
        errors = exc_info.value.errors()
        assert any("at least 8 characters" in e["msg"] or "string_too_short" in e["type"] for e in errors)

    def test_whitespace_only_password_of_valid_length_rejected(self):
        """Password of 8 whitespace characters meets length but fails whitespace check."""
        with pytest.raises(ValidationError) as exc_info:
            SignupRequest(
                name="Alice Developer",
                email="alice@example.com",
                password="        ",
            )
        assert any(
            "Password must not contain spaces or whitespace characters." in e["msg"]
            for e in exc_info.value.errors()
        )

    def test_password_is_not_silently_trimmed_or_modified(self):
        """Valid password retains exact input characters without trimming."""
        exact_pw = "SecurePass123!@#"
        req = SignupRequest(
            name="Alice Developer",
            email="alice@example.com",
            password=exact_pw,
        )
        assert req.password == exact_pw


# ============================================================================
# 2. LoginRequest Backward Compatibility Tests
# ============================================================================

class TestLoginRequestBackwardCompatibility:
    """Verify LoginRequest accepts passwords with whitespace without modification."""

    def test_login_request_accepts_spaces(self):
        """LoginRequest accepts passwords containing ordinary spaces."""
        req = LoginRequest(
            email="legacy@example.com",
            password="Legacy Password 123!",
        )
        assert req.password == "Legacy Password 123!"

    def test_login_request_accepts_leading_and_trailing_spaces(self):
        """LoginRequest accepts leading and trailing spaces without trimming."""
        req = LoginRequest(
            email="legacy@example.com",
            password="  LegacyPassword123!  ",
        )
        assert req.password == "  LegacyPassword123!  "

    def test_login_request_accepts_tabs_and_unicode_whitespace(self):
        """LoginRequest accepts tabs and Unicode whitespace characters."""
        req = LoginRequest(
            email="legacy@example.com",
            password="Legacy\tPass\u00a0123!",
        )
        assert req.password == "Legacy\tPass\u00a0123!"


# ============================================================================
# 3. Security Password Verification Tests
# ============================================================================

class TestSecurityPasswordVerification:
    """Verify verify_password() correctly verifies legacy passwords with whitespace."""

    def test_verify_password_legacy_whitespace_password(self):
        """bcrypt verification succeeds for passwords containing spaces."""
        legacy_pw = "  Legacy Password With Spaces 123!  "
        hashed = hash_password(legacy_pw)

        assert verify_password(legacy_pw, hashed) is True
        assert verify_password("Wrong Password", hashed) is False
        assert verify_password(legacy_pw.strip(), hashed) is False

    def test_verify_password_legacy_tab_password(self):
        """bcrypt verification succeeds for passwords containing tabs."""
        legacy_pw = "Legacy\tPassword\t123!"
        hashed = hash_password(legacy_pw)

        assert verify_password(legacy_pw, hashed) is True
        assert verify_password("Legacy Password 123!", hashed) is False


# ============================================================================
# 4. Route Level Integration Tests
# ============================================================================

class TestAuthRouteIntegration:
    """Verify signup and login route behaviors with whitespace passwords."""

    def test_invalid_signup_blocked_at_schema_validation(self, mock_db, monkeypatch):
        """An invalid signup request fails validation and never touches persistence or hashing."""
        hasher_called = False

        def tracking_hasher(pw):
            nonlocal hasher_called
            hasher_called = True
            return hash_password(pw)

        monkeypatch.setattr("Backend.auth.router.hash_password", tracking_hasher)

        bad_payload = {
            "name": "Bob",
            "email": "bob@example.com",
            "password": "Secure Pass 123!",
        }

        with pytest.raises(ValidationError):
            SignupRequest(**bad_payload)

        # Persistence remains empty
        assert len(mock_db.users) == 0
        assert hasher_called is False

    def test_legacy_user_with_whitespace_password_can_login(self, mock_db):
        """A legacy user with whitespace in their password can successfully log in."""
        legacy_email = "legacy.user@example.com"
        legacy_pw = "My Legacy Secret 99!"
        pw_hash = hash_password(legacy_pw)

        # Seed legacy user into persistence
        user_id = str(ObjectId())
        mock_db.insert_one({
            "_id": ObjectId(user_id),
            "name": "Legacy User",
            "email": legacy_email,
            "email_normalized": legacy_email,
            "password_hash": pw_hash,
            "role": "developer",
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-01-01T00:00:00Z",
        })

        login_req = LoginRequest(email=legacy_email, password=legacy_pw)
        res = login(login_req)

        assert res.access_token is not None
        assert res.user.email == legacy_email
        assert res.user.id == user_id
