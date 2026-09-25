import os
import requests
from typing import Optional
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load GITHUB_TOKEN from .env file (located in the project root, one level above Backend/)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class GitHubTokenMissingError(Exception):
    """Raised when GITHUB_TOKEN is not set in the environment."""
    pass


class GitHubAuthError(Exception):
    """Raised when the provided GITHUB_TOKEN is invalid or expired."""
    pass


class GitHubRepoNotFoundError(Exception):
    """Raised when the repository cannot be found or is not accessible."""
    pass


class GitHubBranchNotFoundError(Exception):
    """Raised when the specified branch does not exist in the repository."""
    pass


class GitHubAPIError(Exception):
    """Raised for unexpected GitHub API or network failures."""
    pass


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _parse_github_url(repo_url: str) -> tuple[str, str]:
    """
    Parses a GitHub repository URL and extracts the owner and repo name.

    Args:
        repo_url: Full GitHub URL (e.g. https://github.com/owner/repo)

    Returns:
        Tuple of (owner, repo_name)

    Raises:
        ValueError: If the URL is not a valid GitHub repository URL.
    """
    parsed = urlparse(repo_url.strip())

    if parsed.netloc not in ("github.com", "www.github.com"):
        raise ValueError(
            f"Invalid GitHub URL '{repo_url}': host must be github.com"
        )

    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(path_parts) < 2:
        raise ValueError(
            f"Invalid GitHub URL '{repo_url}': must contain owner and repository name"
        )

    owner = path_parts[0]
    repo = path_parts[1]

    # Strip .git suffix if present (e.g. https://github.com/owner/repo.git)
    if repo.endswith(".git"):
        repo = repo[:-4]

    return owner, repo


def _get_authenticated_session() -> requests.Session:
    """
    Creates a requests.Session pre-configured with the GitHub token.

    Returns:
        Authenticated requests.Session

    Raises:
        GitHubTokenMissingError: If GITHUB_TOKEN is not set.
    """
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise GitHubTokenMissingError(
            "GITHUB_TOKEN is not set. Add it to your .env file as: GITHUB_TOKEN=<your_token>"
        )

    session = requests.Session()
    session.headers.update({
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    return session


def _fetch_repo_info(session: requests.Session, owner: str, repo: str) -> dict:
    """
    Fetches repository metadata from GitHub API.

    Returns:
        Raw repository info dict from GitHub.

    Raises:
        GitHubAuthError: On 401 Unauthorized.
        GitHubRepoNotFoundError: On 404 Not Found.
        GitHubAPIError: On other API failures.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        response = session.get(url, timeout=10)
    except requests.exceptions.RequestException as exc:
        raise GitHubAPIError(f"Network failure while fetching repo info: {exc}") from exc

    if response.status_code == 401:
        raise GitHubAuthError("Invalid or expired GITHUB_TOKEN.")
    if response.status_code == 404:
        raise GitHubRepoNotFoundError(
            f"Repository '{owner}/{repo}' not found or is not accessible."
        )
    if not response.ok:
        raise GitHubAPIError(
            f"GitHub API error {response.status_code} while fetching repo info."
        )

    return response.json()


def _fetch_commits(
    session: requests.Session,
    owner: str,
    repo: str,
    branch: str,
    max_commits: int,
) -> list[dict]:
    """
    Fetches the list of commits from a branch.

    Returns:
        List of raw commit objects from GitHub API.

    Raises:
        GitHubBranchNotFoundError: If the branch does not exist.
        GitHubAPIError: On other API failures.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    params = {"sha": branch, "per_page": min(max_commits, 100)}

    try:
        response = session.get(url, params=params, timeout=10)
    except requests.exceptions.RequestException as exc:
        raise GitHubAPIError(f"Network failure while fetching commits: {exc}") from exc

    if response.status_code == 404:
        raise GitHubBranchNotFoundError(
            f"Branch '{branch}' not found in '{owner}/{repo}'."
        )
    if response.status_code == 403 and "rate limit" in response.text.lower():
        raise GitHubAPIError("GitHub API rate limit exceeded. Try again later.")
    if not response.ok:
        raise GitHubAPIError(
            f"GitHub API error {response.status_code} while fetching commits."
        )

    return response.json()[:max_commits]


def _fetch_commit_stats(session: requests.Session, owner: str, repo: str, sha: str) -> dict:
    """
    Fetches additions/deletions stats for a single commit.
    Returns a dict with 'additions', 'deletions', 'total_changes'.
    Falls back to zeros on any failure (non-fatal).
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
    try:
        response = session.get(url, timeout=10)
        if response.ok:
            stats = response.json().get("stats", {})
            return {
                "additions": stats.get("additions", 0),
                "deletions": stats.get("deletions", 0),
                "total_changes": stats.get("total", 0),
            }
    except requests.exceptions.RequestException:
        pass  # Non-fatal: return zeros

    return {"additions": 0, "deletions": 0, "total_changes": 0}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_github_commit_history(
    repo_url: str,
    branch: Optional[str] = None,
    max_commits: int = 30,
) -> dict:
    """
    Retrieves commit history from a GitHub repository.

    Args:
        repo_url (str): Full GitHub repository URL (e.g. https://github.com/owner/repo).
        branch (str | None): Branch to retrieve commits from.
                             If None, the repository's default branch is used.
        max_commits (int): Maximum number of commits to return. Default: 30.

    Returns:
        dict: Structured response with repository info, branch info, and commit list.

        {
            "success": True,
            "repository": {
                "owner": str,
                "name": str,
                "full_name": str,
                "url": str
            },
            "branch": {
                "selected": str,       # Branch actually used
                "default": str,        # Repo's default branch
                "was_configured": bool # True if caller passed a branch
            },
            "commit_count": int,
            "commits": [
                {
                    "sha": str,
                    "short_sha": str,
                    "author": str,
                    "github_username": str | None,
                    "timestamp": str,   # ISO 8601 UTC
                    "message": str,
                    "additions": int,
                    "deletions": int,
                    "total_changes": int
                },
                ...
            ]
        }

    Raises:
        ValueError: For an invalid GitHub URL or non-positive max_commits.
        GitHubTokenMissingError: If GITHUB_TOKEN is not configured.
        GitHubAuthError: If GITHUB_TOKEN is invalid or expired.
        GitHubRepoNotFoundError: If the repository is not found.
        GitHubBranchNotFoundError: If the specified branch is not found.
        GitHubAPIError: For GitHub API or network failures.
    """
    if max_commits <= 0:
        raise ValueError("max_commits must be a positive integer.")

    # Parse URL → (owner, repo)
    owner, repo_name = _parse_github_url(repo_url)

    # Build authenticated session (raises GitHubTokenMissingError if no token)
    session = _get_authenticated_session()

    # Fetch repo metadata to confirm it exists and get default branch
    repo_info = _fetch_repo_info(session, owner, repo_name)
    default_branch: str = repo_info["default_branch"]

    # Determine which branch to query
    was_configured = branch is not None
    selected_branch = branch if was_configured else default_branch

    # Fetch list of commits
    raw_commits = _fetch_commits(session, owner, repo_name, selected_branch, max_commits)

    # Normalize each commit
    commits = []
    for raw in raw_commits:
        sha: str = raw.get("sha", "")
        commit_data: dict = raw.get("commit", {})
        author_data: dict = commit_data.get("author", {})
        github_author: dict = raw.get("author") or {}

        stats = _fetch_commit_stats(session, owner, repo_name, sha)

        commits.append({
            "sha": sha,
            "short_sha": sha[:7],
            "author": author_data.get("name", "Unknown"),
            "github_username": github_author.get("login"),
            "timestamp": author_data.get("date"),
            "message": commit_data.get("message", ""),
            "additions": stats["additions"],
            "deletions": stats["deletions"],
            "total_changes": stats["total_changes"],
        })

    return {
        "success": True,
        "repository": {
            "owner": owner,
            "name": repo_name,
            "full_name": f"{owner}/{repo_name}",
            "url": repo_info.get("html_url", repo_url),
        },
        "branch": {
            "selected": selected_branch,
            "default": default_branch,
            "was_configured": was_configured,
        },
        "commit_count": len(commits),
        "commits": commits,
    }
