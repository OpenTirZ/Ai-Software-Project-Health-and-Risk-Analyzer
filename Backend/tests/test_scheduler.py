"""
Unit and Integration Tests for Report Scheduler and Delivery Dispatcher.
-------------------------------------------------------------------------
Tests:
  1. TriggerType and schedule due evaluation (Daily, Weekly, End-of-Sprint)
  2. Delivery Dispatcher:
     - Dashboard delivery (database publishing)
     - Email delivery (skipped without recipients/SMTP, success with adapter, failed with error)
     - Slack delivery (skipped without webhook, success with HTTP 200, failed with HTTP error/network error)
     - Unsupported destination error recording
  3. Database recording of delivery attempt outcomes, timestamps, and error codes
  4. generate_scheduled_report orchestration:
     - Non-existent project handling
     - Valid project telemetry synthesis and multi-destination dispatch
  5. FastAPI BackgroundTasks integration
  6. ReportScheduler class operations (create schedule, list schedules, run_pending, trigger_now)
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import BackgroundTasks

# Mock MongoClient before importing Backend modules to prevent real network calls
_mock_client = MagicMock()
_mock_client.admin.command.return_value = {"ok": 1}
_mock_db = MagicMock()
_mock_client.__getitem__.return_value = _mock_db

with patch("pymongo.MongoClient", return_value=_mock_client):
    from Backend.reporting.delivery_dispatcher import (
        DeliveryDestination,
        DeliveryDispatcher,
        DeliveryErrorCode,
        DeliveryStatus,
        build_report_email_content,
        build_slack_blocks,
        dispatch_report,
        get_delivery_attempts,
        record_delivery_attempt,
    )
    from Backend.reporting.scheduler import (
        ReportScheduler,
        TriggerType,
        check_end_of_sprint_due,
        create_or_update_schedule,
        generate_scheduled_report,
        get_schedule,
        is_schedule_due,
        list_schedules,
        schedule_report_background,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_report():
    return {
        "_id": ObjectId("6afafe69b10c4d6cd579fccf"),
        "id": "6afafe69b10c4d6cd579fccf",
        "projectId": ObjectId("6ace71fbf6fde718d1bcbf8a"),
        "project_id": "6ace71fbf6fde718d1bcbf8a",
        "projectName": "Test Project",
        "project_name": "Test Project",
        "status": "Good",
        "healthScore": 92.5,
        "summaryStatement": "Project is in healthy condition with steady commit activity.",
        "activeFlags": [
            {
                "id": "flag_aging_pr",
                "type": "bottleneck",
                "severity": "medium",
                "message": "1 pull request open > 48h.",
            }
        ],
        "flagsCount": {"total": 1, "high": 0, "medium": 1, "low": 0},
    }


# ---------------------------------------------------------------------------
# Test Group 1: Message Formatting
# ---------------------------------------------------------------------------

class TestMessageFormatting:
    def test_email_content_formatting(self, sample_report):
        subject, plain, html = build_report_email_content(sample_report)
        assert "Test Project" in subject
        assert "Good" in subject
        assert "92.5/100" in subject
        assert "Executive Summary:" in plain
        assert "Active Risk Flags: 1" in plain
        assert "<html" in html
        assert "Test Project" in html

    def test_slack_block_formatting(self, sample_report):
        payload = build_slack_blocks(sample_report)
        assert "text" in payload
        assert "blocks" in payload
        assert len(payload["blocks"]) >= 3
        assert payload["blocks"][0]["type"] == "header"
        assert "Test Project" in payload["blocks"][0]["text"]["text"]


# ---------------------------------------------------------------------------
# Test Group 2: Delivery Dispatcher Outcomes & Database Recording
# ---------------------------------------------------------------------------

class TestDeliveryDispatcher:
    @patch("Backend.reporting.delivery_dispatcher.reports_collection")
    @patch("Backend.reporting.delivery_dispatcher.delivery_attempts_collection")
    def test_record_delivery_attempt(self, mock_attempts, mock_reports):
        mock_attempts.insert_one.return_value = MagicMock(inserted_id=ObjectId("6afb00000000000000000001"))
        attempt_id = record_delivery_attempt({
            "report_id": "6afafe69b10c4d6cd579fccf",
            "project_id": "6ace71fbf6fde718d1bcbf8a",
            "destination": "dashboard",
            "status": DeliveryStatus.SUCCESS.value,
            "error_code": None,
            "error_message": None,
        })
        assert attempt_id == "6afb00000000000000000001"
        assert mock_attempts.insert_one.called
        assert mock_reports.update_one.called

    @patch("Backend.reporting.delivery_dispatcher.delivery_attempts_collection")
    def test_get_delivery_attempts(self, mock_attempts):
        mock_attempts.find.return_value.sort.return_value.limit.return_value = [
            {
                "_id": ObjectId("6afb00000000000000000001"),
                "reportId": ObjectId("6afafe69b10c4d6cd579fccf"),
                "projectId": ObjectId("6ace71fbf6fde718d1bcbf8a"),
                "destination": "dashboard",
                "status": "success",
                "attemptedAt": datetime.now(timezone.utc),
            }
        ]
        history = get_delivery_attempts(project_id="6ace71fbf6fde718d1bcbf8a")
        assert len(history) == 1
        assert history[0]["destination"] == "dashboard"
        assert history[0]["status"] == "success"

    @patch("Backend.reporting.delivery_dispatcher.record_delivery_attempt", return_value="att_1")
    @patch("Backend.reporting.delivery_dispatcher.reports_collection")
    def test_dispatch_to_dashboard_success(self, mock_reports, mock_record, sample_report):
        dispatcher = DeliveryDispatcher()
        outcomes = dispatcher.dispatch(sample_report, destinations=["dashboard"])
        assert "dashboard" in outcomes
        assert outcomes["dashboard"]["status"] == DeliveryStatus.SUCCESS.value
        assert outcomes["dashboard"]["error_code"] is None

    @patch("Backend.reporting.delivery_dispatcher.record_delivery_attempt", return_value="att_2")
    def test_dispatch_to_email_skipped_without_recipients(self, mock_record, sample_report):
        dispatcher = DeliveryDispatcher()
        outcomes = dispatcher.dispatch(sample_report, destinations=["email"], project_config={})
        assert outcomes["email"]["status"] == DeliveryStatus.SKIPPED.value
        assert outcomes["email"]["error_code"] == DeliveryErrorCode.NO_RECIPIENTS.value

    @patch("Backend.reporting.delivery_dispatcher.record_delivery_attempt", return_value="att_3")
    def test_dispatch_to_email_skipped_without_smtp_config(self, mock_record, sample_report, monkeypatch):
        monkeypatch.delenv("SMTP_HOST", raising=False)
        dispatcher = DeliveryDispatcher()
        outcomes = dispatcher.dispatch(
            sample_report,
            destinations=["email"],
            project_config={"email_recipients": ["dev@example.com"]},
        )
        assert outcomes["email"]["status"] == DeliveryStatus.SKIPPED.value
        assert outcomes["email"]["error_code"] == DeliveryErrorCode.SMTP_NOT_CONFIGURED.value

    @patch("Backend.reporting.delivery_dispatcher.record_delivery_attempt", return_value="att_4")
    def test_dispatch_to_email_custom_adapter_success(self, mock_record, sample_report):
        mock_sender = MagicMock(return_value=True)
        dispatcher = DeliveryDispatcher(email_sender=mock_sender)
        outcomes = dispatcher.dispatch(
            sample_report,
            destinations=["email"],
            project_config={"email_recipients": ["team@example.com"]},
        )
        assert outcomes["email"]["status"] == DeliveryStatus.SUCCESS.value
        assert outcomes["email"]["error_code"] is None
        mock_sender.assert_called_once()

    @patch("Backend.reporting.delivery_dispatcher.record_delivery_attempt", return_value="att_5")
    def test_dispatch_to_email_custom_adapter_failure(self, mock_record, sample_report):
        mock_sender = MagicMock(side_effect=Exception("Connection timed out"))
        dispatcher = DeliveryDispatcher(email_sender=mock_sender)
        outcomes = dispatcher.dispatch(
            sample_report,
            destinations=["email"],
            project_config={"email_recipients": ["team@example.com"]},
        )
        assert outcomes["email"]["status"] == DeliveryStatus.FAILED.value
        assert outcomes["email"]["error_code"] == DeliveryErrorCode.SMTP_FAILURE.value

    @patch("Backend.reporting.delivery_dispatcher.record_delivery_attempt", return_value="att_6")
    def test_dispatch_to_slack_skipped_without_webhook(self, mock_record, sample_report, monkeypatch):
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
        dispatcher = DeliveryDispatcher()
        outcomes = dispatcher.dispatch(sample_report, destinations=["slack"], project_config={})
        assert outcomes["slack"]["status"] == DeliveryStatus.SKIPPED.value
        assert outcomes["slack"]["error_code"] == DeliveryErrorCode.NO_SLACK_WEBHOOK.value

    @patch("Backend.reporting.delivery_dispatcher.record_delivery_attempt", return_value="att_7")
    def test_dispatch_to_slack_custom_http_poster_success(self, mock_record, sample_report):
        mock_poster = MagicMock(return_value=(200, "ok"))
        dispatcher = DeliveryDispatcher(http_poster=mock_poster)
        outcomes = dispatcher.dispatch(
            sample_report,
            destinations=["slack"],
            project_config={"slack_webhook_url": "https://hooks.slack.com/services/XYZ"},
        )
        assert outcomes["slack"]["status"] == DeliveryStatus.SUCCESS.value
        assert outcomes["slack"]["error_code"] is None
        mock_poster.assert_called_once()

    @patch("Backend.reporting.delivery_dispatcher.record_delivery_attempt", return_value="att_8")
    def test_dispatch_to_slack_custom_http_poster_failure(self, mock_record, sample_report):
        mock_poster = MagicMock(return_value=(500, "internal server error"))
        dispatcher = DeliveryDispatcher(http_poster=mock_poster)
        outcomes = dispatcher.dispatch(
            sample_report,
            destinations=["slack"],
            project_config={"slack_webhook_url": "https://hooks.slack.com/services/XYZ"},
        )
        assert outcomes["slack"]["status"] == DeliveryStatus.FAILED.value
        assert "ERR_SLACK_HTTP_ERROR_500" in outcomes["slack"]["error_code"]

    @patch("Backend.reporting.delivery_dispatcher.record_delivery_attempt", return_value="att_9")
    def test_dispatch_unsupported_destination(self, mock_record, sample_report):
        dispatcher = DeliveryDispatcher()
        outcomes = dispatcher.dispatch(sample_report, destinations=["unknown_dest"])
        assert "unknown_dest" in outcomes
        assert outcomes["unknown_dest"]["status"] == DeliveryStatus.FAILED.value
        assert outcomes["unknown_dest"]["error_code"] == DeliveryErrorCode.UNSUPPORTED_DESTINATION.value


# ---------------------------------------------------------------------------
# Test Group 3: Schedule Due Evaluation (Daily, Weekly, End-of-Sprint)
# ---------------------------------------------------------------------------

class TestScheduleDueEvaluation:
    def test_daily_trigger_due_when_never_run(self):
        sched = {
            "triggerType": "daily",
            "enabled": True,
            "lastRunAt": None,
            "config": {"hourUtc": 8, "minuteUtc": 0},
        }
        assert is_schedule_due(sched, now=datetime(2026, 11, 17, 9, 0, tzinfo=timezone.utc)) is True

    def test_daily_trigger_not_due_if_already_run_today(self):
        today = datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc)
        sched = {
            "triggerType": "daily",
            "enabled": True,
            "lastRunAt": datetime(2026, 11, 17, 8, 5, tzinfo=timezone.utc),
            "config": {"hourUtc": 8, "minuteUtc": 0},
        }
        assert is_schedule_due(sched, now=today) is False

    def test_daily_trigger_due_when_run_yesterday_and_hour_reached(self):
        now = datetime(2026, 11, 17, 8, 30, tzinfo=timezone.utc)
        yesterday = datetime(2026, 11, 16, 8, 30, tzinfo=timezone.utc)
        sched = {
            "triggerType": "daily",
            "enabled": True,
            "lastRunAt": yesterday,
            "config": {"hourUtc": 8, "minuteUtc": 0},
        }
        assert is_schedule_due(sched, now=now) is True

    def test_daily_trigger_not_due_when_hour_not_reached(self):
        now = datetime(2026, 11, 17, 6, 30, tzinfo=timezone.utc)
        yesterday = datetime(2026, 11, 16, 8, 30, tzinfo=timezone.utc)
        sched = {
            "triggerType": "daily",
            "enabled": True,
            "lastRunAt": yesterday,
            "config": {"hourUtc": 8, "minuteUtc": 0},
        }
        assert is_schedule_due(sched, now=now) is False

    def test_weekly_trigger_due_evaluation(self):
        # 2026-11-16 is a Monday (weekday 0)
        monday_noon = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
        tuesday_noon = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)

        sched = {
            "triggerType": "weekly",
            "enabled": True,
            "lastRunAt": None,
            "config": {"dayOfWeek": 0, "hourUtc": 8},
        }
        # Due on Monday
        assert is_schedule_due(sched, now=monday_noon) is True
        # Not due on Tuesday
        assert is_schedule_due(sched, now=tuesday_noon) is False

    @patch("Backend.reporting.scheduler.milestones_collection")
    @patch("Backend.reporting.scheduler.sprints_collection")
    def test_end_of_sprint_trigger_due_when_milestone_closed(self, mock_sprints, mock_milestones):
        mock_milestones.find.return_value = [
            {
                "projectId": ObjectId("6ace71fbf6fde718d1bcbf8a"),
                "state": "closed",
                "updated_at": "2026-11-17T10:00:00Z",
            }
        ]
        mock_sprints.find.return_value = []

        due = check_end_of_sprint_due(
            project_id="6ace71fbf6fde718d1bcbf8a",
            last_run_at=datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc),
            now=datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc),
        )
        assert due is True

    @patch("Backend.reporting.scheduler.milestones_collection")
    @patch("Backend.reporting.scheduler.sprints_collection")
    def test_end_of_sprint_trigger_not_due_when_no_closed_sprint(self, mock_sprints, mock_milestones):
        mock_milestones.find.return_value = []
        mock_sprints.find.return_value = []

        due = check_end_of_sprint_due(
            project_id="6ace71fbf6fde718d1bcbf8a",
            last_run_at=datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc),
        )
        assert due is False


# ---------------------------------------------------------------------------
# Test Group 4: Orchestration and Report Generation
# ---------------------------------------------------------------------------

class TestReportOrchestration:
    @patch("Backend.reporting.scheduler.get_project", return_value=None)
    def test_generate_report_project_not_found(self, mock_get_proj):
        res = generate_scheduled_report("invalid_pid")
        assert res["success"] is False
        assert "not found" in res["error"]

    @patch("Backend.reporting.scheduler.get_project")
    @patch("Backend.reporting.scheduler.reports_collection")
    @patch("Backend.reporting.scheduler.schedules_collection")
    def test_generate_scheduled_report_success(self, mock_sched, mock_reports, mock_proj):
        mock_proj.return_value = {
            "_id": ObjectId("6ace71fbf6fde718d1bcbf8a"),
            "name": "Alpha Project",
        }
        mock_reports.insert_one.return_value = MagicMock(inserted_id=ObjectId("6afb11111111111111111111"))

        custom_dispatcher = MagicMock()
        custom_dispatcher.dispatch.return_value = {
            "dashboard": {"status": "success", "error_code": None},
        }

        res = generate_scheduled_report(
            project_id="6ace71fbf6fde718d1bcbf8a",
            trigger_type=TriggerType.DAILY,
            destinations=["dashboard"],
            dispatcher=custom_dispatcher,
            custom_generator=lambda pid: {
                "health_score": 95.0,
                "status": "Good",
                "summary_statement": "All systems nominal.",
                "active_flags": [],
            },
        )

        assert res["success"] is True
        assert res["report_id"] == "6afb11111111111111111111"
        assert res["health_score"] == 95.0
        assert res["trigger_type"] == "daily"
        custom_dispatcher.dispatch.assert_called_once()


# ---------------------------------------------------------------------------
# Test Group 5: BackgroundTasks & Scheduler Class
# ---------------------------------------------------------------------------

class TestSchedulerIntegration:
    def test_schedule_report_background_tasks(self):
        bg = BackgroundTasks()
        schedule_report_background(
            background_tasks=bg,
            project_id="6ace71fbf6fde718d1bcbf8a",
            trigger_type=TriggerType.DAILY,
            destinations=["dashboard"],
        )
        assert len(bg.tasks) == 1
        task = bg.tasks[0]
        assert task.func == generate_scheduled_report
        assert task.kwargs["project_id"] == "6ace71fbf6fde718d1bcbf8a"

    @patch("Backend.reporting.scheduler.schedules_collection")
    def test_create_and_get_schedule(self, mock_sched):
        mock_sched.find_one.return_value = {
            "_id": ObjectId("6afb22222222222222222222"),
            "projectId": ObjectId("6ace71fbf6fde718d1bcbf8a"),
            "triggerType": "weekly",
            "enabled": True,
            "destinations": ["dashboard", "slack"],
            "config": {"dayOfWeek": 0, "hourUtc": 9},
        }

        saved = create_or_update_schedule(
            project_id="6ace71fbf6fde718d1bcbf8a",
            trigger_type=TriggerType.WEEKLY,
            destinations=["dashboard", "slack"],
            config={"day_of_week": 0, "hour_utc": 9},
        )

        assert saved["triggerType"] == "weekly"
        assert "dashboard" in saved["destinations"]
        assert "slack" in saved["destinations"]

        fetched = get_schedule("6ace71fbf6fde718d1bcbf8a", TriggerType.WEEKLY)
        assert fetched is not None
        assert fetched["triggerType"] == "weekly"

    @patch("Backend.reporting.scheduler.list_schedules")
    @patch("Backend.reporting.scheduler.generate_scheduled_report")
    def test_run_pending_triggers_due_schedules(self, mock_gen, mock_list):
        mock_list.return_value = [
            {
                "projectId": "6ace71fbf6fde718d1bcbf8a",
                "triggerType": "daily",
                "enabled": True,
                "destinations": ["dashboard"],
                "lastRunAt": None,
                "config": {"hourUtc": 8},
            }
        ]
        mock_gen.return_value = {"success": True, "report_id": "rep_123"}

        scheduler = ReportScheduler()
        results = scheduler.run_pending(now=datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc))

        assert len(results) == 1
        assert results[0]["report_id"] == "rep_123"
        mock_gen.assert_called_once()
