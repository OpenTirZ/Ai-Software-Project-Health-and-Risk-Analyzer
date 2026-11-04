"""
Telemetry Persistence Layer (Sub-DAO) — AI Software Project Health & Risk Analyzer
-----------------------------------------------------------------------------------
Task: TASK-SP2-03 (Tirth Patel - Database Architect & LangGraph AI Engineer)

Isolates data access queries and compound unique upsert logic for:
  - Pull Requests (projectId, number) [UNIQUE]
  - Issues (projectId, number) [UNIQUE]
  - Milestones (projectId, milestone_id) [UNIQUE]
  - Metric Snapshots (projectId, calculatedAt)

Prevents chokepoints and merge conflicts in Backend/persistence.py while ensuring
strict data integrity across asynchronous telemetry synchronizations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from bson import ObjectId
from pymongo.errors import PyMongoError

from Backend.database import (
    issues_collection,
    metric_snapshots_collection,
    milestones_collection,
    pull_requests_collection,
)
from Backend.persistence import DatabaseError, serialize_document, to_object_id

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pull Requests DAO
# ---------------------------------------------------------------------------

def upsert_pull_request(
    project_id: Union[str, ObjectId],
    pr_data: Dict[str, Any],
) -> str:
    """
    Insert a new pull request or update an existing one.
    Compound uniqueness is enforced on (projectId, number).
    """
    if "number" not in pr_data and "pr_number" not in pr_data:
        raise ValueError("Pull request data must contain a 'number' or 'pr_number' field.")

    pr_number = int(pr_data.get("number") or pr_data.get("pr_number"))
    project_oid = to_object_id(project_id)

    filter_query = {
        "projectId": project_oid,
        "number": pr_number,
    }

    update_fields = {
        "projectId": project_oid,
        "number": pr_number,
        "title": pr_data.get("title", "Untitled PR"),
        "state": str(pr_data.get("state", "open")).lower(),
        "author": pr_data.get("author", "Unknown"),
        "github_username": pr_data.get("github_username") or (
            pr_data.get("author") if isinstance(pr_data.get("author"), str) else None
        ),
        "created_at": pr_data.get("created_at") or pr_data.get("createdAt"),
        "updated_at": pr_data.get("updated_at") or pr_data.get("updatedAt"),
        "closed_at": pr_data.get("closed_at") or pr_data.get("closedAt"),
        "merged_at": pr_data.get("merged_at") or pr_data.get("mergedAt"),
        "requested_reviewers": pr_data.get("requested_reviewers", []),
        "reviews": pr_data.get("reviews", []),
        "open_duration_hours": pr_data.get("open_duration_hours", 0.0),
        "additions": pr_data.get("additions", 0),
        "deletions": pr_data.get("deletions", 0),
        "html_url": pr_data.get("html_url") or pr_data.get("url", ""),
        "last_synced_at": datetime.now(timezone.utc),
    }

    try:
        result = pull_requests_collection.update_one(
            filter_query,
            {"$set": update_fields},
            upsert=True,
        )
        if result.upserted_id:
            return str(result.upserted_id)

        doc = pull_requests_collection.find_one(filter_query)
        return str(doc["_id"]) if doc else ""
    except PyMongoError as exc:
        logger.error("Failed to upsert PR #%s for project %s: %s", pr_number, project_id, exc)
        raise DatabaseError(f"Database error during pull request upsert: {exc}") from exc


def get_project_prs(
    project_id: Union[str, ObjectId],
    state: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve stored pull requests for a project, optionally filtered by state ('open', 'closed', 'merged').
    """
    project_oid = to_object_id(project_id)
    query: Dict[str, Any] = {"projectId": project_oid}

    if state:
        query["state"] = state.lower()

    try:
        cursor = pull_requests_collection.find(query).sort("number", -1)
        return [serialize_document(doc) for doc in cursor]
    except PyMongoError as exc:
        logger.error("Failed to fetch PRs for project %s: %s", project_id, exc)
        raise DatabaseError(f"Database error fetching project pull requests: {exc}") from exc


def get_pull_request_by_number(
    project_id: Union[str, ObjectId],
    number: int,
) -> Optional[Dict[str, Any]]:
    """Retrieve a single pull request by its project and PR number."""
    project_oid = to_object_id(project_id)
    try:
        doc = pull_requests_collection.find_one({
            "projectId": project_oid,
            "number": int(number),
        })
        return serialize_document(doc)
    except PyMongoError as exc:
        logger.error("Failed to fetch PR #%s for project %s: %s", number, project_id, exc)
        raise DatabaseError(f"Database error fetching pull request: {exc}") from exc


# ---------------------------------------------------------------------------
# Issues DAO
# ---------------------------------------------------------------------------

def upsert_issue(
    project_id: Union[str, ObjectId],
    issue_data: Dict[str, Any],
) -> str:
    """
    Insert a new issue or update an existing one.
    Compound uniqueness is enforced on (projectId, number).
    """
    if "number" not in issue_data and "issue_number" not in issue_data:
        raise ValueError("Issue data must contain a 'number' or 'issue_number' field.")

    issue_number = int(issue_data.get("number") or issue_data.get("issue_number"))
    project_oid = to_object_id(project_id)

    filter_query = {
        "projectId": project_oid,
        "number": issue_number,
    }

    update_fields = {
        "projectId": project_oid,
        "number": issue_number,
        "title": issue_data.get("title", "Untitled Issue"),
        "state": str(issue_data.get("state", "open")).lower(),
        "author": issue_data.get("author", "Unknown"),
        "assignees": issue_data.get("assignees", []),
        "labels": issue_data.get("labels", []),
        "comments_count": issue_data.get("comments_count", 0),
        "created_at": issue_data.get("created_at") or issue_data.get("createdAt"),
        "updated_at": issue_data.get("updated_at") or issue_data.get("updatedAt"),
        "closed_at": issue_data.get("closed_at") or issue_data.get("closedAt"),
        "html_url": issue_data.get("html_url") or issue_data.get("url", ""),
        "last_synced_at": datetime.now(timezone.utc),
    }

    try:
        result = issues_collection.update_one(
            filter_query,
            {"$set": update_fields},
            upsert=True,
        )
        if result.upserted_id:
            return str(result.upserted_id)

        doc = issues_collection.find_one(filter_query)
        return str(doc["_id"]) if doc else ""
    except PyMongoError as exc:
        logger.error("Failed to upsert issue #%s for project %s: %s", issue_number, project_id, exc)
        raise DatabaseError(f"Database error during issue upsert: {exc}") from exc


def get_project_issues(
    project_id: Union[str, ObjectId],
    state: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve stored issues for a project, optionally filtered by state ('open', 'closed').
    """
    project_oid = to_object_id(project_id)
    query: Dict[str, Any] = {"projectId": project_oid}

    if state:
        query["state"] = state.lower()

    try:
        cursor = issues_collection.find(query).sort("number", -1)
        return [serialize_document(doc) for doc in cursor]
    except PyMongoError as exc:
        logger.error("Failed to fetch issues for project %s: %s", project_id, exc)
        raise DatabaseError(f"Database error fetching project issues: {exc}") from exc


def get_issue_by_number(
    project_id: Union[str, ObjectId],
    number: int,
) -> Optional[Dict[str, Any]]:
    """Retrieve a single issue by project ID and issue number."""
    project_oid = to_object_id(project_id)
    try:
        doc = issues_collection.find_one({
            "projectId": project_oid,
            "number": int(number),
        })
        return serialize_document(doc)
    except PyMongoError as exc:
        logger.error("Failed to fetch issue #%s for project %s: %s", number, project_id, exc)
        raise DatabaseError(f"Database error fetching issue: {exc}") from exc


# ---------------------------------------------------------------------------
# Milestones DAO
# ---------------------------------------------------------------------------

def upsert_milestone(
    project_id: Union[str, ObjectId],
    milestone_data: Dict[str, Any],
) -> str:
    """
    Insert a new milestone or update an existing one.
    Compound uniqueness is enforced on (projectId, milestone_id).
    """
    raw_id = milestone_data.get("milestone_id") or milestone_data.get("id") or milestone_data.get("number")
    if raw_id is None:
        raise ValueError("Milestone data must contain 'milestone_id', 'id', or 'number'.")

    milestone_id_val = str(raw_id)
    project_oid = to_object_id(project_id)

    filter_query = {
        "projectId": project_oid,
        "milestone_id": milestone_id_val,
    }

    update_fields = {
        "projectId": project_oid,
        "milestone_id": milestone_id_val,
        "title": milestone_data.get("title", "Untitled Milestone"),
        "description": milestone_data.get("description", ""),
        "state": str(milestone_data.get("state", "open")).lower(),
        "due_on": milestone_data.get("due_on") or milestone_data.get("due_date"),
        "open_issues": int(milestone_data.get("open_issues", 0)),
        "closed_issues": int(milestone_data.get("closed_issues", 0)),
        "html_url": milestone_data.get("html_url") or milestone_data.get("url", ""),
        "last_synced_at": datetime.now(timezone.utc),
    }

    try:
        result = milestones_collection.update_one(
            filter_query,
            {"$set": update_fields},
            upsert=True,
        )
        if result.upserted_id:
            return str(result.upserted_id)

        doc = milestones_collection.find_one(filter_query)
        return str(doc["_id"]) if doc else ""
    except PyMongoError as exc:
        logger.error("Failed to upsert milestone %s for project %s: %s", milestone_id_val, project_id, exc)
        raise DatabaseError(f"Database error during milestone upsert: {exc}") from exc


def get_project_milestones(
    project_id: Union[str, ObjectId],
    state: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve stored milestones for a project, optionally filtered by state ('open', 'closed').
    """
    project_oid = to_object_id(project_id)
    query: Dict[str, Any] = {"projectId": project_oid}

    if state:
        query["state"] = state.lower()

    try:
        cursor = milestones_collection.find(query).sort("due_on", 1)
        return [serialize_document(doc) for doc in cursor]
    except PyMongoError as exc:
        logger.error("Failed to fetch milestones for project %s: %s", project_id, exc)
        raise DatabaseError(f"Database error fetching project milestones: {exc}") from exc


# ---------------------------------------------------------------------------
# Metric Snapshots DAO
# ---------------------------------------------------------------------------

def upsert_metric_snapshot(
    project_id: Union[str, ObjectId],
    snapshot_data: Dict[str, Any],
) -> str:
    """
    Store a point-in-time calculation snapshot of project health indicators.
    Indexed by (projectId, calculatedAt).
    """
    project_oid = to_object_id(project_id)
    calculated_at = snapshot_data.get("calculatedAt") or datetime.now(timezone.utc)

    filter_query = {
        "projectId": project_oid,
        "calculatedAt": calculated_at,
    }

    update_fields = {
        "projectId": project_oid,
        "calculatedAt": calculated_at,
        "health_score": snapshot_data.get("health_score"),
        "status": snapshot_data.get("status"),
        "indicators": snapshot_data.get("indicators", {}),
        "flags_count": snapshot_data.get("flags_count", {}),
        "weights_used": snapshot_data.get("weights_used", {}),
        "created_at": datetime.now(timezone.utc),
    }

    try:
        result = metric_snapshots_collection.update_one(
            filter_query,
            {"$set": update_fields},
            upsert=True,
        )
        if result.upserted_id:
            return str(result.upserted_id)

        doc = metric_snapshots_collection.find_one(filter_query)
        return str(doc["_id"]) if doc else ""
    except PyMongoError as exc:
        logger.error("Failed to upsert metric snapshot for project %s: %s", project_id, exc)
        raise DatabaseError(f"Database error saving metric snapshot: {exc}") from exc


def get_project_metric_snapshots(
    project_id: Union[str, ObjectId],
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Retrieve historical metric snapshots for a project, sorted by most recent."""
    project_oid = to_object_id(project_id)
    try:
        cursor = (
            metric_snapshots_collection.find({"projectId": project_oid})
            .sort("calculatedAt", -1)
            .limit(limit)
        )
        return [serialize_document(doc) for doc in cursor]
    except PyMongoError as exc:
        logger.error("Failed to fetch metric snapshots for project %s: %s", project_id, exc)
        raise DatabaseError(f"Database error fetching metric snapshots: {exc}") from exc

