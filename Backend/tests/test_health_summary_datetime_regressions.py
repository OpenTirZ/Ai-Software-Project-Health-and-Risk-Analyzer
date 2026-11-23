"""Regression tests for timezone normalization in health indicators."""

from datetime import datetime

from Backend.analysis.health_summary import (
    compute_bottlenecks_indicator,
    compute_schedule_risk_indicator,
    compute_stale_issues_indicator,
)


def test_bottlenecks_accept_naive_now_and_offset_timestamp():
    now = datetime(2026, 11, 4, 12, 0, 0)
    pull_requests = [
        {
            "state": "open",
            "created_at": "2026-11-04T06:00:00+00:00",
            "number": 1,
        }
    ]

    result = compute_bottlenecks_indicator(pull_requests, now=now)

    assert result["details"]["avg_pr_age_hours"] == 6.0


def test_stale_issues_accept_naive_now_and_offset_timestamp():
    now = datetime(2026, 11, 20, 12, 0, 0)
    issues = [
        {
            "state": "open",
            "updated_at": "2026-11-01T12:00:00+05:30",
            "number": 2,
        }
    ]

    result = compute_stale_issues_indicator(issues, now=now)

    assert result["details"]["stale_issues_count"] == 1


def test_schedule_risk_accepts_naive_now_with_offset_dates():
    now = datetime(2026, 11, 20, 12, 0, 0)
    milestones = [
        {
            "state": "open",
            "due_on": "2026-11-19T12:00:00+00:00",
            "open_issues": 1,
            "closed_issues": 0,
        }
    ]

    result = compute_schedule_risk_indicator(milestones=milestones, now=now)

    assert result["details"]["overdue_count"] == 1


def test_bottlenecks_ignore_malformed_pr_records():
    pull_requests = [
        None,
        "not-a-pull-request",
        {"state": "open", "created_at": "2026-11-04T11:00:00+00:00"},
    ]

    result = compute_bottlenecks_indicator(
        pull_requests,
        now=datetime(2026, 11, 4, 12, 0, 0),
    )

    assert result["details"]["total_prs_tracked"] == 1
    assert result["details"]["open_prs_count"] == 1


def test_stale_issues_return_insufficient_for_only_malformed_records():
    result = compute_stale_issues_indicator(
        [None, "not-an-issue"],
        now=datetime(2026, 11, 20, 12, 0, 0),
    )

    assert result["status"] == "Insufficient Data"
    assert result["data_status"] == "insufficient_data"


def test_stale_issues_ignore_malformed_records_when_valid_issues_exist():
    result = compute_stale_issues_indicator(
        [
            None,
            {"state": "open", "updated_at": "2026-11-01T12:00:00+00:00"},
        ],
        now=datetime(2026, 11, 20, 12, 0, 0),
    )

    assert result["details"]["open_issues_count"] == 1
    assert result["details"]["stale_issues_count"] == 1


def test_workload_groups_commits_by_stable_github_login():
    from Backend.analysis.health_summary import compute_workload_indicator

    result = compute_workload_indicator(
        commits=[
            {"author": {"login": "alice", "name": "Alice Smith"}},
            {"author": {"login": "alice", "name": "Alice Patel"}},
            {"author": {"login": "bob", "name": "Bob"}},
        ]
    )

    assert result["details"]["total_contributors"] == 2
    assert result["details"]["top_contributor"] == "alice"
    assert result["details"]["top_contributor_share"] == 0.667


def test_workload_groups_string_authors_case_insensitively():
    from Backend.analysis.health_summary import compute_workload_indicator

    result = compute_workload_indicator(
        commits=[
            {"author": "Alice"},
            {"author": "alice"},
            {"author": "Bob"},
        ]
    )

    assert result["details"]["total_contributors"] == 2
    assert result["details"]["top_contributor"] == "Alice"


def test_workload_ignores_invalid_contributor_counts():
    from Backend.analysis.health_summary import compute_workload_indicator

    result = compute_workload_indicator(
        commits=None,
        contributors=[
            {"github_username": "alice", "contributions": 5},
            {"github_username": "bob", "contributions": -3},
            {"github_username": "carol", "contributions": "many"},
            {"github_username": "dave", "contributions": True},
            None,
        ]
    )

    assert result["details"]["total_contributors"] == 1
    assert result["details"]["total_activity_events"] == 5
    assert result["details"]["top_contributor"] == "alice"


def test_workload_returns_insufficient_when_all_contributor_counts_are_invalid():
    from Backend.analysis.health_summary import compute_workload_indicator

    result = compute_workload_indicator(
        contributors=[
            {"github_username": "alice", "contributions": "five"},
            {"github_username": "bob", "contributions": -1},
        ]
    )

    assert result["status"] == "Insufficient Data"
