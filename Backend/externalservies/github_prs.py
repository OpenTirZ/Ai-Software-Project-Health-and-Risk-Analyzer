"""
GitHub Pull Request Synchronization Service
--------------------------------------------

Fetches the pull requests of a project's GitHub repository, normalizes them
and persists them to MongoDB via persistence_telemetry.

Flow:
    project_id
        -> Verify the project exists
        -> Resolve and validate the repository URL
        -> GET /repos/{owner}/{repo}/pulls?state=all (follow Link pagination)
        -> Fetch individual PR details for additions/deletions/reviews
        -> Normalize every pull request
        -> upsert_pull_request() for each PR (idempotent via projectId+number)
        -> Return summary counts

Public functions:
    get_github_prs(repo_url)             fetch + normalize, no database access
    sync_project_prs(project_id, ...)    full fetch + persist workflow
    get_prs_for_project(project_id)      read persisted PRs, never calls GitHub

Task: TASK-SP2-06 (Issue #70) — Prince Savaliya
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
    upsert_pull_request,
    get_project_prs,
)

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
PRS_PER_PAGE = 100             # GitHub's maximum page size
REQUEST_TIMEOUT_SECONDS = 10   # same timeout the other GitHub services use
MAX_PAGES = 500                # safety cap: 500 pages * 100 = 50,000 PRs
VALID_PR_STATES = ("open", "closed", "merged")


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------
# Both subclass the existing GitHubAPIError, so any code that already catches
# GitHubAPIError keeps working, while the router can give these a more
# precise HTTP status.

class GitHubRateLimitError(GitHubAPIError):
    """Raised when GitHub refuses requests because the rate limit is used up."""
    pass


class GitHubPermissionError(GitHubAPIError):
    """Raised when the token is valid but lacks permission for the repository."""
    pass


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

def _raise_for_pr_response(
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
                f"The GitHub token has no permission to read pull requests of "
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
                f"GitHub API error {status_code} while fetching pull requests.",
            )
        )


def _request_pr_page(
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
            "Request to GitHub timed out while fetching pull requests."
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        raise GitHubAPIError(
            "Could not connect to GitHub while fetching pull requests."
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise GitHubAPIError(
            f"Network failure while fetching pull requests: {exc}"
        ) from exc


def _parse_page_payload(response: requests.Response) -> list[dict]:
    """
    Decode one page of the pull requests response.

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
            "GitHub returned an unexpected response while fetching pull requests."
        )

    if any(not isinstance(item, dict) for item in payload):
        raise GitHubAPIError(
            "GitHub returned malformed pull request data."
        )

    return payload


def _fetch_all_pr_items(
    session: requests.Session,
    owner: str,
    repo: str,
) -> list[dict]:
    """
    Fetch EVERY raw pull request of a repository (state=all, all pages).

    Pagination follows GitHub's ``Link: rel="next"`` header, so repositories
    with more than 100 pull requests are fully retrieved.

    Raises:
        GitHubAPIError (or a subclass): on any HTTP, network, JSON or
            pagination problem.
    """
    url: Optional[str] = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls"
    params: Optional[dict] = {"state": "all", "per_page": PRS_PER_PAGE}

    items: list[dict] = []
    visited_urls: set[str] = set()
    page_count = 0

    while url:
        if url in visited_urls:
            raise GitHubAPIError(
                "GitHub pagination returned a repeated page link."
            )
        visited_urls.add(url)

        page_count += 1
        if page_count > MAX_PAGES:
            raise GitHubAPIError(
                f"Repository '{owner}/{repo}' has more than {MAX_PAGES} "
                f"pages of pull requests; refusing to synchronize a partial list."
            )

        response = _request_pr_page(session, url, params)
        _raise_for_pr_response(response, owner, repo)
        items.extend(_parse_page_payload(response))

        # The "next" link already contains state/per_page, so query
        # parameters are only sent with the very first request.
        url = (response.links.get("next") or {}).get("url")
        params = None

    return items


def _fetch_pr_details(
    session: requests.Session,
    owner: str,
    repo: str,
    pr_number: int,
) -> dict:
    """
    Fetch individual PR details to obtain additions, deletions, and
    the full reviews list.

    The /pulls/{number} endpoint returns additions and deletions that
    are NOT present in the list endpoint.

    Returns:
        dict with "additions", "deletions", and "reviews_count" keys.
        On failure, returns safe defaults rather than aborting the sync.
    """
    details = {"additions": 0, "deletions": 0, "reviews_count": 0, "reviews": []}

    # Fetch PR detail for additions/deletions
    try:
        detail_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
        resp = session.get(detail_url, timeout=REQUEST_TIMEOUT_SECONDS)
        if resp.ok:
            data = resp.json()
            details["additions"] = data.get("additions", 0)
            details["deletions"] = data.get("deletions", 0)
    except requests.exceptions.RequestException:
        logger.warning(
            "Could not fetch PR #%s details for %s/%s; using defaults.",
            pr_number, owner, repo,
        )

    # Fetch reviews count
    try:
        reviews_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        resp = session.get(reviews_url, timeout=REQUEST_TIMEOUT_SECONDS)
        if resp.ok:
            reviews_data = resp.json()
            if isinstance(reviews_data, list):
                details["reviews_count"] = len(reviews_data)
                details["reviews"] = reviews_data
    except requests.exceptions.RequestException:
        logger.warning(
            "Could not fetch reviews for PR #%s of %s/%s; using 0.",
            pr_number, owner, repo,
        )

    return details


# ---------------------------------------------------------------------------
# Normalization layer
# ---------------------------------------------------------------------------

def _normalize_timestamp(value: Any, field_name: str) -> Optional[str]:
    """
    Validate a GitHub timestamp and return it as an ISO-8601 UTC string.

    ``None`` and empty strings stay ``None`` (an open PR has no
    ``closed_at`` or ``merged_at``). Timestamps without a timezone are
    rejected so a value can never silently be read as local time.

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


def _extract_requested_reviewers(item: dict) -> list[str]:
    """
    Return the login names of requested reviewers (no duplicates).

    Uses the ``requested_reviewers`` list from GitHub's pulls endpoint.
    """
    logins: list[str] = []
    for reviewer in item.get("requested_reviewers") or []:
        login = reviewer.get("login") if isinstance(reviewer, dict) else None
        if login and login not in logins:
            logins.append(login)
    return logins


def _calculate_open_duration_hours(
    created_at: Optional[str],
    closed_at: Optional[str],
    merged_at: Optional[str],
) -> float:
    """
    Calculate how long a PR has been (or was) open, in hours.

    - If merged: duration = merged_at - created_at
    - If closed (not merged): duration = closed_at - created_at
    - If still open: duration = now - created_at

    Returns 0.0 if created_at is None (shouldn't happen but safe default).
    """
    if not created_at:
        return 0.0

    try:
        created = datetime.fromisoformat(created_at)
    except (ValueError, TypeError):
        return 0.0

    end_time = None
    if merged_at:
        try:
            end_time = datetime.fromisoformat(merged_at)
        except (ValueError, TypeError):
            pass
    elif closed_at:
        try:
            end_time = datetime.fromisoformat(closed_at)
        except (ValueError, TypeError):
            pass

    if end_time is None:
        end_time = datetime.now(timezone.utc)

    delta = end_time - created
    hours = delta.total_seconds() / 3600.0
    return round(max(hours, 0.0), 2)


def _determine_pr_state(raw: dict) -> str:
    """
    Determine the effective state of a PR.

    GitHub's pulls API returns state as "open" or "closed".
    Merged PRs have state "closed" but merged_at is not None.
    We normalize to "open", "closed", or "merged".
    """
    if raw.get("merged_at") is not None:
        return "merged"

    state = str(raw.get("state") or "").lower()
    if state in ("open", "closed"):
        return state

    return "open"  # safe default


def _normalize_pr(
    raw: dict,
    repository: dict,
    details: dict,
) -> dict:
    """
    Convert one raw GitHub PR into the dict stored in the database.

    Raises:
        GitHubAPIError: if a required field (number, title, created_at)
            is missing or invalid.
    """
    number = raw.get("number")
    if isinstance(number, bool) or not isinstance(number, int):
        raise GitHubAPIError("GitHub returned a PR without a valid 'number'.")

    title = raw.get("title")
    if not isinstance(title, str):
        raise GitHubAPIError(
            f"GitHub returned PR #{number} without a valid 'title'."
        )

    created_at = _normalize_timestamp(raw.get("created_at"), "created_at")
    if created_at is None:
        raise GitHubAPIError(
            f"GitHub returned PR #{number} without a required created_at timestamp."
        )

    closed_at = _normalize_timestamp(raw.get("closed_at"), "closed_at")
    merged_at = _normalize_timestamp(raw.get("merged_at"), "merged_at")
    state = _determine_pr_state(raw)

    author = raw.get("user")
    author_login = author.get("login") if isinstance(author, dict) else None

    return {
        "number": number,
        "title": title,
        "author": author_login or "Unknown",
        "github_username": author_login,
        "state": state,
        "created_at": created_at,
        "updated_at": _normalize_timestamp(raw.get("updated_at"), "updated_at"),
        "closed_at": closed_at,
        "merged_at": merged_at,
        "requested_reviewers": _extract_requested_reviewers(raw),
        "reviews": details.get("reviews", []),
        "reviews_count": details.get("reviews_count", 0),
        "additions": details.get("additions", 0),
        "deletions": details.get("deletions", 0),
        "open_duration_hours": _calculate_open_duration_hours(
            created_at, closed_at, merged_at
        ),
        "html_url": raw.get("html_url"),
        "repository": repository["full_name"],
        "repository_url": repository["url"],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_github_prs(repo_url: str) -> dict:
    """
    Fetch and normalize all pull requests (open and closed) of a
    GitHub repository. Does not touch the database.

    Returns:
        {
            "repository": {"owner", "name", "full_name", "url"},
            "pull_requests": [normalized PR dicts],
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
    raw_items = _fetch_all_pr_items(session, owner, repo)

    pull_requests: list[dict] = []
    for raw in raw_items:
        pr_number = raw.get("number")
        if not isinstance(pr_number, int):
            continue

        details = _fetch_pr_details(session, owner, repo, pr_number)
        pull_requests.append(_normalize_pr(raw, repository, details))

    return {
        "repository": repository,
        "pull_requests": pull_requests,
    }


def sync_project_prs(project_id: str, repo_url: Optional[str] = None) -> dict:
    """
    Fetch a project's GitHub pull requests and persist them.

    Persistence happens only AFTER GitHub was read completely and
    successfully, so a failed fetch never changes stored data.

    Returns:
        {
            "success": True,
            "status": "synced",
            "project_id": str,
            "repository": {...},
            "fetched_count": int,
            "created_count": int,
            "updated_count": int,
        }

    Raises:
        ValueError: empty project_id or invalid repository URL.
        ProjectNotFoundError: project not in database.
        GitHub*Error: see get_github_prs().
        DatabaseError: the upsert failed.
    """
    if not project_id or not project_id.strip():
        raise ValueError("project_id is required.")

    project = get_project(project_id)
    if not project:
        raise ProjectNotFoundError(f"Project '{project_id}' not found.")

    resolved_url = _resolve_repo_url(project, repo_url)
    result = get_github_prs(resolved_url)
    pull_requests = result["pull_requests"]

    created_count = 0
    updated_count = 0

    for pr_data in pull_requests:
        try:
            upsert_pull_request(project_id, pr_data)
            # upsert_pull_request handles insert vs update internally
            # We count all as processed; the upsert is idempotent.
            created_count += 1
        except DatabaseError:
            # Log but continue — one failed PR should not stop the sync
            logger.error(
                "Failed to upsert PR #%s for project %s",
                pr_data.get("number"), project_id,
            )
            raise

    logger.info(
        "PR sync for project %s: fetched=%d persisted=%d",
        project_id,
        len(pull_requests),
        created_count,
    )

    return {
        "success": True,
        "status": "synced",
        "project_id": project_id,
        "repository": result["repository"],
        "fetched_count": len(pull_requests),
        "created_count": created_count,
        "updated_count": updated_count,
    }


def get_prs_for_project(
    project_id: str,
    state: Optional[str] = None,
) -> list[dict]:
    """
    Return the persisted pull requests of a project (never calls GitHub).

    Args:
        project_id: Project ObjectId string.
        state: Optional ``"open"``, ``"closed"``, or ``"merged"`` filter.

    Raises:
        ValueError: empty project_id or unknown state.
        DatabaseError: the database read failed.
    """
    if not project_id or not project_id.strip():
        raise ValueError("project_id is required.")

    if state is not None and state not in VALID_PR_STATES:
        raise ValueError("state must be 'open', 'closed', or 'merged'.")

    documents = get_project_prs(project_id, state=state)
    return [_present_pr(document) for document in documents]


def _present_pr(document: dict) -> dict:
    """Shape a stored PR document into the public API representation."""
    reviews = document.get("reviews") or []
    reviews_count = document.get("reviews_count")
    if reviews_count is None:
        reviews_count = len(reviews) if isinstance(reviews, list) else 0

    return {
        "id": document.get("_id"),
        "project_id": document.get("projectId"),
        "number": document.get("number"),
        "title": document.get("title"),
        "author": document.get("author"),
        "state": document.get("state"),
        "created_at": document.get("created_at"),
        "updated_at": document.get("updated_at"),
        "closed_at": document.get("closed_at"),
        "merged_at": document.get("merged_at"),
        "requested_reviewers": document.get("requested_reviewers") or [],
        "reviews_count": reviews_count,
        "additions": document.get("additions", 0),
        "deletions": document.get("deletions", 0),
        "open_duration_hours": document.get("open_duration_hours", 0.0),
        "html_url": document.get("html_url"),
    }

