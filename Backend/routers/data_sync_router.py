
"""
FastAPI router for Contributor and Commit synchronization.

Endpoints:
    GET  /api/projects/{project_id}/contributors
    POST /api/projects/{project_id}/sync-contributors
    GET  /api/projects/{project_id}/commits
    POST /api/projects/{project_id}/sync-commits
    GET  /api/projects/{project_id}/issues
    POST /api/projects/{project_id}/sync-issues
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from Backend.auth.dependencies import get_current_user
from Backend.auth.roles import Role, require_role
from Backend.externalservies.commit_service import (
    get_commits_for_project,
    sync_project_commits,
)
from Backend.externalservies.contributor_service import (
    ProjectNotFoundError,
    ProjectRepoNotConfiguredError,
    RepoMismatchError,
    sync_project_contributors,
)
from Backend.externalservies.github_commits import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubBranchNotFoundError,
    GitHubRepoNotFoundError,
    GitHubTokenMissingError,
)
from Backend.externalservies.github_issues import (
    GitHubPermissionError,
    GitHubRateLimitError,
    get_issues_for_project,
    sync_project_issues,
)
from Backend.persistence import get_project, get_project_contributors
from Backend.persistence import DatabaseError
from Backend.routers.project_router import (
    _get_user_id,
    _is_project_member,
    _parse_object_id,
)

router = APIRouter(prefix="/api/projects", tags=["Data Sync"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class SyncContributorsRequest(BaseModel):
    repo_url: Optional[str] = None


class SyncCommitsRequest(BaseModel):
    repo_url: Optional[str] = None
    branch: Optional[str] = None
    max_commits: int = 100


class SyncIssuesRequest(BaseModel):
    repo_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Response models (issues)
# ---------------------------------------------------------------------------

class IssueResponse(BaseModel):
    """Public representation of one persisted GitHub issue."""

    id: str
    project_id: str
    github_id: int
    number: int
    title: str
    state: str
    assignees: List[str] = []
    labels: List[str] = []
    comments: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    closed_at: Optional[str] = None
    html_url: Optional[str] = None
    author: Optional[str] = None
    repository: Optional[str] = None


class SyncIssuesResponse(BaseModel):
    """Summary returned after a successful issue synchronization."""

    success: bool
    status: str
    project_id: str
    repository: dict
    fetched_count: int
    pull_requests_skipped: int
    persisted_count: int
    created_count: int
    updated_count: int


# ---------------------------------------------------------------------------
# Shared authorization helper
# ---------------------------------------------------------------------------

def _require_project_member(
    project_id: str,
    current_user: dict,
) -> dict:
    """Require an authenticated project owner or member."""
    user_id = _get_user_id(current_user)

    project = get_project(project_id)

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Project not found.",
        )

    if not _is_project_member(project, user_id):
        raise HTTPException(
            status_code=403,
            detail="Access denied. You are not a member of this project.",
        )

    return project


# ---------------------------------------------------------------------------
# Shared error mapper
# ---------------------------------------------------------------------------

def _map_github_errors(exc: Exception) -> HTTPException:
    """Convert service-layer exceptions to appropriate HTTP responses."""
    if isinstance(exc, ProjectNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))

    if isinstance(
        exc,
        (ProjectRepoNotConfiguredError, RepoMismatchError, ValueError),
    ):
        return HTTPException(status_code=400, detail=str(exc))

    if isinstance(exc, GitHubTokenMissingError):
        return HTTPException(
            status_code=500,
            detail="GitHub token is not configured on the server.",
        )

    if isinstance(exc, GitHubAuthError):
        return HTTPException(
            status_code=401,
            detail="GitHub authentication failed. Check the configured token.",
        )

    if isinstance(exc, (GitHubRepoNotFoundError, GitHubBranchNotFoundError)):
        return HTTPException(status_code=404, detail=str(exc))

    if isinstance(exc, GitHubRateLimitError):
        return HTTPException(status_code=429, detail=str(exc))

    if isinstance(exc, GitHubPermissionError):
        return HTTPException(status_code=403, detail=str(exc))

    if isinstance(exc, GitHubAPIError):
        return HTTPException(status_code=502, detail=str(exc))

    if isinstance(exc, DatabaseError):
        return HTTPException(
            status_code=503,
            detail=str(exc),
        )

    # For any other unexpected exception, return a generic 500 without
    # leaking internal implementation details to the client.
    return HTTPException(
        status_code=500,
        detail="An unexpected server error occurred. Please try again later.",
    )


# ---------------------------------------------------------------------------
# Contributor endpoints
# ---------------------------------------------------------------------------

@router.get("/{project_id}/contributors", summary="List project contributors")
def get_contributors(
    project_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Retrieve stored contributors for a project.

    Requires authentication and verified project membership.
    """
    _require_project_member(project_id, current_user)
    return get_project_contributors(project_id)


@router.post(
    "/{project_id}/sync-contributors",
    summary="Sync contributors from GitHub",
)
def sync_contributors(
    project_id: str,
    request: SyncContributorsRequest,
    current_user: dict = Depends(
        require_role(Role.ADMIN, Role.PROJECT_MANAGER)
    ),
):
    """
    Sync contributors from GitHub.

    Requires authentication and verified project membership.
    """
    _require_project_member(project_id, current_user)

    try:
        return sync_project_contributors(
            project_id=project_id,
            repo_url=request.repo_url,
        )
    except Exception as exc:
        raise _map_github_errors(exc)


# ---------------------------------------------------------------------------
# Commit endpoints
# ---------------------------------------------------------------------------

@router.get("/{project_id}/commits", summary="List project commits")
def get_commits(
    project_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Retrieve stored commits for a project.

    Requires authentication and verified project membership.
    """
    _require_project_member(project_id, current_user)

    try:
        return get_commits_for_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{project_id}/sync-commits", summary="Sync commits from GitHub")
def sync_commits(
    project_id: str,
    request: SyncCommitsRequest,
    current_user: dict = Depends(
        require_role(Role.ADMIN, Role.PROJECT_MANAGER)
    ),
):
    """
    Retrieve commits from GitHub and persist them.

    Requires authentication and verified project membership.
    """
    _require_project_member(project_id, current_user)

    try:
        return sync_project_commits(
            project_id=project_id,
            repo_url=request.repo_url,
            branch=request.branch,
            max_commits=request.max_commits,
        )
    except Exception as exc:
        raise _map_github_errors(exc)


# ---------------------------------------------------------------------------
# Issue endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/{project_id}/issues",
    response_model=List[IssueResponse],
    summary="List project issues",
)
def get_issues(
    project_id: str,
    state: Optional[str] = Query(
        default=None,
        pattern="^(open|closed)$",
        description="Optional filter: open or closed.",
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Retrieve the issues stored for a project (never calls GitHub).

    Requires authentication and verified project membership.
    """
    _parse_object_id(project_id)
    _require_project_member(project_id, current_user)

    try:
        return get_issues_for_project(project_id, state=state)
    except Exception as exc:
        raise _map_github_errors(exc)

    # EXPLANATION (get_issues):
    # Order of checks: valid ID format (400) -> project exists (404) -> user
    # is a member (403) -> read local database. The "state" query parameter
    # is validated by FastAPI itself (422 for anything but open/closed), and
    # response_model guarantees only the documented fields are returned.


@router.post(
    "/{project_id}/sync-issues",
    response_model=SyncIssuesResponse,
    summary="Sync issues from GitHub",
)
def sync_issues(
    project_id: str,
    request: Optional[SyncIssuesRequest] = None,
    current_user: dict = Depends(
        require_role(Role.ADMIN, Role.PROJECT_MANAGER)
    ),
):
    """
    Fetch all open and closed issues (not pull requests) from GitHub and
    store them with one batch upsert.

    Requires an admin or project-manager role and project membership.
    The request body is optional; the project's configured repository is
    used unless a matching repo_url is supplied.
    """
    _parse_object_id(project_id)
    _require_project_member(project_id, current_user)

    try:
        return sync_project_issues(
            project_id=project_id,
            repo_url=request.repo_url if request else None,
        )
    except Exception as exc:
        raise _map_github_errors(exc)

    # EXPLANATION (sync_issues):
    # Same security model as sync-commits: only admins/project managers who
    # belong to the project may trigger a sync. Every failure from the
    # service (missing repo, GitHub errors, database errors) is converted by
    # the shared _map_github_errors, so users get proper 4xx/5xx codes and
    # never a stack trace.
