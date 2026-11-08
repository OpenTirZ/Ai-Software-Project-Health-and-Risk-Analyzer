"""
GitHub Issue Synchronization Service
------------------------------------

Fetches the issues of a project's GitHub repository, normalizes them and
persists them to MongoDB with ONE batch upsert.

Flow:
    project_id
        -> Verify the project exists
        -> Resolve and validate the repository URL
        -> GET /repos/{owner}/{repo}/issues?state=all (follow Link pagination)
        -> Drop pull requests (any item containing the "pull_request" key)
        -> Normalize every genuine issue
        -> bulk_upsert_issues() (single bulk write, idempotent)
        -> Return counts that MongoDB itself confirmed

Public functions:
    get_github_issues(repo_url)          fetch + normalize, no database access
    sync_project_issues(project_id, ...) full fetch + persist workflow
    get_issues_for_project(project_id)   read persisted issues, never calls GitHub
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
from Backend.persistence import (
    bulk_upsert_issues,
    get_project,
    list_project_issues,
)

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
ISSUES_PER_PAGE = 100          # GitHub's maximum page size
REQUEST_TIMEOUT_SECONDS = 10   # same timeout the other GitHub services use
MAX_PAGES = 500                # safety cap: 500 pages * 100 = 50,000 issues
VALID_ISSUE_STATES = ("open", "closed")


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------
# Both subclass the existing GitHubAPIError, so any code that already catches
# GitHubAPIError keeps working, while the router can still give these two
# situations a more precise HTTP status.

class GitHubRateLimitError(GitHubAPIError):
    """Raised when GitHub refuses requests because the rate limit is used up."""
    pass


class GitHubPermissionError(GitHubAPIError):
    """Raised when the token is valid but lacks permission for the repository."""
    pass


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

def _raise_for_issue_response(
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
        GitHubAPIError: 410 (issues disabled) and every other non-2xx status.
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
                f"The GitHub token has no permission to read issues of "
                f"'{owner}/{repo}'.",
            )
        )

    if status_code == 404:
        raise GitHubRepoNotFoundError(
            f"Repository '{owner}/{repo}' not found or is not accessible."
        )

    if status_code == 410:
        raise GitHubAPIError(
            f"Issues are disabled for repository '{owner}/{repo}'."
        )

    if not response.ok:
        raise GitHubAPIError(
            _extract_github_error(
                response,
                f"GitHub API error {status_code} while fetching issues.",
            )
        )

    # EXPLANATION (_raise_for_issue_response):
    # One place that decides what every GitHub status code means. The order
    # matters: a 403 is first checked for "rate limit" (temporary, retry
    # later) and only then treated as a permission problem (permanent until
    # the token changes). Nothing here ever prints or stores the token.


def _request_issue_page(
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
            "Request to GitHub timed out while fetching issues."
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        raise GitHubAPIError(
            "Could not connect to GitHub while fetching issues."
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise GitHubAPIError(
            f"Network failure while fetching issues: {exc}"
        ) from exc

    # EXPLANATION (_request_issue_page):
    # Keeps every network problem in one spot. Callers only ever see
    # GitHubAPIError, never a raw requests exception, so the router needs
    # just one mapping. The original exception stays attached via "from exc".


def _parse_page_payload(response: requests.Response) -> list[dict]:
    """
    Decode one page of the issues response.

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
            "GitHub returned an unexpected response while fetching issues."
        )

    if any(not isinstance(item, dict) for item in payload):
        raise GitHubAPIError(
            "GitHub returned malformed issue data."
        )

    return payload

    # EXPLANATION (_parse_page_payload):
    # A 200 status does not guarantee usable data (proxies and outages can
    # return HTML or error objects). Validating the shape here means a broken
    # page becomes a clear error instead of a crash later or, worse, a fake
    # "0 issues" success.


def _fetch_all_issue_items(
    session: requests.Session,
    owner: str,
    repo: str,
) -> list[dict]:
    """
    Fetch EVERY raw issue/PR item of a repository (state=all, all pages).

    Pagination follows GitHub's ``Link: rel="next"`` header, so repositories
    with more than 100 issues are fully retrieved. If any page fails the
    whole call fails; a partial list is never returned.

    Raises:
        GitHubAPIError (or a subclass): on any HTTP, network, JSON or
            pagination problem, including a pagination loop or a repository
            larger than MAX_PAGES pages.
    """
    url: Optional[str] = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues"
    params: Optional[dict] = {"state": "all", "per_page": ISSUES_PER_PAGE}

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
                f"pages of issues; refusing to synchronize a partial list."
            )

        response = _request_issue_page(session, url, params)
        _raise_for_issue_response(response, owner, repo)
        items.extend(_parse_page_payload(response))

        # The "next" link already contains state/per_page, so query
        # parameters are only sent with the very first request.
        url = (response.links.get("next") or {}).get("url")
        params = None

    return items

    # EXPLANATION (_fetch_all_issue_items):
    # A loop that keeps asking for the next page until GitHub stops
    # providing one. Three guards stop endless loops: a visited-URL set
    # (repeated link), a page cap (absurdly large repo) and the fact that an
    # error on ANY page aborts everything instead of returning half a list.


# ---------------------------------------------------------------------------
# Normalization layer
# ---------------------------------------------------------------------------

def _is_pull_request(item: dict) -> bool:
    """Return True when a GitHub issues-API item is really a pull request."""
    return "pull_request" in item

    # EXPLANATION (_is_pull_request):
    # GitHub's issues endpoint returns pull requests too, marked only by the
    # presence of a "pull_request" key. We test the KEY (not titles, labels
    # or numbers), exactly as GitHub documents it - even if its value is null.


def _normalize_timestamp(value: Any, field_name: str) -> Optional[str]:
    """
    Validate a GitHub timestamp and return it as an ISO-8601 UTC string.

    ``None`` and empty strings stay ``None`` (an open issue has no
    ``closed_at``). Timestamps without a timezone are rejected so a value
    can never silently be read as local time.

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

    # EXPLANATION (_normalize_timestamp):
    # Output is always like "2024-01-02T03:04:05+00:00" - the offset is
    # explicit, so nothing is ambiguous. The same shape is used by the
    # commit data (ISO 8601 UTC strings) and sorts correctly as plain text.


def _extract_assignees(item: dict) -> list[str]:
    """
    Return the assignee logins of an issue (ordered, no duplicates).

    Uses the ``assignees`` list and also the legacy single ``assignee``
    field. Null or malformed entries are ignored.
    """
    candidates = list(item.get("assignees") or [])
    if item.get("assignee"):
        candidates.append(item["assignee"])

    logins: list[str] = []
    for candidate in candidates:
        login = candidate.get("login") if isinstance(candidate, dict) else None
        if login and login not in logins:
            logins.append(login)

    return logins

    # EXPLANATION (_extract_assignees):
    # We store only the login names (a list of strings), which is all the
    # health analysis needs (e.g. "who is overloaded"). "or []" handles
    # GitHub sending null; the duplicate check handles an issue where the
    # legacy "assignee" is also inside "assignees".


def _extract_labels(item: dict) -> list[str]:
    """
    Return the label names of an issue.

    Labels are usually objects with a ``name``; plain strings are accepted
    too. Empty or malformed entries are ignored.
    """
    names: list[str] = []
    for label in item.get("labels") or []:
        name = label.get("name") if isinstance(label, dict) else label
        if isinstance(name, str) and name.strip() and name not in names:
            names.append(name)

    return names

    # EXPLANATION (_extract_labels):
    # Same idea as assignees: a flat list of names. isinstance(name, str)
    # protects against numbers/None sneaking in, so the stored list is always
    # a clean list of strings.


def _normalize_comments_count(value: Any) -> int:
    """
    Return the comments count as a non-negative int (missing/null -> 0).

    Raises:
        GitHubAPIError: if the value is not a whole non-negative number.
    """
    if value is None:
        return 0

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GitHubAPIError("GitHub returned an invalid 'comments' count.")

    return value

    # EXPLANATION (_normalize_comments_count):
    # GitHub already gives the number of comments, so we never download the
    # comments themselves. bool is rejected explicitly because in Python
    # True is also an int and would otherwise become "1 comment".


def _normalize_issue(raw: dict, repository: dict) -> dict:
    """
    Convert one raw GitHub issue into the dict stored in the database.

    Raises:
        GitHubAPIError: if a required field (id, number, title, state,
            created_at, updated_at) is missing or invalid.
    """
    github_id = raw.get("id")
    number = raw.get("number")

    if isinstance(github_id, bool) or not isinstance(github_id, int):
        raise GitHubAPIError("GitHub returned an issue without a valid 'id'.")
    if isinstance(number, bool) or not isinstance(number, int):
        raise GitHubAPIError("GitHub returned an issue without a valid 'number'.")

    title = raw.get("title")
    if not isinstance(title, str):
        raise GitHubAPIError(
            f"GitHub returned issue #{number} without a valid 'title'."
        )

    state = str(raw.get("state") or "").lower()
    if state not in VALID_ISSUE_STATES:
        raise GitHubAPIError(
            f"GitHub returned issue #{number} with an unknown state."
        )

    created_at = _normalize_timestamp(raw.get("created_at"), "created_at")
    updated_at = _normalize_timestamp(raw.get("updated_at"), "updated_at")
    if created_at is None or updated_at is None:
        raise GitHubAPIError(
            f"GitHub returned issue #{number} without required timestamps."
        )

    author = raw.get("user")

    return {
        "github_id": github_id,
        "number": number,
        "title": title,
        "state": state,
        "assignees": _extract_assignees(raw),
        "labels": _extract_labels(raw),
        "comments": _normalize_comments_count(raw.get("comments")),
        "created_at": created_at,
        "updated_at": updated_at,
        "closed_at": _normalize_timestamp(raw.get("closed_at"), "closed_at"),
        "html_url": raw.get("html_url"),
        "author": author.get("login") if isinstance(author, dict) else None,
        "repository": repository["full_name"],
        "repository_url": repository["url"],
    }

    # EXPLANATION (_normalize_issue):
    # Turns GitHub's large, nested JSON into one flat, predictable record.
    # Required fields fail loudly (a half-filled record would corrupt later
    # analysis); optional fields get safe defaults. closed_at stays None for
    # open issues, which is exactly what the requirement asks.


def normalize_issues(
    raw_items: list[dict],
    repository: dict,
) -> tuple[list[dict], int]:
    """
    Remove pull requests and normalize the remaining issues.

    Returns:
        ``(issues, pull_requests_skipped)``
    """
    issues: list[dict] = []
    skipped = 0

    for raw in raw_items:
        if _is_pull_request(raw):
            skipped += 1
            continue
        issues.append(_normalize_issue(raw, repository))

    return issues, skipped

    # EXPLANATION (normalize_issues):
    # The single filtering point. Pull requests are removed BEFORE any
    # normalization, so only genuine issues can ever reach the database, and
    # the skipped count lets the API report how many PRs were ignored.


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_github_issues(repo_url: str) -> dict:
    """
    Fetch and normalize all issues (open and closed) of a GitHub repository.

    Does not touch the database.

    Returns:
        {
            "repository": {"owner", "name", "full_name", "url"},
            "issues": [normalized issue dicts],
            "pull_requests_skipped": int,
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
    raw_items = _fetch_all_issue_items(session, owner, repo)
    issues, skipped = normalize_issues(raw_items, repository)

    return {
        "repository": repository,
        "issues": issues,
        "pull_requests_skipped": skipped,
    }

    # EXPLANATION (get_github_issues):
    # The "pure GitHub" half of the feature: URL -> owner/repo -> download ->
    # normalize. Because it never writes to the database, it can be tested
    # and reused (for example by a future scheduled job) without side effects.


def sync_project_issues(project_id: str, repo_url: Optional[str] = None) -> dict:
    """
    Fetch a project's GitHub issues and persist them with one batch upsert.

    Persistence happens only AFTER GitHub was read completely and
    successfully, so a failed fetch never changes stored data. An empty
    GitHub result stores nothing and deletes nothing.

    Returns:
        {
            "success": True,
            "status": "synced",
            "project_id": str,
            "repository": {...},
            "fetched_count": int,         # genuine issues returned by GitHub
            "pull_requests_skipped": int,
            "persisted_count": int,       # confirmed by MongoDB (new + existing)
            "created_count": int,         # newly inserted
            "updated_count": int,         # existing documents refreshed (matched)
        }

    Raises:
        ValueError: empty project_id or invalid repository URL.
        ProjectNotFoundError, ProjectRepoNotConfiguredError, RepoMismatchError
        GitHub*Error: see get_github_issues().
        DatabaseError: the batch upsert failed.
    """
    if not project_id or not project_id.strip():
        raise ValueError("project_id is required.")

    project = get_project(project_id)
    if not project:
        raise ProjectNotFoundError(f"Project '{project_id}' not found.")

    resolved_url = _resolve_repo_url(project, repo_url)
    result = get_github_issues(resolved_url)
    issues = result["issues"]

    if issues:
        counts = bulk_upsert_issues(project_id, issues)
    else:
        counts = {"matched_count": 0, "modified_count": 0, "upserted_count": 0}

    logger.info(
        "Issue sync for project %s: fetched=%d skipped_prs=%d created=%d",
        project_id,
        len(issues),
        result["pull_requests_skipped"],
        counts["upserted_count"],
    )

    return {
        "success": True,
        "status": "synced",
        "project_id": project_id,
        "repository": result["repository"],
        "fetched_count": len(issues),
        "pull_requests_skipped": result["pull_requests_skipped"],
        "persisted_count": counts["upserted_count"] + counts["matched_count"],
        "created_count": counts["upserted_count"],
        "updated_count": counts["matched_count"],
    }

    # EXPLANATION (sync_project_issues):
    # The orchestrator, in the same style as sync_project_commits. Order is
    # deliberate: validate -> find project -> resolve repo -> fetch -> save.
    # The success dict is built only after bulk_upsert_issues returned, so
    # "synced" always means the data really is in the database.


def get_issues_for_project(
    project_id: str,
    state: Optional[str] = None,
) -> list[dict]:
    """
    Return the persisted issues of a project (never calls GitHub).

    Args:
        project_id: Project ObjectId string.
        state: Optional ``"open"`` or ``"closed"`` filter.

    Raises:
        ValueError: empty project_id, invalid ObjectId or unknown state.
        DatabaseError: the database read failed.
    """
    if not project_id or not project_id.strip():
        raise ValueError("project_id is required.")

    if state is not None and state not in VALID_ISSUE_STATES:
        raise ValueError("state must be 'open' or 'closed'.")

    documents = list_project_issues(project_id, state=state)
    return [_present_issue(document) for document in documents]

    # EXPLANATION (get_issues_for_project):
    # Read-only path used by GET /issues. It validates the input, asks the
    # persistence layer for this project's rows and reshapes them. There is
    # no GitHub call here, so reading is fast and works even when GitHub is
    # down or rate limited.


def _present_issue(document: dict) -> dict:
    """Shape a stored issue document into the public API representation."""
    return {
        "id": document.get("_id"),
        "project_id": document.get("projectId"),
        "github_id": document.get("github_id"),
        "number": document.get("number"),
        "title": document.get("title"),
        "state": document.get("state"),
        "assignees": document.get("assignees") or [],
        "labels": document.get("labels") or [],
        "comments": document.get("comments") or 0,
        "created_at": document.get("created_at"),
        "updated_at": document.get("updated_at"),
        "closed_at": document.get("closed_at"),
        "html_url": document.get("html_url"),
        "author": document.get("author"),
        "repository": document.get("repository"),
    }

    # EXPLANATION (_present_issue):
    # An explicit whitelist of public fields. Internal bookkeeping such as
    # synced_at or repository_url is not exposed by accident, and old
    # documents missing a field still produce a complete, predictable shape.
