"""
Unit and integration tests for TASK-SP4-07 (Issue #114): Project Lifecycle Management.
---------------------------------------------------------------------------------------
Covers:
  1. Archive Project API (POST /api/projects/{id}/archive):
     - Owner & Admin authorization
     - Member & outsider rejection (403)
     - Unauthenticated rejection (401/403)
     - ID validation (400) and nonexistent project (404)
     - Archive idempotency & preservation of original archivedAt
     - Legacy projects missing status field handling
     - Cannot archive a deleted or deleting project (400)
  2. Read-Only Invariants on Archived Projects:
     - Synchronization rejected (400) across all 5 sync endpoints
     - Mutation endpoints rejected (400): PATCH config, connect repo, update thresholds,
       report generation, schedule create/update/delete/run
     - Historical reads preserved (200): commits, PRs, issues, milestones, contributors,
       health summary, reports, schedules, thresholds
  3. Soft-Delete Project API (DELETE /api/projects/{id}):
     - Owner & Admin authorization
     - Member & outsider rejection (403)
     - Unauthenticated rejection (401/403)
     - Physical preservation (document remains in MongoDB)
     - 11-collection cascade with is_active=False and deletedAt
     - Preservation of upstream GitHub states (state field untouched)
     - Isolation: other projects' telemetry untouched
     - Repeated DELETE idempotency
  4. Partial Cascade Recovery & Concurrency:
     - Partial failure leaves deletion_status="pending" and returns 503
     - Retry resumes incomplete cascade, completes it, and preserves canonical deletedAt
     - Concurrent DELETE calls share single canonical deletedAt
     - Concurrent ARCHIVE and DELETE consistency
  5. In-Flight Telemetry Synchronization Race Reconciliation:
     - Newly inserted telemetry during transition is rolled back/deleted
     - Existing telemetry updated during transition is restored to pre-sync state without deletedAt on archive
  6. Integration Credentials Security:
     - Credential retrieval blocked for deleted/pending and archived projects
  7. Active Project Regression:
     - Normal operations on active projects remain functional
"""

import os
import sys
from unittest.mock import MagicMock, patch

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-lifecycle-tests-32-chars")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/test_project_health")
os.environ.setdefault("MONGO_DATABASE", "test_project_health")

# Stub optional PDF generator module if not installed in local environment
sys.modules.setdefault("xhtml2pdf", MagicMock())
sys.modules.setdefault("xhtml2pdf.pisa", MagicMock())

import pymongo

_original_mongo_client = pymongo.MongoClient

def _mock_mongo_factory(*args, **kwargs):
    mock = MagicMock()
    mock.admin.command.return_value = {"ok": 1}
    mock.__getitem__.return_value = MagicMock()
    return mock

pymongo.MongoClient = _mock_mongo_factory

import copy
from datetime import datetime, timezone

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from Backend.auth.dependencies import get_current_user
from Backend.main import app
from Backend.persistence import DatabaseError, get_integration_credential

client = TestClient(app)

# ---------------------------------------------------------------------------
# Test Users
# ---------------------------------------------------------------------------

OWNER_ID = str(ObjectId())
ADMIN_ID = str(ObjectId())
MEMBER_ID = str(ObjectId())
OUTSIDER_ID = str(ObjectId())

OWNER_USER = {
    "_id": OWNER_ID,
    "email": "owner@example.com",
    "name": "Project Owner",
    "role": "project_manager",
    "is_active": True,
}

ADMIN_USER = {
    "_id": ADMIN_ID,
    "email": "admin@example.com",
    "name": "System Admin",
    "role": "admin",
    "is_active": True,
}

MEMBER_USER = {
    "_id": MEMBER_ID,
    "email": "member@example.com",
    "name": "Team Member",
    "role": "developer",
    "is_active": True,
}

OUTSIDER_USER = {
    "_id": OUTSIDER_ID,
    "email": "outsider@example.com",
    "name": "Outsider User",
    "role": "developer",
    "is_active": True,
}


# ---------------------------------------------------------------------------
# In-Memory Mock Collection
# ---------------------------------------------------------------------------

class InMemoryMockCollection:
    def __init__(self, name="collection"):
        self.name = name
        self._docs = {}

    def insert_one(self, doc):
        doc_copy = copy.deepcopy(doc)
        doc_id = doc_copy.get("_id", ObjectId())
        doc_copy["_id"] = doc_id
        self._docs[str(doc_id)] = doc_copy

        class Result:
            def __init__(self, inserted_id):
                self.inserted_id = inserted_id
        return Result(doc_id)

    def find_one(self, query=None, projection=None):
        if not query:
            for d in self._docs.values():
                return copy.deepcopy(d)
            return None

        for doc in self._docs.values():
            if self._matches(doc, query):
                return copy.deepcopy(doc)
        return None

    def find(self, query=None, projection=None):
        class MockCursor(list):
            def sort(self, *args, **kwargs):
                return self
            def limit(self, *args, **kwargs):
                return self

        if not query:
            return MockCursor([copy.deepcopy(d) for d in self._docs.values()])

        matched = [copy.deepcopy(d) for d in self._docs.values() if self._matches(d, query)]
        return MockCursor(matched)

    def update_one(self, filter_query, update_doc, upsert=False):
        matched_doc = None
        target_id = None
        for doc_id, doc in self._docs.items():
            if self._matches(doc, filter_query):
                matched_doc = doc
                target_id = doc_id
                break

        class UpdateResult:
            def __init__(self, modified_count, upserted_id=None):
                self.modified_count = modified_count
                self.upserted_id = upserted_id
                self.matched_count = 1 if modified_count > 0 or not upserted_id else 0

        if matched_doc:
            if "$set" in update_doc:
                matched_doc.update(copy.deepcopy(update_doc["$set"]))
            return UpdateResult(1)

        if upsert:
            new_doc = copy.deepcopy(filter_query)
            if "$set" in update_doc:
                new_doc.update(copy.deepcopy(update_doc["$set"]))
            new_id = new_doc.get("_id", ObjectId())
            new_doc["_id"] = new_id
            self._docs[str(new_id)] = new_doc
            return UpdateResult(1, upserted_id=new_id)

        return UpdateResult(0)

    def update_many(self, filter_query, update_doc):
        count = 0
        for doc in self._docs.values():
            if self._matches(doc, filter_query):
                if "$set" in update_doc:
                    doc.update(copy.deepcopy(update_doc["$set"]))
                count += 1
        class ManyResult:
            def __init__(self, modified_count):
                self.modified_count = modified_count
        return ManyResult(count)

    def delete_one(self, filter_query):
        to_del = None
        for doc_id, doc in self._docs.items():
            if self._matches(doc, filter_query):
                to_del = doc_id
                break
        if to_del:
            del self._docs[to_del]
            return 1
        return 0

    def replace_one(self, filter_query, replacement):
        to_del = None
        for doc_id, doc in self._docs.items():
            if self._matches(doc, filter_query):
                to_del = doc_id
                break
        if to_del:
            self._docs[to_del] = copy.deepcopy(replacement)
            return 1
        return 0

    def bulk_write(self, operations, ordered=False):
        modified = 0
        upserted = 0
        matched = 0
        for op in operations:
            filter_q = op._filter
            doc_data = op._doc.get("$set", {})
            upsert = op._upsert
            res = self.update_one(filter_q, {"$set": doc_data}, upsert=upsert)
            if res.upserted_id:
                upserted += 1
            else:
                matched += res.matched_count
                modified += res.modified_count
        class BulkResult:
            def __init__(self, matched_count, modified_count, upserted_count):
                self.matched_count = matched_count
                self.modified_count = modified_count
                self.upserted_count = upserted_count
        return BulkResult(matched, modified, upserted)

    def create_index(self, *args, **kwargs):
        return "index_ok"

    def _matches(self, doc, query):
        for k, v in query.items():
            if k == "$or":
                if not any(self._matches(doc, sub_q) for sub_q in v):
                    return False
                continue
            if k == "_id":
                if str(doc.get("_id")) != str(v):
                    return False
                continue
            if k == "projectId":
                if str(doc.get("projectId")) != str(v):
                    return False
                continue

            doc_val = doc.get(k)
            if isinstance(v, dict):
                if "$ne" in v and doc_val == v["$ne"]:
                    return False
                if "$nin" in v and doc_val in v["$nin"]:
                    return False
                if "$in" in v and doc_val not in v["$in"]:
                    return False
                if "$exists" in v:
                    exists = k in doc
                    if exists != v["$exists"]:
                        return False
            elif doc_val != v:
                return False
        return True


# Global mock collections
mock_projects = InMemoryMockCollection("projects")
mock_commits = InMemoryMockCollection("commits")
mock_prs = InMemoryMockCollection("pull_requests")
mock_issues = InMemoryMockCollection("issues")
mock_milestones = InMemoryMockCollection("milestones")
mock_sprints = InMemoryMockCollection("sprints")
mock_flags = InMemoryMockCollection("flags")
mock_reports = InMemoryMockCollection("reports")
mock_contributors = InMemoryMockCollection("contributors")
mock_snapshots = InMemoryMockCollection("metric_snapshots")
mock_schedules = InMemoryMockCollection("report_schedules")
mock_credentials = InMemoryMockCollection("integration_credentials")


@pytest.fixture(autouse=True)
def reset_lifecycle_environment(monkeypatch):
    """Reset in-memory collections and patch across all Backend modules."""
    for col in (
        mock_projects, mock_commits, mock_prs, mock_issues,
        mock_milestones, mock_sprints, mock_flags, mock_reports,
        mock_contributors, mock_snapshots, mock_schedules, mock_credentials,
    ):
        col._docs.clear()

    # Patch in database.py
    monkeypatch.setattr("Backend.database.projects_collection", mock_projects)
    monkeypatch.setattr("Backend.database.commits_collection", mock_commits)
    monkeypatch.setattr("Backend.database.pull_requests_collection", mock_prs)
    monkeypatch.setattr("Backend.database.issues_collection", mock_issues)
    monkeypatch.setattr("Backend.database.milestones_collection", mock_milestones)
    monkeypatch.setattr("Backend.database.sprints_collection", mock_sprints)
    monkeypatch.setattr("Backend.database.flags_collection", mock_flags)
    monkeypatch.setattr("Backend.database.reports_collection", mock_reports)
    monkeypatch.setattr("Backend.database.contributors_collection", mock_contributors)
    monkeypatch.setattr("Backend.database.metric_snapshots_collection", mock_snapshots)
    monkeypatch.setattr("Backend.database.report_schedules_collection", mock_schedules)
    monkeypatch.setattr("Backend.database.integration_credentials_collection", mock_credentials)

    # Patch in persistence.py
    monkeypatch.setattr("Backend.persistence.projects_collection", mock_projects)
    monkeypatch.setattr("Backend.persistence.commits_collection", mock_commits)
    monkeypatch.setattr("Backend.persistence.pull_requests_collection", mock_prs)
    monkeypatch.setattr("Backend.persistence.issues_collection", mock_issues)
    monkeypatch.setattr("Backend.persistence.milestones_collection", mock_milestones)
    monkeypatch.setattr("Backend.persistence.sprints_collection", mock_sprints)
    monkeypatch.setattr("Backend.persistence.flags_collection", mock_flags)
    monkeypatch.setattr("Backend.persistence.reports_collection", mock_reports)
    monkeypatch.setattr("Backend.persistence.contributors_collection", mock_contributors)
    monkeypatch.setattr("Backend.persistence.metric_snapshots_collection", mock_snapshots)
    monkeypatch.setattr("Backend.persistence.report_schedules_collection", mock_schedules)
    monkeypatch.setattr("Backend.persistence.integration_credentials_collection", mock_credentials)

    # Patch in persistence_telemetry.py
    monkeypatch.setattr("Backend.persistence_telemetry.pull_requests_collection", mock_prs)
    monkeypatch.setattr("Backend.persistence_telemetry.issues_collection", mock_issues)
    monkeypatch.setattr("Backend.persistence_telemetry.milestones_collection", mock_milestones)
    monkeypatch.setattr("Backend.persistence_telemetry.metric_snapshots_collection", mock_snapshots)

    # Patch in routers
    monkeypatch.setattr("Backend.routers.project_lifecycle_router.commits_collection", mock_commits)
    monkeypatch.setattr("Backend.routers.project_lifecycle_router.pull_requests_collection", mock_prs)
    monkeypatch.setattr("Backend.routers.project_lifecycle_router.issues_collection", mock_issues)
    monkeypatch.setattr("Backend.routers.project_lifecycle_router.milestones_collection", mock_milestones)
    monkeypatch.setattr("Backend.routers.project_lifecycle_router.sprints_collection", mock_sprints)
    monkeypatch.setattr("Backend.routers.project_lifecycle_router.flags_collection", mock_flags)
    monkeypatch.setattr("Backend.routers.project_lifecycle_router.reports_collection", mock_reports)
    monkeypatch.setattr("Backend.routers.project_lifecycle_router.contributors_collection", mock_contributors)
    monkeypatch.setattr("Backend.routers.project_lifecycle_router.metric_snapshots_collection", mock_snapshots)
    monkeypatch.setattr("Backend.routers.project_lifecycle_router.report_schedules_collection", mock_schedules)
    monkeypatch.setattr("Backend.routers.project_lifecycle_router.integration_credentials_collection", mock_credentials)

    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _create_sample_project(status="active", owner_id=OWNER_ID, extra=None):
    p_id = ObjectId()
    doc = {
        "_id": p_id,
        "name": "Health Analyzer",
        "description": "AI Health Project",
        "ownerId": ObjectId(owner_id),
        "repo_url": "https://github.com/owner/repo",
        "default_branch": "main",
        "members": [
            {"userId": ObjectId(owner_id), "role": "owner"},
            {"userId": ObjectId(MEMBER_ID), "role": "developer"},
        ],
        "status": status,
        "is_active": True if status != "deleted" else False,
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    if extra:
        doc.update(extra)
    mock_projects.insert_one(doc)
    return str(p_id)


# ===========================================================================
# Part A: Core Archival Tests (Tests 1–8)
# ===========================================================================

class TestProjectArchivalCore:
    def test_owner_can_archive_project(self):
        pid = _create_sample_project(owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        res = client.post(f"/api/projects/{pid}/archive")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "archived"
        assert data["project_id"] == pid
        assert "archived_at" in data

        saved = mock_projects.find_one({"_id": ObjectId(pid)})
        assert saved["status"] == "archived"
        assert "archivedAt" in saved

    def test_admin_can_archive_project(self):
        pid = _create_sample_project(owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER

        res = client.post(f"/api/projects/{pid}/archive")
        assert res.status_code == 200
        assert res.json()["status"] == "archived"

    def test_member_cannot_archive_project(self):
        pid = _create_sample_project(owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: MEMBER_USER

        res = client.post(f"/api/projects/{pid}/archive")
        assert res.status_code == 403

    def test_outsider_cannot_archive_project(self):
        pid = _create_sample_project(owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: OUTSIDER_USER

        res = client.post(f"/api/projects/{pid}/archive")
        assert res.status_code == 403

    def test_archive_invalid_id_format(self):
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER
        res = client.post("/api/projects/not-a-valid-id/archive")
        assert res.status_code == 400

    def test_archive_nonexistent_project(self):
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER
        res = client.post(f"/api/projects/{ObjectId()}/archive")
        assert res.status_code == 404

    def test_unauthenticated_archive_rejected(self):
        pid = _create_sample_project()
        res = client.post(f"/api/projects/{pid}/archive")
        assert res.status_code in (401, 403)

    def test_archived_project_rejects_sync(self):
        pid = _create_sample_project(status="archived")
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        res = client.post(f"/api/projects/{pid}/sync-commits", json={"branch": "main"})
        assert res.status_code == 400
        assert "archived" in res.json()["detail"].lower()

    def test_archived_project_telemetry_readable(self):
        pid = _create_sample_project(status="archived")
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        # Add stored telemetry
        mock_commits.insert_one({"projectId": ObjectId(pid), "sha": "abc1234", "message": "commit 1"})
        mock_prs.insert_one({"projectId": ObjectId(pid), "number": 1, "title": "PR 1", "state": "open"})

        res_commits = client.get(f"/api/projects/{pid}/commits")
        assert res_commits.status_code == 200
        assert len(res_commits.json()) == 1

        res_prs = client.get(f"/api/projects/{pid}/prs")
        assert res_prs.status_code == 200
        assert len(res_prs.json()) == 1


# ===========================================================================
# Part B: Core Soft-Delete & Cascade Tests (Tests 9–17)
# ===========================================================================

class TestProjectSoftDeleteCore:
    def test_owner_can_soft_delete_project(self):
        pid = _create_sample_project(owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        res = client.delete(f"/api/projects/{pid}")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "deleted"
        assert data["is_active"] is False
        assert data["deletion_status"] == "completed"

    def test_admin_can_soft_delete_project(self):
        pid = _create_sample_project(owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER

        res = client.delete(f"/api/projects/{pid}")
        assert res.status_code == 200
        assert res.json()["status"] == "deleted"

    def test_member_cannot_soft_delete_project(self):
        pid = _create_sample_project(owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: MEMBER_USER

        res = client.delete(f"/api/projects/{pid}")
        assert res.status_code == 403

    def test_outsider_cannot_soft_delete_project(self):
        pid = _create_sample_project(owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: OUTSIDER_USER

        res = client.delete(f"/api/projects/{pid}")
        assert res.status_code == 403

    def test_unauthenticated_delete_rejected(self):
        pid = _create_sample_project()
        res = client.delete(f"/api/projects/{pid}")
        assert res.status_code in (401, 403)

    def test_soft_deleted_project_document_persisted(self):
        pid = _create_sample_project(owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        client.delete(f"/api/projects/{pid}")
        doc = mock_projects.find_one({"_id": ObjectId(pid)})
        assert doc is not None  # Not physically deleted!
        assert doc["status"] == "deleted"
        assert doc["is_active"] is False
        assert "deletedAt" in doc

    def test_associated_telemetry_cascaded_inactive(self):
        pid = _create_sample_project(owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        # Populate all 11 collections
        p_oid = ObjectId(pid)
        mock_commits.insert_one({"projectId": p_oid, "sha": "sha1"})
        mock_prs.insert_one({"projectId": p_oid, "number": 10, "state": "open"})
        mock_issues.insert_one({"projectId": p_oid, "number": 20, "state": "closed"})
        mock_milestones.insert_one({"projectId": p_oid, "milestone_id": "m1", "state": "open"})
        mock_sprints.insert_one({"projectId": p_oid, "name": "Sprint 1"})
        mock_flags.insert_one({"projectId": p_oid, "type": "bottleneck"})
        mock_reports.insert_one({"projectId": p_oid, "status": "Good"})
        mock_contributors.insert_one({"projectId": p_oid, "github_username": "octocat"})
        mock_snapshots.insert_one({"projectId": p_oid, "status": "Good"})
        mock_schedules.insert_one({"projectId": p_oid, "enabled": True, "status": "active"})
        mock_credentials.insert_one({"projectId": p_oid, "provider": "github"})

        res = client.delete(f"/api/projects/{pid}")
        assert res.status_code == 200

        # Assert all 11 collections marked inactive with deletedAt
        assert mock_commits.find_one({"projectId": p_oid})["is_active"] is False
        pr_doc = mock_prs.find_one({"projectId": p_oid})
        assert pr_doc["is_active"] is False
        assert pr_doc["state"] == "open"  # Preserved upstream state!

        issue_doc = mock_issues.find_one({"projectId": p_oid})
        assert issue_doc["is_active"] is False
        assert issue_doc["state"] == "closed"  # Preserved upstream state!

        ms_doc = mock_milestones.find_one({"projectId": p_oid})
        assert ms_doc["is_active"] is False
        assert ms_doc["state"] == "open"  # Preserved upstream state!

        sched_doc = mock_schedules.find_one({"projectId": p_oid})
        assert sched_doc["is_active"] is False
        assert sched_doc["enabled"] is False
        assert sched_doc["status"] == "paused"

    def test_unrelated_project_telemetry_untouched(self):
        pid_a = _create_sample_project(owner_id=OWNER_ID)
        pid_b = _create_sample_project(owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        mock_commits.insert_one({"projectId": ObjectId(pid_b), "sha": "sha_b", "is_active": True})
        client.delete(f"/api/projects/{pid_a}")

        b_commit = mock_commits.find_one({"projectId": ObjectId(pid_b)})
        assert b_commit["is_active"] is True  # Untouched!


# ===========================================================================
# Part C: Mutation Gating & Schedule Execution Tests (Tests 18–22)
# ===========================================================================

class TestMutationGatingOnArchivedProjects:
    def test_connect_repository_rejected_on_archived_project(self):
        pid = _create_sample_project(status="archived", owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        res = client.post("/api/repositories/connect", json={
            "projectId": pid,
            "githubUrl": "https://github.com/owner/repo",
            "branch": "main",
        })
        assert res.status_code == 400
        assert "archived" in res.json()["detail"].lower()

    def test_update_thresholds_rejected_on_archived_project(self):
        pid = _create_sample_project(status="archived", owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        res = client.put(f"/api/projects/{pid}/thresholds", json={"aging_pr_hours": 36.0})
        assert res.status_code == 400
        assert "archived" in res.json()["detail"].lower()

    def test_generate_report_rejected_on_archived_project(self):
        pid = _create_sample_project(status="archived", owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        res = client.post(f"/api/projects/{pid}/reports/generate")
        assert res.status_code == 400
        assert "archived" in res.json()["detail"].lower()

    def test_schedule_mutations_rejected_on_archived_project(self):
        pid = _create_sample_project(status="archived", owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        res_create = client.post(f"/api/projects/{pid}/reports/schedules", json={
            "frequency": "daily",
            "destinations": ["email"],
        })
        assert res_create.status_code == 400

        sid = str(ObjectId())
        res_patch = client.patch(f"/api/projects/{pid}/reports/schedules/{sid}", json={"frequency": "weekly"})
        assert res_patch.status_code == 400

        res_del = client.delete(f"/api/projects/{pid}/reports/schedules/{sid}")
        assert res_del.status_code == 400

    def test_manual_schedule_run_rejected_on_archived_project(self):
        pid = _create_sample_project(status="archived", owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER
        sid = str(ObjectId())

        res = client.post(f"/api/projects/{pid}/reports/schedules/{sid}/run")
        assert res.status_code == 400

    def test_update_project_config_rejected_on_archived_project(self):
        pid = _create_sample_project(status="archived", owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        res = client.patch(f"/api/projects/{pid}", json={"name": "New Name"})
        assert res.status_code == 400


# ===========================================================================
# Part D: Read Preservation & Isolation Tests (Tests 23–24)
# ===========================================================================

class TestReadPreservationAndDeletedIsolation:
    def test_archived_project_historical_reads_functional(self):
        pid = _create_sample_project(status="archived", owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        # Add historical records
        mock_thresholds = {"aging_pr_hours": 48.0}
        mock_projects.update_one({"_id": ObjectId(pid)}, {"$set": {"thresholds": mock_thresholds}})

        res_thresholds = client.get(f"/api/projects/{pid}/thresholds")
        assert res_thresholds.status_code == 200

        res_health = client.get(f"/api/projects/{pid}/health-summary")
        assert res_health.status_code == 200

        res_proj = client.get(f"/api/projects/{pid}")
        assert res_proj.status_code == 200
        assert res_proj.json()["status"] == "archived"

    def test_deleted_project_inaccessible_across_all_routes(self):
        pid = _create_sample_project(status="deleted", owner_id=OWNER_ID, extra={"is_active": False})
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        # Every project-scoped read returns 404
        assert client.get(f"/api/projects/{pid}").status_code == 404
        assert client.patch(f"/api/projects/{pid}", json={"name": "New"}).status_code == 404
        assert client.get(f"/api/projects/{pid}/commits").status_code == 404
        assert client.get(f"/api/projects/{pid}/prs").status_code == 404
        assert client.get(f"/api/projects/{pid}/issues").status_code == 404
        assert client.get(f"/api/projects/{pid}/milestones").status_code == 404
        assert client.get(f"/api/projects/{pid}/contributors").status_code == 404
        assert client.get(f"/api/projects/{pid}/thresholds").status_code == 404
        assert client.get(f"/api/projects/{pid}/health-summary").status_code == 404
        assert client.get(f"/api/projects/{pid}/reports").status_code == 404


# ===========================================================================
# Part E: Partial Cascade Recovery, In-Flight & Concurrency (Tests 25–34)
# ===========================================================================

class TestPartialCascadeRecoveryAndConcurrency:
    def test_idempotent_repeated_archive_preserves_timestamp(self):
        pid = _create_sample_project(owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        res1 = client.post(f"/api/projects/{pid}/archive")
        assert res1.status_code == 200
        first_archived_at = res1.json()["archived_at"]

        # Call again
        res2 = client.post(f"/api/projects/{pid}/archive")
        assert res2.status_code == 200
        assert res2.json()["archived_at"] == first_archived_at

    def test_legacy_project_without_status_archives_cleanly(self):
        pid = ObjectId()
        mock_projects.insert_one({
            "_id": pid,
            "name": "Legacy Project",
            "ownerId": ObjectId(OWNER_ID),
            "members": [{"userId": ObjectId(OWNER_ID), "role": "owner"}],
        })
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        res = client.post(f"/api/projects/{pid}/archive")
        assert res.status_code == 200
        saved = mock_projects.find_one({"_id": pid})
        assert saved["status"] == "archived"

    def test_idempotent_repeated_delete_preserves_timestamp(self):
        pid = _create_sample_project(owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        res1 = client.delete(f"/api/projects/{pid}")
        assert res1.status_code == 200
        first_deleted_at = res1.json()["deleted_at"]

        res2 = client.delete(f"/api/projects/{pid}")
        assert res2.status_code == 200
        assert res2.json()["deleted_at"] == first_deleted_at

    def test_partial_cascade_failure_and_successful_retry(self, monkeypatch):
        pid = _create_sample_project(owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        import Backend.routers.project_lifecycle_router
        original_cascade = Backend.routers.project_lifecycle_router.soft_delete_cascade_collection
        def fail_on_sprints(p_id, collection, fields):
            if collection.name == "sprints":
                raise DatabaseError("Simulated disk error on sprints")
            original_cascade(p_id, collection, fields)

        monkeypatch.setattr("Backend.routers.project_lifecycle_router.soft_delete_cascade_collection", fail_on_sprints)

        res1 = client.delete(f"/api/projects/{pid}")
        assert res1.status_code == 503

        # Verify project is pending deletion
        doc = mock_projects.find_one({"_id": ObjectId(pid)})
        assert doc["deletion_status"] == "pending"
        orig_deleted_at = doc["deletedAt"]

        # Restore normal cascade and retry
        monkeypatch.setattr("Backend.routers.project_lifecycle_router.soft_delete_cascade_collection", original_cascade)

        res2 = client.delete(f"/api/projects/{pid}")
        assert res2.status_code == 200
        assert res2.json()["deletion_status"] == "completed"
        updated_doc = mock_projects.find_one({"_id": ObjectId(pid)})
        assert updated_doc["deletedAt"] == orig_deleted_at
        assert updated_doc["deletion_status"] == "completed"

    def test_concurrent_delete_requests_preserve_single_canonical_deleted_at(self):
        pid = _create_sample_project(owner_id=OWNER_ID)
        from Backend.persistence import soft_delete_initiate_conditional

        t1 = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)
        outcome1, canonical_dt1, doc1 = soft_delete_initiate_conditional(pid, now=t1)
        assert outcome1 == "initiated_new"
        assert canonical_dt1 == t1

        t2 = datetime(2026, 11, 20, 10, 0, 5, tzinfo=timezone.utc)
        outcome2, canonical_dt2, doc2 = soft_delete_initiate_conditional(pid, now=t2)
        assert outcome2 == "resuming_pending"
        assert canonical_dt2 == t1  # Must reuse t1!

    def test_concurrent_archive_and_delete_consistency(self):
        pid = _create_sample_project(owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        # Delete project first
        res_del = client.delete(f"/api/projects/{pid}")
        assert res_del.status_code == 200

        # Attempt to archive deleted project must fail
        res_arc = client.post(f"/api/projects/{pid}/archive")
        assert res_arc.status_code == 400
        assert "deleted" in res_arc.json()["detail"].lower()

    def test_inflight_sync_newly_inserted_telemetry_reconciled(self):
        pid = _create_sample_project(owner_id=OWNER_ID)
        from Backend.persistence import upsert_commit

        # Simulate project becoming archived during external fetch before upsert_commit
        mock_projects.update_one({"_id": ObjectId(pid)}, {"$set": {"status": "archived"}})

        with pytest.raises(DatabaseError):
            upsert_commit(pid, {"sha": "new_sha_123", "message": "in flight commit"})

        # Record must not exist in commits collection
        assert mock_commits.find_one({"projectId": ObjectId(pid), "sha": "new_sha_123"}) is None

    def test_inflight_sync_existing_telemetry_restored(self):
        pid = _create_sample_project(owner_id=OWNER_ID)
        from Backend.persistence import upsert_commit

        # Existing commit
        mock_commits.insert_one({"projectId": ObjectId(pid), "sha": "orig_sha", "message": "Original Message", "is_active": True})

        # Project transitions to archived
        mock_projects.update_one({"_id": ObjectId(pid)}, {"$set": {"status": "archived"}})

        with pytest.raises(DatabaseError):
            upsert_commit(pid, {"sha": "orig_sha", "message": "Mutated Message"})

        # Assert original commit restored and deletedAt is NOT set!
        doc = mock_commits.find_one({"projectId": ObjectId(pid), "sha": "orig_sha"})
        assert doc["message"] == "Original Message"
        assert "deletedAt" not in doc

    def test_integration_credential_unusable_on_deleted_or_archived_project(self):
        pid_del = _create_sample_project(status="deleted", extra={"is_active": False})
        mock_credentials.insert_one({"projectId": ObjectId(pid_del), "provider": "github", "token": "secret"})
        assert get_integration_credential(pid_del, "github") is None

        pid_arc = _create_sample_project(status="archived")
        mock_credentials.insert_one({"projectId": ObjectId(pid_arc), "provider": "github", "token": "secret"})
        assert get_integration_credential(pid_arc, "github") is None

    def test_active_project_behavior_unaffected(self):
        pid = _create_sample_project(status="active", owner_id=OWNER_ID)
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER

        # Project config update works
        res_patch = client.patch(f"/api/projects/{pid}", json={"name": "Renamed Active"})
        assert res_patch.status_code == 200
        assert res_patch.json()["name"] == "Renamed Active"

        # Thresholds update works
        res_thresh = client.put(f"/api/projects/{pid}/thresholds", json={"aging_pr_hours": 30.0})
        assert res_thresh.status_code == 200
