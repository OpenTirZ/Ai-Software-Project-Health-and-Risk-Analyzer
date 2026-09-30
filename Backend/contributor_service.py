"""
Contributor Service
-------------------
Orchestrates contributor retrieval from GitHub and persistence to MongoDB.

Flow:
    project_id
      → Verify project exists and get connected repo URL
      → GitHub API (GET /repos/{owner}/{repo}/contributors)
      → Parse/normalize contributor data
      → Upsert each contributor into MongoDB (duplicate-safe)
      → Return sync summary
"""

from pymongo.errors import DuplicateKeyError

from Backend.github_commits import (
    get_github_contributors,
    GitHubTokenMissingError,
    GitHubAuthError,
    GitHubRepoNotFoundError,
    GitHubAPIError,
)
from Backend.persistence import (
    get_project,
    upsert_contributor,
    get_project_contributors,
)


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class ProjectNotFoundError(Exception):
    """Raised when the specified project does not exist."""
    pass


class ProjectRepoNotConfiguredError(Exception):
    """Raised when the project has no GitHub repository configured."""
    pass


class RepoMismatchError(Exception):
    """Raised when the provided repo_url does not match the project's configured repository."""
    pass


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _normalize_repo_url(url: str) -> str:
    """Normalize a GitHub URL for comparison (lowercase, strip trailing slash and .git)."""
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    return url.lower()


def _resolve_repo_url(project: dict, repo_url: str | None) -> str:
    """
    Determine the repository URL to use for contributor sync.

    Priority:
        1. If the project has a stored repo_url, use it.
           If caller also provided repo_url, validate they match.
        2. If the project has no repo_url, use the provided one.
        3. If neither is available, raise an error.

    Returns:
        The resolved repository URL.

    Raises:
        RepoMismatchError: If both URLs exist and don't match.
        ProjectRepoNotConfiguredError: If no URL can be resolved.
    """
    stored_url = (project.get("repo_url") or "").strip()

    if stored_url and repo_url:
        if _normalize_repo_url(stored_url) != _normalize_repo_url(repo_url):
            raise RepoMismatchError(
                "Provided repo_url does not match the project's configured "
                "repository. Use the project's repository or update the "
                "project configuration."
            )

    resolved = stored_url or (repo_url.strip() if repo_url else "")
    if not resolved:
        raise ProjectRepoNotConfiguredError(
            f"Project '{project.get('_id')}' has no GitHub repository configured. "
            f"Update the project with a repo_url first."
        )

    return resolved


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sync_project_contributors(project_id: str, repo_url: str | None = None) -> dict:
    """
    Retrieves contributors from a GitHub repository and syncs them
    to the database for the given project.

    Each contributor is upserted: new contributors are created,
    existing ones are updated with the latest data from GitHub.

    Args:
        project_id: MongoDB ObjectId string of the project.
        repo_url:   Optional GitHub repository URL override.
                    If omitted, uses the project's configured repo_url.
                    If provided alongside a project with a stored repo_url,
                    they must match.

    Returns:
        dict with sync results:
        {
            "success": True,
            "repository": { ... },
            "project_id": str,
            "synced_count": int,
            "contributors": [
                {
                    "contributor_id": str,
                    "github_username": str,
                    "contributions": int,
                },
                ...
            ]
        }

    Raises:
        ValueError: For empty project_id.
        ProjectNotFoundError: If the project does not exist.
        ProjectRepoNotConfiguredError: If no repository URL is available.
        RepoMismatchError: If repo_url doesn't match project config.
        GitHubTokenMissingError: If GITHUB_TOKEN is not set.
        GitHubAuthError: If token is invalid or expired.
        GitHubRepoNotFoundError: If the repository is not found.
        GitHubAPIError: For other GitHub API or network failures.
    """
    if not project_id or not project_id.strip():
        raise ValueError("project_id is required.")

    # Verify project exists
    project = get_project(project_id)
    if not project:
        raise ProjectNotFoundError(f"Project '{project_id}' not found.")

    # Resolve repository URL from project config and/or provided URL
    resolved_url = _resolve_repo_url(project, repo_url)

    # Fetch contributors from GitHub API
    result = get_github_contributors(resolved_url)

    # Upsert each contributor into the database for this project
    synced = []
    for contributor in result["contributors"]:
        try:
            contributor_id = upsert_contributor(project_id, contributor)
        except DuplicateKeyError:
            # Unique index guard — should not occur because upsert uses
            # the same (projectId, github_username) filter, but handled
            # defensively in case of a race condition.
            continue
        synced.append({
            "contributor_id": contributor_id,
            "github_username": contributor["github_username"],
            "contributions": contributor["contributions"],
        })

    return {
        "success": True,
        "repository": result["repository"],
        "project_id": project_id,
        "synced_count": len(synced),
        "contributors": synced,
    }
