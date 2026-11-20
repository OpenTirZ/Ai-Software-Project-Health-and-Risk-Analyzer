

"""
Privacy filtering utilities for project metrics.

This module is independent of FastAPI routes, database access,
analytics calculations, and LangGraph.
"""

from copy import deepcopy
from typing import Any


PRIVILEGED_ROLES = {"lead", "owner", "admin"}

IDENTITY_FIELDS = (
    "github_username",
    "github_login",
    "username",
    "login",
    "contributor",
    "author",
    "author_name",
)


def _normalize(value: Any) -> str | None:
    """Normalize an identity value for comparison."""
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().casefold()


def _get_user_id(user: dict) -> str | None:
    """Extract the user's ID."""
    value = user.get("_id") or user.get("id")
    return str(value).strip() if value is not None else None


def _get_user_identity(user: dict) -> str | None:
    """Extract a supported GitHub identity from a user document."""
    for field in ("github_username", "github_login", "username"):
        identity = _normalize(user.get(field))
        if identity:
            return identity
    return None


def _get_record_identity(record: dict) -> str | None:
    """Extract contributor identity from a metric record."""
    for field in IDENTITY_FIELDS:
        identity = _normalize(record.get(field))
        if identity:
            return identity

    author = record.get("author")

    if isinstance(author, dict):
        for field in ("login", "name"):
            identity = _normalize(author.get(field))
            if identity:
                return identity

    account = record.get("user")

    if isinstance(account, dict):
        return _normalize(account.get("login"))

    return None


def _is_privileged(
    user: dict,
    project: dict | None = None,
) -> bool:
    """Check whether the user can access full team metrics."""
    role = _normalize(user.get("role"))

    if role in PRIVILEGED_ROLES:
        return True

    if project:
        user_id = _get_user_id(user)
        owner_id = project.get("ownerId") or project.get("owner_id")

        if user_id and owner_id is not None:
            return user_id == str(owner_id)

    return False


def filter_contributor_records(
    records: list[dict],
    current_user: dict,
    contributor_identity: str | None = None,
) -> list[dict]:
    """Return only contributor records belonging to the current user."""
    identity = (
        _normalize(contributor_identity)
        or _get_user_identity(current_user)
    )

    if not identity:
        return []

    return [
        deepcopy(record)
        for record in records
        if isinstance(record, dict)
        and _get_record_identity(record) == identity
    ]


def _filter_distribution(
    distribution: dict,
    identity: str | None,
) -> dict:
    """Keep the user's own contributor row and aggregate peer activity."""
    safe = deepcopy(distribution)
    contributors = safe.get("contributors", [])

    if not isinstance(contributors, list):
        contributors = []

    own_records = []
    peer_records = []

    for record in contributors:
        if not isinstance(record, dict):
            continue

        if identity and _get_record_identity(record) == identity:
            own_records.append(record)
        else:
            peer_records.append(record)

    peer_total = sum(
        record.get("count", 0)
        for record in peer_records
        if isinstance(record.get("count", 0), (int, float))
    )

    total_events = safe.get("total_events", 0)

    peer_percentage = (
        round((peer_total / total_events) * 100, 2)
        if isinstance(total_events, (int, float)) and total_events > 0
        else 0
    )

    safe["contributors"] = own_records
    safe["contributor_count"] = len(contributors)

    safe.pop("top_contributor", None)
    safe.pop("top_contributor_count", None)
    safe.pop("top_contributor_percentage", None)
    safe.pop("flags", None)

    safe["peer_activity"] = {
        "contributor_count": len(peer_records),
        "total_events": peer_total,
        "percentage": peer_percentage,
    }

    return safe


def filter_workload_metrics(
    metrics: dict,
    current_user: dict,
    project: dict | None = None,
    contributor_identity: str | None = None,
) -> dict:
    """
    Apply workload privacy rules.

    Leads, project owners, and admins receive full team metrics.
    Other users see their own contributor row and aggregated peer data.
    """
    safe = deepcopy(metrics)

    if _is_privileged(current_user, project):
        return safe

    identity = (
        _normalize(contributor_identity)
        or _get_user_identity(current_user)
    )

    for distribution_name in (
        "commit_distribution",
        "pr_distribution",
    ):
        distribution = safe.get(distribution_name)

        if isinstance(distribution, dict):
            safe[distribution_name] = _filter_distribution(
                distribution,
                identity,
            )

    return safe


def filter_appeal_history(
    appeals: list[dict],
    current_user: dict,
) -> list[dict]:
    """Return only appeal records belonging to the current user."""
    user_id = _get_user_id(current_user)

    if not user_id:
        return []

    result = []

    for appeal in appeals:
        if not isinstance(appeal, dict):
            continue

        appeal_user_id = (
            appeal.get("user_id") or appeal.get("userId")
        )

        if (
            appeal_user_id is not None
            and str(appeal_user_id) == user_id
        ):
            result.append(deepcopy(appeal))

    return result
