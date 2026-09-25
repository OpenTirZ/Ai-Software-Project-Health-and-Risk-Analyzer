import os
import requests
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse

class GitHubAPIError(Exception):
    """Custom exception for GitHub API errors."""
    pass

def parse_github_url(repo_url: str) -> tuple[str, str]:
    """
    Parses a GitHub URL and returns the owner and repository name.
    Raises ValueError if the URL is invalid.
    """
    parsed = urlparse(repo_url)
    if parsed.netloc not in ["github.com", "www.github.com"]:
        raise ValueError("Invalid GitHub URL: Host must be github.com")
    
    path_parts = parsed.path.strip("/").split("/")
    if len(path_parts) < 2:
        raise ValueError("Invalid GitHub URL: Must contain owner and repository")
    
    owner = path_parts[0]
    repo = path_parts[1]
    
    # Remove .git extension if present
    if repo.endswith(".git"):
        repo = repo[:-4]
        
    return owner, repo

def get_github_commit_history(
    repo_url: str,
    branch: Optional[str] = None,
    max_commits: int = 30
) -> List[Dict[str, Any]]:
    """
    Retrieves commit history from a GitHub repository for the Project Health Analyzer.
    
    Args:
        repo_url (str): The full URL of the GitHub repository (e.g., https://github.com/owner/repo)
        branch (str, optional): The branch to retrieve commits from. Defaults to None (repository default).
        max_commits (int): The maximum number of commits to retrieve. Defaults to 30.
        
    Returns:
        List[Dict[str, Any]]: A structured list of commits, containing author info, timestamps, 
                              and the size of changes (additions, deletions, total).
    """
    if max_commits <= 0:
        raise ValueError("max_commits must be a positive integer.")
    
    owner, repo = parse_github_url(repo_url)
    
    token = os.environ.get("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github.v3+json"
    }
    if token:
        headers["Authorization"] = f"token {token}"
        
    session = requests.Session()
    session.headers.update(headers)
    
    base_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    
    params = {"per_page": min(max_commits, 100)}
    if branch:
        params["sha"] = branch
        
    try:
        response = session.get(base_url, params=params, timeout=10)
        
        if response.status_code == 404:
            raise GitHubAPIError(f"Repository or branch not found: {repo_url}")
        elif response.status_code == 403 and "rate limit" in response.text.lower():
            raise GitHubAPIError("GitHub API rate limit exceeded.")
        
        response.raise_for_status()
        commits_data = response.json()
        
    except requests.exceptions.RequestException as e:
        raise GitHubAPIError(f"Network or request failure: {str(e)}")
        
    # Slice the results to ensure we don't return more than max_commits
    commits_data = commits_data[:max_commits]
    
    result = []
    for commit_obj in commits_data:
        sha = commit_obj.get("sha")
        commit_details = commit_obj.get("commit", {})
        author_info = commit_details.get("author", {})
        
        author_name = author_info.get("name")
        author_email = author_info.get("email")
        timestamp = author_info.get("date")
        message = commit_details.get("message")
        
        author_user = commit_obj.get("author") or {}
        author_username = author_user.get("login")
        
        # To get the "size of changes", we must fetch the individual commit.
        # This adds API overhead but accurately fulfills FR-1 tracking constraints.
        stats = {"additions": 0, "deletions": 0, "total": 0}
        
        try:
            commit_resp = session.get(f"{base_url}/{sha}", timeout=10)
            if commit_resp.status_code == 200:
                individual_commit_data = commit_resp.json()
                fetched_stats = individual_commit_data.get("stats")
                if fetched_stats:
                    stats = fetched_stats
            elif commit_resp.status_code == 403 and "rate limit" in commit_resp.text.lower():
                raise GitHubAPIError("GitHub API rate limit exceeded while fetching commit details.")
        except requests.exceptions.RequestException:
            # Leave stats as 0 if the individual commit fetch fails non-fatally 
            # (e.g., occasional timeout) to still return the rest of the commit data.
            pass
            
        result.append({
            "sha": sha,
            "author_name": author_name,
            "author_email": author_email,
            "author_username": author_username,
            "message": message,
            "timestamp": timestamp,
            "url": commit_obj.get("html_url"),
            "stats": stats
        })
        
    return result
