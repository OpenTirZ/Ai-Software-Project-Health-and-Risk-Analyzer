import pytest
import requests
from unittest.mock import MagicMock
from github_commits import get_github_commit_history, parse_github_url, GitHubAPIError

def test_parse_github_url_valid():
    assert parse_github_url("https://github.com/owner/repo") == ("owner", "repo")
    assert parse_github_url("https://github.com/owner/repo.git") == ("owner", "repo")
    assert parse_github_url("https://www.github.com/owner/repo/") == ("owner", "repo")

def test_parse_github_url_invalid():
    with pytest.raises(ValueError, match="Host must be github.com"):
        parse_github_url("https://gitlab.com/owner/repo")
    with pytest.raises(ValueError, match="Must contain owner and repository"):
        parse_github_url("https://github.com/owner")

def test_get_github_commit_history_success(mocker):
    # Mock requests.Session
    mock_session = MagicMock()
    
    # First call is the list of commits
    mock_list_response = MagicMock()
    mock_list_response.status_code = 200
    mock_list_response.json.return_value = [
        {
            "sha": "12345",
            "commit": {
                "author": {"name": "Test User", "email": "test@example.com", "date": "2023-10-01T12:00:00Z"},
                "message": "Initial commit"
            },
            "author": {"login": "testuser"},
            "html_url": "https://github.com/owner/repo/commit/12345"
        }
    ]
    
    # Second call is the individual commit details for stats
    mock_detail_response = MagicMock()
    mock_detail_response.status_code = 200
    mock_detail_response.json.return_value = {
        "stats": {"additions": 10, "deletions": 5, "total": 15}
    }
    
    def side_effect(url, **kwargs):
        if url.endswith("/commits"):
            return mock_list_response
        elif url.endswith("/12345"):
            return mock_detail_response
        return MagicMock()
        
    mock_session.get.side_effect = side_effect
    mocker.patch("requests.Session", return_value=mock_session)
    
    result = get_github_commit_history("https://github.com/owner/repo", max_commits=1)
    
    assert len(result) == 1
    assert result[0]["sha"] == "12345"
    assert result[0]["author_name"] == "Test User"
    assert result[0]["timestamp"] == "2023-10-01T12:00:00Z"
    assert result[0]["stats"]["total"] == 15

def test_get_github_commit_history_repo_not_found(mocker):
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_session.get.return_value = mock_response
    mocker.patch("requests.Session", return_value=mock_session)
    
    with pytest.raises(GitHubAPIError, match="not found"):
        get_github_commit_history("https://github.com/owner/repo")

def test_get_github_commit_history_rate_limit(mocker):
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.text = "API rate limit exceeded"
    mock_session.get.return_value = mock_response
    mocker.patch("requests.Session", return_value=mock_session)
    
    with pytest.raises(GitHubAPIError, match="rate limit"):
        get_github_commit_history("https://github.com/owner/repo")

def test_get_github_commit_history_invalid_max_commits():
    with pytest.raises(ValueError, match="positive integer"):
        get_github_commit_history("https://github.com/owner/repo", max_commits=0)

def test_get_github_commit_history_branch_params(mocker):
    mock_session = MagicMock()
    
    mock_list_response = MagicMock()
    mock_list_response.status_code = 200
    mock_list_response.json.return_value = []
    
    mock_session.get.return_value = mock_list_response
    mocker.patch("requests.Session", return_value=mock_session)
    
    get_github_commit_history("https://github.com/owner/repo", branch="feature-branch", max_commits=5)
    
    # Check that params were set correctly
    mock_session.get.assert_called_with(
        "https://api.github.com/repos/owner/repo/commits", 
        params={"per_page": 5, "sha": "feature-branch"}, 
        timeout=10
    )
