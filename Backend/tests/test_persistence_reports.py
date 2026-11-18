"""
Unit Tests for the Reports & Schedules Persistence Layer.
---------------------------------------------------------
Backend/persistence_reports.py — reports collection and report_schedules
collection (report generation pipeline persistence).

Covers:
  1. Report persistence   (save, read, newest-first listing, latest, delete,
                          count, DatabaseError on driver failures)
  2. Schedule persistence (create with validation, read, filter by status,
                          partial update re-validation, run stamping, delete,
                          due-schedule selection, DatabaseError)
  3. Input validation     (invalid frequency/destinations/status rejected
                          before any database call)
"""

from datetime import datetime, timedelta, timezone
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
    from Backend.persistence import DatabaseError
    from Backend.persistence_reports import (
        count_project_reports,
        create_report_schedule,
        delete_report,
        delete_report_schedule,
        get_due_schedules,
        get_latest_project_report,
        get_project_reports,
        get_project_schedules,
        get_report,
        get_schedule,
        record_schedule_run,
        save_report,
        update_report_schedule,
    )


SAMPLE_PROJECT_ID = str(ObjectId())
NOW = datetime(2026, 11, 4, 12, 0, 0, tzinfo=timezone.utc)


def _sample_report(**overrides):
    """Build a minimal valid pipeline report payload."""
    report = {
        "generated_at": "2026-11-04T12:00:00+00:00",
        "pipeline_version": "2.0.0",
        "executive_summary": "Composite health is 72/100 (needs_attention).",
        "project_health": {
            "score": 72,
            "status": "needs_attention",
            "risk_factors": [
                {
                    "risk_id": "stale_issue_backlog",
                    "severity": "high",
                    "evidence": "2 open issue(s) stale.",
                    "recommendation": "Triage stale issues.",
                }
            ],
        },
        "recommendations": ["Triage stale issues.", "Assign reviewers."],
        "contributor_report": {"metrics": {"contributor_count": 4}},
        "commit_report": {"metrics": {"commit_count": 12}},
        "pull_request_report": {"metrics": {"total_prs": 6}},
        "issue_report": {"metrics": {"total_issues": 6}},
        "sprint_report": {"metrics": {"total_milestones": 4}},
        "llm": {"used": True, "raw_prompt_tokens": 1533},
    }
    report.update(overrides)
    return report


# ===========================================================================
# 1. Report persistence
# ===========================================================================

class TestReportPersistence:
    @patch("Backend.persistence_reports.reports_collection")
    def test_save_report_inserts_document(self, mock_col):
        """save_report stores projectId/generatedAt/summary/risks/recommendations/metricsSnapshot."""
        inserted_id = ObjectId()
        mock_col.insert_one.return_value = MagicMock(inserted_id=inserted_id)

        result = save_report(_sample_report(), SAMPLE_PROJECT_ID)

        assert result == str(inserted_id)
        mock_col.insert_one.assert_called_once()
        document = mock_col.insert_one.call_args[0][0]
        assert document["projectId"] == ObjectId(SAMPLE_PROJECT_ID)
        assert document["summary"] == "Composite health is 72/100 (needs_attention)."
        assert document["risks"][0]["risk_id"] == "stale_issue_backlog"
        assert document["recommendations"] == ["Triage stale issues.", "Assign reviewers."]
        assert document["metricsSnapshot"]["project_health"]["score"] == 72
        assert document["rawPromptTokens"] == 1533

    @patch("Backend.persistence_reports.reports_collection")
    def test_save_report_explicit_tokens_override(self, mock_col):
        """An explicit raw_prompt_tokens argument wins over the LLM status block."""
        mock_col.insert_one.return_value = MagicMock(inserted_id=ObjectId())

        save_report(_sample_report(), SAMPLE_PROJECT_ID, raw_prompt_tokens=999)

        document = mock_col.insert_one.call_args[0][0]
        assert document["rawPromptTokens"] == 999

    @patch("Backend.persistence_reports.reports_collection")
    def test_save_report_missing_fields_raises(self, mock_col):
        """Reports without generated_at/summary/metrics are rejected before the DB call."""
        with pytest.raises(ValueError, match="generated_at"):
            save_report({"executive_summary": "x", "project_health": {}, "contributor_report": {"metrics": {}}}, SAMPLE_PROJECT_ID)
        mock_col.insert_one.assert_not_called()

    @patch("Backend.persistence_reports.reports_collection")
    def test_save_report_not_a_dict_raises(self, mock_col):
        with pytest.raises(ValueError, match="must be a JSON object"):
            save_report("not-a-dict", SAMPLE_PROJECT_ID)
        mock_col.insert_one.assert_not_called()

    @patch("Backend.persistence_reports.reports_collection")
    def test_get_report_returns_serialized(self, mock_col):
        """get_report serializes ObjectIds and datetimes to JSON-safe values."""
        report_oid = ObjectId()
        mock_col.find_one.return_value = {
            "_id": report_oid,
            "projectId": ObjectId(SAMPLE_PROJECT_ID),
            "generatedAt": NOW,
            "summary": "s",
        }

        result = get_report(str(report_oid))

        assert result["_id"] == str(report_oid)
        assert result["projectId"] == SAMPLE_PROJECT_ID
        assert result["generatedAt"] == NOW.isoformat()

    @patch("Backend.persistence_reports.reports_collection")
    def test_get_project_reports_newest_first(self, mock_col):
        """Listing sorts by generatedAt descending and applies the limit."""
        newer = {"_id": ObjectId(), "generatedAt": "2026-11-04", "summary": "new"}
        older = {"_id": ObjectId(), "generatedAt": "2026-11-01", "summary": "old"}
        cursor = MagicMock()
        cursor.sort.return_value.limit.return_value = iter([newer, older])
        mock_col.find.return_value = cursor

        results = get_project_reports(SAMPLE_PROJECT_ID, limit=2)

        assert [r["summary"] for r in results] == ["new", "old"]
        mock_col.find.assert_called_once_with({"projectId": ObjectId(SAMPLE_PROJECT_ID)})
        cursor.sort.assert_called_once_with([("generatedAt", -1)])
        cursor.sort.return_value.limit.assert_called_once_with(2)

    @patch("Backend.persistence_reports.reports_collection")
    def test_get_latest_project_report_returns_first(self, mock_col):
        newest = {"_id": ObjectId(), "summary": "newest"}
        cursor = MagicMock()
        cursor.sort.return_value.limit.return_value = iter([newest])
        mock_col.find.return_value = cursor

        assert get_latest_project_report(SAMPLE_PROJECT_ID)["summary"] == "newest"

    @patch("Backend.persistence_reports.reports_collection")
    def test_delete_report_true_when_removed(self, mock_col):
        mock_col.delete_one.return_value = MagicMock(deleted_count=1)
        assert delete_report(str(ObjectId())) is True

    @patch("Backend.persistence_reports.reports_collection")
    def test_delete_report_false_when_missing(self, mock_col):
        mock_col.delete_one.return_value = MagicMock(deleted_count=0)
        assert delete_report(str(ObjectId())) is False

    @patch("Backend.persistence_reports.reports_collection")
    def test_count_project_reports(self, mock_col):
        mock_col.count_documents.return_value = 7
        assert count_project_reports(SAMPLE_PROJECT_ID) == 7
        mock_col.count_documents.assert_called_once_with({"projectId": ObjectId(SAMPLE_PROJECT_ID)})

    @pytest.mark.parametrize(
        "function_name,args",
        [
            ("get_report", ("not-an-object-id",)),
            ("delete_report", ("not-an-object-id",)),
            ("save_report", (None, "not-an-object-id")),
        ],
    )
    def test_invalid_object_id_raises(self, function_name, args):
        with pytest.raises(ValueError, match="Invalid ObjectId"):
            if function_name == "save_report":
                save_report(_sample_report(), args[1])
            else:
                {"get_report": get_report, "delete_report": delete_report}[function_name](*args)

    @patch("Backend.persistence_reports.reports_collection")
    def test_save_report_database_error(self, mock_col):
        mock_col.insert_one.side_effect = PyMongoError("boom")
        with pytest.raises(DatabaseError, match="saving the report"):
            save_report(_sample_report(), SAMPLE_PROJECT_ID)

    @patch("Backend.persistence_reports.reports_collection")
    def test_get_project_reports_database_error(self, mock_col):
        mock_col.find.side_effect = PyMongoError("boom")
        with pytest.raises(DatabaseError, match="retrieving reports"):
            get_project_reports(SAMPLE_PROJECT_ID)


# ===========================================================================
# 2. Schedule persistence
# ===========================================================================

class TestSchedulePersistence:
    @patch("Backend.persistence_reports.report_schedules_collection")
    def test_create_schedule_inserts_validated_document(self, mock_col):
        inserted_id = ObjectId()
        mock_col.insert_one.return_value = MagicMock(inserted_id=inserted_id)

        result = create_report_schedule(
            SAMPLE_PROJECT_ID,
            {"frequency": "weekly", "destinations": ["email", "slack"]},
        )

        assert result == str(inserted_id)
        document = mock_col.insert_one.call_args[0][0]
        assert document["projectId"] == ObjectId(SAMPLE_PROJECT_ID)
        assert document["frequency"] == "weekly"
        assert document["destinations"] == ["email", "slack"]
        assert document["status"] == "active"
        assert document["lastRun"] is None
        assert "createdAt" in document

    def test_create_schedule_invalid_frequency_rejected(self):
        with pytest.raises(ValueError, match="frequency"):
            create_report_schedule(
                SAMPLE_PROJECT_ID,
                {"frequency": "hourly", "destinations": ["email"]},
            )

    def test_create_schedule_invalid_destination_rejected(self):
        with pytest.raises(ValueError, match="destinations"):
            create_report_schedule(
                SAMPLE_PROJECT_ID,
                {"frequency": "daily", "destinations": ["sms"]},
            )

    def test_create_schedule_empty_destinations_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            create_report_schedule(
                SAMPLE_PROJECT_ID,
                {"frequency": "daily", "destinations": []},
            )

    @patch("Backend.persistence_reports.report_schedules_collection")
    def test_create_schedule_database_error(self, mock_col):
        mock_col.insert_one.side_effect = PyMongoError("boom")
        with pytest.raises(DatabaseError, match="creating the schedule"):
            create_report_schedule(
                SAMPLE_PROJECT_ID,
                {"frequency": "daily", "destinations": ["email"]},
            )

    @patch("Backend.persistence_reports.report_schedules_collection")
    def test_get_schedule_serialized(self, mock_col):
        schedule_oid = ObjectId()
        mock_col.find_one.return_value = {
            "_id": schedule_oid,
            "projectId": ObjectId(SAMPLE_PROJECT_ID),
            "frequency": "daily",
            "destinations": ["email"],
            "lastRun": NOW,
            "status": "active",
        }

        result = get_schedule(str(schedule_oid))

        assert result["_id"] == str(schedule_oid)
        assert result["lastRun"] == NOW.isoformat()

    @patch("Backend.persistence_reports.report_schedules_collection")
    def test_get_project_schedules_filters_by_status(self, mock_col):
        cursor = MagicMock()
        cursor.sort.return_value = iter([])
        mock_col.find.return_value = cursor

        get_project_schedules(SAMPLE_PROJECT_ID, status="active")

        mock_col.find.assert_called_once_with(
            {"projectId": ObjectId(SAMPLE_PROJECT_ID), "status": "active"}
        )

    def test_get_project_schedules_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="status"):
            get_project_schedules(SAMPLE_PROJECT_ID, status="archived")

    @patch("Backend.persistence_reports.report_schedules_collection")
    def test_update_schedule_merges_and_revalidates(self, mock_col):
        """Partial update re-validates merged fields against the stored document."""
        schedule_oid = ObjectId()
        mock_col.find_one.return_value = {
            "_id": schedule_oid,
            "frequency": "weekly",
            "destinations": ["email"],
            "status": "active",
        }
        mock_col.update_one.return_value = MagicMock(modified_count=1)

        updated = update_report_schedule(str(schedule_oid), {"status": "paused"})

        assert updated is True
        update_doc = mock_col.update_one.call_args[0][1]["$set"]
        assert update_doc["status"] == "paused"
        assert "updatedAt" in update_doc

    @patch("Backend.persistence_reports.report_schedules_collection")
    def test_update_schedule_rejects_invalid_frequency(self, mock_col):
        mock_col.find_one.return_value = {
            "_id": ObjectId(),
            "frequency": "weekly",
            "destinations": ["email"],
            "status": "active",
        }
        with pytest.raises(ValueError, match="frequency"):
            update_report_schedule(str(ObjectId()), {"frequency": "hourly"})

    @patch("Backend.persistence_reports.report_schedules_collection")
    def test_update_schedule_missing_document_returns_false(self, mock_col):
        mock_col.find_one.return_value = None
        assert update_report_schedule(str(ObjectId()), {"status": "paused"}) is False

    def test_update_schedule_no_editable_fields_rejected(self):
        with pytest.raises(ValueError, match="No editable fields"):
            update_report_schedule(str(ObjectId()), {"hacker_field": "x"})

    @patch("Backend.persistence_reports.report_schedules_collection")
    def test_update_schedule_ignores_unknown_fields(self, mock_col):
        """Unknown keys are never written to the database."""
        mock_col.find_one.return_value = {
            "_id": ObjectId(),
            "frequency": "weekly",
            "destinations": ["email"],
            "status": "active",
        }
        mock_col.update_one.return_value = MagicMock(modified_count=1)

        update_report_schedule(str(ObjectId()), {"status": "paused", "projectId": "evil"})

        update_doc = mock_col.update_one.call_args[0][1]["$set"]
        assert "projectId" not in update_doc
        assert update_doc["status"] == "paused"

    @patch("Backend.persistence_reports.report_schedules_collection")
    def test_record_schedule_run_stamps_lastrun_and_status(self, mock_col):
        mock_col.update_one.return_value = MagicMock(modified_count=1)

        stamped = record_schedule_run(str(ObjectId()), status="failed", ran_at=NOW)

        assert stamped is True
        update_doc = mock_col.update_one.call_args[0][1]["$set"]
        assert update_doc["lastRun"] == NOW
        assert update_doc["status"] == "failed"

    def test_record_schedule_run_invalid_status(self):
        with pytest.raises(ValueError, match="status"):
            record_schedule_run(str(ObjectId()), status="exploded")

    @patch("Backend.persistence_reports.report_schedules_collection")
    def test_delete_schedule_true_when_removed(self, mock_col):
        mock_col.delete_one.return_value = MagicMock(deleted_count=1)
        assert delete_report_schedule(str(ObjectId())) is True

    @patch("Backend.persistence_reports.report_schedules_collection")
    def test_delete_schedule_database_error(self, mock_col):
        mock_col.delete_one.side_effect = PyMongoError("boom")
        with pytest.raises(DatabaseError, match="deleting the schedule"):
            delete_report_schedule(str(ObjectId()))


# ===========================================================================
# 3. Due-schedule selection (scheduler loop)
# ===========================================================================

class TestDueSchedules:
    @patch("Backend.persistence_reports.report_schedules_collection")
    def test_due_when_nextrun_in_past(self, mock_col):
        mock_col.find.return_value = iter(
            [
                {
                    "frequency": "daily",
                    "status": "active",
                    "nextRunAt": NOW - timedelta(hours=1),
                    "lastRun": NOW - timedelta(days=2),
                }
            ]
        )

        due = get_due_schedules(now=NOW)

        assert len(due) == 1

    @patch("Backend.persistence_reports.report_schedules_collection")
    def test_not_due_when_nextrun_in_future(self, mock_col):
        mock_col.find.return_value = iter(
            [
                {
                    "frequency": "daily",
                    "status": "active",
                    "nextRunAt": NOW + timedelta(hours=1),
                }
            ]
        )

        assert get_due_schedules(now=NOW) == []

    @patch("Backend.persistence_reports.report_schedules_collection")
    def test_due_when_no_lastrun_and_no_nextrun(self, mock_col):
        """A fresh schedule without lastRun/nextRunAt is immediately due."""
        mock_col.find.return_value = iter(
            [{"frequency": "weekly", "status": "active"}]
        )

        due = get_due_schedules(now=NOW)

        assert len(due) == 1

    @patch("Backend.persistence_reports.report_schedules_collection")
    def test_not_due_when_lastrun_recent(self, mock_col):
        mock_col.find.return_value = iter(
            [
                {
                    "frequency": "weekly",
                    "status": "active",
                    "lastRun": NOW - timedelta(hours=2),
                }
            ]
        )

        assert get_due_schedules(now=NOW) == []

    @patch("Backend.persistence_reports.report_schedules_collection")
    def test_due_when_lastrun_older_than_frequency(self, mock_col):
        mock_col.find.return_value = iter(
            [
                {
                    "frequency": "daily",
                    "status": "active",
                    "lastRun": NOW - timedelta(hours=25),
                }
            ]
        )

        due = get_due_schedules(now=NOW)

        assert len(due) == 1

    @patch("Backend.persistence_reports.report_schedules_collection")
    def test_paused_schedules_not_selected(self, mock_col):
        """Only the requested statuses are queried."""
        cursor = MagicMock()
        cursor.__iter__ = MagicMock(return_value=iter([]))
        mock_col.find.return_value = cursor

        get_due_schedules(now=NOW)

        mock_col.find.assert_called_once_with({"status": {"$in": ["active"]}})

    @patch("Backend.persistence_reports.report_schedules_collection")
    def test_database_error_wrapped(self, mock_col):
        mock_col.find.side_effect = PyMongoError("boom")
        with pytest.raises(DatabaseError, match="due schedules"):
            get_due_schedules(now=NOW)
