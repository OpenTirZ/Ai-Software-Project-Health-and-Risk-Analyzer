"""
Tests for GitHub issue synchronization.

Covers:
  1. Fetching, pagination and normalization (Backend/externalservies/github_issues.py)
  2. Pull-request filtering
  3. GitHub HTTP / network / malformed-response failures
  4. Persistence behaviour (bulk_upsert_issues, list_project_issues, index)
  5. The sync orchestration service
  6. The two API endpoints:
        POST /api/projects/{id}/sync-issues
        GET  /api/projects/{id}/issues

Nothing here needs a network connection, a GitHub token or a real MongoDB:
GitHub is replaced by a FakeSession and MongoDB by FakeIssuesCollection.
"""

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests

# Environment needed before any Backend module is imported.
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/test_project_health")
os.environ.setdefault("MONGO_DATABASE", "test_project_health")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-github-issue-tests-0123456789")

# Backend.database pings MongoDB when it is first imported. If no other test
# module imported it yet, import it once with the Mongo client replaced so
# these tests also run on a machine without a database.
if "Backend.database" not in sys.modules:
    with patch("pymongo.MongoClient", MagicMock()):
        import Backend.database  # noqa: F401

from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError, ConnectionFailure, PyMongoError

from Backend import persistence
from Backend.auth.dependencies import get_current_user
from Backend.externalservies import github_issues
from Backend.externalservies.contributor_service import (
    ProjectNotFoundError,
    ProjectRepoNotConfiguredError,
    RepoMismatchError,
)
from Backend.externalservies.github_commits import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubRepoNotFoundError,
    GitHubTokenMissingError,
)
from Backend.externalservies.github_issues import (
    GitHubPermissionError,
    GitHubRateLimitError,
)
from Backend.main import app
from Backend.persistence import DatabaseError

client = TestClient(app)

SERVICE = "Backend.externalservies.github_issues"
ROUTER = "Backend.routers.data_sync_router"
REPO_URL = "https://github.com/acme/widgets"
REPOSITORY = {
    "owner": "acme",
    "name": "widgets",
    "full_name": "acme/widgets",
    "url": REPO_URL,
}

PROJECT_ID = str(ObjectId())
OTHER_PROJECT_ID = str(ObjectId())
MANAGER_ID = str(ObjectId())
DEVELOPER_ID = str(ObjectId())
OUTSIDER_ID = str(ObjectId())

MANAGER = {"_id": MANAGER_ID, "email": "pm@example.com", "role": "project_manager"}
DEVELOPER = {"_id": DEVELOPER_ID, "email": "dev@example.com", "role": "developer"}
OUTSIDER = {"_id": OUTSIDER_ID, "email": "out@example.com", "role": "project_manager"}


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def make_response(status=200, body=None, headers=None, raw=None):
    """Build a real requests.Response so .ok, .json(), .links behave exactly."""
    response = requests.Response()
    response.status_code = status
    response.encoding = "utf-8"
    response.url = "https://api.github.com/repos/acme/widgets/issues"
    if raw is not None:
        response._content = raw
    else:
        response._content = json.dumps([] if body is None else body).encode()
    response.headers.update(headers or {})
    return response

    # Explanation: tests need many different GitHub replies (success, 404,
    # broken JSON...). Building genuine Response objects, not MagicMocks,
    # means the production code is exercised against the real library.


def link_header(next_url):
    """Return a GitHub style Link header pointing to the next page."""
    return {"Link": f'<{next_url}>; rel="next"'}

    # Explanation: GitHub tells the client where page 2 is through this
    # header; the pagination tests use it to simulate multi-page results.


def make_issue(number=1, **overrides):
    """Return a raw GitHub issue payload with sensible defaults."""
    raw = {
        "id": 1000 + number,
        "number": number,
        "title": f"Issue {number}",
        "state": "open",
        "user": {"login": "reporter"},
        "assignees": [],
        "labels": [],
        "comments": 0,
        "created_at": "2024-01-02T03:04:05Z",
        "updated_at": "2024-01-03T03:04:05Z",
        "closed_at": None,
        "html_url": f"{REPO_URL}/issues/{number}",
    }
    raw.update(overrides)
    return raw

    # Explanation: a factory keeps each test short; a test only states the
    # fields it cares about, everything else is a valid default.


def make_pr(number=2, **overrides):
    """Return a raw pull request as the GitHub issues API reports it."""
    return make_issue(
        number,
        pull_request={"url": f"https://api.github.com/repos/acme/widgets/pulls/{number}"},
        **overrides,
    )

    # Explanation: identical to an issue except for the "pull_request" key,
    # which is precisely how GitHub marks pull requests.


class FakeSession:
    """Stand-in for requests.Session that replays queued outcomes."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        if not self.outcomes:
            raise AssertionError("Unexpected extra HTTP request.")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    # Explanation: returns (or raises) the prepared outcomes in order and
    # records every call, so tests can assert on URLs, params and timeouts.


class FakeIssuesCollection:
    """Tiny in-memory replacement for the MongoDB issues collection."""

    def __init__(self, documents=None):
        self.documents = list(documents or [])
        self.bulk_calls = 0
        self.delete_many = MagicMock(name="delete_many")
        self.delete_one = MagicMock(name="delete_one")

    def bulk_write(self, operations, ordered=True):
        self.bulk_calls += 1
        self.last_ordered = ordered
        matched = upserted = 0
        for operation in operations:
            query, document = operation._filter, operation._doc["$set"]
            existing = next(
                (d for d in self.documents
                 if all(d.get(k) == v for k, v in query.items())),
                None,
            )
            if existing:
                existing.update(document)
                matched += 1
            else:
                self.documents.append({"_id": ObjectId(), **document})
                upserted += 1
        return SimpleNamespace(
            matched_count=matched, modified_count=matched, upserted_count=upserted
        )

    def find(self, query):
        rows = [
            d for d in self.documents
            if all(d.get(k) == v for k, v in query.items())
        ]
        return FakeCursor(rows)

    # Explanation: implements only what persistence.py uses. Because it
    # applies the real UpdateOne filters/updates, idempotency and project
    # scoping are tested through the REAL persistence functions.


class FakeCursor(list):
    """List with the sort() method MongoDB cursors have."""

    def sort(self, key, direction=1):
        return FakeCursor(
            sorted(self, key=lambda d: d.get(key) or "", reverse=direction == -1)
        )

    # Explanation: mimics cursor.sort("updated_at", -1) (newest first).


def stored_issue(project_id, github_id, **overrides):
    """A document as it exists inside the issues collection."""
    document = {
        "_id": ObjectId(),
        "projectId": ObjectId(project_id),
        "github_id": github_id,
        "number": github_id - 1000,
        "title": f"Stored {github_id}",
        "state": "open",
        "assignees": ["alice"],
        "labels": ["bug"],
        "comments": 3,
        "created_at": "2024-01-02T03:04:05+00:00",
        "updated_at": "2024-01-03T03:04:05+00:00",
        "closed_at": None,
        "html_url": f"{REPO_URL}/issues/{github_id - 1000}",
        "author": "reporter",
        "repository": "acme/widgets",
    }
    document.update(overrides)
    return document

    # Explanation: builds a ready-made database row for the GET tests.


def project_document(project_id=PROJECT_ID, repo_url=REPO_URL):
    """A project document whose owner is the MANAGER test user."""
    return {
        "_id": project_id,
        "name": "Widgets",
        "repo_url": repo_url,
        "ownerId": MANAGER_ID,
        "members": [],
    }

    # Explanation: the router checks membership, so the manager must own it.


@pytest.fixture
def session():
    """Patch the authenticated GitHub session with an empty FakeSession."""
    fake = FakeSession()
    with patch(f"{SERVICE}._get_authenticated_session", return_value=fake):
        yield fake

    # Explanation: tests append outcomes to session.outcomes; no real HTTP.


@pytest.fixture
def collection():
    """Replace the real issues collection with the in-memory fake."""
    fake = FakeIssuesCollection()
    with patch("Backend.persistence.issues_collection", fake):
        yield fake

    # Explanation: every persistence call inside a test hits the fake only.


@pytest.fixture
def project():
    """Make both the service and the router find the same project."""
    doc = project_document()
    with patch(f"{SERVICE}.get_project", return_value=doc) as service_lookup, \
            patch(f"{ROUTER}.get_project", return_value=doc):
        yield service_lookup

    # Explanation: the router and the service each import get_project, so
    # both names must be patched for an end-to-end request to find it.


@pytest.fixture
def as_manager():
    """Authenticate requests as the project manager who owns the project."""
    app.dependency_overrides[get_current_user] = lambda: MANAGER
    yield
    app.dependency_overrides.clear()

    # Explanation: overriding get_current_user also satisfies require_role,
    # which depends on it. Cleanup prevents leaking into other test files.


# ===========================================================================
# 1. Fetching and pagination
# ===========================================================================

class TestFetching:
    def test_open_issues_are_retrieved(self, session):
        session.outcomes = [make_response(body=[make_issue(1), make_issue(2)])]
        result = github_issues.get_github_issues(REPO_URL)
        assert [i["number"] for i in result["issues"]] == [1, 2]
        assert all(i["state"] == "open" for i in result["issues"])
        # Explanation: two open issues in, two normalized open issues out.

    def test_closed_issues_are_retrieved(self, session):
        closed = make_issue(
            3, state="closed", closed_at="2024-02-01T00:00:00Z"
        )
        session.outcomes = [make_response(body=[closed])]
        result = github_issues.get_github_issues(REPO_URL)
        assert result["issues"][0]["state"] == "closed"
        assert result["issues"][0]["closed_at"] == "2024-02-01T00:00:00+00:00"
        # Explanation: closed issues must be kept and keep their closed date.

    def test_request_asks_for_all_states_and_max_page_size(self, session):
        session.outcomes = [make_response(body=[])]
        github_issues.get_github_issues(REPO_URL)
        call = session.calls[0]
        assert call["url"] == "https://api.github.com/repos/acme/widgets/issues"
        assert call["params"] == {"state": "all", "per_page": 100}
        assert call["timeout"] == github_issues.REQUEST_TIMEOUT_SECONDS
        # Explanation: state=all is what returns BOTH open and closed
        # issues; a timeout is always set so a request can never hang.

    def test_multiple_pages_are_followed(self, session):
        page2 = "https://api.github.com/repositories/1/issues?page=2"
        page3 = "https://api.github.com/repositories/1/issues?page=3"
        session.outcomes = [
            make_response(body=[make_issue(1)], headers=link_header(page2)),
            make_response(body=[make_issue(2)], headers=link_header(page3)),
            make_response(body=[make_issue(3)]),
        ]
        result = github_issues.get_github_issues(REPO_URL)
        assert [i["number"] for i in result["issues"]] == [1, 2, 3]
        assert [c["url"] for c in session.calls[1:]] == [page2, page3]
        assert session.calls[1]["params"] is None
        # Explanation: the code must follow Link headers until none is left;
        # follow-up requests reuse the full "next" URL without extra params.

    def test_more_than_one_hundred_issues_are_not_truncated(self, session):
        page2 = "https://api.github.com/repositories/1/issues?page=2"
        first = [make_issue(n) for n in range(1, 101)]
        second = [make_issue(n) for n in range(101, 151)]
        session.outcomes = [
            make_response(body=first, headers=link_header(page2)),
            make_response(body=second),
        ]
        result = github_issues.get_github_issues(REPO_URL)
        assert len(result["issues"]) == 150
        # Explanation: a naive "first page only" implementation would
        # return 100; this proves we collect all 150.

    def test_empty_repository_returns_empty_result(self, session):
        session.outcomes = [make_response(body=[])]
        result = github_issues.get_github_issues(REPO_URL)
        assert result["issues"] == []
        assert result["pull_requests_skipped"] == 0
        assert result["repository"]["full_name"] == "acme/widgets"
        # Explanation: an empty list is a valid success, not an error.

    @pytest.mark.parametrize(
        "bad_url",
        [
            "https://gitlab.com/acme/widgets",
            "https://github.com/acme",
            "not a url",
        ],
    )
    def test_invalid_repository_url_is_rejected(self, bad_url, session):
        with pytest.raises(ValueError):
            github_issues.get_github_issues(bad_url)
        assert session.calls == []
        # Explanation: bad URLs fail BEFORE any request is sent.

    def test_dot_git_suffix_is_removed_from_repository_name(self, session):
        session.outcomes = [make_response(body=[])]
        result = github_issues.get_github_issues(REPO_URL + ".git")
        assert result["repository"]["name"] == "widgets"
        assert "widgets/issues" in session.calls[0]["url"]
        # Explanation: clone URLs end in .git; the API path must not.

    def test_missing_token_is_reported(self):
        with patch(
            f"{SERVICE}._get_authenticated_session",
            side_effect=GitHubTokenMissingError("GITHUB_TOKEN is not set."),
        ):
            with pytest.raises(GitHubTokenMissingError):
                github_issues.get_github_issues(REPO_URL)
        # Explanation: the existing credential mechanism is reused and its
        # error is not hidden.


# ===========================================================================
# 2. Normalization
# ===========================================================================

class TestNormalization:
    def normalize(self, raw):
        return github_issues._normalize_issue(raw, REPOSITORY)

    def test_identifiers_title_and_repository_context(self):
        issue = self.normalize(make_issue(7, title="Crash on start"))
        assert issue["github_id"] == 1007
        assert issue["number"] == 7
        assert issue["title"] == "Crash on start"
        assert issue["repository"] == "acme/widgets"
        assert issue["repository_url"] == REPO_URL
        assert issue["html_url"] == f"{REPO_URL}/issues/7"
        assert issue["author"] == "reporter"
        # Explanation: id + number identify the issue, repository fields
        # let the record be traced back to its source.

    @pytest.mark.parametrize("state", ["open", "closed", "OPEN", "Closed"])
    def test_state_is_mapped_to_lowercase(self, state):
        assert self.normalize(make_issue(state=state))["state"] == state.lower()
        # Explanation: only open/closed are stored, always lowercase.

    @pytest.mark.parametrize("state", ["merged", "", None, 5])
    def test_unknown_state_is_rejected(self, state):
        with pytest.raises(GitHubAPIError):
            self.normalize(make_issue(state=state))
        # Explanation: an unknown state means GitHub's data is unusable.

    def test_assignees_are_login_names(self):
        raw = make_issue(assignees=[{"login": "alice"}, {"login": "bob"}])
        assert self.normalize(raw)["assignees"] == ["alice", "bob"]
        # Explanation: only the login names are stored.

    def test_legacy_single_assignee_is_merged_without_duplicates(self):
        raw = make_issue(
            assignees=[{"login": "alice"}],
            assignee={"login": "alice"},
        )
        assert self.normalize(raw)["assignees"] == ["alice"]
        raw = make_issue(assignees=[], assignee={"login": "carol"})
        assert self.normalize(raw)["assignees"] == ["carol"]
        # Explanation: GitHub still sends the old "assignee" field; it must
        # not create a duplicate entry.

    @pytest.mark.parametrize("assignees", [None, [], [None, {}, {"login": ""}]])
    def test_missing_or_empty_assignees_become_empty_list(self, assignees):
        assert self.normalize(make_issue(assignees=assignees))["assignees"] == []
        # Explanation: null/empty/junk entries never crash normalization.

    def test_labels_are_names(self):
        raw = make_issue(labels=[{"name": "bug"}, {"name": "help wanted"}])
        assert self.normalize(raw)["labels"] == ["bug", "help wanted"]
        # Explanation: the label objects are reduced to their names.

    def test_plain_string_labels_and_junk_labels(self):
        raw = make_issue(labels=["bug", {"name": "  "}, {"color": "red"}, 5, None])
        assert self.normalize(raw)["labels"] == ["bug"]
        # Explanation: strings are accepted; empty or malformed ones are
        # dropped, so the stored list always holds real label names.

    @pytest.mark.parametrize("labels", [None, []])
    def test_missing_or_empty_labels_become_empty_list(self, labels):
        assert self.normalize(make_issue(labels=labels))["labels"] == []
        # Explanation: same safety net as assignees.

    def test_comments_count_is_copied(self):
        assert self.normalize(make_issue(comments=12))["comments"] == 12
        # Explanation: the count comes straight from GitHub; comments are
        # never downloaded.

    def test_missing_or_null_comments_default_to_zero(self):
        raw = make_issue()
        del raw["comments"]
        assert self.normalize(raw)["comments"] == 0
        assert self.normalize(make_issue(comments=None))["comments"] == 0
        # Explanation: absent data is treated as "no comments".

    @pytest.mark.parametrize("value", ["3", -1, True, 2.5])
    def test_invalid_comments_count_is_rejected(self, value):
        with pytest.raises(GitHubAPIError):
            self.normalize(make_issue(comments=value))
        # Explanation: strings, negatives, booleans and floats are not
        # acceptable counts.

    def test_timestamps_are_timezone_aware_utc_strings(self):
        issue = self.normalize(make_issue(
            created_at="2024-01-02T03:04:05Z",
            updated_at="2024-01-03T08:34:05+05:30",
        ))
        assert issue["created_at"] == "2024-01-02T03:04:05+00:00"
        assert issue["updated_at"] == "2024-01-03T03:04:05+00:00"
        # Explanation: "Z" and offsets are converted to explicit UTC, so no
        # value can be mistaken for local time.

    def test_open_issue_keeps_closed_at_null(self):
        assert self.normalize(make_issue(closed_at=None))["closed_at"] is None
        assert self.normalize(make_issue(closed_at=""))["closed_at"] is None
        # Explanation: open issues must show closed_at = null, never a
        # made-up date or an empty string.

    @pytest.mark.parametrize("value", ["2024-01-02T03:04:05", "yesterday", 12345])
    def test_invalid_or_naive_timestamps_are_rejected(self, value):
        with pytest.raises(GitHubAPIError):
            self.normalize(make_issue(created_at=value))
        # Explanation: a timestamp without timezone would be ambiguous, so
        # it is refused like any other garbage.

    def test_missing_optional_fields_do_not_fail(self):
        raw = {
            "id": 5, "number": 5, "title": "Minimal", "state": "open",
            "created_at": "2024-01-02T03:04:05Z",
            "updated_at": "2024-01-02T03:04:05Z",
        }
        issue = self.normalize(raw)
        assert issue["assignees"] == []
        assert issue["labels"] == []
        assert issue["comments"] == 0
        assert issue["closed_at"] is None
        assert issue["html_url"] is None
        assert issue["author"] is None
        # Explanation: a minimal payload (only required fields) works and
        # every optional field gets a safe default.

    @pytest.mark.parametrize(
        "missing", ["id", "number", "title", "state", "created_at", "updated_at"]
    )
    def test_missing_required_fields_raise(self, missing):
        raw = make_issue()
        del raw[missing]
        with pytest.raises(GitHubAPIError):
            self.normalize(raw)
        # Explanation: a record without identity, state or dates would
        # corrupt later analysis, so it fails loudly.

    def test_normalized_record_has_exactly_the_expected_keys(self):
        assert set(self.normalize(make_issue())) == {
            "github_id", "number", "title", "state", "assignees", "labels",
            "comments", "created_at", "updated_at", "closed_at", "html_url",
            "author", "repository", "repository_url",
        }
        # Explanation: locks the persistence contract; adding or removing a
        # field by accident makes this test fail.


# ===========================================================================
# 3. Pull request filtering
# ===========================================================================

class TestPullRequestFiltering:
    def test_mixed_response_keeps_only_issues(self, session):
        session.outcomes = [make_response(body=[
            make_issue(1), make_pr(2), make_issue(3), make_pr(4),
        ])]
        result = github_issues.get_github_issues(REPO_URL)
        assert [i["number"] for i in result["issues"]] == [1, 3]
        assert result["pull_requests_skipped"] == 2
        # Explanation: PRs #2 and #4 disappear, and are counted.

    def test_every_object_with_pull_request_key_is_excluded(self):
        items = [
            make_pr(1),
            make_issue(2, pull_request=None),
            make_pr(3, title="Looks like a normal issue", labels=[{"name": "bug"}]),
        ]
        issues, skipped = github_issues.normalize_issues(items, REPOSITORY)
        assert issues == []
        assert skipped == 3
        # Explanation: the KEY decides, even when its value is null or the
        # title/labels look like an ordinary issue.

    def test_issue_without_key_is_kept_even_if_title_mentions_pull_request(self):
        items = [make_issue(1, title="Pull request template is broken")]
        issues, skipped = github_issues.normalize_issues(items, REPOSITORY)
        assert len(issues) == 1 and skipped == 0
        # Explanation: no guessing from titles; only the key matters.

    def test_only_genuine_issues_reach_persistence(self, session, project):
        session.outcomes = [make_response(body=[make_issue(1), make_pr(2)])]
        with patch(f"{SERVICE}.bulk_upsert_issues") as bulk:
            bulk.return_value = {
                "matched_count": 0, "modified_count": 0, "upserted_count": 1,
            }
            github_issues.sync_project_issues(PROJECT_ID)
        saved = bulk.call_args.args[1]
        assert [i["number"] for i in saved] == [1]
        assert all("pull_request" not in i for i in saved)
        # Explanation: checks the data actually handed to the database.

    def test_only_pull_requests_means_nothing_is_persisted(self, session, project):
        session.outcomes = [make_response(body=[make_pr(1), make_pr(2)])]
        with patch(f"{SERVICE}.bulk_upsert_issues") as bulk:
            result = github_issues.sync_project_issues(PROJECT_ID)
        bulk.assert_not_called()
        assert result["fetched_count"] == 0
        assert result["pull_requests_skipped"] == 2
        assert result["persisted_count"] == 0
        # Explanation: no issues -> no database call at all.


# ===========================================================================
# 4. GitHub HTTP / network failures
# ===========================================================================

class TestGitHubFailures:
    def fetch(self, session, *outcomes):
        session.outcomes = list(outcomes)
        return github_issues.get_github_issues(REPO_URL)

    def test_authentication_failure(self, session):
        with pytest.raises(GitHubAuthError):
            self.fetch(session, make_response(401, {"message": "Bad credentials"}))
        # Explanation: 401 means the configured token is invalid.

    def test_insufficient_permissions(self, session):
        with pytest.raises(GitHubPermissionError):
            self.fetch(session, make_response(
                403, {"message": "Resource not accessible by integration"}
            ))
        # Explanation: 403 without rate-limit signs is a permission problem.

    def test_repository_not_found(self, session):
        with pytest.raises(GitHubRepoNotFoundError):
            self.fetch(session, make_response(404, {"message": "Not Found"}))
        # Explanation: missing or private repository.

    @pytest.mark.parametrize(
        "response",
        [
            make_response(403, {"message": "API rate limit exceeded"}),
            make_response(403, {"message": "Forbidden"}, {"X-RateLimit-Remaining": "0"}),
            make_response(429, {"message": "Too many requests"}),
        ],
        ids=["403-text", "403-header", "429"],
    )
    def test_rate_limiting(self, session, response):
        with pytest.raises(GitHubRateLimitError):
            self.fetch(session, response)
        # Explanation: all three ways GitHub reports rate limiting are
        # recognized and kept separate from permission errors.

    def test_rate_limit_error_is_also_a_github_api_error(self, session):
        with pytest.raises(GitHubAPIError):
            self.fetch(session, make_response(429, {"message": "slow down"}))
        # Explanation: subclassing keeps older "except GitHubAPIError"
        # handlers working.

    def test_issues_disabled_repository(self, session):
        with pytest.raises(GitHubAPIError, match="disabled"):
            self.fetch(session, make_response(410, {"message": "Gone"}))
        # Explanation: 410 means issues are turned off, which is NOT the
        # same as "zero issues".

    @pytest.mark.parametrize("status", [400, 418, 500, 502, 503])
    def test_unexpected_http_status(self, session, status):
        with pytest.raises(GitHubAPIError):
            self.fetch(session, make_response(status, {"message": "boom"}))
        # Explanation: every other failure status becomes GitHubAPIError.

    def test_upstream_message_is_included_in_error(self, session):
        with pytest.raises(GitHubAPIError, match="Server exploded"):
            self.fetch(session, make_response(500, {"message": "Server exploded"}))
        # Explanation: GitHub's own message helps debugging.

    @pytest.mark.parametrize(
        "exception, text",
        [
            (requests.exceptions.Timeout("slow"), "timed out"),
            (requests.exceptions.ConnectionError("down"), "connect"),
            (requests.exceptions.RequestException("odd"), "Network failure"),
        ],
        ids=["timeout", "connection", "other"],
    )
    def test_network_errors(self, session, exception, text):
        with pytest.raises(GitHubAPIError, match=text):
            self.fetch(session, exception)
        # Explanation: low-level network errors never leak as raw
        # requests exceptions.

    def test_malformed_json_body(self, session):
        with pytest.raises(GitHubAPIError, match="not valid JSON"):
            self.fetch(session, make_response(raw=b"<html>Bad gateway</html>"))
        # Explanation: HTTP 200 with a non-JSON body must not be treated as
        # an empty repository.

    @pytest.mark.parametrize("body", [{"message": "oops"}, "text", 5, None])
    def test_response_that_is_not_a_list(self, session, body):
        response = make_response(raw=json.dumps(body).encode())
        with pytest.raises(GitHubAPIError, match="unexpected response"):
            self.fetch(session, response)
        # Explanation: the endpoint must return a list; anything else is
        # an upstream error.

    def test_list_containing_non_objects(self, session):
        with pytest.raises(GitHubAPIError, match="malformed"):
            self.fetch(session, make_response(body=[make_issue(1), "garbage"]))
        # Explanation: items must be JSON objects.

    def test_incomplete_issue_data_is_an_error(self, session):
        broken = make_issue(1)
        del broken["title"]
        with pytest.raises(GitHubAPIError):
            self.fetch(session, make_response(body=[broken]))
        # Explanation: missing required fields are surfaced, not skipped.

    def test_failure_on_second_page_is_not_a_partial_success(self, session):
        page2 = "https://api.github.com/repositories/1/issues?page=2"
        with pytest.raises(GitHubAPIError):
            self.fetch(
                session,
                make_response(body=[make_issue(1)], headers=link_header(page2)),
                make_response(500, {"message": "boom"}),
            )
        # Explanation: page 1 worked but page 2 failed - the caller gets an
        # exception, never the incomplete list.

    def test_timeout_on_second_page(self, session):
        page2 = "https://api.github.com/repositories/1/issues?page=2"
        with pytest.raises(GitHubAPIError, match="timed out"):
            self.fetch(
                session,
                make_response(body=[make_issue(1)], headers=link_header(page2)),
                requests.exceptions.Timeout("slow"),
            )
        # Explanation: network failures in the middle of pagination are
        # also fatal for the whole fetch.

    def test_repeated_next_link_is_detected(self, session):
        loop = "https://api.github.com/repositories/1/issues?page=2"
        with pytest.raises(GitHubAPIError, match="repeated"):
            self.fetch(
                session,
                make_response(body=[make_issue(1)], headers=link_header(loop)),
                make_response(body=[make_issue(2)], headers=link_header(loop)),
                make_response(body=[make_issue(3)], headers=link_header(loop)),
            )
        # Explanation: a broken pagination link pointing to itself would
        # loop forever; it is detected and reported.

    def test_page_limit_stops_runaway_pagination(self, session):
        outcomes = [
            make_response(
                body=[make_issue(n)],
                headers=link_header(f"https://api.github.com/p?page={n + 1}"),
            )
            for n in range(1, 6)
        ]
        with patch.object(github_issues, "MAX_PAGES", 3):
            with pytest.raises(GitHubAPIError, match="more than 3 pages"):
                self.fetch(session, *outcomes)
        # Explanation: an unbounded repository cannot make the server
        # download pages endlessly or return a silently truncated list.


# ===========================================================================
# 5. Persistence behaviour
# ===========================================================================

def normalized(number):
    """Return one normalized issue as the service would produce it."""
    return github_issues._normalize_issue(make_issue(number), REPOSITORY)

    # Explanation: shortcut for persistence tests that need valid records.


class TestPersistence:
    def test_bulk_upsert_sends_one_unordered_bulk_write(self):
        fake = MagicMock()
        fake.bulk_write.return_value = SimpleNamespace(
            matched_count=1, modified_count=1, upserted_count=1
        )
        with patch("Backend.persistence.issues_collection", fake):
            counts = persistence.bulk_upsert_issues(
                PROJECT_ID, [normalized(1), normalized(2)]
            )
        assert fake.bulk_write.call_count == 1
        operations = fake.bulk_write.call_args.args[0]
        assert len(operations) == 2
        assert all(isinstance(op, UpdateOne) for op in operations)
        assert fake.bulk_write.call_args.kwargs == {"ordered": False}
        assert counts == {
            "matched_count": 1, "modified_count": 1, "upserted_count": 1,
        }
        # Explanation: two issues cost ONE database call, not two, and the
        # counts returned are exactly MongoDB's.

    def test_upsert_filter_uses_project_and_github_id(self):
        fake = MagicMock()
        fake.bulk_write.return_value = SimpleNamespace(
            matched_count=0, modified_count=0, upserted_count=1
        )
        with patch("Backend.persistence.issues_collection", fake):
            persistence.bulk_upsert_issues(PROJECT_ID, [normalized(4)])
        operation = fake.bulk_write.call_args.args[0][0]
        assert operation._filter == {
            "projectId": ObjectId(PROJECT_ID), "github_id": 1004,
        }
        assert operation._upsert is True
        document = operation._doc["$set"]
        assert document["number"] == 4
        assert document["state"] == "open"
        assert document["closed_at"] is None
        assert "synced_at" in document
        # Explanation: (projectId, github_id) is the unique identity; the
        # stored record keeps closed_at = None and gets a sync timestamp.

    def test_empty_list_does_not_touch_the_database(self):
        fake = MagicMock()
        with patch("Backend.persistence.issues_collection", fake):
            counts = persistence.bulk_upsert_issues(PROJECT_ID, [])
        fake.bulk_write.assert_not_called()
        fake.delete_many.assert_not_called()
        assert counts == {"matched_count": 0, "modified_count": 0, "upserted_count": 0}
        # Explanation: nothing to save means nothing is written or deleted.

    def test_issue_without_github_id_is_rejected(self):
        with patch("Backend.persistence.issues_collection", MagicMock()):
            with pytest.raises(ValueError, match="github_id"):
                persistence.bulk_upsert_issues(PROJECT_ID, [{"title": "x"}])
        # Explanation: without github_id there is no identity to upsert on.

    def test_invalid_project_id_is_rejected(self):
        with patch("Backend.persistence.issues_collection", MagicMock()) as fake:
            with pytest.raises(ValueError):
                persistence.bulk_upsert_issues("not-an-id", [normalized(1)])
        fake.bulk_write.assert_not_called()
        # Explanation: a bad ID fails before any write.

    @pytest.mark.parametrize(
        "error",
        [
            BulkWriteError({"writeErrors": [{"code": 1}]}),
            ConnectionFailure("down"),
            PyMongoError("driver"),
        ],
        ids=["bulk-write", "connection", "driver"],
    )
    def test_driver_failures_become_database_error(self, error):
        fake = MagicMock()
        fake.bulk_write.side_effect = error
        with patch("Backend.persistence.issues_collection", fake):
            with pytest.raises(DatabaseError):
                persistence.bulk_upsert_issues(PROJECT_ID, [normalized(1)])
        # Explanation: raw pymongo errors never escape; the app's own
        # DatabaseError (mapped to HTTP 503) is raised instead.

    def test_repeated_upsert_is_idempotent(self, collection):
        records = [normalized(1), normalized(2)]
        first = persistence.bulk_upsert_issues(PROJECT_ID, records)
        second = persistence.bulk_upsert_issues(PROJECT_ID, records)
        assert first["upserted_count"] == 2
        assert second["upserted_count"] == 0
        assert second["matched_count"] == 2
        assert len(collection.documents) == 2
        # Explanation: running the same sync twice creates no duplicates.

    def test_upsert_updates_changed_issue_instead_of_duplicating(self, collection):
        persistence.bulk_upsert_issues(PROJECT_ID, [normalized(1)])
        changed = github_issues._normalize_issue(
            make_issue(1, state="closed", closed_at="2024-05-01T00:00:00Z",
                       comments=9),
            REPOSITORY,
        )
        persistence.bulk_upsert_issues(PROJECT_ID, [changed])
        assert len(collection.documents) == 1
        assert collection.documents[0]["state"] == "closed"
        assert collection.documents[0]["comments"] == 9
        assert collection.documents[0]["closed_at"] == "2024-05-01T00:00:00+00:00"
        # Explanation: a re-sync reflects changes made on GitHub.

    def test_same_github_id_in_two_projects_is_stored_twice(self, collection):
        persistence.bulk_upsert_issues(PROJECT_ID, [normalized(1)])
        persistence.bulk_upsert_issues(OTHER_PROJECT_ID, [normalized(1)])
        assert len(collection.documents) == 2
        # Explanation: uniqueness is per project, so two projects tracking
        # the same repository do not overwrite each other.

    def test_list_project_issues_filters_by_project_and_state(self):
        fake = MagicMock()
        fake.find.return_value.sort.return_value = []
        with patch("Backend.persistence.issues_collection", fake):
            persistence.list_project_issues(PROJECT_ID, state="closed")
        fake.find.assert_called_once_with(
            {"projectId": ObjectId(PROJECT_ID), "state": "closed"}
        )
        fake.find.return_value.sort.assert_called_once_with("updated_at", -1)
        # Explanation: the filter and the newest-first sort run inside the
        # database query.

    def test_list_project_issues_without_state_has_no_state_filter(self):
        fake = MagicMock()
        fake.find.return_value.sort.return_value = []
        with patch("Backend.persistence.issues_collection", fake):
            persistence.list_project_issues(PROJECT_ID)
        fake.find.assert_called_once_with({"projectId": ObjectId(PROJECT_ID)})
        # Explanation: with no state given, both open and closed come back.

    def test_list_project_issues_database_failure(self):
        fake = MagicMock()
        fake.find.side_effect = ConnectionFailure("down")
        with patch("Backend.persistence.issues_collection", fake):
            with pytest.raises(DatabaseError):
                persistence.list_project_issues(PROJECT_ID)
        # Explanation: read failures are converted just like write failures.

    def test_ensure_indexes_creates_unique_issue_index(self):
        import Backend.database as database

        issues = MagicMock()
        with patch.object(database, "issues_collection", issues), \
                patch.object(database, "contributors_collection", MagicMock()), \
                patch.object(database, "commits_collection", MagicMock()), \
                patch.object(database, "projects_collection", MagicMock()):
            database.ensure_indexes()
        args, kwargs = issues.create_index.call_args
        assert args[0] == [("projectId", 1), ("github_id", 1)]
        assert kwargs["unique"] is True
        assert kwargs["partialFilterExpression"] == {"github_id": {"$exists": True}}
        # Explanation: the database itself enforces "no duplicate issue per
        # project", the partial filter protects old documents.


# ===========================================================================
# 6. Sync orchestration (service layer)
# ===========================================================================

class TestSyncService:
    def test_successful_sync_returns_confirmed_counts(self, session, project):
        session.outcomes = [make_response(body=[make_issue(1), make_issue(2)])]
        with patch(f"{SERVICE}.bulk_upsert_issues") as bulk:
            bulk.return_value = {
                "matched_count": 1, "modified_count": 1, "upserted_count": 1,
            }
            result = github_issues.sync_project_issues(PROJECT_ID)
        assert result["success"] is True
        assert result["status"] == "synced"
        assert result["project_id"] == PROJECT_ID
        assert result["repository"]["full_name"] == "acme/widgets"
        assert result["fetched_count"] == 2
        assert result["created_count"] == 1
        assert result["updated_count"] == 1
        assert result["persisted_count"] == 2
        # Explanation: persisted/created/updated come from the database
        # result, fetched from GitHub; they are never guessed.

    def test_persistence_receives_the_real_contract(self, session, project):
        session.outcomes = [make_response(body=[
            make_issue(1, assignees=[{"login": "alice"}], labels=[{"name": "bug"}],
                       comments=4),
        ])]
        with patch(f"{SERVICE}.bulk_upsert_issues") as bulk:
            bulk.return_value = {
                "matched_count": 0, "modified_count": 0, "upserted_count": 1,
            }
            github_issues.sync_project_issues(PROJECT_ID)
        project_arg, records = bulk.call_args.args
        assert project_arg == PROJECT_ID
        assert records[0]["assignees"] == ["alice"]
        assert records[0]["labels"] == ["bug"]
        assert records[0]["comments"] == 4
        assert records[0]["repository"] == "acme/widgets"
        # Explanation: the record handed to bulk_upsert_issues has the
        # structure persistence expects.

    def test_empty_project_id_is_rejected(self, session):
        with pytest.raises(ValueError):
            github_issues.sync_project_issues("  ")
        assert session.calls == []
        # Explanation: validated first, so no lookup or request happens.

    def test_missing_project_stops_before_github_and_persistence(self, session):
        with patch(f"{SERVICE}.get_project", return_value=None), \
                patch(f"{SERVICE}.bulk_upsert_issues") as bulk:
            with pytest.raises(ProjectNotFoundError):
                github_issues.sync_project_issues(PROJECT_ID)
        assert session.calls == []
        bulk.assert_not_called()
        # Explanation: an invalid project causes neither HTTP nor DB work.

    def test_project_without_repository_configuration(self, session):
        with patch(f"{SERVICE}.get_project",
                   return_value=project_document(repo_url="")), \
                patch(f"{SERVICE}.bulk_upsert_issues") as bulk:
            with pytest.raises(ProjectRepoNotConfiguredError):
                github_issues.sync_project_issues(PROJECT_ID)
        assert session.calls == []
        bulk.assert_not_called()
        # Explanation: no repo_url anywhere -> clear error, nothing else.

    def test_repo_url_of_another_repository_is_rejected(self, session, project):
        with patch(f"{SERVICE}.bulk_upsert_issues") as bulk:
            with pytest.raises(RepoMismatchError):
                github_issues.sync_project_issues(
                    PROJECT_ID, "https://github.com/someone/else"
                )
        assert session.calls == []
        bulk.assert_not_called()
        # Explanation: a caller cannot import issues of a different repo
        # into this project.

    def test_repo_url_is_used_when_project_has_none(self, session):
        session.outcomes = [make_response(body=[])]
        with patch(f"{SERVICE}.get_project",
                   return_value=project_document(repo_url="")):
            result = github_issues.sync_project_issues(PROJECT_ID, REPO_URL)
        assert result["repository"]["full_name"] == "acme/widgets"
        # Explanation: the optional repo_url can supply the repository.

    def test_github_failure_means_no_persistence(self, session, project):
        session.outcomes = [make_response(500, {"message": "boom"})]
        with patch(f"{SERVICE}.bulk_upsert_issues") as bulk:
            with pytest.raises(GitHubAPIError):
                github_issues.sync_project_issues(PROJECT_ID)
        bulk.assert_not_called()
        # Explanation: a failed fetch never changes the stored data.

    def test_failure_on_later_page_means_no_persistence(self, session, project):
        page2 = "https://api.github.com/repositories/1/issues?page=2"
        session.outcomes = [
            make_response(body=[make_issue(1)], headers=link_header(page2)),
            requests.exceptions.ConnectionError("down"),
        ]
        with patch(f"{SERVICE}.bulk_upsert_issues") as bulk:
            with pytest.raises(GitHubAPIError):
                github_issues.sync_project_issues(PROJECT_ID)
        bulk.assert_not_called()
        # Explanation: page 1 alone is never saved when page 2 fails.

    def test_persistence_failure_propagates_and_is_not_reported_as_success(
        self, session, project
    ):
        session.outcomes = [make_response(body=[make_issue(1)])]
        with patch(f"{SERVICE}.bulk_upsert_issues",
                   side_effect=DatabaseError("db down")):
            with pytest.raises(DatabaseError):
                github_issues.sync_project_issues(PROJECT_ID)
        # Explanation: "synced" is only returned after the database
        # confirmed the write.

    def test_empty_github_result_does_not_delete_stored_issues(
        self, session, project, collection
    ):
        collection.documents.append(stored_issue(PROJECT_ID, 1001))
        session.outcomes = [make_response(body=[])]
        result = github_issues.sync_project_issues(PROJECT_ID)
        assert result["fetched_count"] == 0
        assert result["persisted_count"] == 0
        assert len(collection.documents) == 1
        assert collection.bulk_calls == 0
        collection.delete_many.assert_not_called()
        collection.delete_one.assert_not_called()
        # Explanation: GitHub returning nothing leaves earlier data alone.

    def test_repeated_synchronization_is_idempotent(
        self, session, project, collection
    ):
        body = [make_issue(1), make_issue(2), make_pr(3)]
        session.outcomes = [make_response(body=body), make_response(body=body)]
        first = github_issues.sync_project_issues(PROJECT_ID)
        second = github_issues.sync_project_issues(PROJECT_ID)
        assert first["created_count"] == 2
        assert second["created_count"] == 0
        assert second["updated_count"] == 2
        assert len(collection.documents) == 2
        assert collection.last_ordered is False
        # Explanation: full service + real persistence code: two syncs,
        # still exactly two stored issues.


class TestReadService:
    def test_reads_are_project_scoped_and_never_call_github(
        self, session, collection
    ):
        collection.documents = [
            stored_issue(PROJECT_ID, 1001),
            stored_issue(OTHER_PROJECT_ID, 2001),
        ]
        result = github_issues.get_issues_for_project(PROJECT_ID)
        assert [i["github_id"] for i in result] == [1001]
        assert session.calls == []
        # Explanation: only this project's issues are returned, and the
        # GitHub client is never even created.

    def test_state_filter(self, collection):
        collection.documents = [
            stored_issue(PROJECT_ID, 1001, state="open"),
            stored_issue(PROJECT_ID, 1002, state="closed"),
        ]
        closed = github_issues.get_issues_for_project(PROJECT_ID, state="closed")
        assert [i["github_id"] for i in closed] == [1002]
        # Explanation: state=closed returns only closed issues.

    def test_results_are_sorted_newest_activity_first(self, collection):
        collection.documents = [
            stored_issue(PROJECT_ID, 1001, updated_at="2024-01-01T00:00:00+00:00"),
            stored_issue(PROJECT_ID, 1002, updated_at="2024-03-01T00:00:00+00:00"),
        ]
        result = github_issues.get_issues_for_project(PROJECT_ID)
        assert [i["github_id"] for i in result] == [1002, 1001]
        # Explanation: the most recently updated issue comes first.

    def test_public_shape_contains_required_metadata_only(self, collection):
        collection.documents = [stored_issue(PROJECT_ID, 1001)]
        collection.documents[0]["synced_at"] = "internal"
        collection.documents[0]["repository_url"] = "internal"
        issue = github_issues.get_issues_for_project(PROJECT_ID)[0]
        assert issue["state"] == "open"
        assert issue["assignees"] == ["alice"]
        assert issue["labels"] == ["bug"]
        assert issue["comments"] == 3
        assert issue["created_at"] and issue["updated_at"]
        assert issue["closed_at"] is None
        assert "synced_at" not in issue and "repository_url" not in issue
        assert "projectId" not in issue
        # Explanation: required fields are present; internal bookkeeping
        # fields are not exposed.

    def test_old_documents_with_missing_fields_still_render(self, collection):
        collection.documents = [
            {"_id": ObjectId(), "projectId": ObjectId(PROJECT_ID),
             "github_id": 1, "number": 1, "title": "Old", "state": "open"},
        ]
        issue = github_issues.get_issues_for_project(PROJECT_ID)[0]
        assert issue["assignees"] == [] and issue["labels"] == []
        assert issue["comments"] == 0
        # Explanation: missing optional fields become empty values.

    @pytest.mark.parametrize("state", ["all", "OPEN", "merged"])
    def test_invalid_state_is_rejected(self, state):
        with pytest.raises(ValueError):
            github_issues.get_issues_for_project(PROJECT_ID, state=state)
        # Explanation: only "open" and "closed" are allowed.

    def test_empty_project_id_is_rejected(self):
        with pytest.raises(ValueError):
            github_issues.get_issues_for_project("")
        # Explanation: same validation style as the commit service.


# ===========================================================================
# 7. API endpoints
# ===========================================================================

class TestSyncEndpoint:
    URL = f"/api/projects/{PROJECT_ID}/sync-issues"

    def test_successful_sync(self, as_manager, project, session, collection):
        session.outcomes = [make_response(body=[
            make_issue(1), make_issue(2), make_pr(3),
        ])]
        response = client.post(self.URL)
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {
            "success", "status", "project_id", "repository", "fetched_count",
            "pull_requests_skipped", "persisted_count", "created_count",
            "updated_count",
        }
        assert body["status"] == "synced"
        assert body["project_id"] == PROJECT_ID
        assert body["fetched_count"] == 2
        assert body["pull_requests_skipped"] == 1
        assert body["created_count"] == 2
        assert len(collection.documents) == 2
        # Explanation: end to end through the real router, service and
        # persistence code; the body is optional.

    def test_sync_accepts_a_matching_repo_url_body(
        self, as_manager, project, session, collection
    ):
        session.outcomes = [make_response(body=[make_issue(1)])]
        response = client.post(self.URL, json={"repo_url": REPO_URL + "/"})
        assert response.status_code == 200
        # Explanation: trailing slashes do not count as a different repo.

    def test_sync_rejects_a_different_repository(
        self, as_manager, project, session, collection
    ):
        response = client.post(
            self.URL, json={"repo_url": "https://github.com/x/y"}
        )
        assert response.status_code == 400
        assert collection.bulk_calls == 0
        # Explanation: mismatch -> 400 and nothing saved.

    def test_second_sync_does_not_duplicate(
        self, as_manager, project, session, collection
    ):
        body = [make_issue(1), make_issue(2)]
        session.outcomes = [make_response(body=body), make_response(body=body)]
        client.post(self.URL)
        second = client.post(self.URL).json()
        assert second["created_count"] == 0
        assert len(collection.documents) == 2
        # Explanation: repeated API calls stay idempotent.

    def test_missing_project(self, as_manager, session):
        with patch(f"{ROUTER}.get_project", return_value=None):
            response = client.post(self.URL)
        assert response.status_code == 404
        assert session.calls == []
        # Explanation: unknown project -> 404 without calling GitHub.

    def test_invalid_project_id_format(self, as_manager):
        response = client.post("/api/projects/not-an-id/sync-issues")
        assert response.status_code == 400
        # Explanation: malformed IDs are a client error, not a 500.

    def test_project_without_repository_configuration(
        self, as_manager, session
    ):
        doc = project_document(repo_url="")
        with patch(f"{ROUTER}.get_project", return_value=doc), \
                patch(f"{SERVICE}.get_project", return_value=doc):
            response = client.post(self.URL)
        assert response.status_code == 400
        assert "repository" in response.json()["detail"].lower()
        assert session.calls == []
        # Explanation: configuration problem -> 400 with a readable reason.

    def test_non_member_is_forbidden(self, session):
        app.dependency_overrides[get_current_user] = lambda: OUTSIDER
        try:
            with patch(f"{ROUTER}.get_project", return_value=project_document()):
                response = client.post(self.URL)
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 403
        assert session.calls == []
        # Explanation: a manager who is not in the project cannot sync it.

    def test_developer_role_cannot_sync(self, session):
        doc = project_document()
        doc["members"] = [{"userId": DEVELOPER_ID}]
        app.dependency_overrides[get_current_user] = lambda: DEVELOPER
        try:
            with patch(f"{ROUTER}.get_project", return_value=doc):
                response = client.post(self.URL)
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 403
        assert session.calls == []
        # Explanation: syncing needs admin/project-manager role.

    def test_unauthenticated_request_is_rejected(self):
        app.dependency_overrides.clear()
        response = client.post(self.URL)
        assert response.status_code in (401, 403)
        # Explanation: no token, no access.

    @pytest.mark.parametrize(
        "outcome, expected",
        [
            (make_response(401, {"message": "Bad credentials"}), 401),
            (make_response(403, {"message": "Forbidden"}), 403),
            (make_response(404, {"message": "Not Found"}), 404),
            (make_response(429, {"message": "slow down"}), 429),
            (make_response(500, {"message": "boom"}), 502),
            (requests.exceptions.Timeout("slow"), 502),
            (make_response(raw=b"<html>"), 502),
        ],
        ids=["auth", "permission", "not-found", "rate-limit", "http-500",
             "timeout", "malformed"],
    )
    def test_github_failures_map_to_http_errors(
        self, as_manager, project, session, collection, outcome, expected
    ):
        session.outcomes = [outcome]
        response = client.post(self.URL)
        assert response.status_code == expected
        assert collection.bulk_calls == 0
        # Explanation: each upstream problem gets a meaningful status and
        # nothing is written.

    def test_missing_github_token_is_a_server_error(self, as_manager, project):
        with patch(f"{SERVICE}._get_authenticated_session",
                   side_effect=GitHubTokenMissingError("no token")):
            response = client.post(self.URL)
        assert response.status_code == 500
        assert "not configured" in response.json()["detail"]
        # Explanation: the client is told the server is misconfigured; the
        # token itself is never mentioned.

    def test_database_failure_returns_503_not_success(
        self, as_manager, project, session
    ):
        session.outcomes = [make_response(body=[make_issue(1)])]
        with patch(f"{SERVICE}.bulk_upsert_issues",
                   side_effect=DatabaseError("Database is temporarily unavailable.")):
            response = client.post(self.URL)
        assert response.status_code == 503
        assert response.json().get("success") is None
        # Explanation: a failed write is reported as an error, never as
        # "synced".


class TestListEndpoint:
    URL = f"/api/projects/{PROJECT_ID}/issues"

    def test_returns_persisted_issues_with_required_metadata(
        self, as_manager, project, collection
    ):
        collection.documents = [
            stored_issue(PROJECT_ID, 1001, assignees=["alice", "bob"],
                         labels=["bug", "urgent"], comments=5),
        ]
        response = client.get(self.URL)
        assert response.status_code == 200
        [issue] = response.json()
        assert issue["state"] == "open"
        assert issue["assignees"] == ["alice", "bob"]
        assert issue["labels"] == ["bug", "urgent"]
        assert issue["comments"] == 5
        assert issue["created_at"] == "2024-01-02T03:04:05+00:00"
        assert issue["updated_at"] == "2024-01-03T03:04:05+00:00"
        assert issue["closed_at"] is None
        assert issue["project_id"] == PROJECT_ID
        # Explanation: all metadata the feature requires, with timestamps
        # that carry an explicit UTC offset.

    def test_only_issues_of_the_requested_project_are_returned(
        self, as_manager, project, collection
    ):
        collection.documents = [
            stored_issue(PROJECT_ID, 1001),
            stored_issue(OTHER_PROJECT_ID, 2001),
            stored_issue(OTHER_PROJECT_ID, 2002),
        ]
        response = client.get(self.URL)
        assert [i["github_id"] for i in response.json()] == [1001]
        # Explanation: other projects' issues are invisible.

    def test_does_not_call_github(self, as_manager, project, collection, session):
        collection.documents = [stored_issue(PROJECT_ID, 1001)]
        client.get(self.URL)
        assert session.calls == []
        # Explanation: reading stored data must stay local.

    def test_empty_project_returns_empty_list(self, as_manager, project, collection):
        response = client.get(self.URL)
        assert response.status_code == 200
        assert response.json() == []
        # Explanation: no issues synced yet is a normal empty list.

    def test_state_query_filters_results(self, as_manager, project, collection):
        collection.documents = [
            stored_issue(PROJECT_ID, 1001, state="open"),
            stored_issue(PROJECT_ID, 1002, state="closed",
                         closed_at="2024-02-01T00:00:00+00:00"),
        ]
        closed = client.get(self.URL, params={"state": "closed"}).json()
        assert [i["github_id"] for i in closed] == [1002]
        assert closed[0]["closed_at"] == "2024-02-01T00:00:00+00:00"
        # Explanation: ?state=closed narrows the list.

    def test_invalid_state_query_is_a_validation_error(self, as_manager, project):
        assert client.get(self.URL, params={"state": "weird"}).status_code == 422
        # Explanation: FastAPI validates the query parameter.

    def test_developer_member_can_read(self, collection):
        doc = project_document()
        doc["members"] = [{"userId": DEVELOPER_ID}]
        collection.documents = [stored_issue(PROJECT_ID, 1001)]
        app.dependency_overrides[get_current_user] = lambda: DEVELOPER
        try:
            with patch(f"{ROUTER}.get_project", return_value=doc):
                response = client.get(self.URL)
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 200
        # Explanation: any project member may read, only managers sync.

    def test_non_member_is_forbidden(self, collection):
        app.dependency_overrides[get_current_user] = lambda: OUTSIDER
        try:
            with patch(f"{ROUTER}.get_project", return_value=project_document()):
                response = client.get(self.URL)
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 403
        # Explanation: outsiders cannot read a project's issues.

    def test_missing_project(self, as_manager):
        with patch(f"{ROUTER}.get_project", return_value=None):
            response = client.get(self.URL)
        assert response.status_code == 404
        # Explanation: unknown project -> 404.

    def test_invalid_project_id_format(self, as_manager):
        assert client.get("/api/projects/bad-id/issues").status_code == 400
        # Explanation: malformed ID -> 400.

    def test_unauthenticated_request_is_rejected(self):
        app.dependency_overrides.clear()
        assert client.get(self.URL).status_code in (401, 403)
        # Explanation: authentication is required for reading too.

    def test_database_failure_returns_503(self, as_manager, project):
        with patch(f"{SERVICE}.list_project_issues",
                   side_effect=DatabaseError("Database is temporarily unavailable.")):
            response = client.get(self.URL)
        assert response.status_code == 503
        # Explanation: a read failure is a 503, not a crash.


class TestRouting:
    def test_both_endpoints_are_registered_once(self):
        routes = [
            (method, route.path)
            for route in app.routes
            if hasattr(route, "methods")
            for method in route.methods
        ]
        assert routes.count(("GET", "/api/projects/{project_id}/issues")) == 1
        assert routes.count(("POST", "/api/projects/{project_id}/sync-issues")) == 1
        # Explanation: proves the endpoints exist on the real FastAPI app
        # exactly once (no duplicate router registration).

    def test_existing_sync_routes_are_still_registered(self):
        paths = {route.path for route in app.routes if hasattr(route, "path")}
        assert "/api/projects/{project_id}/sync-commits" in paths
        assert "/api/projects/{project_id}/sync-contributors" in paths
        # Explanation: the new endpoints did not disturb the older ones.
