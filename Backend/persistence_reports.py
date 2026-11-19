
"""
Reports & Schedules Persistence Layer (Sub-DAO) — AI Software Project Health & Risk Analyzer
---------------------------------------------------------------------------------------------
Modular persistence for the report generation pipeline, isolated from
Backend/persistence.py (and persistence_telemetry.py) to prevent chokepoints
and merge conflicts.

Collections:
  - reports:           validated JSON status reports produced by the LangGraph
                       V2 pipeline. Compound index (projectId, generatedAt DESC).
  - report_schedules:  recurring report delivery schedules
                       (frequency + email/slack destinations, lastRun, status).
                       Compound index (projectId, status).

reports document shape:
  {
      projectId, generatedAt, pipelineVersion, summary, risks,
      recommendations, metricsSnapshot, rawPromptTokens, createdAt
  }

report_schedules document shape:
  {
      projectId, frequency, destinations, lastRun, status,
      nextRunAt (optional), createdAt, updatedAt
  }
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

from bson import ObjectId
from pymongo.errors import (
    ConnectionFailure,
    PyMongoError,
    ServerSelectionTimeoutError,
)

from Backend.database import report_schedules_collection, reports_collection
from Backend.persistence import DatabaseError, serialize_document, to_object_id

logger = logging.getLogger(__name__)

VALID_FREQUENCIES = ("daily", "weekly", "monthly")
VALID_DESTINATIONS = ("email", "slack")
VALID_SCHEDULE_STATUSES = ("active", "paused", "completed", "failed")

FREQUENCY_INTERVALS_HOURS = {
    "daily": 24,
    "weekly": 24 * 7,
    "monthly": 24 * 30,
}


def _schedule_to_document(schedule_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize schedule input into a Mongo-safe document."""
    if not isinstance(schedule_data, dict):
        raise ValueError("Schedule data must be a JSON object.")

    frequency = str(schedule_data.get("frequency") or "").strip().lower()
    if frequency not in VALID_FREQUENCIES:
        raise ValueError(
            f"frequency must be one of {', '.join(VALID_FREQUENCIES)}."
        )

    destinations = schedule_data.get("destinations") or []
    if not isinstance(destinations, (list, tuple)) or not destinations:
        raise ValueError("destinations must be a non-empty list.")

    cleaned_destinations = []
    for destination in destinations:
        value = str(destination).strip().lower()
        if value not in VALID_DESTINATIONS:
            raise ValueError(
                f"destinations may only contain {', '.join(VALID_DESTINATIONS)}; got '{destination}'."
            )
        if value not in cleaned_destinations:
            cleaned_destinations.append(value)

    now = datetime.now(timezone.utc)
    status = str(schedule_data.get("status") or "active").strip().lower()
    if status not in VALID_SCHEDULE_STATUSES:
        raise ValueError(
            f"status must be one of {', '.join(VALID_SCHEDULE_STATUSES)}."
        )

    return {
        "frequency": frequency,
        "destinations": cleaned_destinations,
        "status": status,
        "lastRun": schedule_data.get("lastRun") or None,
        "nextRunAt": schedule_data.get("nextRunAt") or None,
        "updatedAt": now,
    }


# ---------------------------------------------------------------------------
# REPORTS DAO
# ---------------------------------------------------------------------------


def save_report(
    report: Dict[str, Any],
    project_id: Union[str, ObjectId],
    *,
    raw_prompt_tokens: Optional[int] = None,
) -> str:
    """
    Persist one validated pipeline status report into the reports collection.
    """
    if not isinstance(report, dict):
        raise ValueError(
            "report must be a JSON object produced by pipeline_v2.run_analysis."
        )

    generated_at = report.get("generated_at")
    summary = report.get("executive_summary")

    contributor_report = report.get("contributor_report")
    if not isinstance(contributor_report, dict):
        contributor_report = {}

    pull_request_report = report.get("pull_request_report")
    if not isinstance(pull_request_report, dict):
        pull_request_report = {}

    sprint_report = report.get("sprint_report")
    if not isinstance(sprint_report, dict):
        sprint_report = {}

    metrics_snapshot = report.get("metricsSnapshot")

    if not isinstance(metrics_snapshot, dict):
        metrics_snapshot = {
            "project_health": report.get("project_health"),
            "contributor_report": contributor_report.get("metrics"),
            "commit_report": (
                (report.get("commit_report") or {}).get("metrics")
                if isinstance(report.get("commit_report"), dict)
                else None
            ),
            "pull_request_report": pull_request_report.get("metrics"),
            "issue_report": (
                (report.get("issue_report") or {}).get("metrics")
                if isinstance(report.get("issue_report"), dict)
                else None
            ),
            "sprint_report": sprint_report.get("metrics"),
        }
    else:
        metrics_snapshot = dict(metrics_snapshot)

    metric_sections = (
        "project_health",
        "contributor_report",
        "commit_report",
        "pull_request_report",
        "issue_report",
        "sprint_report",
    )

    has_metrics = any(
        isinstance(metrics_snapshot.get(section), dict)
        and bool(metrics_snapshot[section])
        for section in metric_sections
    )

    if not generated_at or summary is None or not has_metrics:
        raise ValueError(
            "report must contain 'generated_at', 'executive_summary' and metric sections."
        )

    metrics_snapshot["contributors"] = (
        metrics_snapshot.get("contributors")
        or contributor_report.get("contributors", [])
    )

    metrics_snapshot["bottleneck_prs"] = (
        metrics_snapshot.get("bottleneck_prs")
        or pull_request_report.get("bottleneck_prs", [])
    )

    metrics_snapshot["milestones"] = (
        metrics_snapshot.get("milestones")
        or sprint_report.get("milestones", [])
    )

    if raw_prompt_tokens is None:
        llm_status = report.get("llm") or {}
        candidate = llm_status.get("raw_prompt_tokens")
        raw_prompt_tokens = (
            candidate
            if isinstance(candidate, int) and candidate >= 0
            else None
        )

    project_health = report.get("project_health")
    if not isinstance(project_health, dict):
        project_health = {}

    document = {
        "projectId": to_object_id(project_id),
        "generatedAt": (
            _parse_mongo_date(generated_at)
            or datetime.now(timezone.utc)
        ),
        "pipelineVersion": report.get("pipeline_version"),
        "summary": summary,
        "risks": project_health.get("risk_factors", []),
        "recommendations": report.get("recommendations", []),
        "metricsSnapshot": metrics_snapshot,
        "rawPromptTokens": raw_prompt_tokens,
        "createdAt": datetime.now(timezone.utc),
    }

    try:
        result = reports_collection.insert_one(document)
        return str(result.inserted_id)
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("Database unreachable during save_report: %s", exc)
        raise DatabaseError(
            "Database is temporarily unavailable. Please try again later."
        ) from exc
    except PyMongoError as exc:
        logger.error("Database error during save_report: %s", exc)
        raise DatabaseError(
            "A database error occurred while saving the report."
        ) from exc


def get_report(report_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
    """Retrieve one report by id (serialized, JSON-safe)."""
    try:
        document = reports_collection.find_one({"_id": to_object_id(report_id)})
        return serialize_document(document)
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("Database unreachable during get_report: %s", exc)
        raise DatabaseError("Database is temporarily unavailable. Please try again later.") from exc
    except PyMongoError as exc:
        logger.error("Database error during get_report: %s", exc)
        raise DatabaseError("A database error occurred while retrieving the report.") from exc


def get_project_reports(
    project_id: Union[str, ObjectId],
    *,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Return a project's reports, newest generatedAt first.

    Uses the (projectId, generatedAt DESC) compound index; one query, sorted
    in MongoDB, bounded by limit.
    """
    if limit is None or int(limit) <= 0:
        limit = 50

    try:
        cursor = (
            reports_collection.find({"projectId": to_object_id(project_id)})
            .sort([("generatedAt", -1)])
            .limit(int(limit))
        )
        return [serialize_document(doc) for doc in cursor]
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("Database unreachable during get_project_reports: %s", exc)
        raise DatabaseError("Database is temporarily unavailable. Please try again later.") from exc
    except PyMongoError as exc:
        logger.error("Database error during get_project_reports: %s", exc)
        raise DatabaseError("A database error occurred while retrieving reports.") from exc


def get_latest_project_report(project_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
    """Return the single newest report for a project, or None."""
    reports = get_project_reports(project_id, limit=1)
    return reports[0] if reports else None


def delete_report(report_id: Union[str, ObjectId]) -> bool:
    """Delete one report by id. Returns True when a document was removed."""
    try:
        result = reports_collection.delete_one({"_id": to_object_id(report_id)})
        return result.deleted_count > 0
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("Database unreachable during delete_report: %s", exc)
        raise DatabaseError("Database is temporarily unavailable. Please try again later.") from exc
    except PyMongoError as exc:
        logger.error("Database error during delete_report: %s", exc)
        raise DatabaseError("A database error occurred while deleting the report.") from exc


def count_project_reports(project_id: Union[str, ObjectId]) -> int:
    """Count the persisted reports of one project."""
    try:
        return int(reports_collection.count_documents({"projectId": to_object_id(project_id)}))
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("Database unreachable during count_project_reports: %s", exc)
        raise DatabaseError("Database is temporarily unavailable. Please try again later.") from exc
    except PyMongoError as exc:
        logger.error("Database error during count_project_reports: %s", exc)
        raise DatabaseError("A database error occurred while counting reports.") from exc


# ---------------------------------------------------------------------------
# REPORT SCHEDULES DAO
# ---------------------------------------------------------------------------

def create_report_schedule(
    project_id: Union[str, ObjectId],
    schedule_data: Dict[str, Any],
) -> str:
    """
    Create one report delivery schedule for a project.

    Validations (before any database write):
      - frequency in {daily, weekly, monthly}
      - destinations: non-empty list drawn from {email, slack}
      - optional status in {active, paused, completed, failed} (default active)

    Returns:
        The inserted schedule _id as a string.
    """
    project_oid = to_object_id(project_id)
    document = _schedule_to_document(schedule_data)
    document["projectId"] = project_oid
    document["createdAt"] = datetime.now(timezone.utc)

    try:
        result = report_schedules_collection.insert_one(document)
        return str(result.inserted_id)
    except PyMongoError as exc:
        logger.error("Database error during create_report_schedule: %s", exc)
        raise DatabaseError("A database error occurred while creating the schedule.") from exc


def get_schedule(schedule_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
    """Retrieve one schedule by id (serialized, JSON-safe)."""
    try:
        document = report_schedules_collection.find_one({"_id": to_object_id(schedule_id)})
        return serialize_document(document)
    except PyMongoError as exc:
        logger.error("Database error during get_schedule: %s", exc)
        raise DatabaseError("A database error occurred while retrieving the schedule.") from exc


def get_project_schedules(
    project_id: Union[str, ObjectId],
    *,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return a project's schedules, optionally filtered by status."""
    query: Dict[str, Any] = {"projectId": to_object_id(project_id)}
    if status:
        normalized = str(status).strip().lower()
        if normalized not in VALID_SCHEDULE_STATUSES:
            raise ValueError(
                f"status must be one of {', '.join(VALID_SCHEDULE_STATUSES)}."
            )
        query["status"] = normalized

    try:
        cursor = report_schedules_collection.find(query).sort([("createdAt", -1)])
        return [serialize_document(doc) for doc in cursor]
    except PyMongoError as exc:
        logger.error("Database error during get_project_schedules: %s", exc)
        raise DatabaseError("A database error occurred while retrieving schedules.") from exc


def update_report_schedule(
    schedule_id: Union[str, ObjectId],
    update_data: Dict[str, Any],
) -> bool:
    """
    Update editable schedule fields (frequency, destinations, status, nextRunAt).

    Only validated fields are written; unknown keys are ignored so callers
    cannot inject arbitrary database fields.

    Returns:
        True when at least one document was modified.
    """
    if not isinstance(update_data, dict):
        raise ValueError("update_data must be a JSON object.")

    allowed_keys = {"frequency", "destinations", "status", "nextRunAt", "lastRun"}
    merge_source: Dict[str, Any] = {}
    current: Optional[Dict[str, Any]] = None

    for key in ("frequency", "destinations", "status"):
        if key in update_data:
            merge_source[key] = update_data[key]

    if merge_source:
        current = report_schedules_collection.find_one({"_id": to_object_id(schedule_id)})
        if current is None:
            return False

        merged = {
            key: serialize_document(current.get(key))
            for key in ("frequency", "destinations", "status")
        }
        merged.update(merge_source)
        validated = _schedule_to_document(merged)
        update_data = {**update_data, **{key: validated[key] for key in merge_source}}

    update_fields: Dict[str, Any] = {}
    for key, value in update_data.items():
        if key in allowed_keys:
            update_fields[key] = value

    if not update_fields:
        raise ValueError("No editable fields provided for the schedule update.")

    update_fields["updatedAt"] = datetime.now(timezone.utc)

    try:
        result = report_schedules_collection.update_one(
            {"_id": to_object_id(schedule_id)},
            {"$set": update_fields},
        )
        return result.modified_count > 0
    except PyMongoError as exc:
        logger.error("Database error during update_report_schedule: %s", exc)
        raise DatabaseError("A database error occurred while updating the schedule.") from exc


def record_schedule_run(
    schedule_id: Union[str, ObjectId],
    *,
    status: str = "completed",
    ran_at: Optional[datetime] = None,
) -> bool:
    """
    Stamp a schedule after a report run: lastRun=now (or ran_at) and status.

    This is the hook the report scheduler calls after each delivery attempt.
    """
    normalized = str(status).strip().lower()
    if normalized not in VALID_SCHEDULE_STATUSES:
        raise ValueError(
            f"status must be one of {', '.join(VALID_SCHEDULE_STATUSES)}."
        )

    moment = ran_at or datetime.now(timezone.utc)

    try:
        result = report_schedules_collection.update_one(
            {"_id": to_object_id(schedule_id)},
            {"$set": {"lastRun": moment, "status": normalized, "updatedAt": moment}},
        )
        return result.modified_count > 0
    except PyMongoError as exc:
        logger.error("Database error during record_schedule_run: %s", exc)
        raise DatabaseError("A database error occurred while recording the schedule run.") from exc


def delete_report_schedule(schedule_id: Union[str, ObjectId]) -> bool:
    """Delete one schedule by id. Returns True when a document was removed."""
    try:
        result = report_schedules_collection.delete_one({"_id": to_object_id(schedule_id)})
        return result.deleted_count > 0
    except PyMongoError as exc:
        logger.error("Database error during delete_report_schedule: %s", exc)
        raise DatabaseError("A database error occurred while deleting the schedule.") from exc


def get_due_schedules(
    *,
    now: Optional[datetime] = None,
    statuses: tuple = ("active",),
) -> List[Dict[str, Any]]:
    """
    Return active schedules whose next scheduled moment has passed.

    A schedule is due when nextRunAt <= now, or when it has no nextRunAt and
    lastRun is missing or older than one frequency interval. Used by the
    scheduler loop; callers pass now for deterministic tests.
    """
    moment = now or datetime.now(timezone.utc)

    try:
        cursor = report_schedules_collection.find({"status": {"$in": list(statuses)}})
        due: List[Dict[str, Any]] = []

        for document in cursor:
            next_run = document.get("nextRunAt")
            if next_run is not None:
                is_due = _parse_mongo_date(next_run) <= moment
            else:
                last_run = _parse_mongo_date(document.get("lastRun"))
                interval_hours = FREQUENCY_INTERVALS_HOURS.get(
                    document.get("frequency"), 24 * 7
                )
                is_due = last_run is None or last_run <= moment - timedelta(hours=interval_hours)

            if is_due:
                due.append(serialize_document(document))

        return due
    except PyMongoError as exc:
        logger.error("Database error during get_due_schedules: %s", exc)
        raise DatabaseError("A database error occurred while retrieving due schedules.") from exc


def _parse_mongo_date(value: Any) -> Optional[datetime]:
    """Parse ISO strings / datetimes into aware UTC datetimes (Mongo-safe)."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    return None
