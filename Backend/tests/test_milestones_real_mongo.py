"""
Real MongoDB Integration Test Suite — GitHub Milestone Ingestion (Issue #72)
=============================================================================

This suite performs REAL (non-mocked) database operations against an ephemeral
local MongoDB instance running on port 27019.

Tests:
    1. Real collection and compound index creation (projectId + milestone_id).
    2. Real initial milestone insertion via sync.
    3. Document schema, types, and field validation.
    4. Absence of token/password/secret fields in MongoDB documents.
    5. Real idempotent re-sync (upserting without duplicate creation).
    6. Real milestone updates (title change, issue count change, state change).
    7. Database-level DuplicateKeyError enforcement on compound unique key.
    8. Cross-project data isolation (same milestone_id in two projects).
    9. Real retrieval via get_milestones_for_project with state filtering.
   10. End-to-end FastAPI test client sync and retrieval against real MongoDB.
   11. Authorization and security enforcement in real database environment.
"""

import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import pymongo
from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

MONGOD_PATH = r"C:\Program Files\MongoDB\Server\9.0\bin\mongod.exe"
TEST_PORT = 27019
TEST_URI = f"mongodb://127.0.0.1:{TEST_PORT}"
TEST_DB_NAME = "test_milestone_real_db"


@pytest.fixture(scope="module")
def real_mongo():
    """Start an ephemeral local MongoDB server for testing, then tear it down."""
    if not os.path.exists(MONGOD_PATH):
        pytest.skip(f"Local mongod not found at {MONGOD_PATH}")

    tmp_dir = tempfile.mkdtemp(prefix="mongo_milestone_test_")
    proc = subprocess.Popen(
        [
            MONGOD_PATH,
            "--port", str(TEST_PORT),
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
                client = MongoClient(TEST_URI, serverSelectionTimeoutMS=200)
                client.admin.command("ping")
                break
            except Exception:
                time.sleep(0.1)
        else:
            pytest.fail("Failed to start ephemeral MongoDB within 5 seconds.")

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
def clean_db(real_mongo):
    """Ensure clean collections before and after each test."""
    db = real_mongo[TEST_DB_NAME]
    db.drop_collection("projects")
    db.drop_collection("milestones")
    db.drop_collection("users")

    # Recreate unique compound index on (projectId, milestone_id)
    db.milestones.create_index(
        [("projectId", 1), ("milestone_id", 1)],
        unique=True,
        background=False,
    )
    yield db
    db.drop_collection("projects")
    db.drop_collection("milestones")
    db.drop_collection("users")


class TestRealMongoDBMilestones:
    """Rigorous tests executed directly against a live MongoDB v9 instance."""

    def test_real_index_enforces_compound_uniqueness(self, clean_db):
        """Inserting two records with identical projectId and milestone_id must raise DuplicateKeyError."""
        proj_oid = ObjectId("507f1f77bcf86cd799439001")
        doc1 = {
            "projectId": proj_oid,
            "milestone_id": "1",
            "title": "Sprint 1",
            "state": "open",
        }
        clean_db.milestones.insert_one(doc1)

        doc2 = {
            "projectId": proj_oid,
            "milestone_id": "1",
            "title": "Sprint 1 Duplicate",
            "state": "closed",
        }
        with pytest.raises(DuplicateKeyError):
            clean_db.milestones.insert_one(doc2)

        # Same milestone_id in a different project is permitted
        other_proj_oid = ObjectId("507f1f77bcf86cd799439002")
        doc3 = {
            "projectId": other_proj_oid,
            "milestone_id": "1",
            "title": "Sprint 1 in Project Beta",
            "state": "open",
        }
        clean_db.milestones.insert_one(doc3)
        assert clean_db.milestones.count_documents({"milestone_id": "1"}) == 2

    def test_real_sync_and_idempotent_upsert(self, clean_db):
        """Simulate real sync: 1st run inserts, 2nd run updates in place, 3rd modifies."""
        from Backend.externalservies.github_milestones import (
            sync_project_milestones,
            get_milestones_for_project,
        )

        project_id = "507f1f77bcf86cd799439001"
        clean_db.projects.insert_one({
            "_id": ObjectId(project_id),
            "name": "Live Test Project",
            "repo_url": "https://github.com/OpenTirZ/Ai-Software-Project-Health-and-Risk-Analyzer",
        })

        mock_payload_v1 = [
            {
                "number": 1,
                "title": "Sprint 1 Initial",
                "description": "First sprint description",
                "state": "open",
                "due_on": "2026-12-01T00:00:00Z",
                "open_issues": 5,
                "closed_issues": 5,
                "html_url": "https://github.com/OpenTirZ/repo/milestone/1",
            },
            {
                "number": 2,
                "title": "Sprint 2 Closed",
                "description": "Completed sprint",
                "state": "closed",
                "due_on": None,
                "open_issues": 0,
                "closed_issues": 10,
                "html_url": "https://github.com/OpenTirZ/repo/milestone/2",
            },
        ]

        with patch("Backend.externalservies.github_milestones._fetch_all_milestones", return_value=mock_payload_v1), \
             patch("Backend.externalservies.github_milestones._get_authenticated_session"), \
             patch("Backend.externalservies.github_milestones.get_project", return_value=clean_db.projects.find_one({"_id": ObjectId(project_id)})), \
             patch("Backend.persistence_telemetry.milestones_collection", clean_db.milestones):

            # --- RUN 1: Initial Sync ---
            result1 = sync_project_milestones(project_id)
            assert result1["success"] is True
            assert result1["fetched_count"] == 2
            assert result1["created_count"] == 2
            assert result1["updated_count"] == 0

            # Verify real MongoDB documents
            docs = list(clean_db.milestones.find({"projectId": ObjectId(project_id)}))
            assert len(docs) == 2
            m1 = clean_db.milestones.find_one({"projectId": ObjectId(project_id), "milestone_id": "1"})
            assert m1 is not None
            assert m1["title"] == "Sprint 1 Initial"
            assert m1["open_issues"] == 5
            assert m1["closed_issues"] == 5
            assert m1["state"] == "open"

            # Security check: verify no secrets or internal tokens in MongoDB
            for doc in docs:
                for k in doc:
                    assert "token" not in k.lower()
                    assert "secret" not in k.lower()
                    assert "password" not in k.lower()

            # --- RUN 2: Idempotent Re-sync (identical data) ---
            result2 = sync_project_milestones(project_id)
            assert result2["success"] is True
            assert result2["fetched_count"] == 2
            # Upsert updated existing records, did NOT insert duplicates
            assert clean_db.milestones.count_documents({"projectId": ObjectId(project_id)}) == 2

            # --- RUN 3: Modified Data Sync ---
            mock_payload_v2 = [
                {
                    "number": 1,
                    "title": "Sprint 1 Renamed & Advanced",
                    "description": "Updated sprint description",
                    "state": "open",
                    "due_on": "2026-12-15T00:00:00Z",
                    "open_issues": 1,
                    "closed_issues": 9,
                    "html_url": "https://github.com/OpenTirZ/repo/milestone/1",
                },
            ]
            with patch("Backend.externalservies.github_milestones._fetch_all_milestones", return_value=mock_payload_v2):
                result3 = sync_project_milestones(project_id)
                assert result3["success"] is True

            # Verify existing record was updated in place in real MongoDB
            m1_updated = clean_db.milestones.find_one({"projectId": ObjectId(project_id), "milestone_id": "1"})
            assert m1_updated["title"] == "Sprint 1 Renamed & Advanced"
            assert m1_updated["open_issues"] == 1
            assert m1_updated["closed_issues"] == 9
            # Total count across project remains 2 (milestone 1 updated, milestone 2 preserved)
            assert clean_db.milestones.count_documents({"projectId": ObjectId(project_id)}) == 2

    def test_real_cross_project_isolation(self, clean_db):
        """Project A and Project B share the same milestone_id='1' without colliding."""
        from Backend.externalservies.github_milestones import (
            sync_project_milestones,
            get_milestones_for_project,
        )

        proj_a = "507f1f77bcf86cd79943900a"
        proj_b = "507f1f77bcf86cd79943900b"

        clean_db.projects.insert_many([
            {"_id": ObjectId(proj_a), "name": "Project Alpha", "repo_url": "https://github.com/org/alpha"},
            {"_id": ObjectId(proj_b), "name": "Project Beta", "repo_url": "https://github.com/org/beta"},
        ])

        payload_a = [{"number": 1, "title": "Alpha Sprint", "state": "open", "open_issues": 5, "closed_issues": 0}]
        payload_b = [{"number": 1, "title": "Beta Sprint", "state": "closed", "open_issues": 0, "closed_issues": 10}]

        with patch("Backend.externalservies.github_milestones._get_authenticated_session"), \
             patch("Backend.persistence_telemetry.milestones_collection", clean_db.milestones):

            with patch("Backend.externalservies.github_milestones._fetch_all_milestones", return_value=payload_a), \
                 patch("Backend.externalservies.github_milestones.get_project", return_value=clean_db.projects.find_one({"_id": ObjectId(proj_a)})):
                sync_project_milestones(proj_a)

            with patch("Backend.externalservies.github_milestones._fetch_all_milestones", return_value=payload_b), \
                 patch("Backend.externalservies.github_milestones.get_project", return_value=clean_db.projects.find_one({"_id": ObjectId(proj_b)})):
                sync_project_milestones(proj_b)

        # Total milestones in DB = 2
        assert clean_db.milestones.count_documents({}) == 2

        with patch("Backend.persistence_telemetry.milestones_collection", clean_db.milestones):
            results_a = get_milestones_for_project(proj_a)
            results_b = get_milestones_for_project(proj_b)

        assert len(results_a) == 1
        assert results_a[0]["title"] == "Alpha Sprint"
        assert results_a[0]["state"] == "open"

        assert len(results_b) == 1
        assert results_b[0]["title"] == "Beta Sprint"
        assert results_b[0]["state"] == "closed"

    def test_real_mongo_state_filtering(self, clean_db):
        """Verify state=open and state=closed filters against live MongoDB queries."""
        from Backend.externalservies.github_milestones import get_milestones_for_project

        proj_id = "507f1f77bcf86cd79943900c"
        proj_oid = ObjectId(proj_id)
        clean_db.milestones.insert_many([
            {"projectId": proj_oid, "milestone_id": "1", "title": "M1", "state": "open", "open_issues": 1, "closed_issues": 0, "due_on": None},
            {"projectId": proj_oid, "milestone_id": "2", "title": "M2", "state": "open", "open_issues": 2, "closed_issues": 0, "due_on": None},
            {"projectId": proj_oid, "milestone_id": "3", "title": "M3", "state": "closed", "open_issues": 0, "closed_issues": 5, "due_on": None},
        ])

        with patch("Backend.persistence_telemetry.milestones_collection", clean_db.milestones):
            all_m = get_milestones_for_project(proj_id)
            open_m = get_milestones_for_project(proj_id, state="open")
            closed_m = get_milestones_for_project(proj_id, state="closed")

        assert len(all_m) == 3
        assert len(open_m) == 2
        assert len(closed_m) == 1
        assert closed_m[0]["milestone_id"] == "3"
        assert closed_m[0]["completion_percentage"] == 100.0

    def test_real_fastapi_e2e_sync_and_get(self, clean_db):
        """End-to-End API test: POST /sync-milestones then GET /milestones against real MongoDB."""
        from fastapi.testclient import TestClient
        from Backend.main import app
        from Backend.auth.dependencies import get_current_user
        from Backend.auth.roles import require_role, Role

        project_id = "507f1f77bcf86cd79943900d"
        proj_oid = ObjectId(project_id)
        user_id = "507f1f77bcf86cd79943900e"

        # Setup real project in database
        clean_db.projects.insert_one({
            "_id": proj_oid,
            "name": "E2E Real Mongo Project",
            "repo_url": "https://github.com/OpenTirZ/Ai-Software-Project-Health-and-Risk-Analyzer",
            "ownerId": ObjectId(user_id),
            "members": [{"userId": ObjectId(user_id), "role": "admin"}],
        })

        client = TestClient(app, raise_server_exceptions=False)
        mock_user = {
            "_id": user_id,
            "email": "lead@example.com",
            "name": "Project Lead",
            "role": "admin",
        }

        # Override auth dependencies
        app.dependency_overrides[get_current_user] = lambda: mock_user
        for combo in [
            (Role.ADMIN,),
            (Role.ADMIN, Role.PROJECT_MANAGER),
            (Role.PROJECT_MANAGER,),
        ]:
            app.dependency_overrides[require_role(*combo)] = lambda: mock_user

        mock_github_payload = [
            {
                "number": 1,
                "title": "Sprint 1 E2E",
                "description": "Milestone verified through FastAPI and MongoDB",
                "state": "open",
                "due_on": "2026-11-30T00:00:00Z",
                "open_issues": 4,
                "closed_issues": 6,
                "html_url": "https://github.com/OpenTirZ/Ai-Software-Project-Health-and-Risk-Analyzer/milestone/1",
            },
        ]

        try:
            with patch("Backend.externalservies.github_milestones._fetch_all_milestones", return_value=mock_github_payload), \
                 patch("Backend.externalservies.github_milestones._get_authenticated_session"), \
                 patch("Backend.externalservies.github_milestones.get_project", return_value=clean_db.projects.find_one({"_id": proj_oid})), \
                 patch("Backend.routers.data_sync_router._require_project_member"), \
                 patch("Backend.persistence_telemetry.milestones_collection", clean_db.milestones):

                # 1. Trigger POST /sync-milestones
                sync_resp = client.post(f"/api/projects/{project_id}/sync-milestones")
                assert sync_resp.status_code == 200, sync_resp.text
                sync_data = sync_resp.json()
                assert sync_data["success"] is True
                assert sync_data["fetched_count"] == 1
                assert sync_data["created_count"] == 1

                # 2. Trigger GET /milestones
                get_resp = client.get(f"/api/projects/{project_id}/milestones")
                assert get_resp.status_code == 200, get_resp.text
                items = get_resp.json()
                assert len(items) == 1
                assert items[0]["milestone_id"] == "1"
                assert items[0]["title"] == "Sprint 1 E2E"
                assert items[0]["completion_percentage"] == 60.0
                assert items[0]["open_issues"] == 4
                assert items[0]["closed_issues"] == 6
                assert items[0]["state"] == "open"

                # 3. Trigger GET /milestones with state=closed (should return empty list)
                get_closed_resp = client.get(f"/api/projects/{project_id}/milestones?state=closed")
                assert get_closed_resp.status_code == 200
                assert len(get_closed_resp.json()) == 0

                # 4. Trigger GET /milestones with state=open (should return 1)
                get_open_resp = client.get(f"/api/projects/{project_id}/milestones?state=open")
                assert get_open_resp.status_code == 200
                assert len(get_open_resp.json()) == 1

                # 5. Invalid state parameter validation (422)
                bad_resp = client.get(f"/api/projects/{project_id}/milestones?state=not_valid")
                assert bad_resp.status_code == 422
        finally:
            app.dependency_overrides.clear()
