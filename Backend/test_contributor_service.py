"""
Tests for contributor retrieval, project mapping, and persistence.

Covers:
  1.  Successful contributor retrieval from GitHub API
  2.  Correct project association
  3.  GitHub username extraction
  4.  Duplicate prevention (upsert semantics)
  5.  Existing contributor update
  6.  GitHub API error handling (401, 403, 404, rate limit, network)
  7.  End-to-end sync orchestration
  8.  Project verification and repository validation
  9.  Pagination support
  10. Unique index enforcement (DuplicateKeyError)
  11. GET /api/projects/{id}/contributors endpoint
  12. POST /api/projects/{id}/sync-contributors endpoint

All tests mock external dependencies (GitHub API, MongoDB).
"""

import pytest
from unittest.mock import patch, MagicMock
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from Backend.github_commits import (
    get_github_contributors,
    GitHubTokenMissingError,
    GitHubAuthError,
    GitHubRepoNotFoundError,
    GitHubAPIError,
)
from Backend.persistence import upsert_contributor, get_project_contributors
from Backend.contributor_service import (
    sync_project_contributors,
    ProjectNotFoundError,
    ProjectRepoNotConfiguredError,
    RepoMismatchError,
)


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

SAMPLE_REPO_URL = "https://github.com/test-owner/test-repo"
SAMPLE_PROJECT_ID = str(ObjectId())

SAMPLE_PROJECT = {
    "_id": SAMPLE_PROJECT_ID,
    "name": "Test Project",
    "repo_url": SAMPLE_REPO_URL,
}

SAMPLE_PROJECT_NO_REPO = {
    "_id": SAMPLE_PROJECT_ID,
    "name": "Test Project Without Repo",
}

SAMPLE_GITHUB_CONTRIBUTORS = [
    {
        "login": "dev1",
        "id": 1001,
        "avatar_url": "https://avatars.githubusercontent.com/u/1001",
        "html_url": "https://github.com/dev1",
        "type": "User",
        "contributions": 42,
    },
    {
        "login": "dev2",
        "id": 1002,
        "avatar_url": "https://avatars.githubusercontent.com/u/1002",
        "html_url": "https://github.com/dev2",
        "type": "User",
        "contributions": 17,
    },
]

SAMPLE_GET_CONTRIBUTORS_RESULT = {
    "success": True,
    "repository": {
        "owner": "test-owner",
        "name": "test-repo",
        "full_name": "test-owner/test-repo",
        "url": SAMPLE_REPO_URL,
    },
    "contributor_count": 2,
    "contributors": [
        {
            "github_username": "dev1",
            "github_id": 1001,
            "avatar_url": "",
            "profile_url": "",
            "type": "User",
            "contributions": 42,
        },
        {
            "github_username": "dev2",
            "github_id": 1002,
            "avatar_url": "",
            "profile_url": "",
            "type": "User",
            "contributions": 17,
        },
    ],
}


def _mock_response(status_code=200, json_data=None, text=""):
    """Create a mock requests.Response with the given attributes."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = text
    return resp


# ===========================================================================
# 1. GitHub contributor retrieval
# ===========================================================================

class TestGetGitHubContributors:
    """Tests for get_github_contributors (GitHub API layer)."""

    @patch("Backend.github_commits._get_authenticated_session")
    def test_successful_retrieval(self, mock_session_factory):
        """Successful retrieval returns correct structure and counts."""
        session = MagicMock()
        mock_session_factory.return_value = session
        session.get.return_value = _mock_response(
            200, SAMPLE_GITHUB_CONTRIBUTORS
        )

        result = get_github_contributors(SAMPLE_REPO_URL)

        assert result["success"] is True
        assert result["contributor_count"] == 2
        assert len(result["contributors"]) == 2
        assert result["repository"]["owner"] == "test-owner"
        assert result["repository"]["name"] == "test-repo"
        assert result["repository"]["full_name"] == "test-owner/test-repo"

    @patch("Backend.github_commits._get_authenticated_session")
    def test_username_extraction(self, mock_session_factory):
        """GitHub 'login' field is correctly mapped to 'github_username'."""
        session = MagicMock()
        mock_session_factory.return_value = session
        session.get.return_value = _mock_response(
            200, SAMPLE_GITHUB_CONTRIBUTORS
        )

        result = get_github_contributors(SAMPLE_REPO_URL)

        assert result["contributors"][0]["github_username"] == "dev1"
        assert result["contributors"][1]["github_username"] == "dev2"

    @patch("Backend.github_commits._get_authenticated_session")
    def test_metadata_extraction(self, mock_session_factory):
        """All useful contributor metadata is extracted and normalized."""
        session = MagicMock()
        mock_session_factory.return_value = session
        session.get.return_value = _mock_response(
            200, SAMPLE_GITHUB_CONTRIBUTORS
        )

        result = get_github_contributors(SAMPLE_REPO_URL)
        contrib = result["contributors"][0]

        assert contrib["github_id"] == 1001
        assert contrib["avatar_url"] == (
            "https://avatars.githubusercontent.com/u/1001"
        )
        assert contrib["profile_url"] == "https://github.com/dev1"
        assert contrib["type"] == "User"
        assert contrib["contributions"] == 42

    @patch("Backend.github_commits._get_authenticated_session")
    def test_empty_contributors(self, mock_session_factory):
        """Repository with no contributors returns empty list, not error."""
        session = MagicMock()
        mock_session_factory.return_value = session
        session.get.return_value = _mock_response(200, [])

        result = get_github_contributors(SAMPLE_REPO_URL)

        assert result["success"] is True
        assert result["contributor_count"] == 0
        assert result["contributors"] == []

    @patch("Backend.github_commits._get_authenticated_session")
    def test_204_no_content(self, mock_session_factory):
        """HTTP 204 (empty repository) is handled as zero contributors."""
        session = MagicMock()
        mock_session_factory.return_value = session
        session.get.return_value = _mock_response(204)

        result = get_github_contributors(SAMPLE_REPO_URL)

        assert result["success"] is True
        assert result["contributor_count"] == 0

    def test_invalid_url_rejected(self):
        """Non-GitHub URL raises ValueError."""
        with pytest.raises(ValueError):
            get_github_contributors("https://notgithub.com/owner/repo")

    def test_invalid_url_no_repo(self):
        """URL missing owner/repo path raises ValueError."""
        with pytest.raises(ValueError):
            get_github_contributors("https://github.com/only-owner")

    def test_zero_max_contributors_rejected(self):
        """max_contributors <= 0 raises ValueError."""
        with pytest.raises(ValueError):
            get_github_contributors(SAMPLE_REPO_URL, max_contributors=0)

    def test_negative_max_contributors_rejected(self):
        """Negative max_contributors raises ValueError."""
        with pytest.raises(ValueError):
            get_github_contributors(SAMPLE_REPO_URL, max_contributors=-5)

    @patch("Backend.github_commits._get_authenticated_session")
    def test_git_suffix_stripped(self, mock_session_factory):
        """URL ending in .git is handled correctly."""
        session = MagicMock()
        mock_session_factory.return_value = session
        session.get.return_value = _mock_response(
            200, SAMPLE_GITHUB_CONTRIBUTORS
        )

        result = get_github_contributors(
            "https://github.com/test-owner/test-repo.git"
        )

        assert result["repository"]["name"] == "test-repo"


# ===========================================================================
# 2. GitHub API error handling
# ===========================================================================

class TestGitHubContributorErrors:
    """Tests for error handling in contributor retrieval."""

    @patch("Backend.github_commits._get_authenticated_session")
    def test_token_missing(self, mock_session_factory):
        """Missing GITHUB_TOKEN raises GitHubTokenMissingError."""
        mock_session_factory.side_effect = GitHubTokenMissingError(
            "GITHUB_TOKEN is not set."
        )

        with pytest.raises(GitHubTokenMissingError):
            get_github_contributors(SAMPLE_REPO_URL)

    @patch("Backend.github_commits._get_authenticated_session")
    def test_auth_error_401(self, mock_session_factory):
        """Invalid token (HTTP 401) raises GitHubAuthError."""
        session = MagicMock()
        mock_session_factory.return_value = session
        session.get.return_value = _mock_response(401)

        with pytest.raises(GitHubAuthError):
            get_github_contributors(SAMPLE_REPO_URL)

    @patch("Backend.github_commits._get_authenticated_session")
    def test_repo_not_found_404(self, mock_session_factory):
        """Non-existent repository (HTTP 404) raises GitHubRepoNotFoundError."""
        session = MagicMock()
        mock_session_factory.return_value = session
        session.get.return_value = _mock_response(404)

        with pytest.raises(GitHubRepoNotFoundError):
            get_github_contributors(SAMPLE_REPO_URL)

    @patch("Backend.github_commits._get_authenticated_session")
    def test_rate_limit_403(self, mock_session_factory):
        """Rate-limited (HTTP 403 with message) raises GitHubAPIError."""
        session = MagicMock()
        mock_session_factory.return_value = session
        session.get.return_value = _mock_response(
            403, text="API rate limit exceeded"
        )

        with pytest.raises(GitHubAPIError, match="rate limit"):
            get_github_contributors(SAMPLE_REPO_URL)

    @patch("Backend.github_commits._get_authenticated_session")
    def test_server_error_500(self, mock_session_factory):
        """Unexpected server error (HTTP 500) raises GitHubAPIError."""
        session = MagicMock()
        mock_session_factory.return_value = session
        session.get.return_value = _mock_response(500)

        with pytest.raises(GitHubAPIError):
            get_github_contributors(SAMPLE_REPO_URL)

    @patch("Backend.github_commits._get_authenticated_session")
    def test_network_failure(self, mock_session_factory):
        """Network error raises GitHubAPIError (not silent empty result)."""
        import requests as req

        session = MagicMock()
        mock_session_factory.return_value = session
        session.get.side_effect = req.exceptions.ConnectionError(
            "Network unreachable"
        )

        with pytest.raises(GitHubAPIError):
            get_github_contributors(SAMPLE_REPO_URL)

    @patch("Backend.github_commits._get_authenticated_session")
    def test_timeout(self, mock_session_factory):
        """Request timeout raises GitHubAPIError."""
        import requests as req

        session = MagicMock()
        mock_session_factory.return_value = session
        session.get.side_effect = req.exceptions.Timeout("Request timed out")

        with pytest.raises(GitHubAPIError):
            get_github_contributors(SAMPLE_REPO_URL)


# ===========================================================================
# 3. Pagination
# ===========================================================================

class TestContributorPagination:
    """Tests for paginated contributor retrieval."""

    @patch("Backend.github_commits._get_authenticated_session")
    def test_multiple_pages_collected(self, mock_session_factory):
        """Contributors spanning multiple pages are all collected."""
        session = MagicMock()
        mock_session_factory.return_value = session

        page1 = [
            {"login": f"dev{i}", "id": i, "avatar_url": "",
             "html_url": "", "type": "User", "contributions": i}
            for i in range(100)
        ]
        page2 = [
            {"login": f"dev{i}", "id": i, "avatar_url": "",
             "html_url": "", "type": "User", "contributions": i}
            for i in range(100, 150)
        ]

        session.get.side_effect = [
            _mock_response(200, page1),
            _mock_response(200, page2),
        ]

        result = get_github_contributors(SAMPLE_REPO_URL, max_contributors=200)

        assert result["contributor_count"] == 150
        assert len(result["contributors"]) == 150
        assert session.get.call_count == 2

    @patch("Backend.github_commits._get_authenticated_session")
    def test_pagination_respects_max(self, mock_session_factory):
        """Pagination respects the max_contributors limit."""
        session = MagicMock()
        mock_session_factory.return_value = session

        page1 = [
            {"login": f"dev{i}", "id": i, "avatar_url": "",
             "html_url": "", "type": "User", "contributions": i}
            for i in range(100)
        ]
        page2 = [
            {"login": f"dev{i}", "id": i, "avatar_url": "",
             "html_url": "", "type": "User", "contributions": i}
            for i in range(100, 200)
        ]

        session.get.side_effect = [
            _mock_response(200, page1),
            _mock_response(200, page2),
        ]

        result = get_github_contributors(SAMPLE_REPO_URL, max_contributors=120)

        assert result["contributor_count"] == 120
        assert len(result["contributors"]) == 120

    @patch("Backend.github_commits._get_authenticated_session")
    def test_single_page_no_extra_request(self, mock_session_factory):
        """When first page is incomplete, no second request is made."""
        session = MagicMock()
        mock_session_factory.return_value = session

        page = [
            {"login": f"dev{i}", "id": i, "avatar_url": "",
             "html_url": "", "type": "User", "contributions": i}
            for i in range(50)
        ]

        session.get.return_value = _mock_response(200, page)

        result = get_github_contributors(SAMPLE_REPO_URL)

        assert result["contributor_count"] == 50
        assert session.get.call_count == 1


# ===========================================================================
# 4. Contributor persistence (upsert / duplicate prevention)
# ===========================================================================

class TestContributorPersistence:
    """Tests for persistence layer (upsert, read, duplicate handling)."""

    @patch("Backend.persistence.contributors_collection")
    def test_upsert_creates_new_contributor(self, mock_collection):
        """First upsert for a contributor creates a new record."""
        new_id = ObjectId()
        mock_collection.update_one.return_value = MagicMock(
            upserted_id=new_id, modified_count=0
        )

        result = upsert_contributor(SAMPLE_PROJECT_ID, {
            "github_username": "dev1",
            "github_id": 1001,
            "avatar_url": "https://example.com/avatar.png",
            "contributions": 42,
        })

        assert result == str(new_id)
        mock_collection.update_one.assert_called_once()

    @patch("Backend.persistence.contributors_collection")
    def test_upsert_updates_existing_contributor(self, mock_collection):
        """Subsequent upsert for same contributor updates, not inserts."""
        existing_id = ObjectId()
        mock_collection.update_one.return_value = MagicMock(
            upserted_id=None, modified_count=1
        )
        mock_collection.find_one.return_value = {
            "_id": existing_id,
            "projectId": ObjectId(SAMPLE_PROJECT_ID),
            "github_username": "dev1",
        }

        result = upsert_contributor(SAMPLE_PROJECT_ID, {
            "github_username": "dev1",
            "github_id": 1001,
            "avatar_url": "https://example.com/avatar_v2.png",
            "contributions": 50,
        })

        assert result == str(existing_id)
        mock_collection.update_one.assert_called_once()
        mock_collection.find_one.assert_called_once()

    @patch("Backend.persistence.contributors_collection")
    def test_upsert_prevents_duplicates(self, mock_collection):
        """Two upserts for the same (project, username) return same _id."""
        contributor_data = {
            "github_username": "dev1",
            "github_id": 1001,
            "avatar_url": "https://example.com/avatar.png",
            "contributions": 42,
        }

        shared_id = ObjectId()

        # First call: new insert
        mock_collection.update_one.return_value = MagicMock(
            upserted_id=shared_id, modified_count=0
        )
        id_first = upsert_contributor(SAMPLE_PROJECT_ID, contributor_data)

        # Second call: update existing
        mock_collection.update_one.return_value = MagicMock(
            upserted_id=None, modified_count=1
        )
        mock_collection.find_one.return_value = {
            "_id": shared_id,
            "projectId": ObjectId(SAMPLE_PROJECT_ID),
            "github_username": "dev1",
        }
        id_second = upsert_contributor(SAMPLE_PROJECT_ID, contributor_data)

        assert id_first == id_second
        assert mock_collection.update_one.call_count == 2

    @patch("Backend.persistence.contributors_collection")
    def test_project_association_in_filter(self, mock_collection):
        """Upsert filter includes the correct projectId."""
        new_id = ObjectId()
        mock_collection.update_one.return_value = MagicMock(
            upserted_id=new_id, modified_count=0
        )

        upsert_contributor(SAMPLE_PROJECT_ID, {
            "github_username": "dev1",
            "github_id": 1001,
        })

        call_args = mock_collection.update_one.call_args
        filter_arg = call_args[0][0]
        update_arg = call_args[0][1]

        assert filter_arg["projectId"] == ObjectId(SAMPLE_PROJECT_ID)
        assert update_arg["$set"]["projectId"] == ObjectId(SAMPLE_PROJECT_ID)
        assert filter_arg["github_username"] == "dev1"

    @patch("Backend.persistence.contributors_collection")
    def test_get_project_contributors(self, mock_collection):
        """Retrieves all contributors for a given project."""
        project_oid = ObjectId(SAMPLE_PROJECT_ID)
        mock_collection.find.return_value = [
            {
                "_id": ObjectId(),
                "projectId": project_oid,
                "github_username": "dev1",
                "contributions": 42,
            },
            {
                "_id": ObjectId(),
                "projectId": project_oid,
                "github_username": "dev2",
                "contributions": 17,
            },
        ]

        result = get_project_contributors(SAMPLE_PROJECT_ID)

        assert len(result) == 2
        assert result[0]["github_username"] == "dev1"
        assert result[1]["github_username"] == "dev2"
        mock_collection.find.assert_called_once_with(
            {"projectId": project_oid}
        )

    @patch("Backend.persistence.contributors_collection")
    def test_upsert_sets_updated_at(self, mock_collection):
        """Upsert always sets updated_at timestamp."""
        mock_collection.update_one.return_value = MagicMock(
            upserted_id=ObjectId(), modified_count=0
        )

        upsert_contributor(SAMPLE_PROJECT_ID, {
            "github_username": "dev1",
            "github_id": 1001,
        })

        call_args = mock_collection.update_one.call_args
        update_doc = call_args[0][1]["$set"]

        assert "updated_at" in update_doc
        from datetime import datetime
        assert isinstance(update_doc["updated_at"], datetime)

    @patch("Backend.persistence.contributors_collection")
    def test_upsert_duplicate_key_error_propagates(self, mock_collection):
        """DuplicateKeyError from MongoDB propagates to caller."""
        mock_collection.update_one.side_effect = DuplicateKeyError(
            "duplicate key error"
        )

        with pytest.raises(DuplicateKeyError):
            upsert_contributor(SAMPLE_PROJECT_ID, {
                "github_username": "dev1",
                "github_id": 1001,
            })


# ===========================================================================
# 5. Sync service (end-to-end orchestration)
# ===========================================================================

class TestSyncProjectContributors:
    """Tests for sync_project_contributors (orchestration layer)."""

    @patch("Backend.contributor_service.get_project")
    @patch("Backend.contributor_service.upsert_contributor")
    @patch("Backend.contributor_service.get_github_contributors")
    def test_successful_sync(self, mock_get_contribs, mock_upsert, mock_get_project):
        """Full sync retrieves from GitHub and upserts to database."""
        mock_get_project.return_value = SAMPLE_PROJECT
        mock_get_contribs.return_value = SAMPLE_GET_CONTRIBUTORS_RESULT
        mock_upsert.side_effect = [str(ObjectId()), str(ObjectId())]

        result = sync_project_contributors(
            SAMPLE_PROJECT_ID, repo_url=SAMPLE_REPO_URL
        )

        assert result["success"] is True
        assert result["synced_count"] == 2
        assert result["project_id"] == SAMPLE_PROJECT_ID
        assert len(result["contributors"]) == 2
        assert mock_upsert.call_count == 2

    @patch("Backend.contributor_service.get_project")
    @patch("Backend.contributor_service.upsert_contributor")
    @patch("Backend.contributor_service.get_github_contributors")
    def test_sync_passes_correct_project_id(
        self, mock_get_contribs, mock_upsert, mock_get_project
    ):
        """Each upsert call receives the correct project_id."""
        mock_get_project.return_value = SAMPLE_PROJECT
        mock_get_contribs.return_value = {
            "success": True,
            "repository": {
                "owner": "o", "name": "r",
                "full_name": "o/r", "url": SAMPLE_REPO_URL,
            },
            "contributor_count": 1,
            "contributors": [
                {
                    "github_username": "dev1",
                    "github_id": 1001,
                    "avatar_url": "",
                    "profile_url": "",
                    "type": "User",
                    "contributions": 10,
                },
            ],
        }
        mock_upsert.return_value = str(ObjectId())

        sync_project_contributors(SAMPLE_PROJECT_ID, repo_url=SAMPLE_REPO_URL)

        mock_upsert.assert_called_once()
        assert mock_upsert.call_args[0][0] == SAMPLE_PROJECT_ID

    @patch("Backend.contributor_service.get_project")
    @patch("Backend.contributor_service.upsert_contributor")
    @patch("Backend.contributor_service.get_github_contributors")
    def test_sync_empty_contributors(
        self, mock_get_contribs, mock_upsert, mock_get_project
    ):
        """Sync with no contributors succeeds with zero count."""
        mock_get_project.return_value = SAMPLE_PROJECT
        mock_get_contribs.return_value = {
            "success": True,
            "repository": {
                "owner": "o", "name": "r",
                "full_name": "o/r", "url": SAMPLE_REPO_URL,
            },
            "contributor_count": 0,
            "contributors": [],
        }

        result = sync_project_contributors(
            SAMPLE_PROJECT_ID, repo_url=SAMPLE_REPO_URL
        )

        assert result["success"] is True
        assert result["synced_count"] == 0
        assert result["contributors"] == []
        mock_upsert.assert_not_called()

    @patch("Backend.contributor_service.get_project")
    @patch("Backend.contributor_service.get_github_contributors")
    def test_sync_github_error_propagates(self, mock_get_contribs, mock_get_project):
        """GitHub API errors propagate through sync, not silenced."""
        mock_get_project.return_value = SAMPLE_PROJECT
        mock_get_contribs.side_effect = GitHubRepoNotFoundError("Not found")

        with pytest.raises(GitHubRepoNotFoundError):
            sync_project_contributors(
                SAMPLE_PROJECT_ID, repo_url=SAMPLE_REPO_URL
            )

    @patch("Backend.contributor_service.get_project")
    @patch("Backend.contributor_service.get_github_contributors")
    def test_sync_auth_error_propagates(self, mock_get_contribs, mock_get_project):
        """Authentication errors propagate through sync."""
        mock_get_project.return_value = SAMPLE_PROJECT
        mock_get_contribs.side_effect = GitHubAuthError("Invalid token")

        with pytest.raises(GitHubAuthError):
            sync_project_contributors(
                SAMPLE_PROJECT_ID, repo_url=SAMPLE_REPO_URL
            )

    @patch("Backend.contributor_service.get_project")
    @patch("Backend.contributor_service.get_github_contributors")
    def test_sync_api_error_propagates(self, mock_get_contribs, mock_get_project):
        """Generic API errors propagate through sync."""
        mock_get_project.return_value = SAMPLE_PROJECT
        mock_get_contribs.side_effect = GitHubAPIError("Server error")

        with pytest.raises(GitHubAPIError):
            sync_project_contributors(
                SAMPLE_PROJECT_ID, repo_url=SAMPLE_REPO_URL
            )

    def test_sync_empty_project_id_rejected(self):
        """Empty project_id raises ValueError."""
        with pytest.raises(ValueError, match="project_id"):
            sync_project_contributors("")

    def test_sync_whitespace_project_id_rejected(self):
        """Whitespace-only project_id raises ValueError."""
        with pytest.raises(ValueError, match="project_id"):
            sync_project_contributors("   ")

    @patch("Backend.contributor_service.get_project")
    @patch("Backend.contributor_service.upsert_contributor")
    @patch("Backend.contributor_service.get_github_contributors")
    def test_sync_returns_contributor_usernames(
        self, mock_get_contribs, mock_upsert, mock_get_project
    ):
        """Sync result includes github_username for each synced contributor."""
        mock_get_project.return_value = SAMPLE_PROJECT
        mock_get_contribs.return_value = {
            "success": True,
            "repository": {
                "owner": "o", "name": "r",
                "full_name": "o/r", "url": SAMPLE_REPO_URL,
            },
            "contributor_count": 1,
            "contributors": [
                {
                    "github_username": "dev1",
                    "github_id": 1001,
                    "avatar_url": "",
                    "profile_url": "",
                    "type": "User",
                    "contributions": 10,
                },
            ],
        }
        mock_upsert.return_value = str(ObjectId())

        result = sync_project_contributors(
            SAMPLE_PROJECT_ID, repo_url=SAMPLE_REPO_URL
        )

        assert result["contributors"][0]["github_username"] == "dev1"
        assert result["contributors"][0]["contributions"] == 10
        assert "contributor_id" in result["contributors"][0]


# ===========================================================================
# 6. Project verification and repository validation
# ===========================================================================

class TestProjectVerification:
    """Tests for project existence and repository validation in sync."""

    @patch("Backend.contributor_service.get_project")
    def test_project_not_found(self, mock_get_project):
        """Sync fails with ProjectNotFoundError when project doesn't exist."""
        mock_get_project.return_value = None

        with pytest.raises(ProjectNotFoundError):
            sync_project_contributors(
                SAMPLE_PROJECT_ID, repo_url=SAMPLE_REPO_URL
            )

    @patch("Backend.contributor_service.get_project")
    def test_no_repo_configured_and_none_provided(self, mock_get_project):
        """Sync fails when project has no repo_url and none provided."""
        mock_get_project.return_value = SAMPLE_PROJECT_NO_REPO

        with pytest.raises(ProjectRepoNotConfiguredError):
            sync_project_contributors(SAMPLE_PROJECT_ID)

    @patch("Backend.contributor_service.get_project")
    def test_repo_mismatch_rejected(self, mock_get_project):
        """Sync fails when provided repo_url doesn't match project config."""
        mock_get_project.return_value = SAMPLE_PROJECT

        with pytest.raises(RepoMismatchError):
            sync_project_contributors(
                SAMPLE_PROJECT_ID,
                repo_url="https://github.com/different-owner/different-repo",
            )

    @patch("Backend.contributor_service.get_project")
    @patch("Backend.contributor_service.upsert_contributor")
    @patch("Backend.contributor_service.get_github_contributors")
    def test_uses_project_stored_repo_url(
        self, mock_get_contribs, mock_upsert, mock_get_project
    ):
        """Sync uses the project's stored repo_url when none is provided."""
        mock_get_project.return_value = SAMPLE_PROJECT
        mock_get_contribs.return_value = {
            "success": True,
            "repository": {
                "owner": "test-owner", "name": "test-repo",
                "full_name": "test-owner/test-repo", "url": SAMPLE_REPO_URL,
            },
            "contributor_count": 0,
            "contributors": [],
        }

        result = sync_project_contributors(SAMPLE_PROJECT_ID)

        assert result["success"] is True
        mock_get_contribs.assert_called_once_with(SAMPLE_REPO_URL)

    @patch("Backend.contributor_service.get_project")
    @patch("Backend.contributor_service.upsert_contributor")
    @patch("Backend.contributor_service.get_github_contributors")
    def test_repo_url_with_git_suffix_matches(
        self, mock_get_contribs, mock_upsert, mock_get_project
    ):
        """repo_url with .git suffix matches stored URL without it."""
        mock_get_project.return_value = SAMPLE_PROJECT
        mock_get_contribs.return_value = {
            "success": True,
            "repository": {
                "owner": "test-owner", "name": "test-repo",
                "full_name": "test-owner/test-repo", "url": SAMPLE_REPO_URL,
            },
            "contributor_count": 0,
            "contributors": [],
        }

        result = sync_project_contributors(
            SAMPLE_PROJECT_ID,
            repo_url=SAMPLE_REPO_URL + ".git",
        )
        assert result["success"] is True

    @patch("Backend.contributor_service.get_project")
    @patch("Backend.contributor_service.upsert_contributor")
    @patch("Backend.contributor_service.get_github_contributors")
    def test_duplicate_key_handled_gracefully(
        self, mock_get_contribs, mock_upsert, mock_get_project
    ):
        """DuplicateKeyError during upsert is caught, not propagated."""
        mock_get_project.return_value = SAMPLE_PROJECT
        mock_get_contribs.return_value = SAMPLE_GET_CONTRIBUTORS_RESULT
        mock_upsert.side_effect = DuplicateKeyError("duplicate key error")

        result = sync_project_contributors(
            SAMPLE_PROJECT_ID, repo_url=SAMPLE_REPO_URL
        )

        assert result["success"] is True
        assert result["synced_count"] == 0


# ===========================================================================
# 7. API endpoints
# ===========================================================================

class TestContributorAPI:
    """Tests for the FastAPI contributor endpoints."""

    def _get_client(self):
        from fastapi.testclient import TestClient
        from Backend.main import app
        return TestClient(app)

    @patch("Backend.main.ensure_indexes")
    @patch("Backend.main.get_project_contributors")
    @patch("Backend.main.get_project")
    def test_get_contributors_success(
        self, mock_get_project, mock_get_contribs, mock_indexes
    ):
        """GET /api/projects/{id}/contributors returns stored contributors."""
        mock_get_project.return_value = SAMPLE_PROJECT
        mock_get_contribs.return_value = [
            {"_id": str(ObjectId()), "github_username": "dev1",
             "contributions": 42},
            {"_id": str(ObjectId()), "github_username": "dev2",
             "contributions": 17},
        ]

        with self._get_client() as client:
            response = client.get(
                f"/api/projects/{SAMPLE_PROJECT_ID}/contributors"
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @patch("Backend.main.ensure_indexes")
    @patch("Backend.main.get_project")
    def test_get_contributors_project_not_found(
        self, mock_get_project, mock_indexes
    ):
        """GET returns 404 when project does not exist."""
        mock_get_project.return_value = None

        with self._get_client() as client:
            response = client.get(
                f"/api/projects/{SAMPLE_PROJECT_ID}/contributors"
            )

        assert response.status_code == 404

    @patch("Backend.main.ensure_indexes")
    @patch("Backend.main.sync_project_contributors")
    def test_sync_contributors_success(self, mock_sync, mock_indexes):
        """POST /api/projects/{id}/sync-contributors triggers sync."""
        mock_sync.return_value = {
            "success": True,
            "repository": {
                "owner": "test-owner", "name": "test-repo",
                "full_name": "test-owner/test-repo", "url": SAMPLE_REPO_URL,
            },
            "project_id": SAMPLE_PROJECT_ID,
            "synced_count": 2,
            "contributors": [
                {"contributor_id": str(ObjectId()),
                 "github_username": "dev1", "contributions": 42},
                {"contributor_id": str(ObjectId()),
                 "github_username": "dev2", "contributions": 17},
            ],
        }

        with self._get_client() as client:
            response = client.post(
                f"/api/projects/{SAMPLE_PROJECT_ID}/sync-contributors",
                json={"repo_url": SAMPLE_REPO_URL},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["synced_count"] == 2
        mock_sync.assert_called_once()

    @patch("Backend.main.ensure_indexes")
    @patch("Backend.main.sync_project_contributors")
    def test_sync_contributors_project_not_found(self, mock_sync, mock_indexes):
        """POST returns 404 when project does not exist."""
        mock_sync.side_effect = ProjectNotFoundError("Not found")

        with self._get_client() as client:
            response = client.post(
                f"/api/projects/{SAMPLE_PROJECT_ID}/sync-contributors",
                json={"repo_url": SAMPLE_REPO_URL},
            )

        assert response.status_code == 404

    @patch("Backend.main.ensure_indexes")
    @patch("Backend.main.sync_project_contributors")
    def test_sync_contributors_github_auth_error(self, mock_sync, mock_indexes):
        """POST returns 401 on GitHub auth failure."""
        mock_sync.side_effect = GitHubAuthError("Invalid token")

        with self._get_client() as client:
            response = client.post(
                f"/api/projects/{SAMPLE_PROJECT_ID}/sync-contributors",
                json={"repo_url": SAMPLE_REPO_URL},
            )

        assert response.status_code == 401
