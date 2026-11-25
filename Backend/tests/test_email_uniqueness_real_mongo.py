"""
Real MongoDB Integration Test Suite — Unique Email Constraint & Concurrency (B2)
==================================================================================

Performs REAL (non-mocked) database operations against an ephemeral local MongoDB
instance running on port 27019 when mongod is available.

Contains two distinctly separated test classes:
  1. TestRealMongoDirectFunctionConcurrency:
     Direct concurrent function calls to signup() across parallel threads.
     Tests persistence-level and business-logic constraint enforcement under real database concurrency.
  2. TestRealMongoHttpEndpointTransport:
     End-to-end HTTP transport tests via FastAPI TestClient verifying real HTTP status codes (201 and 409).
     Skips gracefully if the local execution environment blocks loopback sockets.

NOTE: If a local mongod binary is not found, the entire suite is reported as SKIPPED.
Skipped tests are never counted as passing concurrency tests.
"""

import glob
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from bson import ObjectId
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError
from pymongo.mongo_client import MongoClient as RealMongoClient

from Backend import database, persistence
from Backend.auth.router import signup
from Backend.auth.schemas import SignupRequest
from Backend.main import app

TEST_DB_NAME = "test_b2_email_uniqueness_ephemeral"


def get_free_port() -> int:
    """Find an available local TCP port to avoid collisions."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def find_mongod_binary():
    """Locate local mongod executable if installed."""
    system_path = shutil.which("mongod")
    if system_path and os.path.exists(system_path):
        return system_path

    # Common Windows MongoDB Server paths
    candidates = glob.glob(r"C:\Program Files\MongoDB\Server\*\bin\mongod.exe")
    if candidates:
        return candidates[0]

    return None


@pytest.fixture(scope="module")
def real_mongo():
    """Start an ephemeral local MongoDB server for testing, then tear it down."""
    mongod_path = find_mongod_binary()
    if not mongod_path:
        pytest.skip("Local mongod binary not found; skipping real MongoDB integration tests.")

    port = get_free_port()
    test_uri = f"mongodb://127.0.0.1:{port}"
    tmp_dir = tempfile.mkdtemp(prefix="mongo_b2_test_")
    proc = subprocess.Popen(
        [
            mongod_path,
            "--port", str(port),
            "--dbpath", tmp_dir,
            "--bind_ip", "127.0.0.1",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    client = None
    try:
        # Wait up to 5 seconds for mongod to accept connections
        for _ in range(50):
            try:
                client = RealMongoClient(test_uri, serverSelectionTimeoutMS=200)
                client.admin.command("ping")
                break
            except Exception:
                time.sleep(0.1)
        else:
            pytest.fail(f"Failed to start ephemeral MongoDB on port {port} within 5 seconds.")

        yield client
    finally:
        if client:
            client.close()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def clean_db(real_mongo, monkeypatch):
    """Provide a clean test database with uniq_users_email_normalized index created."""
    db = real_mongo[TEST_DB_NAME]
    db.drop_collection("users")

    # Create the exact expected unique index
    db.users.create_index(
        [("email_normalized", 1)],
        unique=True,
        name="uniq_users_email_normalized",
        background=False,
    )

    # Wire both persistence and database collections to the real live collection
    users_col = db["users"]
    db.users = users_col
    monkeypatch.setattr(database, "users_collection", users_col)
    monkeypatch.setattr(persistence, "users_collection", users_col)
    yield db
    db.drop_collection("users")


# ============================================================================
# PART A: DIRECT CONCURRENT SIGNUP FUNCTION TESTS (Real MongoDB Concurrency)
# ============================================================================

class TestRealMongoDirectFunctionConcurrency:
    """
    Tests persistence-level and domain logic constraint enforcement directly
    against real MongoDB without depending on loopback HTTP sockets.
    """

    def test_real_mongo_rejects_duplicate_normalized_insert(self, clean_db):
        """Direct database insert must raise DuplicateKeyError on duplicate email_normalized."""
        clean_db.users.insert_one({
            "name": "First User",
            "email": "alex@example.com",
            "email_normalized": "alex@example.com",
        })

        with pytest.raises(DuplicateKeyError):
            clean_db.users.insert_one({
                "name": "Second User",
                "email": "ALEX@example.com",
                "email_normalized": "alex@example.com",
            })

    def test_real_mongo_concurrent_signup_calls_thread_race(self, clean_db, monkeypatch):
        """
        Execute 10 concurrent signup() calls with identical/case-variant emails.
        A threading.Barrier ensures ALL threads complete their get_user_by_email()
        pre-check (which returns None for all, since the DB is empty) before ANY
        thread proceeds to create_user(). This guarantees the TOCTOU race is exercised:
        all 10 threads observe no duplicate pre-check, then collide at the unique index.
        Exactly 1 must succeed; remaining 9 must raise HTTPException(409).
        """
        # 1. Verify that persistence and database collections share the exact same clean_db.users collection
        assert persistence.users_collection is clean_db.users
        assert database.users_collection is clean_db.users

        # 2. Verify that the actual unique index exists and is properly configured before executing the race
        database.verify_user_unique_index()

        email_variants = [
            "om+test@example.com",
            "OM+TEST@EXAMPLE.COM",
            "  om+test@example.com  ",
            "Om+Test@Example.Com",
            "om+test@example.com",
            "OM+TEST@example.com",
            "  OM+TEST@EXAMPLE.COM  ",
            "om+test@EXAMPLE.COM",
            "Om+test@example.com",
            "om+TEST@example.com",
        ]

        # Barrier: all 10 threads must finish their real pre-check before any proceeds
        barrier = threading.Barrier(10, timeout=10)

        # Keep a reference to the real persistence lookup (uses the real MongoDB collection)
        real_get_user_by_email = persistence.get_user_by_email

        def synced_get_user_by_email(email):
            # Perform the real pre-check against the real (empty) MongoDB collection
            result = real_get_user_by_email(email)
            # Explicitly assert that the genuine database lookup returned None (no user exists)
            assert result is None, f"Expected user to not exist in real DB prior to race, got: {result}"
            # Wait until all 10 threads have completed their pre-check
            # At this point all return None (DB is empty), so all will proceed to create_user()
            try:
                barrier.wait()
            except threading.BrokenBarrierError:
                pytest.fail("Barrier timed out or was broken — concurrency test inconclusive")
            return result

        # Patch the router's reference to get_user_by_email (not the persistence module directly)
        monkeypatch.setattr("Backend.auth.router.get_user_by_email", synced_get_user_by_email)

        def attempt_signup(variant_email, index):
            req = SignupRequest(
                name=f"Concurrent User {index}",
                email=variant_email,
                password="SecurePassword123!",
            )
            return signup(req)

        successes = []
        conflicts = []
        other_errors = []

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(attempt_signup, email_variants[i], i): i
                for i in range(10)
            }
            for fut in as_completed(futures):
                try:
                    res = fut.result()
                    successes.append(res)
                except HTTPException as exc:
                    if exc.status_code == 409:
                        conflicts.append(exc)
                    else:
                        other_errors.append(exc)
                except Exception as exc:
                    other_errors.append(exc)

        # Assertions on real concurrency outcome
        assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}: {successes}"
        assert len(conflicts) == 9, f"Expected 9 conflicts (409), got {len(conflicts)}"
        assert len(other_errors) == 0, f"Unexpected errors: {other_errors}"

        # Verify database state: exactly one document with the canonical email
        all_docs = list(clean_db.users.find({"email_normalized": "om+test@example.com"}))
        assert len(all_docs) == 1
        assert all_docs[0]["email_normalized"] == "om+test@example.com"


# ============================================================================
# PART B: HTTP ENDPOINT INTEGRATION TESTS (TestClient Transport)
# ============================================================================

class TestRealMongoHttpEndpointTransport:
    """
    Tests end-to-end HTTP serialization, headers, and status codes (201 & 409)
    using FastAPI TestClient against real MongoDB.
    """

    def test_http_endpoint_signup_duplicate_returns_201_then_409(self, clean_db):
        """HTTP client receives status 201 on initial signup and 409 on duplicate using TestClient context."""
        try:
            with TestClient(app) as client:
                payload1 = {
                    "name": "HTTP User",
                    "email": "http.user@example.com",
                    "password": "SecurePassword123!",
                }
                res1 = client.post("/auth/signup", json=payload1)
                assert res1.status_code == 201
                body1 = res1.json()
                assert "access_token" in body1

                payload2 = {
                    "name": "HTTP Duplicate",
                    "email": "  HTTP.USER@EXAMPLE.COM  ",
                    "password": "OtherPassword123!",
                }
                res2 = client.post("/auth/signup", json=payload2)
                assert res2.status_code == 409
                body2 = res2.json()
                assert "already exists" in body2.get("detail", "").lower()
        except OSError as exc:
            # Environment constraint: loopback sockets blocked in restricted sandbox
            pytest.skip(f"Loopback socket blocked in sandbox environment: {exc}")
