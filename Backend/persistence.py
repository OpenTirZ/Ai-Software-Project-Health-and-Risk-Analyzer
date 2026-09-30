from bson import ObjectId
from datetime import datetime, timezone
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
    Convert MongoDB ObjectId and datetime values
    into JSON-friendly values.
    """
    if document is None:
        return None

    document["_id"] = str(document["_id"])

    for key, value in document.items():
        if isinstance(value, datetime):
            document[key] = value.isoformat()

    return document


# --------------------------------------------------
# USERS
# --------------------------------------------------

def create_user(user_data):
    result = users_collection.insert_one(user_data)
    return str(result.inserted_id)


def get_user(user_id):
    document = users_collection.find_one(
        {"_id": to_object_id(user_id)}
    )
    return serialize_document(document)


def get_user_by_email(email):
    document = users_collection.find_one(
        {"email": email}
    )
    return serialize_document(document)


def get_users():
    documents = users_collection.find()
    return [serialize_document(doc) for doc in documents]


def update_user(user_id, update_data):
    result = users_collection.update_one(
        {"_id": to_object_id(user_id)},
        {"$set": update_data}
    )
    return result.modified_count > 0


def delete_user(user_id):
    result = users_collection.delete_one(
        {"_id": to_object_id(user_id)}
    )
    return result.deleted_count > 0


# --------------------------------------------------
# PROJECTS
# --------------------------------------------------

def create_project(project_data):
    result = projects_collection.insert_one(project_data)
    return str(result.inserted_id)


def get_project(project_id):
    document = projects_collection.find_one(
        {"_id": to_object_id(project_id)}
    )
    return serialize_document(document)


def get_projects():
    documents = projects_collection.find()
    return [serialize_document(doc) for doc in documents]


def get_projects_by_user(user_id):
    documents = projects_collection.find(
        {"members.userId": to_object_id(user_id)}
    )
    return [serialize_document(doc) for doc in documents]


def update_project(project_id, update_data):
    result = projects_collection.update_one(
        {"_id": to_object_id(project_id)},
        {"$set": update_data}
    )
    return result.modified_count > 0


def delete_project(project_id):
    result = projects_collection.delete_one(
        {"_id": to_object_id(project_id)}
    )
    return result.deleted_count > 0


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
    Uniqueness is enforced on (projectId, sha).
    """
    filter_query = {
        "projectId": to_object_id(project_id),
        "sha": commit_data["sha"],
    }
    update_doc = {
        "$set": {
            "projectId": to_object_id(project_id),
            "sha": commit_data["sha"],
            "short_sha": commit_data.get("short_sha", commit_data["sha"][:7]),
            "author": commit_data.get("author", "Unknown"),
            "github_username": commit_data.get("github_username"),
            "timestamp": commit_data.get("timestamp"),
            "message": commit_data.get("message", ""),
            "additions": commit_data.get("additions", 0),
            "deletions": commit_data.get("deletions", 0),
            "total_changes": commit_data.get("total_changes", 0),
            "updated_at": datetime.now(timezone.utc),
        }
    }
    result = commits_collection.update_one(
        filter_query, update_doc, upsert=True
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