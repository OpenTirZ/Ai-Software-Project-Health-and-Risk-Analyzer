"""
Report Scheduler & Orchestration Engine.
-----------------------------------------
Automated report scheduling engine supporting:
- Recurring triggers: Daily, Weekly, and End-of-Sprint.
- Report synthesis: Fetches project telemetry, computes composite health and risk flags.
- Multi-destination dispatch: Dashboard, Email, and Slack via DeliveryDispatcher.
- Execution options:
    1. FastAPI BackgroundTasks (in-process asynchronous execution)
    2. AsyncReportScheduler (in-process polling loop)
    3. APScheduler (if installed in runtime environment)
    4. Standalone worker daemon (separate background process for Docker)
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from bson import ObjectId
from fastapi import BackgroundTasks

from Backend.analysis.health_summary import build_health_summary
from Backend.database import (
    db,
    milestones_collection,
    projects_collection,
    reports_collection,
    sprints_collection,
)
from Backend.persistence import (
    get_project,
    get_project_commits,
    get_project_contributors,
    get_project_issues,
    get_project_pull_requests,
    get_project_sprints,
    to_object_id,
)
from Backend.reporting.delivery_dispatcher import (
    DeliveryDestination,
    DeliveryDispatcher,
    dispatch_report,
)

logger = logging.getLogger(__name__)

schedules_collection = db["report_schedules"]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TriggerType(str, Enum):
    """Supported recurring and on-demand report schedule triggers."""
    DAILY = "daily"
    WEEKLY = "weekly"
    END_OF_SPRINT = "end_of_sprint"
    MANUAL = "manual"


# ---------------------------------------------------------------------------
# Core Report Generation and Dispatching
# ---------------------------------------------------------------------------

def generate_scheduled_report(
    project_id: str,
    trigger_type: Union[TriggerType, str] = TriggerType.DAILY,
    destinations: Optional[List[str]] = None,
    dispatcher: Optional[DeliveryDispatcher] = None,
    custom_generator: Optional[Callable[[str], Dict[str, Any]]] = None,
    custom_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Synthesize project health report and dispatch it to configured destinations.
    Records delivery attempt outcomes, timestamps, and error codes in database.
    """
    clean_project_id = str(project_id)
    normalized_trigger = (
        trigger_type.value if isinstance(trigger_type, TriggerType) else str(trigger_type).lower()
    )

    # 1. Fetch project and verify existence
    project = get_project(clean_project_id)
    if not project:
        logger.error("Cannot generate report: Project %s not found.", clean_project_id)
        return {
            "success": False,
            "project_id": clean_project_id,
            "error": f"Project {clean_project_id} not found",
            "deliveries": {},
        }

    # 2. Determine destinations and project delivery configurations
    if destinations is None:
        schedule = get_schedule(clean_project_id, normalized_trigger)
        if schedule and schedule.get("destinations"):
            destinations = schedule["destinations"]
        else:
            destinations = [DeliveryDestination.DASHBOARD.value]

    delivery_config = custom_config or {}
    schedule = get_schedule(clean_project_id, normalized_trigger)
    if schedule:
        delivery_config = {**schedule.get("config", {}), **delivery_config}

    # 3. Generate report data (using custom generator if provided or default health_summary)
    now_utc = datetime.now(timezone.utc)
    if custom_generator:
        report_data = custom_generator(clean_project_id)
    else:
        try:
            commits = get_project_commits(clean_project_id) or []
            contributors = get_project_contributors(clean_project_id) or []
            prs = get_project_pull_requests(clean_project_id) or []
            issues = get_project_issues(clean_project_id) or []
            sprints = get_project_sprints(clean_project_id) or []

            summary = build_health_summary(
                project=project,
                commits=commits,
                contributors=contributors,
                pull_requests=prs,
                issues=issues,
                sprints=sprints,
                now=now_utc,
            )
            report_data = summary
        except Exception as exc:
            logger.exception("Failed computing health summary for project %s: %s", clean_project_id, exc)
            report_data = {
                "project_id": clean_project_id,
                "project_name": project.get("name", "Project"),
                "health_score": None,
                "status": "Insufficient Data",
                "summary_statement": f"Report generation failed: {exc}",
                "active_flags": [],
                "flags_count": {"total": 0, "high": 0, "medium": 0, "low": 0},
            }

    # 4. Construct persistent report document
    report_doc = {
        "projectId": to_object_id(clean_project_id),
        "projectName": project.get("name") or report_data.get("project_name") or "Unnamed Project",
        "triggerType": normalized_trigger,
        "status": report_data.get("status", "Good"),
        "healthScore": report_data.get("health_score"),
        "summaryStatement": (
            report_data.get("summary_statement")
            or report_data.get("executive_summary")
            or "Automated scheduled health assessment."
        ),
        "activeFlags": report_data.get("active_flags", []),
        "flagsCount": report_data.get("flags_count", {"total": 0, "high": 0, "medium": 0, "low": 0}),
        "destinations": [d.lower() for d in destinations],
        "generatedAt": now_utc,
        "dashboardPublished": DeliveryDestination.DASHBOARD.value in [d.lower() for d in destinations],
        "deliveryAttempts": [],
        "deliveryStatus": {},
    }

    try:
        insert_res = reports_collection.insert_one(report_doc)
        report_id = str(insert_res.inserted_id)
        report_doc["_id"] = insert_res.inserted_id
        report_doc["id"] = report_id
    except Exception as exc:
        logger.error("Failed to persist report document: %s", exc)
        return {
            "success": False,
            "project_id": clean_project_id,
            "error": f"Failed persisting report: {exc}",
            "deliveries": {},
        }

    # 5. Dispatch report to configured destinations
    active_dispatcher = dispatcher or DeliveryDispatcher()
    delivery_results = active_dispatcher.dispatch(
        report=report_doc,
        destinations=destinations,
        project_config=delivery_config,
    )

    # 6. Update schedule last_run_at timestamp
    try:
        schedules_collection.update_one(
            {"projectId": to_object_id(clean_project_id), "triggerType": normalized_trigger},
            {"$set": {"lastRunAt": now_utc, "updatedAt": now_utc}},
        )
    except Exception as exc:
        logger.warning("Could not update lastRunAt on schedule: %s", exc)

    logger.info(
        "Generated scheduled report %s for project %s (%s). Deliveries: %s",
        report_id, clean_project_id, normalized_trigger, list(delivery_results.keys()),
    )

    return {
        "success": True,
        "report_id": report_id,
        "project_id": clean_project_id,
        "trigger_type": normalized_trigger,
        "health_score": report_doc["healthScore"],
        "status": report_doc["status"],
        "generated_at": now_utc.isoformat(),
        "deliveries": delivery_results,
    }


# ---------------------------------------------------------------------------
# Schedule Management & Due Evaluation
# ---------------------------------------------------------------------------

def create_or_update_schedule(
    project_id: str,
    trigger_type: Union[TriggerType, str],
    destinations: Optional[List[str]] = None,
    enabled: bool = True,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create or update a recurring report schedule for a project.
    """
    clean_pid = str(project_id)
    t_type = trigger_type.value if isinstance(trigger_type, TriggerType) else str(trigger_type).lower()
    destinations = [d.lower() for d in (destinations or [DeliveryDestination.DASHBOARD.value])]
    config = config or {}

    now = datetime.now(timezone.utc)
    filter_query = {
        "projectId": to_object_id(clean_pid),
        "triggerType": t_type,
    }

    doc = {
        "projectId": to_object_id(clean_pid),
        "triggerType": t_type,
        "destinations": destinations,
        "enabled": enabled,
        "config": {
            "hourUtc": config.get("hour_utc", config.get("hourUtc", 8)),
            "minuteUtc": config.get("minute_utc", config.get("minuteUtc", 0)),
            "dayOfWeek": config.get("day_of_week", config.get("dayOfWeek", 0)),  # 0 = Monday
            "email_recipients": config.get("email_recipients", []),
            "slack_webhook_url": config.get("slack_webhook_url", ""),
            **config,
        },
        "updatedAt": now,
    }

    res = schedules_collection.update_one(
        filter_query,
        {"$set": doc, "$setOnInsert": {"createdAt": now, "lastRunAt": None}},
        upsert=True,
    )

    saved = schedules_collection.find_one(filter_query)
    if saved:
        saved["id"] = str(saved["_id"])
        saved["projectId"] = str(saved["projectId"])
    return saved or doc


def get_schedule(project_id: str, trigger_type: Union[TriggerType, str]) -> Optional[Dict[str, Any]]:
    """Retrieve schedule definition for project and trigger type."""
    t_type = trigger_type.value if isinstance(trigger_type, TriggerType) else str(trigger_type).lower()
    doc = schedules_collection.find_one({
        "projectId": to_object_id(project_id),
        "triggerType": t_type,
    })
    if not doc:
        return None
    doc["id"] = str(doc["_id"])
    doc["projectId"] = str(doc["projectId"])
    return doc


def list_schedules(enabled_only: bool = True) -> List[Dict[str, Any]]:
    """List configured report schedules across projects."""
    query = {"enabled": True} if enabled_only else {}
    docs = schedules_collection.find(query)
    out = []
    for d in docs:
        d["id"] = str(d["_id"])
        d["projectId"] = str(d.get("projectId", ""))
        out.append(d)
    return out


def is_schedule_due(schedule: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    """
    Evaluate if a schedule trigger is due for execution.
    Supports:
    - Daily: Checks if last run was on a previous day and current hour/minute is reached.
    - Weekly: Checks if today is the scheduled weekday and not yet executed this week.
    - End-of-Sprint: Checks if any sprint or milestone reached its conclusion or due date.
    """
    if not schedule.get("enabled", True):
        return False

    now_utc = now or datetime.now(timezone.utc)
    trigger_type = str(schedule.get("triggerType", "")).lower()
    last_run_at = schedule.get("lastRunAt")
    cfg = schedule.get("config", {})
    hour_target = int(cfg.get("hourUtc", 8))
    minute_target = int(cfg.get("minuteUtc", 0))

    if trigger_type == TriggerType.DAILY.value:
        if not last_run_at:
            return True
        if isinstance(last_run_at, str):
            try:
                last_run_at = datetime.fromisoformat(last_run_at.replace("Z", "+00:00"))
            except ValueError:
                return True
        if last_run_at.tzinfo is None:
            last_run_at = last_run_at.replace(tzinfo=timezone.utc)

        # Due if not run today (UTC) and current time is past scheduled hour/minute
        same_day = (
            last_run_at.year == now_utc.year
            and last_run_at.month == now_utc.month
            and last_run_at.day == now_utc.day
        )
        if not same_day and (now_utc.hour > hour_target or (now_utc.hour == hour_target and now_utc.minute >= minute_target)):
            return True
        return False

    elif trigger_type == TriggerType.WEEKLY.value:
        scheduled_weekday = int(cfg.get("dayOfWeek", 0))  # 0 is Monday
        if now_utc.weekday() != scheduled_weekday:
            return False
        if not last_run_at:
            return True
        if isinstance(last_run_at, str):
            try:
                last_run_at = datetime.fromisoformat(last_run_at.replace("Z", "+00:00"))
            except ValueError:
                return True
        if last_run_at.tzinfo is None:
            last_run_at = last_run_at.replace(tzinfo=timezone.utc)

        # Has it run within the last 6 days?
        if (now_utc - last_run_at) >= timedelta(days=6) and (now_utc.hour > hour_target or (now_utc.hour == hour_target and now_utc.minute >= minute_target)):
            return True
        return False

    elif trigger_type == TriggerType.END_OF_SPRINT.value:
        # Check if project has a closed milestone or sprint that completed since last_run_at
        project_id = schedule.get("projectId")
        if not project_id:
            return False
        return check_end_of_sprint_due(project_id, last_run_at, now_utc)

    return False


def check_end_of_sprint_due(
    project_id: str,
    last_run_at: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> bool:
    """
    Check if a project milestone or sprint ended and requires an End-of-Sprint report.
    """
    now_utc = now or datetime.now(timezone.utc)
    clean_pid = to_object_id(project_id)

    # 1. Check milestones collection for closed milestones or past due_on dates
    closed_milestones = milestones_collection.find({
        "projectId": clean_pid,
        "state": "closed",
    })
    for m in closed_milestones:
        updated_at = m.get("updated_at") or m.get("updatedAt")
        if updated_at and isinstance(updated_at, str):
            try:
                updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            except ValueError:
                updated_at = None
        if not last_run_at or (updated_at and updated_at > last_run_at):
            return True

    # 2. Check sprints collection for completed sprints
    completed_sprints = sprints_collection.find({
        "projectId": clean_pid,
        "status": {"$in": ["completed", "closed"]},
    })
    for s in completed_sprints:
        end_date = s.get("endDate") or s.get("end_date")
        if end_date and isinstance(end_date, str):
            try:
                end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            except ValueError:
                end_date = None
        if not last_run_at or (end_date and end_date > last_run_at):
            return True

    return False


# ---------------------------------------------------------------------------
# FastAPI BackgroundTasks Integration
# ---------------------------------------------------------------------------

def schedule_report_background(
    background_tasks: BackgroundTasks,
    project_id: str,
    trigger_type: Union[TriggerType, str] = TriggerType.DAILY,
    destinations: Optional[List[str]] = None,
    dispatcher: Optional[DeliveryDispatcher] = None,
) -> None:
    """
    Queue report generation and delivery as a FastAPI BackgroundTask.
    Runs asynchronously after the HTTP response is returned.
    """
    background_tasks.add_task(
        generate_scheduled_report,
        project_id=project_id,
        trigger_type=trigger_type,
        destinations=destinations,
        dispatcher=dispatcher,
    )
    logger.info("Enqueued report background task for project %s (%s)", project_id, trigger_type)


# ---------------------------------------------------------------------------
# ReportScheduler Class
# ---------------------------------------------------------------------------

class ReportScheduler:
    """
    Report Scheduler that orchestrates recurring triggers and delivery.
    Supports in-process polling, FastAPI integration, or standalone daemon execution.
    """

    def __init__(
        self,
        dispatcher: Optional[DeliveryDispatcher] = None,
        poll_interval_seconds: int = 60,
    ):
        self.dispatcher = dispatcher or DeliveryDispatcher()
        self.poll_interval = poll_interval_seconds
        self._is_running = False
        self._task: Optional[asyncio.Task] = None

    def trigger_now(
        self,
        project_id: str,
        trigger_type: Union[TriggerType, str] = TriggerType.MANUAL,
        destinations: Optional[List[str]] = None,
        custom_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Trigger an immediate report generation and dispatch."""
        return generate_scheduled_report(
            project_id=project_id,
            trigger_type=trigger_type,
            destinations=destinations,
            dispatcher=self.dispatcher,
            custom_config=custom_config,
        )

    def run_pending(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Evaluate all enabled project schedules and execute any that are due.
        Returns a list of execution outcome reports.
        """
        now_utc = now or datetime.now(timezone.utc)
        schedules = list_schedules(enabled_only=True)
        executed_results = []

        for sched in schedules:
            project_id = str(sched.get("projectId", ""))
            trigger_type = str(sched.get("triggerType", "daily"))
            destinations = sched.get("destinations", [DeliveryDestination.DASHBOARD.value])

            if is_schedule_due(sched, now=now_utc):
                logger.info("Schedule due for project %s (%s). Executing...", project_id, trigger_type)
                res = generate_scheduled_report(
                    project_id=project_id,
                    trigger_type=trigger_type,
                    destinations=destinations,
                    dispatcher=self.dispatcher,
                    custom_config=sched.get("config"),
                )
                executed_results.append(res)

        return executed_results

    async def start(self) -> None:
        """Start async polling loop as an in-process background worker."""
        if self._is_running:
            return
        self._is_running = True
        logger.info("AsyncReportScheduler started (poll interval: %ds).", self.poll_interval)
        try:
            while self._is_running:
                try:
                    self.run_pending()
                except Exception as exc:
                    logger.exception("Error evaluating pending schedules: %s", exc)
                await asyncio.sleep(self.poll_interval)
        except asyncio.CancelledError:
            logger.info("AsyncReportScheduler task cancelled.")
        finally:
            self._is_running = False

    def stop(self) -> None:
        """Stop polling loop."""
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("AsyncReportScheduler stopped.")


# Global singleton instance
_default_scheduler = ReportScheduler()


def get_scheduler() -> ReportScheduler:
    """Access the global scheduler singleton."""
    return _default_scheduler


# ---------------------------------------------------------------------------
# Standalone Worker Daemon (for separate Docker process execution)
# ---------------------------------------------------------------------------

def run_worker_daemon(poll_interval_seconds: int = 60) -> None:
    """
    Entrypoint for standalone background worker process (e.g. docker worker container).
    Listens for termination signals and continuously executes due report schedules.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting Aegis AI Background Report Worker Daemon...")

    scheduler = ReportScheduler(poll_interval_seconds=poll_interval_seconds)
    running = True

    def _handle_exit(sig, frame):
        nonlocal running
        logger.info("Shutdown signal received (%s). Exiting worker daemon...", sig)
        running = False

    signal.signal(signal.SIGINT, _handle_exit)
    signal.signal(signal.SIGTERM, _handle_exit)

    # Initial run check on startup
    try:
        scheduler.run_pending()
    except Exception as e:
        logger.error("Initial schedule evaluation error: %s", e)

    while running:
        try:
            time.sleep(poll_interval_seconds)
            if running:
                scheduler.run_pending()
        except KeyboardInterrupt:
            break
        except Exception as exc:
            logger.exception("Worker loop error: %s", exc)

    logger.info("Aegis AI Report Worker Daemon stopped cleanly.")


if __name__ == "__main__":
    interval = int(os.getenv("SCHEDULER_POLL_INTERVAL", "60"))
    run_worker_daemon(poll_interval_seconds=interval)
