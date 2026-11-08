"""
Unit and Integration Tests for Telemetry Persistence Layer and Indexing.
------------------------------------------------------------------------
Task: TASK-SP2-03 (Tirth Patel - Database Architect & LangGraph AI Engineer)

Tests cover:
  1. Pull Request persistence (upsert, read, filter by state, find by number, DatabaseError)
  2. Issue persistence (upsert, read, filter by state, find by number, DatabaseError)
  3. Milestone persistence (upsert, read, filter by state, DatabaseError)
  4. Metric Snapshots persistence (upsert, read historical, DatabaseError)
  5. Compound index registration in ensure_indexes()
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId
from pymongo.errors import PyMongoError

# Mock MongoClient before importing Backend modules to prevent real network calls
_mock_client = MagicMock()
_mock_client.admin.command.return_value = {"ok": 1}
_mock_db = MagicMock()
_mock_client.__getitem__.return_value = _mock_db

with patch("pymongo.MongoClient", return_value=_mock_client):
    from Backend.database import (
        ensure_indexes,
        issues_collection,
        metric_snapshots_collection,
        milestones_collection,
        pull_requests_collection,
    )
    from Backend.persistence import DatabaseError
    from Backend.persistence_telemetry import (
        get_issue_by_number,
        get_project_issues,
        get_project_metric_snapshots,
        get_project_milestones,
        get_project_prs,
        get_pull_request_by_number,
        upsert_issue,
        upsert_metric_snapshot,
        upsert_milestone,
        upsert_pull_request,
    )


SAMPLE_PROJECT_ID = str(ObjectId())
NOW = datetime(2026, 11, 4, 12, 0, 0, tzinfo=timezone.utc)


# ===========================================================================
# 1. Pull Request Persistence Tests
# ===========================================================================

class TestPullRequestPersistence:
    @patch("Backend.persistence_telemetry.pull_requests_collection")
    def test_upsert_pr_creates_new(self, mock_col):
        """First upsert for a PR creates a new record and returns upserted ID."""
        new_id = ObjectId()
        mock_col.update_one.return_value = MagicMock(upserted_id=new_id)

        pr_data = {
            "number": 42,
            "title": "Add telemetry API",
            "state": "open",
            "author": "tirth",
            "open_duration_hours": 12.5,
        }

        result = upsert_pull_request(SAMPLE_PROJECT_ID, pr_data)
        assert result == str(new_id)

        mock_col.update_one.assert_called_once()
        call_args = mock_col.update_one.call_args
        filter_query = call_args[0][0]
        update_doc = call_args[0][1]["$set"]

        assert filter_query == {"projectId": ObjectId(SAMPLE_PROJECT_ID), "number": 42}
        assert update_doc["title"] == "Add telemetry API"
        assert update_doc["state"] == "open"
        assert update_doc["open_duration_hours"] == 12.5

    @patch("Backend.persistence_telemetry.pull_requests_collection")
    def test_upsert_pr_updates_existing(self, mock_col):
        """Subsequent upsert for existing PR updates record and returns its _id."""
        existing_id = ObjectId()
        mock_col.update_one.return_value = MagicMock(upserted_id=None)
        mock_col.find_one.return_value = {"_id": existing_id, "number": 42}

        pr_data = {"number": 42, "title": "Updated Title", "state": "closed"}
        result = upsert_pull_request(SAMPLE_PROJECT_ID, pr_data)

        assert result == str(existing_id)
        mock_col.find_one.assert_called_once()

    def test_upsert_pr_missing_number_raises_error(self):
        """PR data without number must raise ValueError."""
        with pytest.raises(ValueError, match="must contain a 'number'"):
            upsert_pull_request(SAMPLE_PROJECT_ID, {"title": "Missing number"})

    @patch("Backend.persistence_telemetry.pull_requests_collection")
    def test_get_project_prs_all(self, mock_col):
        """get_project_prs returns sorted list of serialized PRs."""
        mock_docs = [
            {"_id": ObjectId(), "projectId": ObjectId(SAMPLE_PROJECT_ID), "number": 2, "state": "open"},
            {"_id": ObjectId(), "projectId": ObjectId(SAMPLE_PROJECT_ID), "number": 1, "state": "closed"},
        ]
        cursor_mock = MagicMock()
        cursor_mock.sort.return_value = mock_docs
        mock_col.find.return_value = cursor_mock

        results = get_project_prs(SAMPLE_PROJECT_ID)
        assert len(results) == 2
        assert results[0]["number"] == 2
        mock_col.find.assert_called_once_with({"projectId": ObjectId(SAMPLE_PROJECT_ID)})

    @patch("Backend.persistence_telemetry.pull_requests_collection")
    def test_get_project_prs_filtered_by_state(self, mock_col):
        """get_project_prs respects state filter."""
        cursor_mock = MagicMock()
        cursor_mock.sort.return_value = []
        mock_col.find.return_value = cursor_mock

        get_project_prs(SAMPLE_PROJECT_ID, state="open")
        mock_col.find.assert_called_once_with({
            "projectId": ObjectId(SAMPLE_PROJECT_ID),
            "state": "open",
        })

    @patch("Backend.persistence_telemetry.pull_requests_collection")
    def test_get_pull_request_by_number(self, mock_col):
        """get_pull_request_by_number finds PR by project and number."""
        doc_id = ObjectId()
        mock_col.find_one.return_value = {
            "_id": doc_id,
            "projectId": ObjectId(SAMPLE_PROJECT_ID),
            "number": 10,
            "title": "Auth fix",
        }

        pr = get_pull_request_by_number(SAMPLE_PROJECT_ID, 10)
        assert pr["number"] == 10
        assert pr["_id"] == str(doc_id)
        mock_col.find_one.assert_called_once_with({
            "projectId": ObjectId(SAMPLE_PROJECT_ID),
            "number": 10,
        })

    @patch("Backend.persistence_telemetry.pull_requests_collection")
    def test_pr_pymongo_error_raises_database_error(self, mock_col):
        """PyMongoError during PR operations wraps into DatabaseError."""
        mock_col.update_one.side_effect = PyMongoError("Connection timeout")
        with pytest.raises(DatabaseError, match="pull request upsert"):
            upsert_pull_request(SAMPLE_PROJECT_ID, {"number": 1})


# ===========================================================================
# 2. Issue Persistence Tests
# ===========================================================================

class TestIssuePersistence:
    @patch("Backend.persistence_telemetry.issues_collection")
    def test_upsert_issue_creates_new(self, mock_col):
        """First upsert for an issue creates a new record."""
        new_id = ObjectId()
        mock_col.update_one.return_value = MagicMock(upserted_id=new_id)

        issue_data = {
            "number": 15,
            "title": "Memory leak investigation",
            "state": "open",
            "labels": ["bug", "priority-high"],
            "comments_count": 4,
        }

        result = upsert_issue(SAMPLE_PROJECT_ID, issue_data)
        assert result == str(new_id)

        mock_col.update_one.assert_called_once()
        filter_query = mock_col.update_one.call_args[0][0]
        update_doc = mock_col.update_one.call_args[0][1]["$set"]

        assert filter_query == {"projectId": ObjectId(SAMPLE_PROJECT_ID), "number": 15}
        assert update_doc["title"] == "Memory leak investigation"
        assert update_doc["comments_count"] == 4
        assert update_doc["labels"] == ["bug", "priority-high"]

    @patch("Backend.persistence_telemetry.issues_collection")
    def test_upsert_issue_updates_existing(self, mock_col):
        """Subsequent upsert updates existing issue."""
        existing_id = ObjectId()
        mock_col.update_one.return_value = MagicMock(upserted_id=None)
        mock_col.find_one.return_value = {"_id": existing_id, "number": 15}

        result = upsert_issue(SAMPLE_PROJECT_ID, {"number": 15, "state": "closed"})
        assert result == str(existing_id)

    def test_upsert_issue_missing_number_raises_error(self):
        """Issue data without number must raise ValueError."""
        with pytest.raises(ValueError, match="must contain a 'number'"):
            upsert_issue(SAMPLE_PROJECT_ID, {"title": "Missing number"})

    @patch("Backend.persistence_telemetry.issues_collection")
    def test_get_project_issues_all_and_filtered(self, mock_col):
        """get_project_issues queries all and state-filtered."""
        cursor_mock = MagicMock()
        cursor_mock.sort.return_value = [
            {"_id": ObjectId(), "projectId": ObjectId(SAMPLE_PROJECT_ID), "number": 1, "state": "open"}
        ]
        mock_col.find.return_value = cursor_mock

        res = get_project_issues(SAMPLE_PROJECT_ID, state="open")
        assert len(res) == 1
        mock_col.find.assert_called_once_with({
            "projectId": ObjectId(SAMPLE_PROJECT_ID),
            "state": "open",
        })

    @patch("Backend.persistence_telemetry.issues_collection")
    def test_get_issue_by_number(self, mock_col):
        """get_issue_by_number returns serialized issue."""
        doc_id = ObjectId()
        mock_col.find_one.return_value = {"_id": doc_id, "number": 7}

        issue = get_issue_by_number(SAMPLE_PROJECT_ID, 7)
        assert issue["_id"] == str(doc_id)
        assert issue["number"] == 7

    @patch("Backend.persistence_telemetry.issues_collection")
    def test_issue_pymongo_error_raises_database_error(self, mock_col):
        """PyMongoError wraps into DatabaseError."""
        mock_col.update_one.side_effect = PyMongoError("Write error")
        with pytest.raises(DatabaseError, match="issue upsert"):
            upsert_issue(SAMPLE_PROJECT_ID, {"number": 1})


# ===========================================================================
# 3. Milestone Persistence Tests
# ===========================================================================

class TestMilestonePersistence:
    @patch("Backend.persistence_telemetry.milestones_collection")
    def test_upsert_milestone_creates_new(self, mock_col):
        """First upsert for a milestone creates a record with (projectId, milestone_id)."""
        new_id = ObjectId()
        mock_col.update_one.return_value = MagicMock(upserted_id=new_id)

        milestone_data = {
            "milestone_id": "m-v1.0",
            "title": "Release v1.0",
            "state": "open",
            "open_issues": 5,
            "closed_issues": 10,
        }

        result = upsert_milestone(SAMPLE_PROJECT_ID, milestone_data)
        assert result == str(new_id)

        mock_col.update_one.assert_called_once()
        filter_query = mock_col.update_one.call_args[0][0]
        update_doc = mock_col.update_one.call_args[0][1]["$set"]

        assert filter_query == {"projectId": ObjectId(SAMPLE_PROJECT_ID), "milestone_id": "m-v1.0"}
        assert update_doc["open_issues"] == 5
        assert update_doc["closed_issues"] == 10

    @patch("Backend.persistence_telemetry.milestones_collection")
    def test_upsert_milestone_updates_existing(self, mock_col):
        """Subsequent upsert updates existing milestone."""
        existing_id = ObjectId()
        mock_col.update_one.return_value = MagicMock(upserted_id=None)
        mock_col.find_one.return_value = {"_id": existing_id, "milestone_id": "1"}

        result = upsert_milestone(SAMPLE_PROJECT_ID, {"number": 1, "title": "Updated Milestone"})
        assert result == str(existing_id)

    def test_upsert_milestone_missing_id_raises_error(self):
        """Milestone without milestone_id, id, or number raises ValueError."""
        with pytest.raises(ValueError, match="must contain 'milestone_id'"):
            upsert_milestone(SAMPLE_PROJECT_ID, {"title": "Missing id"})

    @patch("Backend.persistence_telemetry.milestones_collection")
    def test_get_project_milestones(self, mock_col):
        """get_project_milestones returns sorted list of milestones."""
        cursor_mock = MagicMock()
        cursor_mock.sort.return_value = [
            {"_id": ObjectId(), "milestone_id": "1", "title": "Sprint 1", "state": "open"}
        ]
        mock_col.find.return_value = cursor_mock

        milestones = get_project_milestones(SAMPLE_PROJECT_ID)
        assert len(milestones) == 1
        assert milestones[0]["title"] == "Sprint 1"

    @patch("Backend.persistence_telemetry.milestones_collection")
    def test_milestone_pymongo_error_raises_database_error(self, mock_col):
        """PyMongoError wraps into DatabaseError."""
        mock_col.update_one.side_effect = PyMongoError("Timeout")
        with pytest.raises(DatabaseError, match="milestone upsert"):
            upsert_milestone(SAMPLE_PROJECT_ID, {"milestone_id": "1"})


# ===========================================================================
# 4. Metric Snapshot Persistence Tests
# ===========================================================================

class TestMetricSnapshotPersistence:
    @patch("Backend.persistence_telemetry.metric_snapshots_collection")
    def test_upsert_metric_snapshot(self, mock_col):
        """Stores historical calculation snapshot indexed by (projectId, calculatedAt)."""
        new_id = ObjectId()
        mock_col.update_one.return_value = MagicMock(upserted_id=new_id)

        snapshot_data = {
            "calculatedAt": NOW,
            "health_score": 85.0,
            "status": "Good",
            "indicators": {"bottlenecks": 90.0, "workload": 80.0},
        }

        res = upsert_metric_snapshot(SAMPLE_PROJECT_ID, snapshot_data)
        assert res == str(new_id)
        mock_col.update_one.assert_called_once()
        filter_query = mock_col.update_one.call_args[0][0]
        assert filter_query == {"projectId": ObjectId(SAMPLE_PROJECT_ID), "calculatedAt": NOW}

    @patch("Backend.persistence_telemetry.metric_snapshots_collection")
    def test_get_project_metric_snapshots(self, mock_col):
        """Retrieves snapshots sorted by calculatedAt descending with limit."""
        cursor_mock = MagicMock()
        cursor_mock.sort.return_value = cursor_mock
        cursor_mock.limit.return_value = [
            {"_id": ObjectId(), "health_score": 88.0, "status": "Good"}
        ]
        mock_col.find.return_value = cursor_mock

        res = get_project_metric_snapshots(SAMPLE_PROJECT_ID, limit=5)
        assert len(res) == 1
        assert res[0]["health_score"] == 88.0

    @patch("Backend.persistence_telemetry.metric_snapshots_collection")
    def test_snapshot_pymongo_error_raises_database_error(self, mock_col):
        """PyMongoError wraps into DatabaseError."""
        mock_col.update_one.side_effect = PyMongoError("Snapshot failure")
        with pytest.raises(DatabaseError, match="metric snapshot"):
            upsert_metric_snapshot(SAMPLE_PROJECT_ID, {})


# ===========================================================================
# 5. Compound Index Verification Tests
# ===========================================================================

class TestCompoundIndexRegistration:
    @patch("Backend.database.pull_requests_collection")
    @patch("Backend.database.issues_collection")
    @patch("Backend.database.milestones_collection")
    @patch("Backend.database.metric_snapshots_collection")
    @patch("Backend.database.commits_collection")
    @patch("Backend.database.contributors_collection")
    @patch("Backend.database.projects_collection")
    def test_ensure_indexes_creates_all_telemetry_compound_indexes(
        self,
        mock_projects,
        mock_contribs,
        mock_commits,
        mock_snapshots,
        mock_milestones,
        mock_issues,
        mock_prs,
    ):
        """ensure_indexes() must register compound unique keys for all telemetry collections."""
        ensure_indexes()

        # Check pull_requests compound unique index (projectId, number)
        mock_prs.create_index.assert_called_once_with(
            [("projectId", 1), ("number", 1)],
            unique=True,
            background=True,
        )

        # Check issues compound unique index (projectId, number)
        mock_issues.create_index.assert_called_once_with(
            [("projectId", 1), ("number", 1)],
            unique=True,
            background=True,
        )

        # Check milestones compound unique index (projectId, milestone_id)
        mock_milestones.create_index.assert_called_once_with(
            [("projectId", 1), ("milestone_id", 1)],
            unique=True,
            background=True,
        )

        # Check metric_snapshots compound index (projectId, calculatedAt)
        mock_snapshots.create_index.assert_called_once_with(
            [("projectId", 1), ("calculatedAt", 1)],
            background=True,
        )

