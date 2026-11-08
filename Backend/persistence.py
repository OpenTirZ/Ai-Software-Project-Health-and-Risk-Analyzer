import logging
from bson import ObjectId
from datetime import datetime, timezone
from pymongo import UpdateOne
from pymongo.errors import (
    BulkWriteError,
    ConnectionFailure,
    PyMongoError,
    ServerSelectionTimeoutError,
)
from Backend.database import (
    users_collection,
    projects_collection,
    commits_collection,
    pull_requests_collection,
    issues_collection,
    sprints_collection,
    flags_collection,
    reports_collection,
    integration_credentials_collection,
    org_settings_collection,
    audit_logs_collection,
    contributors_collection,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application-level database exception
# ---------------------------------------------------------------------------

class DatabaseError(Exception):
    """Raised when a database operation fails due to a connectivity or driver error."""
    pass


# --------------------------------------------------
# Helper functions
# --------------------------------------------------

def to_object_id(value):
    """
    Convert a string ID to MongoDB ObjectId.
    """
    if isinstance(value, ObjectId):
        return value

    if not ObjectId.is_valid(value):
        raise ValueError(f"Invalid ObjectId: {value}")

    return ObjectId(value)


def serialize_document(document):
    """
    Convert MongoDB values into JSON-serializable values.
    """

    if document is None:
        return None

    if isinstance(document, ObjectId):
        return str(document)

    if isinstance(document, datetime):
        return document.isoformat()

    if isinstance(document, dict):
        return {
            key: serialize_document(value)
            for key, value in document.items()
        }

    if isinstance(document, list):
        return [
            serialize_document(value)
            for value in document
        ]

    return document


# --------------------------------------------------
# USERS
# --------------------------------------------------

def create_user(user_data):
    try:
        result = users_collection.insert_one(user_data)
        return str(result.inserted_id)
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("Database unreachable during create_user: %s", exc)
        raise DatabaseError("Database is temporarily unavailable. Please try again later.") from exc
    except PyMongoError as exc:
        logger.error("Database error during create_user: %s", exc)
        raise DatabaseError("A database error occurred while creating the user.") from exc


def get_user(user_id):
    try:
        document = users_collection.find_one(
            {"_id": to_object_id(user_id)}
        )
        return serialize_document(document)
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("Database unreachable during get_user: %s", exc)
        raise DatabaseError("Database is temporarily unavailable. Please try again later.") from exc
    except PyMongoError as exc:
        logger.error("Database error during get_user: %s", exc)
        raise DatabaseError("A database error occurred while retrieving the user.") from exc


def get_user_by_email(email):
    if not email:
        return None
    try:
        # Case-insensitive regex query for email search
        document = users_collection.find_one(
            {"email": {"$regex": f"^{email.strip()}$", "$options": "i"}}
        )
        return serialize_document(document)
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("Database unreachable during get_user_by_email: %s", exc)
        raise DatabaseError("Database is temporarily unavailable. Please try again later.") from exc
    except PyMongoError as exc:
        logger.error("Database error during get_user_by_email: %s", exc)
        raise DatabaseError("A database error occurred while looking up the user.") from exc


def get_users():
    try:
        documents = users_collection.find()
        return [serialize_document(doc) for doc in documents]
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("Database unreachable during get_users: %s", exc)
        raise DatabaseError("Database is temporarily unavailable. Please try again later.") from exc
    except PyMongoError as exc:
        logger.error("Database error during get_users: %s", exc)
        raise DatabaseError("A database error occurred while retrieving users.") from exc


def update_user(user_id, update_data):
    try:
        result = users_collection.update_one(
            {"_id": to_object_id(user_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("Database unreachable during update_user: %s", exc)
        raise DatabaseError("Database is temporarily unavailable. Please try again later.") from exc
    except PyMongoError as exc:
        logger.error("Database error during update_user: %s", exc)
        raise DatabaseError("A database error occurred while updating the user.") from exc


def delete_user(user_id):
    try:
        result = users_collection.delete_one(
            {"_id": to_object_id(user_id)}
        )
        return result.deleted_count > 0
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("Database unreachable during delete_user: %s", exc)
        raise DatabaseError("Database is temporarily unavailable. Please try again later.") from exc
    except PyMongoError as exc:
        logger.error("Database error during delete_user: %s", exc)
        raise DatabaseError("A database error occurred while deleting the user.") from exc


def clear_users():
    """Helper method to reset the database during tests."""
    try:
        users_collection.delete_many({})
    except Exception:
        pass


# --------------------------------------------------
# PROJECTS
# --------------------------------------------------

def create_project(project_data):
    try:
        result = projects_collection.insert_one(project_data)
        return str(result.inserted_id)
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("Database unreachable during create_project: %s", exc)
        raise DatabaseError("Database is temporarily unavailable. Please try again later.") from exc
    except PyMongoError as exc:
        logger.error("Database error during create_project: %s", exc)
        raise DatabaseError("A database error occurred while creating the project.") from exc


def get_project(project_id):
    try:
        document = projects_collection.find_one(
            {"_id": to_object_id(project_id)}
        )
        return serialize_document(document)
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("Database unreachable during get_project: %s", exc)
        raise DatabaseError("Database is temporarily unavailable. Please try again later.") from exc
    except PyMongoError as exc:
        logger.error("Database error during get_project: %s", exc)
        raise DatabaseError("A database error occurred while retrieving the project.") from exc


def get_projects():
    try:
        documents = projects_collection.find()
        return [serialize_document(doc) for doc in documents]
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("Database unreachable during get_projects: %s", exc)
        raise DatabaseError("Database is temporarily unavailable. Please try again later.") from exc
    except PyMongoError as exc:
        logger.error("Database error during get_projects: %s", exc)
        raise DatabaseError("A database error occurred while retrieving projects.") from exc


def get_projects_by_user(user_id):
    try:
        oid = to_object_id(user_id)
        documents = projects_collection.find(
            {"$or": [{"members.userId": oid}, {"ownerId": oid}]}
        )
        return [serialize_document(doc) for doc in documents]
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("Database unreachable during get_projects_by_user: %s", exc)
        raise DatabaseError("Database is temporarily unavailable. Please try again later.") from exc
    except PyMongoError as exc:
        logger.error("Database error during get_projects_by_user: %s", exc)
        raise DatabaseError("A database error occurred while retrieving projects.") from exc


def update_project(project_id, update_data):
    try:
        result = projects_collection.update_one(
            {"_id": to_object_id(project_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("Database unreachable during update_project: %s", exc)
        raise DatabaseError("Database is temporarily unavailable. Please try again later.") from exc
    except PyMongoError as exc:
        logger.error("Database error during update_project: %s", exc)
        raise DatabaseError("A database error occurred while updating the project.") from exc


def delete_project(project_id):
    try:
        result = projects_collection.delete_one(
            {"_id": to_object_id(project_id)}
        )
        return result.deleted_count > 0
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("Database unreachable during delete_project: %s", exc)
        raise DatabaseError("Database is temporarily unavailable. Please try again later.") from exc
    except PyMongoError as exc:
        logger.error("Database error during delete_project: %s", exc)
        raise DatabaseError("A database error occurred while deleting the project.") from exc


# --------------------------------------------------
# COMMITS
# --------------------------------------------------

def create_commit(commit_data):
    result = commits_collection.insert_one(commit_data)
    return str(result.inserted_id)


def get_commit(commit_id):
    document = commits_collection.find_one(
        {"_id": to_object_id(commit_id)}
    )
    return serialize_document(document)


def get_project_commits(project_id):
    documents = commits_collection.find(
        {"projectId": to_object_id(project_id)}
    )
    return [serialize_document(doc) for doc in documents]


def upsert_commit(project_id, commit_data):
    """
    Insert a new commit or update an existing one.

    Commit uniqueness is enforced by the database using the
    compound key (projectId, sha).

    In addition to the normalized GitHub commit fields, repository
    and branch context are stored so each commit can be traced back
    to the repository and branch from which it was ingested.
    """
    filter_query = {
        "projectId": to_object_id(project_id),
        "sha": commit_data["sha"],
    }

    update_doc = {
        "$set": {
            "projectId": to_object_id(project_id),
            "sha": commit_data["sha"],
            "short_sha": commit_data.get(
                "short_sha",
                commit_data["sha"][:7],
            ),
            "author": commit_data.get("author", "Unknown"),
            "github_username": commit_data.get("github_username"),
            "timestamp": commit_data.get("timestamp"),
            "message": commit_data.get("message", ""),
            "additions": commit_data.get("additions", 0),
            "deletions": commit_data.get("deletions", 0),
            "total_changes": commit_data.get("total_changes", 0),

            # Repository association
            "repository": commit_data.get("repository"),
            "repository_url": commit_data.get("repository_url"),

            # Branch context
            "branch": commit_data.get("branch"),
            "default_branch": commit_data.get("default_branch"),

            "updated_at": datetime.now(timezone.utc),
        }
    }

    result = commits_collection.update_one(
        filter_query,
        update_doc,
        upsert=True,
    )

    if result.upserted_id:
        return str(result.upserted_id)

    document = commits_collection.find_one(filter_query)
    return str(document["_id"]) if document else None



# --------------------------------------------------
# PULL REQUESTS
# --------------------------------------------------

def create_pull_request(pr_data):
    result = pull_requests_collection.insert_one(pr_data)
    return str(result.inserted_id)


def get_pull_request(pr_id):
    document = pull_requests_collection.find_one(
        {"_id": to_object_id(pr_id)}
    )
    return serialize_document(document)


def get_project_pull_requests(project_id):
    documents = pull_requests_collection.find(
        {"projectId": to_object_id(project_id)}
    )
    return [serialize_document(doc) for doc in documents]


def update_pull_request(pr_id, update_data):
    result = pull_requests_collection.update_one(
        {"_id": to_object_id(pr_id)},
        {"$set": update_data}
    )
    return result.modified_count > 0


# --------------------------------------------------
# ISSUES
# --------------------------------------------------

def create_issue(issue_data):
    result = issues_collection.insert_one(issue_data)
    return str(result.inserted_id)


def get_issue(issue_id):
    document = issues_collection.find_one(
        {"_id": to_object_id(issue_id)}
    )
    return serialize_document(document)


def get_project_issues(project_id):
    documents = issues_collection.find(
        {"projectId": to_object_id(project_id)}
    )
    return [serialize_document(doc) for doc in documents]


def bulk_upsert_issues(project_id, issues):
    """
    Insert or update many synchronized GitHub issues in ONE database call.

    Issue identity is the compound key (projectId, github_id), so running the
    same synchronization twice updates the existing documents instead of
    creating duplicates.

    Args:
        project_id: Project ObjectId (string or ObjectId).
        issues: List of normalized issue dicts. Every dict must contain a
            ``github_id``; the remaining fields are optional and default to
            safe empty values.

    Returns:
        dict with ``matched_count``, ``modified_count`` and ``upserted_count``
        taken directly from MongoDB's bulk-write result. An empty ``issues``
        list performs no database call and returns zeros; it never deletes
        previously stored issues.

    Raises:
        ValueError: If project_id is invalid or an issue has no github_id.
        DatabaseError: On any connectivity, driver or bulk-write failure.
            Because the bulk write is unordered and MongoDB has no
            multi-document transaction on a standalone server, a failure
            may leave some issues written. Re-running the sync is safe
            (idempotent) and completes the remaining writes.
    """
    if not issues:
        return {"matched_count": 0, "modified_count": 0, "upserted_count": 0}

    project_oid = to_object_id(project_id)
    synced_at = datetime.now(timezone.utc)
    operations = []

    for issue in issues:
        if issue.get("github_id") is None:
            raise ValueError("Every issue must contain a github_id.")

        operations.append(
            UpdateOne(
                {"projectId": project_oid, "github_id": issue["github_id"]},
                {
                    "$set": {
                        "projectId": project_oid,
                        "github_id": issue["github_id"],
                        "number": issue.get("number"),
                        "title": issue.get("title", ""),
                        "state": issue.get("state"),
                        "assignees": issue.get("assignees", []),
                        "labels": issue.get("labels", []),
                        "comments": issue.get("comments", 0),
                        "created_at": issue.get("created_at"),
                        "updated_at": issue.get("updated_at"),
                        "closed_at": issue.get("closed_at"),
                        "html_url": issue.get("html_url"),
                        "author": issue.get("author"),
                        "repository": issue.get("repository"),
                        "repository_url": issue.get("repository_url"),
                        # When OUR database last wrote this issue. Kept
                        # separate from GitHub's own updated_at above.
                        "synced_at": synced_at,
                    }
                },
                upsert=True,
            )
        )

    try:
        result = issues_collection.bulk_write(operations, ordered=False)
    except BulkWriteError as exc:
        logger.error("Bulk write failed during bulk_upsert_issues: %s", exc.details)
        raise DatabaseError(
            "A database error occurred while saving issues."
        ) from exc
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("Database unreachable during bulk_upsert_issues: %s", exc)
        raise DatabaseError(
            "Database is temporarily unavailable. Please try again later."
        ) from exc
    except PyMongoError as exc:
        logger.error("Database error during bulk_upsert_issues: %s", exc)
        raise DatabaseError(
            "A database error occurred while saving issues."
        ) from exc

    return {
        "matched_count": result.matched_count,
        "modified_count": result.modified_count,
        "upserted_count": result.upserted_count,
    }

    # EXPLANATION (bulk_upsert_issues):
    # Builds one UpdateOne(upsert=True) per issue and sends them all with a
    # single bulk_write call, so 500 issues cost one round trip rather than
    # 500. The filter (projectId, github_id) is the identity of an issue.
    # The counts returned are MongoDB's own numbers, so the API never
    # reports more than the database confirmed.


def list_project_issues(project_id, state=None):
    """
    Return the stored issues of ONE project, newest GitHub activity first.

    Args:
        project_id: Project ObjectId (string or ObjectId).
        state: Optional ``"open"`` or ``"closed"`` filter.

    Raises:
        ValueError: If project_id is not a valid ObjectId.
        DatabaseError: On connectivity or driver failures.
    """
    query = {"projectId": to_object_id(project_id)}
    if state:
        query["state"] = state

    try:
        documents = issues_collection.find(query).sort("updated_at", -1)
        return [serialize_document(doc) for doc in documents]
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("Database unreachable during list_project_issues: %s", exc)
        raise DatabaseError(
            "Database is temporarily unavailable. Please try again later."
        ) from exc
    except PyMongoError as exc:
        logger.error("Database error during list_project_issues: %s", exc)
        raise DatabaseError(
            "A database error occurred while retrieving issues."
        ) from exc

    # EXPLANATION (list_project_issues):
    # Always filters by projectId first, so one project can never see the
    # issues of another. The optional state filter and the updated_at sort
    # are done inside MongoDB (not in Python) to keep the read to one query.


def update_issue(issue_id, update_data):
    result = issues_collection.update_one(
        {"_id": to_object_id(issue_id)},
        {"$set": update_data}
    )
    return result.modified_count > 0


# --------------------------------------------------
# SPRINTS
# --------------------------------------------------

def create_sprint(sprint_data):
    result = sprints_collection.insert_one(sprint_data)
    return str(result.inserted_id)


def get_sprint(sprint_id):
    document = sprints_collection.find_one(
        {"_id": to_object_id(sprint_id)}
    )
    return serialize_document(document)


def get_project_sprints(project_id):
    documents = sprints_collection.find(
        {"projectId": to_object_id(project_id)}
    )
    return [serialize_document(doc) for doc in documents]


def update_sprint(sprint_id, update_data):
    result = sprints_collection.update_one(
        {"_id": to_object_id(sprint_id)},
        {"$set": update_data}
    )
    return result.modified_count > 0


# --------------------------------------------------
# FLAGS
# --------------------------------------------------

def create_flag(flag_data):
    result = flags_collection.insert_one(flag_data)
    return str(result.inserted_id)


def get_flag(flag_id):
    document = flags_collection.find_one(
        {"_id": to_object_id(flag_id)}
    )
    return serialize_document(document)


def get_project_flags(project_id):
    documents = flags_collection.find(
        {"projectId": to_object_id(project_id)}
    )
    return [serialize_document(doc) for doc in documents]


def update_flag(flag_id, update_data):
    result = flags_collection.update_one(
        {"_id": to_object_id(flag_id)},
        {"$set": update_data}
    )
    return result.modified_count > 0


# --------------------------------------------------
# REPORTS
# --------------------------------------------------

def create_report(report_data):
    result = reports_collection.insert_one(report_data)
    return str(result.inserted_id)


def get_report(report_id):
    document = reports_collection.find_one(
        {"_id": to_object_id(report_id)}
    )
    return serialize_document(document)


def get_project_reports(project_id):
    documents = reports_collection.find(
        {"projectId": to_object_id(project_id)}
    ).sort("generatedAt", -1)

    return [serialize_document(doc) for doc in documents]


# --------------------------------------------------
# INTEGRATION CREDENTIALS
# --------------------------------------------------

def create_integration_credential(credential_data):
    result = integration_credentials_collection.insert_one(
        credential_data
    )
    return str(result.inserted_id)


def get_integration_credential(project_id, provider):
    document = integration_credentials_collection.find_one(
        {
            "projectId": to_object_id(project_id)
            if project_id
            else None,
            "provider": provider
        }
    )

    return serialize_document(document)


# --------------------------------------------------
# ORGANIZATION SETTINGS
# --------------------------------------------------

def get_org_settings():
    document = org_settings_collection.find_one(
        {"key": "defaults"}
    )
    return serialize_document(document)


def update_org_settings(update_data):
    result = org_settings_collection.update_one(
        {"key": "defaults"},
        {"$set": update_data},
        upsert=True
    )

    return result.modified_count > 0 or result.upserted_id is not None


# --------------------------------------------------
# AUDIT LOGS
# --------------------------------------------------

def create_audit_log(log_data):
    result = audit_logs_collection.insert_one(log_data)
    return str(result.inserted_id)


def get_audit_logs(limit=100):
    documents = (
        audit_logs_collection
        .find()
        .sort("createdAt", -1)
        .limit(limit)
    )

    return [serialize_document(doc) for doc in documents]


# --------------------------------------------------
# CONTRIBUTORS
# --------------------------------------------------

def upsert_contributor(project_id, contributor_data):
    """
    Insert a new contributor or update an existing one.
    Uniqueness is enforced on (projectId, github_username).
    """
    filter_query = {
        "projectId": to_object_id(project_id),
        "github_username": contributor_data["github_username"],
    }
    update_doc = {
        "$set": {
            "projectId": to_object_id(project_id),
            "github_username": contributor_data["github_username"],
            "github_id": contributor_data.get("github_id"),
            "avatar_url": contributor_data.get("avatar_url", ""),
            "profile_url": contributor_data.get("profile_url", ""),
            "type": contributor_data.get("type", "User"),
            "contributions": contributor_data.get("contributions", 0),
            "updated_at": datetime.now(timezone.utc),
        }
    }
    result = contributors_collection.update_one(
        filter_query, update_doc, upsert=True
    )

    if result.upserted_id:
        return str(result.upserted_id)

    document = contributors_collection.find_one(filter_query)
    return str(document["_id"]) if document else None


def get_project_contributors(project_id):
    documents = contributors_collection.find(
        {"projectId": to_object_id(project_id)}
    )
    return [serialize_document(doc) for doc in documents]


def get_contributor(contributor_id):
    document = contributors_collection.find_one(
        {"_id": to_object_id(contributor_id)}
    )
    return serialize_document(document)
