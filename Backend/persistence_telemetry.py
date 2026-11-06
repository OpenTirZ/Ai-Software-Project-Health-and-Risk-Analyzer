"""
Telemetry persistence layer.

Provides CRUD and upsert operations for GitHub pull requests, issues,
milestones, and computed metric snapshots with idempotent upserts and
safe concurrent retry handling.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)


def _get_db(db: Any = None) -> Any:
    """Return the injected db or lazily load the default application database."""
    if db is not None:
        return db
    from Backend.database import db as default_db
    return default_db


def _validate_and_normalize_project_id(project_id: Any) -> Any:
    """
    Validate project_id and normalize to ObjectId if applicable.

    Raises ValueError if project_id is missing, empty, a boolean,
    or not a string/ObjectId.
    """
    if project_id is None:
        raise ValueError("projectId cannot be None")
    if isinstance(project_id, bool):
        raise ValueError("projectId cannot be a boolean")
    if not isinstance(project_id, (str, ObjectId)):
        raise ValueError("projectId must be a string or ObjectId")
    if isinstance(project_id, str):
        if not project_id.strip():
            raise ValueError("projectId cannot be empty")
        if ObjectId.is_valid(project_id):
            return ObjectId(project_id)
        return project_id
    return project_id


def _validate_key_field(item: Dict[str, Any], key_name: str) -> int:
    """
    Validate that a numeric key field exists, is not boolean, and is an integer.

    Raises ValueError if missing or of wrong type.
    """
    if key_name not in item or item[key_name] is None:
        raise ValueError(f"Missing required key field: '{key_name}'")
    value = item[key_name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            f"Key field '{key_name}' must be an integer, got {type(value).__name__}"
        )
    return value


def _upsert_entity(
    collection_name: str,
    key_name: str,
    project_id: Any,
    item: Dict[str, Any],
    db: Any = None,
) -> Dict[str, Any]:
    """
    Generic upsert for an entity uniquely identified by (projectId, key_name).

    Performs an update_one with upsert=True, separating caller fields into $set
    and insert-only fields into $setOnInsert to avoid path-conflict errors.
    Retries once on DuplicateKeyError to handle concurrent inserts.
    """
    norm_project_id = _validate_and_normalize_project_id(project_id)
    key_value = _validate_key_field(item, key_name)

    doc_copy = dict(item)
    doc_copy.pop("_id", None)

    now = datetime.now(timezone.utc)

    # Exclude identity, timestamps, and _id from $set
    set_fields = {
        k: v
        for k, v in doc_copy.items()
        if k not in (key_name, "projectId", "createdAt", "updatedAt")
    }
    set_fields["updatedAt"] = now

    set_on_insert = {
        "projectId": norm_project_id,
        key_name: key_value,
        "createdAt": now,
    }

    filter_doc = {
        "projectId": norm_project_id,
        key_name: key_value,
    }
    update_doc = {
        "$set": set_fields,
        "$setOnInsert": set_on_insert,
    }

    database = _get_db(db)
    coll = database[collection_name]

    try:
        result = coll.update_one(filter_doc, update_doc, upsert=True)
    except DuplicateKeyError:
        logger.warning(
            "DuplicateKeyError encountered upserting %s into %s; retrying once",
            key_value,
            collection_name,
        )
        result = coll.update_one(filter_doc, update_doc, upsert=True)

    created = result.upserted_id is not None
    modified = result.modified_count > 0

    return {
        "created": created,
        "modified": modified,
        "projectId": project_id,
        key_name: key_value,
    }


def _get_entities(
    collection_name: str,
    sort_key: str,
    project_id: Any,
    state: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    db: Any = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve entities for a given project with optional state filtering,
    stable descending sort, pagination, and exclusion of _id.
    """
    norm_project_id = _validate_and_normalize_project_id(project_id)
    clamped_limit = max(1, min(int(limit), 1000))
    clamped_skip = max(0, int(skip))

    query: Dict[str, Any] = {"projectId": norm_project_id}
    if state is not None:
        query["state"] = state

    database = _get_db(db)
    coll = database[collection_name]

    cursor = (
        coll.find(query, {"_id": 0})
        .sort(sort_key, -1)
        .skip(clamped_skip)
        .limit(clamped_limit)
    )
    return list(cursor)


# ---------------------------------------------------------------------------
# Pull Requests
# ---------------------------------------------------------------------------

def upsert_pull_request(
    project_id: Any,
    pr: Dict[str, Any],
    db: Any = None,
) -> Dict[str, Any]:
    """Upsert a pull request doc identified by (projectId, number)."""
    return _upsert_entity("pull_requests", "number", project_id, pr, db=db)


def get_project_prs(
    project_id: Any,
    state: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    db: Any = None,
) -> List[Dict[str, Any]]:
    """Return stored pull requests for a project, sorted by number DESC."""
    return _get_entities(
        "pull_requests", "number", project_id, state=state, limit=limit, skip=skip, db=db
    )


# ---------------------------------------------------------------------------
# Issues
# ---------------------------------------------------------------------------

def upsert_issue(
    project_id: Any,
    issue: Dict[str, Any],
    db: Any = None,
) -> Dict[str, Any]:
    """Upsert an issue doc identified by (projectId, number)."""
    return _upsert_entity("issues", "number", project_id, issue, db=db)


def get_project_issues(
    project_id: Any,
    state: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    db: Any = None,
) -> List[Dict[str, Any]]:
    """Return stored issues for a project, sorted by number DESC."""
    return _get_entities(
        "issues", "number", project_id, state=state, limit=limit, skip=skip, db=db
    )


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------

def upsert_milestone(
    project_id: Any,
    milestone: Dict[str, Any],
    db: Any = None,
) -> Dict[str, Any]:
    """Upsert a milestone doc identified by (projectId, milestone_id)."""
    return _upsert_entity("milestones", "milestone_id", project_id, milestone, db=db)


def get_project_milestones(
    project_id: Any,
    state: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    db: Any = None,
) -> List[Dict[str, Any]]:
    """Return stored milestones for a project, sorted by milestone_id DESC."""
    return _get_entities(
        "milestones", "milestone_id", project_id, state=state, limit=limit, skip=skip, db=db
    )


# ---------------------------------------------------------------------------
# Metric Snapshots
# ---------------------------------------------------------------------------

def insert_metric_snapshot(
    project_id: Any,
    snapshot: Dict[str, Any],
    db: Any = None,
) -> Dict[str, Any]:
    """
    Insert a point-in-time calculated telemetry metric snapshot for a project.

    Ensures timestamps and projectId are populated, strips _id from input.
    """
    norm_project_id = _validate_and_normalize_project_id(project_id)
    doc_copy = dict(snapshot)
    doc_copy.pop("_id", None)

    now = datetime.now(timezone.utc)
    doc_copy["projectId"] = norm_project_id
    if "calculatedAt" not in doc_copy or doc_copy["calculatedAt"] is None:
        doc_copy["calculatedAt"] = now
    if "createdAt" not in doc_copy or doc_copy["createdAt"] is None:
        doc_copy["createdAt"] = now

    database = _get_db(db)
    coll = database["metric_snapshots"]
    result = coll.insert_one(doc_copy)

    return {
        "inserted": True,
        "projectId": project_id,
        "snapshot_id": str(result.inserted_id),
    }


def get_project_metric_snapshots(
    project_id: Any,
    limit: int = 50,
    db: Any = None,
) -> List[Dict[str, Any]]:
    """Return metric snapshots for a project, newest first (calculatedAt DESC)."""
    norm_project_id = _validate_and_normalize_project_id(project_id)
    clamped_limit = max(1, min(int(limit), 1000))

    database = _get_db(db)
    coll = database["metric_snapshots"]
    cursor = (
        coll.find({"projectId": norm_project_id}, {"_id": 0})
        .sort("calculatedAt", -1)
        .limit(clamped_limit)
    )
    return list(cursor)
