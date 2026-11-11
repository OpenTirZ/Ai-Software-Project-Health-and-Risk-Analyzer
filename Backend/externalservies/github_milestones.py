"""
GitHub Milestone Synchronization Service
-----------------------------------------

Fetches the milestones of a project's GitHub repository, normalizes them,
calculates completion percentages, and persists them to MongoDB via
persistence_telemetry.

Flow:
    project_id
        -> Verify the project exists
        -> Resolve and validate the repository URL
        -> GET /repos/{owner}/{repo}/milestones?state=open  (all pages)
        -> GET /repos/{owner}/{repo}/milestones?state=closed (all pages)
        -> Normalize every milestone
        -> Calculate completion_percentage per milestone
        -> upsert_milestone() for each (idempotent via projectId+milestone_id)
        -> Return summary counts

Public functions:
    get_github_milestones(repo_url)           fetch + normalize, no database
    sync_project_milestones(project_id, ...)  full fetch + persist workflow
    get_milestones_for_project(project_id)    read persisted milestones only

Task: TASK-SP2-08 (Issue #72) — Prince Savaliya
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from Backend.externalservies.contributor_service import (
    ProjectNotFoundError,
    _resolve_repo_url,
)
from Backend.externalservies.github_commits import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubRepoNotFoundError,
    _extract_github_error,
    _get_authenticated_session,
    _parse_github_url,
)
from Backend.persistence import get_project, DatabaseError
from Backend.persistence_telemetry import (
    upsert_milestone,
    get_project_milestones,
)

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
MILESTONES_PER_PAGE = 100      # GitHub's maximum page size
REQUEST_TIMEOUT_SECONDS = 10   # same timeout the other GitHub services use
MAX_PAGES = 100                # safety cap: 100 pages * 100 = 10,000 milestones
VALID_MILESTONE_STATES = ("open", "closed")


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class GitHubRateLimitError(GitHubAPIError):
    """Raised when GitHub refuses requests because the rate limit is used up."""
    pass


class GitHubPermissionError(GitHubAPIError):
    """Raised when the token is valid but lacks permission for the repository."""
    pass


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

def _raise_for_milestone_response(
    response: requests.Response,
    owner: str,
    repo: str,
) -> None:
    """
    Convert an unsuccessful GitHub response into the right project exception.

    Raises:
        GitHubAuthError: 401 (bad or expired token).
        GitHubRateLimitError: 429, or 403 caused by the rate limit.
        GitHubPermissionError: any other 403.
        GitHubRepoNotFoundError: 404.
        GitHubAPIError: every other non-2xx status.
    """
    status_code = response.status_code

    if status_code == 401:
        raise GitHubAuthError("Invalid or expired GITHUB_TOKEN.")

    if status_code == 429 or (
        status_code == 403
        and (
            response.headers.get("X-RateLimit-Remaining") == "0"
            or "rate limit" in response.text.lower()
        )
    ):
        raise GitHubRateLimitError(
            "GitHub API rate limit exceeded. Try again later."
        )

    if status_code == 403:
        raise GitHubPermissionError(
            _extract_github_error(
                response,
                f"The GitHub token has no permission to read milestones of "
                f"'{owner}/{repo}'.",
            )
        )

    if status_code == 404:
        raise GitHubRepoNotFoundError(
            f"Repository '{owner}/{repo}' not found or is not accessible."
        )

    if not response.ok:
        raise GitHubAPIError(
            _extract_github_error(
                response,
                f"GitHub API error {status_code} while fetching milestones.",
            )
        )


def _request_milestone_page(
    session: requests.Session,
    url: str,
    params: Optional[dict] = None,
) -> requests.Response:
    """
    Perform one GET request and translate network failures.

    Raises:
        GitHubAPIError: on timeout, connection failure or any other
            ``requests`` exception.
    """
    try:
        return session.get(
            url,
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout as exc:
        raise GitHubAPIError(
            "Request to GitHub timed out while fetching milestones."
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        raise GitHubAPIError(
            "Could not connect to GitHub while fetching milestones."
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise GitHubAPIError(
            f"Network failure while fetching milestones: {exc}"
        ) from exc


def _parse_page_payload(response: requests.Response) -> list[dict]:
    """
    Decode one page of the milestones response.

    Raises:
        GitHubAPIError: if the body is not JSON, is not a list, or contains
            items that are not JSON objects.
    """
    try:
        payload = response.json()
    except ValueError as exc:
        raise GitHubAPIError(
            "GitHub returned a response that is not valid JSON."
        ) from exc

    if not isinstance(payload, list):
        raise GitHubAPIError(
            "GitHub returned an unexpected response while fetching milestones."
        )

    if any(not isinstance(item, dict) for item in payload):
        raise GitHubAPIError(
            "GitHub returned malformed milestone data."
        )

    return payload


def _fetch_milestones_by_state(
    session: requests.Session,
    owner: str,
    repo: str,
    state: str,
) -> list[dict]:
    """
    Fetch all milestones for a single state (open or closed) with pagination.

    Uses page-number pagination (``page=1,2,3...``) because the GitHub
    milestones endpoint does not emit ``Link: rel="next"`` headers.

    Raises:
        GitHubAPIError (or subclass): on any HTTP, network, JSON or
            pagination problem.
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/milestones"
    items: list[dict] = []

    for page in range(1, MAX_PAGES + 1):
        params = {
            "state": state,
            "per_page": MILESTONES_PER_PAGE,
            "page": page,
        }

        response = _request_milestone_page(session, url, params)
        _raise_for_milestone_response(response, owner, repo)
        page_items = _parse_page_payload(response)

        items.extend(page_items)

        # Stop when page is incomplete or empty
        if len(page_items) < MILESTONES_PER_PAGE:
            break
    else:
        raise GitHubAPIError(
            f"Repository '{owner}/{repo}' has more than {MAX_PAGES} "
            f"pages of milestones; refusing to synchronize a partial list."
        )

    return items


def _fetch_all_milestones(
    session: requests.Session,
    owner: str,
    repo: str,
) -> list[dict]:
    """
    Fetch ALL milestones (both open and closed) for a repository.

    Two separate requests because the GitHub milestones endpoint does not
    support ``state=all`` — unlike the issues endpoint.

    Returns:
        Combined list of raw milestone dicts from GitHub.
    """
    open_milestones = _fetch_milestones_by_state(session, owner, repo, "open")
    closed_milestones = _fetch_milestones_by_state(session, owner, repo, "closed")
    return open_milestones + closed_milestones


# ---------------------------------------------------------------------------
# Normalization layer
# ---------------------------------------------------------------------------

def _safe_int(value: Any, default: int = 0) -> int:
    """
    Convert a value to a non-negative integer safely.

    Returns ``default`` for None, negative, boolean, or non-numeric values.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    try:
        result = int(value)
        return result if result >= 0 else default
    except (ValueError, TypeError):
        return default


def calculate_completion_percentage(
    open_issues: int,
    closed_issues: int,
) -> float:
    """
    Calculate milestone completion as a percentage.

    Formula: closed / (open + closed) * 100

    Returns 0.0 when there are no issues (prevents division by zero).
    Guarantees the result is between 0.0 and 100.0.
    """
    safe_open = max(int(open_issues), 0) if isinstance(open_issues, (int, float)) and not isinstance(open_issues, bool) else 0
    safe_closed = max(int(closed_issues), 0) if isinstance(closed_issues, (int, float)) and not isinstance(closed_issues, bool) else 0
    total = safe_open + safe_closed
    if total <= 0:
        return 0.0
    percentage = (safe_closed / total) * 100.0
    return round(min(max(percentage, 0.0), 100.0), 2)


def map_issues_to_milestones(
    milestones: list[dict],
    issues: list[dict],
) -> dict[str, list[dict]]:
    """
    Map a list of issues to their respective milestones.

    Args:
        milestones: List of normalized milestone dicts or stored documents.
        issues: List of issue dicts (which may contain a 'milestone' key/object).

    Returns:
        Dict mapping milestone_id -> list of issues assigned to that milestone.
        Issues with no milestone or an unrecognized milestone are grouped
        under '__unassigned__'.
    """
    mapping: dict[str, list[dict]] = {
        str(ms.get("milestone_id") or ms.get("number") or ms.get("id")): []
        for ms in milestones
        if ms.get("milestone_id") or ms.get("number") or ms.get("id")
    }
    mapping["__unassigned__"] = []

    for issue in issues:
        ms_ref = issue.get("milestone")
        ms_id = None
        if isinstance(ms_ref, dict):
            raw_id = ms_ref.get("number") or ms_ref.get("id") or ms_ref.get("milestone_id")
            ms_id = str(raw_id) if raw_id is not None else None
        elif ms_ref is not None:
            ms_id = str(ms_ref)

        if ms_id and ms_id in mapping:
            mapping[ms_id].append(issue)
        else:
            mapping["__unassigned__"].append(issue)

    return mapping


def _normalize_timestamp(value: Any, field_name: str) -> Optional[str]:
    """
    Validate a GitHub timestamp and return it as an ISO-8601 UTC string.

    ``None`` and empty strings stay ``None``.

    Raises:
        GitHubAPIError: if the value is not a timezone-aware ISO-8601 string.
    """
    if value is None or value == "":
        return None

    if not isinstance(value, str):
        raise GitHubAPIError(f"GitHub returned an invalid '{field_name}' value.")

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GitHubAPIError(
            f"GitHub returned an invalid '{field_name}' timestamp."
        ) from exc

    if parsed.tzinfo is None:
        raise GitHubAPIError(
            f"GitHub returned a '{field_name}' timestamp without a timezone."
        )

    return parsed.astimezone(timezone.utc).isoformat()


def _normalize_milestone(raw: dict) -> dict:
    """
    Convert one raw GitHub milestone into the dict stored in the database.

    Required fields: ``number`` (used as milestone_id), ``title``.
    All other fields have safe defaults.

    Raises:
        GitHubAPIError: if a required field is missing or invalid.
    """
    # milestone_id: GitHub uses "number" as the stable identifier
    milestone_id = raw.get("number")
    if milestone_id is None:
        # Fall back to "id" if "number" is absent
        milestone_id = raw.get("id")
    if (
        milestone_id is None
        or isinstance(milestone_id, bool)
        or not str(milestone_id).strip()
    ):
        raise GitHubAPIError("GitHub returned a milestone without a valid identifier.")

    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        title = "Untitled Milestone"

    state = str(raw.get("state") or "open").lower()
    if state not in VALID_MILESTONE_STATES:
        state = "open"

    open_issues = _safe_int(raw.get("open_issues"))
    closed_issues = _safe_int(raw.get("closed_issues"))

    return {
        "milestone_id": str(milestone_id),
        "title": title,
        "description": raw.get("description") or "",
        "state": state,
        "due_on": _normalize_timestamp(raw.get("due_on"), "due_on")
                  if raw.get("due_on") else None,
        "open_issues": open_issues,
        "closed_issues": closed_issues,
        "completion_percentage": calculate_completion_percentage(
            open_issues, closed_issues
        ),
        "html_url": raw.get("html_url") or "",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_github_milestones(repo_url: str) -> dict:
    """
    Fetch and normalize all milestones (open and closed) of a GitHub
    repository. Does not touch the database.

    Returns:
        {
            "repository": {"owner", "name", "full_name", "url"},
            "milestones": [normalized milestone dicts],
        }

    Raises:
        ValueError: if repo_url is not a valid GitHub repository URL.
        GitHubTokenMissingError: if GITHUB_TOKEN is not configured.
        GitHubAuthError, GitHubPermissionError, GitHubRateLimitError,
        GitHubRepoNotFoundError, GitHubAPIError: GitHub/network failures.
    """
    owner, repo = _parse_github_url(repo_url)
    repository = {
        "owner": owner,
        "name": repo,
        "full_name": f"{owner}/{repo}",
        "url": f"https://github.com/{owner}/{repo}",
    }

    session = _get_authenticated_session()
    raw_items = _fetch_all_milestones(session, owner, repo)

    milestones_by_id: dict[str, dict] = {}
    for raw in raw_items:
        try:
            normalized = _normalize_milestone(raw)
            ms_id = normalized["milestone_id"]
            # Deduplicate by milestone_id: later state (e.g. closed) updates earlier
            milestones_by_id[ms_id] = normalized
        except GitHubAPIError as exc:
            # Skip individual malformed milestones but log the issue
            logger.warning("Skipping malformed milestone: %s", exc)

    return {
        "repository": repository,
        "milestones": list(milestones_by_id.values()),
    }


def sync_project_milestones(
    project_id: str,
    repo_url: Optional[str] = None,
) -> dict:
    """
    Fetch a project's GitHub milestones and persist them.

    Persistence happens only AFTER GitHub was read completely and
    successfully, so a failed fetch never changes stored data.

    When the repository has no milestones, the response indicates
    "Insufficient milestone data" instead of crashing.

    Returns:
        {
            "success": True,
            "status": "synced" | "no_milestones",
            "project_id": str,
            "repository": {...},
            "fetched_count": int,
            "created_count": int,
            "updated_count": int,
            "message": str | None,
        }

    Raises:
        ValueError: empty project_id or invalid repository URL.
        ProjectNotFoundError: project not in database.
        GitHub*Error: see get_github_milestones().
        DatabaseError: the upsert failed.
    """
    if not project_id or not project_id.strip():
        raise ValueError("project_id is required.")

    project = get_project(project_id)
    if not project:
        raise ProjectNotFoundError(f"Project '{project_id}' not found.")

    resolved_url = _resolve_repo_url(project, repo_url)
    result = get_github_milestones(resolved_url)
    milestones = result["milestones"]

    # Handle empty milestones gracefully
    if not milestones:
        logger.info(
            "No milestones found for project %s in repository %s.",
            project_id, resolved_url,
        )
        return {
            "success": True,
            "status": "no_milestones",
            "project_id": project_id,
            "repository": result["repository"],
            "fetched_count": 0,
            "created_count": 0,
            "updated_count": 0,
            "message": "Insufficient milestone data",
        }

    created_count = 0
    for ms_data in milestones:
        upsert_milestone(project_id, ms_data)
        created_count += 1

    logger.info(
        "Milestone sync for project %s: fetched=%d persisted=%d",
        project_id, len(milestones), created_count,
    )

    return {
        "success": True,
        "status": "synced",
        "project_id": project_id,
        "repository": result["repository"],
        "fetched_count": len(milestones),
        "created_count": created_count,
        "updated_count": 0,
        "message": None,
    }


def get_milestones_for_project(
    project_id: str,
    state: Optional[str] = None,
) -> list[dict]:
    """
    Return the persisted milestones of a project (never calls GitHub).

    Args:
        project_id: Project ObjectId string.
        state: Optional ``"open"`` or ``"closed"`` filter.

    Raises:
        ValueError: empty project_id or unknown state.
        DatabaseError: the database read failed.
    """
    if not project_id or not project_id.strip():
        raise ValueError("project_id is required.")

    if state is not None and state not in VALID_MILESTONE_STATES:
        raise ValueError("state must be 'open' or 'closed'.")

    documents = get_project_milestones(project_id, state=state)
    return [_present_milestone(document) for document in documents]


def _present_milestone(document: dict) -> dict:
    """Shape a stored milestone document into the public API representation."""
    open_issues = document.get("open_issues", 0)
    closed_issues = document.get("closed_issues", 0)

    return {
        "id": document.get("_id"),
        "project_id": document.get("projectId"),
        "milestone_id": document.get("milestone_id"),
        "title": document.get("title"),
        "description": document.get("description") or "",
        "state": document.get("state"),
        "due_on": document.get("due_on"),
        "open_issues": open_issues if isinstance(open_issues, int) else 0,
        "closed_issues": closed_issues if isinstance(closed_issues, int) else 0,
        "completion_percentage": calculate_completion_percentage(
            open_issues if isinstance(open_issues, int) else 0,
            closed_issues if isinstance(closed_issues, int) else 0,
        ),
        "html_url": document.get("html_url") or "",
    }

