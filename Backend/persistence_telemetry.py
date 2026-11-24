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
from pymongo import UpdateOne
from pymongo.errors import (
    BulkWriteError,
    ConnectionFailure,
    PyMongoError,
    ServerSelectionTimeoutError,
)

from Backend.database import (
    issues_collection,
    metric_snapshots_collection,
    milestones_collection,
    projects_collection,
    pull_requests_collection,
)
from Backend.persistence import (
    DatabaseError,
    _check_project_writable,
    _reconcile_write,
    serialize_document,
    to_object_id,
)

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

    _check_project_writable(project_id)

    pr_number = int(pr_data.get("number") or pr_data.get("pr_number"))
    project_oid = to_object_id(project_id)

    filter_query = {
        "projectId": project_oid,
        "number": pr_number,
    }

    existing_doc = pull_requests_collection.find_one(filter_query)

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
        _reconcile_write(pull_requests_collection, filter_query, existing_doc, result.upserted_id, project_id)
        if result.upserted_id:
            return str(result.upserted_id)

        if existing_doc and "_id" in existing_doc:
            return str(existing_doc["_id"])

        doc = pull_requests_collection.find_one(filter_query)
        return str(doc["_id"]) if doc else ""
    except PyMongoError as exc:
        logger.error("Failed to upsert PR #%s for project %s: %s", pr_number, project_id, exc)
        raise DatabaseError(f"Database error during pull request upsert: {exc}") from exc


def bulk_upsert_pull_requests(
    project_id: Union[str, ObjectId],
    pull_requests: List[Dict[str, Any]],
) -> Dict[str, int]:
    """
    Insert or update many synchronized GitHub pull requests in ONE database batch call.

    Preserves project write protection, compound uniqueness on (projectId, number),
    and lifecycle reconciliation.

    Args:
        project_id: Project ObjectId (string or ObjectId).
        pull_requests: List of normalized PR dicts. Each must contain 'number' or 'pr_number'.

    Returns:
        dict with 'matched_count', 'modified_count', and 'upserted_count'.

    Raises:
        ValueError: If project_id is invalid or a PR has no number.
        DatabaseError: On connectivity, driver, or bulk-write failure.
    """
    if not project_id or not str(project_id).strip():
        raise ValueError("project_id is required.")

    if not pull_requests:
        return {"matched_count": 0, "modified_count": 0, "upserted_count": 0}

    _check_project_writable(project_id)

    project_oid = to_object_id(project_id)
    synced_at = datetime.now(timezone.utc)
    operations = []

    # Map existing PRs for safe restoration if lifecycle transition occurs during bulk write
    existing_prs = {}
    pr_numbers = [
        int(p.get("number") or p.get("pr_number"))
        for p in pull_requests
        if p.get("number") is not None or p.get("pr_number") is not None
    ]
    if pr_numbers:
        try:
            cursor = pull_requests_collection.find(
                {"projectId": project_oid, "number": {"$in": pr_numbers}}
            )
            for doc in cursor:
                existing_prs[doc["number"]] = doc
        except Exception as e:
            logger.warning("Could not pre-fetch existing PRs for reconciliation: %s", e)

    for pr_data in pull_requests:
        if "number" not in pr_data and "pr_number" not in pr_data:
            raise ValueError("Pull request data must contain a 'number' or 'pr_number' field.")

        pr_number = int(pr_data.get("number") or pr_data.get("pr_number"))

        filter_query = {
            "projectId": project_oid,
            "number": pr_number,
        }

        reviews = pr_data.get("reviews", [])
        reviews_count = pr_data.get("reviews_count")
        if reviews_count is None:
            reviews_count = len(reviews) if isinstance(reviews, list) else 0

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
            "reviews": reviews,
            "reviews_count": reviews_count,
            "open_duration_hours": pr_data.get("open_duration_hours", 0.0),
            "additions": pr_data.get("additions", 0),
            "deletions": pr_data.get("deletions", 0),
            "html_url": pr_data.get("html_url") or pr_data.get("url", ""),
            "repository": pr_data.get("repository"),
            "repository_url": pr_data.get("repository_url"),
            "last_synced_at": synced_at,
        }

        operations.append(
            UpdateOne(
                filter_query,
                {"$set": update_fields},
                upsert=True,
            )
        )

    try:
        result = pull_requests_collection.bulk_write(operations, ordered=False)
    except BulkWriteError as exc:
        logger.error("Bulk write failed during bulk_upsert_pull_requests: %s", exc.details)
        raise DatabaseError(f"A database error occurred while saving pull requests: {exc}") from exc
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("Database unreachable during bulk_upsert_pull_requests: %s", exc)
        raise DatabaseError("Database is temporarily unavailable. Please try again later.") from exc
    except PyMongoError as exc:
        logger.error("Database error during bulk_upsert_pull_requests: %s", exc)
        raise DatabaseError(f"A database error occurred while saving pull requests: {exc}") from exc

    # Post-write reconciliation: check if lifecycle state transitioned during write
    post = projects_collection.find_one(
        {"_id": project_oid},
        {"status": 1, "is_active": 1, "deletion_status": 1}
    )
    if (
        not post
        or post.get("status") in ("archived", "deleted")
        or post.get("is_active") is False
        or post.get("deletion_status") in ("pending", "completed")
    ):
        for pr_item in pull_requests:
            num = int(pr_item.get("number") or pr_item.get("pr_number"))
            if num in existing_prs:
                pull_requests_collection.replace_one({"_id": existing_prs[num]["_id"]}, existing_prs[num])
            else:
                pull_requests_collection.delete_one({"projectId": project_oid, "number": num})
        raise DatabaseError("Project transitioned during synchronization. Pull requests batch reconciled.")

    return {
        "matched_count": result.matched_count,
        "modified_count": result.modified_count,
        "upserted_count": result.upserted_count,
    }


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

    _check_project_writable(project_id)

    issue_number = int(issue_data.get("number") or issue_data.get("issue_number"))
    project_oid = to_object_id(project_id)

    filter_query = {
        "projectId": project_oid,
        "number": issue_number,
    }

    existing_doc = issues_collection.find_one(filter_query)

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
        _reconcile_write(issues_collection, filter_query, existing_doc, result.upserted_id, project_id)
        if result.upserted_id:
            return str(result.upserted_id)

        if existing_doc and "_id" in existing_doc:
            return str(existing_doc["_id"])

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

    _check_project_writable(project_id)

    milestone_id_val = str(raw_id)
    project_oid = to_object_id(project_id)

    filter_query = {
        "projectId": project_oid,
        "milestone_id": milestone_id_val,
    }

    existing_doc = milestones_collection.find_one(filter_query)

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
        _reconcile_write(milestones_collection, filter_query, existing_doc, result.upserted_id, project_id)
        if result.upserted_id:
            return str(result.upserted_id)

        if existing_doc and "_id" in existing_doc:
            return str(existing_doc["_id"])

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

