"""
B2 Test Suite: Unique Email Constraint, Central Normalization, and Concurrent Signup Prevention.
=================================================================================================

Covers:
  1. Central derivation of email_normalized and caller dictionary immutability.
  2. Strict validation in create_user() rejecting missing or empty email values.
  3. Precise DuplicateKeyError matching on uniq_users_email_normalized vs unrelated errors.
  4. Auth router signup() mapping DuplicateEmailError to HTTP 409 Conflict.
  5. Strict index verification in verify_user_unique_index().
  6. Demo seed data population of email_normalized.
  7. Migration audit and backfill logic (Pydantic EmailStr validation, duplicate detection,
     stale field resolution, collision hazard aborts, and idempotency).
"""

from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError, PyMongoError

from Backend import database, persistence
from Backend.auth.router import signup
from Backend.auth.schemas import SignupRequest
from Backend.persistence import DatabaseError, DuplicateEmailError
from Backend.scripts.migrate_b2_email_uniqueness import (
    audit_users_collection,
    is_valid_email_str,
    run_migration,
)
from Backend.seed_demo_data import seed_demo_project


# ============================================================================
# 1. CENTRAL NORMALIZATION & INPUT IMMUTABILITY
# ============================================================================

class TestCentralEmailNormalization:
    def test_create_user_always_derives_email_normalized(self, monkeypatch):
        """create_user() must derive email_normalized using normalize_email()."""
        captured_doc = {}

        def mock_insert_one(doc):
            captured_doc.update(doc)
            return MagicMock(inserted_id=ObjectId())

        mock_coll = MagicMock()
        mock_coll.insert_one = mock_insert_one
        monkeypatch.setattr(persistence, "users_collection", mock_coll)

        input_data = {
            "name": "Alex",
            "email": "  ALEX.JOHNSON+DEV@EXAMPLE.COM  ",
            "role": "developer",
        }
        persistence.create_user(input_data)

        assert captured_doc["email_normalized"] == "alex.johnson+dev@example.com"
        assert captured_doc["email"] == "  ALEX.JOHNSON+DEV@EXAMPLE.COM  "

    def test_create_user_overwrites_caller_provided_email_normalized(self, monkeypatch):
        """create_user() must never trust a caller-provided email_normalized value."""
        captured_doc = {}

        def mock_insert_one(doc):
            captured_doc.update(doc)
            return MagicMock(inserted_id=ObjectId())

        mock_coll = MagicMock()
        mock_coll.insert_one = mock_insert_one
        monkeypatch.setattr(persistence, "users_collection", mock_coll)

        input_data = {
            "name": "Tamperer",
            "email": "real.user@example.com",
            "email_normalized": "forged.normalized@example.com",
        }
        persistence.create_user(input_data)

        # Forged canonical field is overwritten by the true derivation
        assert captured_doc["email_normalized"] == "real.user@example.com"

    def test_create_user_does_not_mutate_caller_input_dict(self, monkeypatch):
        """create_user() must copy the input dict and leave the caller's dict unmutated."""
        mock_coll = MagicMock()
        mock_coll.insert_one.return_value = MagicMock(inserted_id=ObjectId())
        monkeypatch.setattr(persistence, "users_collection", mock_coll)

        input_data = {
            "name": "Immutable Caller",
            "email": "test@example.com",
        }
        persistence.create_user(input_data)

        assert "email_normalized" not in input_data
        assert input_data == {"name": "Immutable Caller", "email": "test@example.com"}

    def test_create_user_rejects_missing_or_empty_email(self):
        """create_user() must raise ValueError for missing or empty email."""
        with pytest.raises(ValueError, match="User email is required"):
            persistence.create_user({"name": "No Email"})

        with pytest.raises(ValueError, match="User email is required"):
            persistence.create_user({"name": "Empty Email", "email": ""})

        with pytest.raises(ValueError, match="User email must not be empty after normalization"):
            persistence.create_user({"name": "Whitespace Email", "email": "   \t\n  "})

    def test_create_user_direct_raw_canonicalization_parity(self, monkeypatch):
        """
        Verify that direct calls to create_user() with original raw inputs (not yet
        processed by SignupRequest) produce the exact canonical email:
        - user@Ｄｏｍａｉｎ.com -> user@domain.com
        - user@bücher.de -> user@bücher.de
        - user@xn--bcher-kva.de -> user@bücher.de
        """
        test_cases = [
            ("user@Ｄｏｍａｉｎ.com", "user@domain.com"),
            ("user@bücher.de", "user@bücher.de"),
            ("user@xn--bcher-kva.de", "user@bücher.de"),
        ]

        for raw_email, expected_canonical in test_cases:
            captured_doc = {}
            mock_coll = MagicMock()
            mock_coll.insert_one.side_effect = lambda doc: captured_doc.update(doc) or MagicMock(inserted_id=ObjectId())
            monkeypatch.setattr(persistence, "users_collection", mock_coll)

            persistence.create_user({"name": "Direct User", "email": raw_email})

            assert captured_doc["email_normalized"] == expected_canonical, (
                f"create_user({raw_email!r}) produced {captured_doc['email_normalized']!r}, "
                f"expected {expected_canonical!r}"
            )
            # Immutability: input original email is preserved
            assert captured_doc["email"] == raw_email

    def test_create_user_rejects_invalid_email_directly(self):
        """create_user() must strictly reject invalid email addresses with ValueError."""
        invalid_emails = [
            "not-an-email",
            "missing-at.com",
            "@missing-user.com",
            "spaces in@domain.com",
            "user@.com",
        ]
        for bad_email in invalid_emails:
            with pytest.raises(ValueError, match="Invalid email address format"):
                persistence.create_user({"name": "Bad User", "email": bad_email})

    def test_get_user_by_email_unicode_and_punycode_equivalence(self, monkeypatch):
        """get_user_by_email() seamlessly finds accounts using either Unicode or Punycode queries."""
        sample_doc = {
            "_id": ObjectId(),
            "name": "Bücher User",
            "email": "user@bücher.de",
            "email_normalized": "user@bücher.de",
        }

        mock_coll = MagicMock()
        mock_coll.find_one.side_effect = lambda q: sample_doc if q.get("email_normalized") == "user@bücher.de" else None
        monkeypatch.setattr(persistence, "users_collection", mock_coll)

        # Lookup with Unicode IDN
        res1 = persistence.get_user_by_email("user@bücher.de")
        assert res1 is not None
        assert res1["email_normalized"] == "user@bücher.de"

        # Lookup with Punycode representation
        res2 = persistence.get_user_by_email("user@xn--bcher-kva.de")
        assert res2 is not None
        assert res2["email_normalized"] == "user@bücher.de"

        # Lookup with Full-width Unicode
        full_width_doc = {
            "_id": ObjectId(),
            "name": "Full Width User",
            "email": "user@domain.com",
            "email_normalized": "user@domain.com",
        }
        mock_coll.find_one.side_effect = lambda q: full_width_doc if q.get("email_normalized") == "user@domain.com" else None

        res3 = persistence.get_user_by_email("user@Ｄｏｍａｉｎ.com")
        assert res3 is not None
        assert res3["email_normalized"] == "user@domain.com"


# ============================================================================
# 2. PRECISE DUPLICATEKEYERROR IDENTIFICATION
# ============================================================================

class TestDuplicateKeyErrorPrecision:
    def test_exact_key_pattern_match_triggers_duplicate_email_error(self, monkeypatch):
        """DuplicateKeyError with keyPattern {'email_normalized': 1} raises DuplicateEmailError."""
        exc = DuplicateKeyError("E11000 duplicate key error", details={"keyPattern": {"email_normalized": 1}})
        mock_coll = MagicMock()
        mock_coll.insert_one.side_effect = exc
        monkeypatch.setattr(persistence, "users_collection", mock_coll)

        with pytest.raises(DuplicateEmailError) as exc_info:
            persistence.create_user({"name": "Alex", "email": "alex@example.com"})

        assert exc_info.value.email == "alex@example.com"
        assert "already exists" in str(exc_info.value)

    def test_exact_index_name_match_triggers_duplicate_email_error(self, monkeypatch):
        """DuplicateKeyError with index name uniq_users_email_normalized raises DuplicateEmailError."""
        errmsg = "E11000 duplicate key error collection: test.users index: uniq_users_email_normalized dup key: { email_normalized: 'alex@example.com' }"
        exc = DuplicateKeyError(errmsg, details={"errmsg": errmsg})
        mock_coll = MagicMock()
        mock_coll.insert_one.side_effect = exc
        monkeypatch.setattr(persistence, "users_collection", mock_coll)

        with pytest.raises(DuplicateEmailError):
            persistence.create_user({"name": "Alex", "email": "alex@example.com"})

    def test_unrelated_duplicate_key_error_remains_database_error(self, monkeypatch):
        """DuplicateKeyError on an unrelated index (e.g. _id) must remain DatabaseError."""
        exc = DuplicateKeyError("E11000 duplicate key error", details={"keyPattern": {"_id": 1}, "errmsg": "index: _id_ dup key"})
        mock_coll = MagicMock()
        mock_coll.insert_one.side_effect = exc
        monkeypatch.setattr(persistence, "users_collection", mock_coll)

        with pytest.raises(DatabaseError) as exc_info:
            persistence.create_user({"name": "Alex", "email": "alex@example.com"})

        assert not isinstance(exc_info.value, DuplicateEmailError)
        assert "database error occurred while creating the user" in str(exc_info.value)

    def test_generic_text_containing_email_normalized_not_misclassified(self, monkeypatch):
        """A compound index or error message mentioning email_normalized is not misclassified."""
        exc = DuplicateKeyError(
            "E11000 duplicate key error",
            details={"keyPattern": {"email_normalized": 1, "tenantId": 1}, "errmsg": "index: email_normalized_tenantId dup key"},
        )
        mock_coll = MagicMock()
        mock_coll.insert_one.side_effect = exc
        monkeypatch.setattr(persistence, "users_collection", mock_coll)

        with pytest.raises(DatabaseError):
            persistence.create_user({"name": "Alex", "email": "alex@example.com"})


# ============================================================================
# 3. AUTH ROUTER SIGNUP ENDPOINT CONFLICT MAPPING
# ============================================================================

class TestAuthRouterB2Integration:
    def test_signup_maps_duplicate_email_error_to_http_409(self, monkeypatch):
        """signup() must map DuplicateEmailError from create_user() to HTTP 409 Conflict."""
        monkeypatch.setattr("Backend.auth.router.get_user_by_email", lambda email: None)

        def mock_create_user(doc):
            raise DuplicateEmailError(doc["email"])

        monkeypatch.setattr("Backend.auth.router.create_user", mock_create_user)

        req = SignupRequest(name="Concurrent User", email="concurrent@example.com", password="SecurePassword123!")
        with pytest.raises(HTTPException) as exc_info:
            signup(req)

        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail

    def test_signup_maps_database_error_to_http_503(self, monkeypatch):
        """signup() must map DatabaseError from create_user() to HTTP 503."""
        monkeypatch.setattr("Backend.auth.router.get_user_by_email", lambda email: None)

        def mock_create_user(doc):
            raise DatabaseError("DB connection lost")

        monkeypatch.setattr("Backend.auth.router.create_user", mock_create_user)

        req = SignupRequest(name="Alex", email="alex@example.com", password="SecurePassword123!")
        with pytest.raises(HTTPException) as exc_info:
            signup(req)

        assert exc_info.value.status_code == 503

    def test_signup_precheck_race_condition_simulation(self, monkeypatch):
        """
        Simulate TOCTOU race: pre-check get_user_by_email returns None,
        but database unique constraint catches concurrent insert.
        """
        # Pre-check passes (returns None as if user didn't exist yet)
        monkeypatch.setattr("Backend.auth.router.get_user_by_email", lambda email: None)

        # Database insert fails with unique index violation
        exc = DuplicateKeyError("E11000", details={"keyPattern": {"email_normalized": 1}})
        mock_coll = MagicMock()
        mock_coll.insert_one.side_effect = exc
        monkeypatch.setattr(persistence, "users_collection", mock_coll)

        req = SignupRequest(name="Racer", email="racer@example.com", password="SecurePassword123!")
        with pytest.raises(HTTPException) as exc_info:
            signup(req)

        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail


# ============================================================================
# 4. INDEX VERIFICATION IN DATABASE STARTUP
# ============================================================================

class TestIndexVerification:
    def test_verify_user_unique_index_passes_with_correct_index(self, monkeypatch):
        """verify_user_unique_index() succeeds when exact index is present and unique."""
        mock_coll = MagicMock()
        mock_coll.list_indexes.return_value = [
            {"name": "_id_", "key": {"_id": 1}},
            {"name": "uniq_users_email_normalized", "key": {"email_normalized": 1}, "unique": True},
        ]
        monkeypatch.setattr(database, "users_collection", mock_coll)

        # Must not raise
        database.verify_user_unique_index()

    def test_verify_user_unique_index_fails_when_index_missing(self, monkeypatch):
        """verify_user_unique_index() raises RuntimeError when index is missing."""
        mock_coll = MagicMock()
        mock_coll.list_indexes.return_value = [
            {"name": "_id_", "key": {"_id": 1}},
        ]
        monkeypatch.setattr(database, "users_collection", mock_coll)

        with pytest.raises(RuntimeError, match="Required unique index 'uniq_users_email_normalized' .* is missing"):
            database.verify_user_unique_index()

    def test_verify_user_unique_index_fails_when_unique_is_false(self, monkeypatch):
        """verify_user_unique_index() raises RuntimeError when index exists but unique=False."""
        mock_coll = MagicMock()
        mock_coll.list_indexes.return_value = [
            {"name": "uniq_users_email_normalized", "key": {"email_normalized": 1}, "unique": False},
        ]
        monkeypatch.setattr(database, "users_collection", mock_coll)

        with pytest.raises(RuntimeError, match="exists but is NOT unique"):
            database.verify_user_unique_index()

    def test_verify_user_unique_index_fails_on_differently_named_index(self, monkeypatch):
        """verify_user_unique_index() rejects differently named index with key email_normalized."""
        mock_coll = MagicMock()
        mock_coll.list_indexes.return_value = [
            {"name": "email_normalized_1", "key": {"email_normalized": 1}, "unique": True},
        ]
        monkeypatch.setattr(database, "users_collection", mock_coll)

        with pytest.raises(RuntimeError, match="Conflicting index 'email_normalized_1'"):
            database.verify_user_unique_index()

    def test_verify_user_unique_index_fails_when_sparse(self, monkeypatch):
        """verify_user_unique_index() raises RuntimeError when index has sparse=True."""
        mock_coll = MagicMock()
        mock_coll.list_indexes.return_value = [
            {
                "name": "uniq_users_email_normalized",
                "key": {"email_normalized": 1},
                "unique": True,
                "sparse": True,
            },
        ]
        monkeypatch.setattr(database, "users_collection", mock_coll)

        with pytest.raises(RuntimeError, match="sparse=True"):
            database.verify_user_unique_index()

    def test_verify_user_unique_index_fails_when_partial_filter_expression(self, monkeypatch):
        """verify_user_unique_index() raises RuntimeError when index has partialFilterExpression."""
        mock_coll = MagicMock()
        mock_coll.list_indexes.return_value = [
            {
                "name": "uniq_users_email_normalized",
                "key": {"email_normalized": 1},
                "unique": True,
                "partialFilterExpression": {"email_normalized": {"$exists": True}},
            },
        ]
        monkeypatch.setattr(database, "users_collection", mock_coll)

        with pytest.raises(RuntimeError, match="partialFilterExpression"):
            database.verify_user_unique_index()


# ============================================================================
# 5. DEMO SEED DATA ALIGNMENT
# ============================================================================

class TestDemoSeedData:
    def test_seed_demo_project_populates_email_normalized(self, monkeypatch):
        """seed_demo_project() must include email_normalized in demo user."""
        inserted_docs = []

        mock_users = MagicMock()
        mock_users.find_one.return_value = None
        mock_users.insert_one.side_effect = lambda doc: inserted_docs.append(doc) or MagicMock(inserted_id=ObjectId())

        monkeypatch.setattr("Backend.seed_demo_data.users_collection", mock_users)
        monkeypatch.setattr("Backend.seed_demo_data.projects_collection", MagicMock())
        monkeypatch.setattr("Backend.seed_demo_data.commits_collection", MagicMock())
        monkeypatch.setattr("Backend.seed_demo_data.issues_collection", MagicMock())
        monkeypatch.setattr("Backend.seed_demo_data.pull_requests_collection", MagicMock())
        monkeypatch.setattr("Backend.seed_demo_data.milestones_collection", MagicMock())
        monkeypatch.setattr("Backend.seed_demo_data.metric_snapshots_collection", MagicMock())

        seed_demo_project()

        assert len(inserted_docs) == 1
        demo_user = inserted_docs[0]
        assert demo_user["email"] == "demo@kavach.ai"
        assert demo_user["email_normalized"] == "demo@kavach.ai"


# ============================================================================
# 6. MIGRATION SCRIPT INTEGRITY & AUDIT
# ============================================================================

class MockCollectionForMigration:
    """In-memory mock supporting find, bulk_write, create_index, list_indexes."""
    def __init__(self, initial_docs=None):
        self.docs = {str(d.get("_id", ObjectId())): dict(d) for d in (initial_docs or [])}
        for doc_id, doc in self.docs.items():
            if "_id" not in doc:
                doc["_id"] = ObjectId(doc_id)
        self.indexes = [{"name": "_id_", "key": {"_id": 1}}]
        self.bulk_write_calls = 0
        self.create_index_calls = 0
        self.update_calls = 0

    def find(self, query=None):
        return [dict(d) for d in self.docs.values()]

    def bulk_write(self, ops, ordered=False):
        self.bulk_write_calls += 1
        modified_count = 0
        for op in ops:
            filter_dict = op._filter
            doc_id = str(filter_dict["_id"])
            if doc_id in self.docs:
                update_set = op._doc.get("$set", {})
                self.docs[doc_id].update(update_set)
                modified_count += 1
        return MagicMock(modified_count=modified_count)

    def create_index(self, keys, unique=False, name=None, **kwargs):
        self.create_index_calls += 1
        key_dict = dict(keys)
        self.indexes.append({"name": name or "idx", "key": key_dict, "unique": unique})
        return name

    def update_one(self, *args, **kwargs):
        self.update_calls += 1
        return MagicMock(modified_count=1)

    def update_many(self, *args, **kwargs):
        self.update_calls += 1
        return MagicMock(modified_count=1)

    def list_indexes(self):
        return list(self.indexes)


class TestMigrationScript:
    def test_pydantic_email_validator(self):
        """Pydantic EmailStr validation correctly classifies addresses."""
        assert is_valid_email_str("valid@example.com") is True
        assert is_valid_email_str("user.name+tag@domain.co.uk") is True
        assert is_valid_email_str("spaces in@domain.com") is False
        assert is_valid_email_str("missing_at.com") is False
        assert is_valid_email_str("@missing_user.com") is False
        assert is_valid_email_str("") is False
        assert is_valid_email_str(None) is False

    def test_canonicalize_email_strict_validation(self):
        """canonicalize_email strictly validates emails, returning canonical forms or raising ValueError."""
        from Backend.auth.normalization import canonicalize_email

        # Valid normal ASCII
        assert canonicalize_email("  Test.User@Example.COM  ") == "test.user@example.com"
        # Full-width Unicode
        assert canonicalize_email("user@Ｄｏｍａｉｎ.com") == "user@domain.com"
        # Unicode IDN
        assert canonicalize_email("user@bücher.de") == "user@bücher.de"
        # Equivalent Punycode
        assert canonicalize_email("user@xn--bcher-kva.de") == "user@bücher.de"

        # Invalid emails must raise ValueError explicitly
        with pytest.raises(ValueError, match="Invalid email address format"):
            canonicalize_email("not-an-email")
        with pytest.raises(ValueError, match="Invalid email address format"):
            canonicalize_email("missing-at.com")
        with pytest.raises(ValueError, match="Invalid email address format"):
            canonicalize_email("@missing-user.com")
        with pytest.raises(ValueError, match="User email is required"):
            canonicalize_email("")
        with pytest.raises(ValueError, match="User email must not be empty after normalization"):
            canonicalize_email("   ")
        with pytest.raises(ValueError, match="User email is required"):
            canonicalize_email(None)

    def test_audit_detects_duplicate_canonical_groups(self):
        """Audit groups case/whitespace variants into duplicate groups."""
        coll = MockCollectionForMigration([
            {"_id": ObjectId(), "name": "User 1", "email": "john.doe@example.com"},
            {"_id": ObjectId(), "name": "User 2", "email": "  JOHN.DOE@EXAMPLE.COM  "},
            {"_id": ObjectId(), "name": "User 3", "email": "unique@example.com"},
        ])
        result = audit_users_collection(coll)
        assert len(result.duplicate_groups) == 1
        assert "john.doe@example.com" in result.duplicate_groups
        assert len(result.duplicate_groups["john.doe@example.com"]) == 2
        assert result.has_blocking_conflicts is True

    def test_audit_detects_missing_and_invalid_emails(self):
        """Audit detects missing and invalid email records."""
        coll = MockCollectionForMigration([
            {"_id": ObjectId(), "name": "No Email", "email": None},
            {"_id": ObjectId(), "name": "Bad Email", "email": "not-an-email"},
            {"_id": ObjectId(), "name": "Good", "email": "good@example.com"},
        ])
        result = audit_users_collection(coll)
        assert len(result.missing_emails) == 1
        assert len(result.invalid_emails) == 1
        assert result.has_blocking_conflicts is True

    def test_migration_aborts_without_writes_on_invalid_email_records(self):
        """Migration aborts with exit code 2 and zero writes when invalid email records exist."""
        bad_doc_id = ObjectId()
        good_doc_id = ObjectId()
        coll = MockCollectionForMigration([
            {"_id": bad_doc_id, "name": "Bad Email User", "email": "invalid-email-address"},
            {"_id": good_doc_id, "name": "Good Email User", "email": "valid@example.com"},
        ])
        result = audit_users_collection(coll)
        assert len(result.invalid_emails) == 1
        assert result.has_blocking_conflicts is True

        code = run_migration(coll, apply=True, verbose=False)
        assert code == 2
        # Explicitly verify zero database writes and zero index creations occurred
        assert coll.bulk_write_calls == 0
        assert coll.create_index_calls == 0
        assert coll.update_calls == 0
        assert "email_normalized" not in coll.docs[str(bad_doc_id)]
        assert "email_normalized" not in coll.docs[str(good_doc_id)]

    def test_audit_detects_stale_canonical_fields(self):
        """Audit identifies inconsistent email_normalized fields."""
        coll = MockCollectionForMigration([
            {"_id": ObjectId(), "name": "User", "email": "alex@example.com", "email_normalized": "wrong@example.com"},
        ])
        result = audit_users_collection(coll)
        assert len(result.stale_fields) == 1
        assert result.stale_fields[0][1] == "alex@example.com"

    def test_audit_detects_backfill_collision_hazards(self):
        """Audit prevents an update from colliding with an existing normalized field."""
        existing_doc_id = ObjectId()
        stale_doc_id = ObjectId()
        coll = MockCollectionForMigration([
            {"_id": existing_doc_id, "name": "A", "email": "alpha@example.com", "email_normalized": "alpha@example.com"},
            # Record B's email changes to alpha@example.com, but its old normalized was beta
            {"_id": stale_doc_id, "name": "B", "email": "alpha@example.com", "email_normalized": "beta@example.com"},
        ])
        result = audit_users_collection(coll)
        assert len(result.collision_hazards) == 1
        assert result.has_blocking_conflicts is True

    def test_migration_dry_run_returns_1_when_conflicts_exist(self):
        """dry-run returns exit code 1 when conflicts exist and makes no writes."""
        coll = MockCollectionForMigration([
            {"_id": ObjectId(), "email": "dup@example.com"},
            {"_id": ObjectId(), "email": "DUP@example.com"},
        ])
        code = run_migration(coll, apply=False, verbose=False)
        assert code == 1
        # No indexes created
        assert len(coll.indexes) == 1

    def test_migration_apply_aborts_when_conflicts_exist(self):
        """--apply aborts with exit code 2 when conflicts exist and performs zero writes."""
        coll = MockCollectionForMigration([
            {"_id": ObjectId(), "name": "A", "email": "dup@example.com"},
            {"_id": ObjectId(), "name": "B", "email": "DUP@example.com"},
        ])
        code = run_migration(coll, apply=True, verbose=False)
        assert code == 2
        # No index created, no documents backfilled
        assert len(coll.indexes) == 1
        for doc in coll.docs.values():
            assert "email_normalized" not in doc

    def test_migration_apply_succeeds_on_clean_database_idempotently(self):
        """--apply backfills clean database, creates unique index, and is idempotent."""
        coll = MockCollectionForMigration([
            {"_id": ObjectId(), "name": "User 1", "email": "user1@example.com"},
            {"_id": ObjectId(), "name": "User 2", "email": "  USER2@EXAMPLE.COM  "},
        ])

        # Run 1: Apply backfill and create index
        code1 = run_migration(coll, apply=True, verbose=False)
        assert code1 == 0

        # Verify backfill
        docs = list(coll.docs.values())
        assert docs[0]["email_normalized"] == "user1@example.com"
        assert docs[1]["email_normalized"] == "user2@example.com"

        # Verify index was created
        idx_names = [i["name"] for i in coll.indexes]
        assert "uniq_users_email_normalized" in idx_names

        # Run 2: Idempotent re-run on migrated database
        code2 = run_migration(coll, apply=True, verbose=False)
        assert code2 == 0

    def test_migration_cli_main_dry_run_flag(self, monkeypatch):
        """CLI main with --dry-run parses arguments and calls run_migration."""
        from Backend.scripts import migrate_b2_email_uniqueness

        coll = MockCollectionForMigration([{"_id": ObjectId(), "email": "a@b.com"}])
        monkeypatch.setattr("Backend.database.users_collection", coll)

        with pytest.raises(SystemExit) as exc_info:
            migrate_b2_email_uniqueness.main(["--dry-run"])
        assert exc_info.value.code == 0

    def test_migration_cli_main_apply_flag(self, monkeypatch):
        """CLI main with --apply parses arguments and executes migration."""
        from Backend.scripts import migrate_b2_email_uniqueness

        coll = MockCollectionForMigration([{"_id": ObjectId(), "email": "a@b.com"}])
        monkeypatch.setattr("Backend.database.users_collection", coll)

        with pytest.raises(SystemExit) as exc_info:
            migrate_b2_email_uniqueness.main(["--apply"])
        assert exc_info.value.code == 0

    def test_audit_normalizes_whitespace_padded_legacy_email_before_validation(self):
        """
        Regression Test: whitespace-padded legacy email is normalized first
        (matching SignupRequest sequence), successfully passes Pydantic EmailStr,
        and is scheduled for backfill without being marked invalid.
        """
        coll = MockCollectionForMigration([
            {"_id": ObjectId(), "name": "Padded", "email": "   alex.legacy@example.com   \n"},
        ])
        result = audit_users_collection(coll)
        assert len(result.invalid_emails) == 0
        assert len(result.missing_emails) == 0
        assert len(result.pending_backfill) == 1
        assert result.pending_backfill[0][1] == "alex.legacy@example.com"
        assert result.has_blocking_conflicts is False

    def test_migration_aborts_on_incompatible_existing_index(self):
        """
        Migration aborts before modifying records if an incompatible or conflicting
        index exists on email_normalized. Verifies zero bulk_write and create_index calls.
        """
        coll = MockCollectionForMigration([
            {"_id": ObjectId(), "name": "User", "email": "valid@example.com"},
        ])
        # Add a conflicting index named differently or non-unique
        coll.indexes.append({"name": "wrong_index_name", "key": {"email_normalized": 1}, "unique": True})

        result = audit_users_collection(coll)
        assert len(result.incompatible_indexes) == 1
        assert result.has_blocking_conflicts is True

        code = run_migration(coll, apply=True, verbose=False)
        assert code == 2
        # Explicitly verify no database writes or index creation occurred
        assert coll.bulk_write_calls == 0
        assert coll.create_index_calls == 0
        assert coll.update_calls == 0
        docs = list(coll.docs.values())
        assert "email_normalized" not in docs[0]

    def test_migration_aborts_on_sparse_unique_index(self):
        """
        Migration aborts when the named index exists with sparse=True,
        since a sparse index does not enforce uniqueness on all documents.
        Verifies zero bulk_write and create_index calls.
        """
        coll = MockCollectionForMigration([
            {"_id": ObjectId(), "name": "User", "email": "valid@example.com"},
        ])
        # Named correctly but sparse — still incompatible
        coll.indexes.append({
            "name": "uniq_users_email_normalized",
            "key": {"email_normalized": 1},
            "unique": True,
            "sparse": True,
        })

        result = audit_users_collection(coll)
        assert len(result.incompatible_indexes) == 1
        assert "sparse" in result.incompatible_indexes[0]["reason"].lower()
        assert result.has_blocking_conflicts is True

        code = run_migration(coll, apply=True, verbose=False)
        assert code == 2
        assert coll.bulk_write_calls == 0
        assert coll.create_index_calls == 0
        assert coll.update_calls == 0
        docs = list(coll.docs.values())
        assert "email_normalized" not in docs[0]

    def test_migration_aborts_on_partial_filter_expression_index(self):
        """
        Migration aborts when the named index exists with a partialFilterExpression,
        since a partial index does not enforce uniqueness across all documents.
        Verifies zero bulk_write and create_index calls.
        """
        coll = MockCollectionForMigration([
            {"_id": ObjectId(), "name": "User", "email": "valid@example.com"},
        ])
        # Named correctly but has partialFilterExpression — still incompatible
        coll.indexes.append({
            "name": "uniq_users_email_normalized",
            "key": {"email_normalized": 1},
            "unique": True,
            "partialFilterExpression": {"email_normalized": {"$exists": True}},
        })

        result = audit_users_collection(coll)
        assert len(result.incompatible_indexes) == 1
        assert "partialfilterexpression" in result.incompatible_indexes[0]["reason"].lower()
        assert result.has_blocking_conflicts is True

        code = run_migration(coll, apply=True, verbose=False)
        assert code == 2
        assert coll.bulk_write_calls == 0
        assert coll.create_index_calls == 0
        assert coll.update_calls == 0
        docs = list(coll.docs.values())
        assert "email_normalized" not in docs[0]

    def test_migration_aborts_on_non_unique_existing_named_index(self):
        """
        Migration aborts when uniq_users_email_normalized exists with unique=False.
        Verifies zero bulk_write and create_index calls.
        """
        coll = MockCollectionForMigration([
            {"_id": ObjectId(), "name": "User", "email": "valid@example.com"},
        ])
        coll.indexes.append({
            "name": "uniq_users_email_normalized",
            "key": {"email_normalized": 1},
            "unique": False,
        })

        result = audit_users_collection(coll)
        assert len(result.incompatible_indexes) == 1
        assert "unique flag" in result.incompatible_indexes[0]["reason"].lower()
        assert result.has_blocking_conflicts is True

        code = run_migration(coll, apply=True, verbose=False)
        assert code == 2
        assert coll.bulk_write_calls == 0
        assert coll.create_index_calls == 0
        assert coll.update_calls == 0
        docs = list(coll.docs.values())
        assert "email_normalized" not in docs[0]

    def test_migration_aborts_on_wrong_key_pattern_existing_named_index(self):
        """
        Migration aborts when uniq_users_email_normalized exists with an incorrect key pattern.
        Verifies zero bulk_write and create_index calls.
        """
        coll = MockCollectionForMigration([
            {"_id": ObjectId(), "name": "User", "email": "valid@example.com"},
        ])
        coll.indexes.append({
            "name": "uniq_users_email_normalized",
            "key": {"email_normalized": 1, "tenant": 1},
            "unique": True,
        })

        result = audit_users_collection(coll)
        assert len(result.incompatible_indexes) == 1
        assert "incorrect key" in result.incompatible_indexes[0]["reason"].lower()
        assert result.has_blocking_conflicts is True

        code = run_migration(coll, apply=True, verbose=False)
        assert code == 2
        assert coll.bulk_write_calls == 0
        assert coll.create_index_calls == 0
        assert coll.update_calls == 0
        docs = list(coll.docs.values())
        assert "email_normalized" not in docs[0]

    def test_migration_aborts_on_list_indexes_failure(self):
        """
        Migration aborts with exit code 2 and zero writes if list_indexes() raises an exception.
        """
        coll = MockCollectionForMigration([
            {"_id": ObjectId(), "name": "User", "email": "valid@example.com"},
        ])

        def broken_list_indexes():
            raise PyMongoError("Database connection failed during list_indexes")

        coll.list_indexes = broken_list_indexes

        result = audit_users_collection(coll)
        assert len(result.incompatible_indexes) == 1
        assert "failed to list collection indexes" in result.incompatible_indexes[0]["reason"].lower()
        assert result.has_blocking_conflicts is True

        code = run_migration(coll, apply=True, verbose=False)
        assert code == 2
        assert coll.bulk_write_calls == 0
        assert coll.create_index_calls == 0
        assert coll.update_calls == 0
        docs = list(coll.docs.values())
        assert "email_normalized" not in docs[0]

    def test_canonicalization_parity_with_signup_request_and_create_user(self, monkeypatch):
        """
        Verify canonicalization parity between:
          1. SignupRequest validation (B1 Pydantic pipeline)
          2. create_user() insertion (B2 runtime persistence)
          3. audit_users_collection() backfill (B2 migration)
        All three pipelines must derive the identical canonical email string for any valid input.
        """
        test_emails = [
            "user@example.com",
            "  John.Doe@Example.COM  ",
            "Alex.O'Connor+Dev@Domain.Org",
            "support+billing@corp.sub.domain.co.uk",
            "12345.numerical_id@domain-name.com",
            "  USER.NAME+TAG@EXAMPLE.COM \n",
            # Unicode & IDN test cases
            "user@Ｄｏｍａｉｎ.com",       # Full-width Unicode domain -> canonicalizes to user@domain.com
            "user@bücher.de",             # Internationalized domain with umlaut
            "user@xn--bcher-kva.de",      # Punycode representation -> canonicalizes to user@bücher.de
        ]

        for raw_email in test_emails:
            # 1. SignupRequest pipeline (B1 schema)
            req = SignupRequest(name="Test User", email=raw_email, password="SecurePassword123!")
            signup_pipeline_email = req.email

            # 2. create_user pipeline called directly with original raw email input (B2 runtime)
            captured = {}
            mock_coll = MagicMock()
            mock_coll.insert_one.side_effect = lambda doc: captured.update(doc) or MagicMock(inserted_id=ObjectId())
            monkeypatch.setattr(persistence, "users_collection", mock_coll)
            persistence.create_user({"name": "Test User", "email": raw_email})
            create_user_canonical = captured["email_normalized"]

            # 3. Migration audit pipeline directly on legacy raw email (B2 migration)
            migration_coll = MockCollectionForMigration([
                {"_id": ObjectId(), "name": "Legacy", "email": raw_email},
            ])
            audit_result = audit_users_collection(migration_coll)
            assert len(audit_result.invalid_emails) == 0
            assert len(audit_result.pending_backfill) == 1
            migration_canonical = audit_result.pending_backfill[0][1]

            # Parity check: all three pipelines derive the exact same canonical string
            assert migration_canonical == create_user_canonical == signup_pipeline_email

    def test_migration_detects_punycode_and_unicode_domain_as_duplicate_group(self):
        """
        Verify that an internationalized domain (user@bücher.de) and its Punycode
        equivalent (user@xn--bcher-kva.de) are identified as the exact same canonical
        email group and flagged as a duplicate conflict.
        """
        coll = MockCollectionForMigration([
            {"_id": ObjectId(), "name": "Unicode User", "email": "user@bücher.de"},
            {"_id": ObjectId(), "name": "Punycode User", "email": "user@xn--bcher-kva.de"},
        ])
        result = audit_users_collection(coll)
        assert len(result.duplicate_groups) == 1
        assert "user@bücher.de" in result.duplicate_groups
        assert len(result.duplicate_groups["user@bücher.de"]) == 2
        assert result.has_blocking_conflicts is True
