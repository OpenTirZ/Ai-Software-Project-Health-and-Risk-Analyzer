
from datetime import datetime, timedelta, timezone

import pytest

from Backend.analysis.bottleneck_engine import (
    detect_aging_prs,
    detect_review_queue_congestion,
    detect_bottlenecks,
)
from Backend.analysis.stale_issues_engine import detect_stale_issues


NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def timestamp(hours_ago=0, days_ago=0):
    return (NOW - timedelta(hours=hours_ago, days=days_ago)).isoformat()


# -------------------- Aging PR tests --------------------

def test_detect_aging_prs():
    prs = [
        {
            "number": 1,
            "title": "Old PR",
            "state": "open",
            "created_at": timestamp(hours_ago=60),
            "reviews": [],
        },
        {
            "number": 2,
            "title": "Recent PR",
            "state": "open",
            "created_at": timestamp(hours_ago=24),
            "reviews": [],
        },
    ]

    result = detect_aging_prs(prs, now=NOW)

    assert len(result) == 1
    assert result[0]["pr_number"] == 1
    assert result[0]["age_hours"] == 60
    assert result[0]["threshold_hours"] == 48


def test_aging_pr_threshold_boundary():
    prs = [
        {
            "number": 1,
            "state": "open",
            "created_at": timestamp(hours_ago=48),
            "reviews": [],
        },
        {
            "number": 2,
            "state": "open",
            "created_at": timestamp(hours_ago=49),
            "reviews": [],
        },
    ]

    result = detect_aging_prs(prs, now=NOW)

    assert [pr["pr_number"] for pr in result] == [2]


def test_aging_pr_ignores_closed_merged_and_reviewed_prs():
    prs = [
        {
            "number": 1,
            "state": "closed",
            "created_at": timestamp(hours_ago=80),
            "reviews": [],
        },
        {
            "number": 2,
            "state": "open",
            "merged": True,
            "created_at": timestamp(hours_ago=80),
            "reviews": [],
        },
        {
            "number": 3,
            "state": "open",
            "created_at": timestamp(hours_ago=80),
            "reviews": [{"user": {"login": "reviewer1"}}],
        },
        {
            "number": 4,
            "state": "open",
            "created_at": timestamp(hours_ago=80),
            "reviews_count": 1,
        },
    ]

    assert detect_aging_prs(prs, now=NOW) == []


@pytest.mark.parametrize(
    "created_at",
    [
        None,
        "invalid-date",
        "2026-11-10T12:00:00",
        timestamp(hours_ago=-2),
    ],
)
def test_aging_pr_ignores_invalid_or_future_dates(created_at):
    prs = [{
        "number": 1,
        "state": "open",
        "created_at": created_at,
        "reviews": [],
    }]

    assert detect_aging_prs(prs, now=NOW) == []


def test_aging_pr_custom_threshold_and_empty_input():
    prs = [{
        "number": 1,
        "state": "open",
        "created_at": timestamp(hours_ago=30),
        "reviews": [],
    }]

    assert len(detect_aging_prs(prs, threshold_hours=24, now=NOW)) == 1
    assert detect_aging_prs([], now=NOW) == []
    assert detect_aging_prs(None, now=NOW) == []


def test_aging_pr_invalid_threshold():
    with pytest.raises(ValueError):
        detect_aging_prs([], threshold_hours=0, now=NOW)


# -------------------- Reviewer congestion tests --------------------

def test_detect_review_queue_congestion():
    prs = [
        {
            "number": i,
            "state": "open",
            "requested_reviewers": ["reviewer1"],
            "reviews": [],
        }
        for i in range(1, 7)
    ]

    result = detect_review_queue_congestion(prs)

    assert len(result) == 1
    assert result[0]["reviewer"] == "reviewer1"
    assert result[0]["pending_count"] == 6
    assert result[0]["pr_numbers"] == [1, 2, 3, 4, 5, 6]


def test_review_queue_threshold_boundary():
    prs = [
        {
            "number": i,
            "state": "open",
            "requested_reviewers": ["reviewer1"],
            "reviews": [],
        }
        for i in range(1, 7)
    ]

    assert detect_review_queue_congestion(prs[:5]) == []
    assert len(detect_review_queue_congestion(prs)) == 1


def test_review_queue_ignores_reviewed_closed_and_duplicate_requests():
    prs = [
        {
            "number": 1,
            "state": "open",
            "requested_reviewers": ["reviewer1", "reviewer1"],
            "reviews": [],
        },
        {
            "number": 2,
            "state": "open",
            "requested_reviewers": ["reviewer1"],
            "reviews": [{"user": {"login": "reviewer1"}}],
        },
        {
            "number": 3,
            "state": "closed",
            "requested_reviewers": ["reviewer1"],
            "reviews": [],
        },
    ]

    assert detect_review_queue_congestion(prs) == []


def test_review_queue_supports_reviewer_objects_and_case_insensitive_matching():
    prs = [
        {
            "number": i,
            "state": "open",
            "requested_reviewers": [{"login": "Reviewer1"}],
            "reviews": [],
        }
        for i in range(1, 7)
    ]

    result = detect_review_queue_congestion(prs)

    assert len(result) == 1
    assert result[0]["pending_count"] == 6


def test_review_queue_empty_input_and_custom_threshold():
    prs = [
        {
            "number": i,
            "state": "open",
            "requested_reviewers": ["reviewer1"],
            "reviews": [],
        }
        for i in range(1, 4)
    ]

    assert detect_review_queue_congestion([]) == []
    assert detect_review_queue_congestion(None) == []
    assert detect_review_queue_congestion(
        prs, max_pending_prs=2
    )[0]["pending_count"] == 3


def test_review_queue_invalid_threshold():
    with pytest.raises(ValueError):
        detect_review_queue_congestion([], max_pending_prs=-1)


# -------------------- Combined bottleneck tests --------------------

def test_detect_bottlenecks_returns_both_categories():
    prs = [
        {
            "number": i,
            "state": "open",
            "created_at": timestamp(hours_ago=60),
            "requested_reviewers": ["reviewer1"],
            "reviews": [],
        }
        for i in range(1, 7)
    ]

    result = detect_bottlenecks(prs, now=NOW)

    assert "aging_prs" in result
    assert "review_queue_congestion" in result
    assert len(result["aging_prs"]) == 6
    assert len(result["review_queue_congestion"]) == 1


def test_detect_bottlenecks_empty_input():
    result = detect_bottlenecks([], now=NOW)

    assert result == {
        "aging_prs": [],
        "review_queue_congestion": [],
    }


# -------------------- Stale issue tests --------------------

def test_detect_stale_issues():
    issues = [
        {
            "number": 1,
            "title": "Old issue",
            "state": "open",
            "updated_at": timestamp(days_ago=20),
            "labels": [],
        },
        {
            "number": 2,
            "title": "Recent issue",
            "state": "open",
            "updated_at": timestamp(days_ago=5),
            "labels": [],
        },
    ]

    result = detect_stale_issues(issues, now=NOW)

    stale = result["stale_issues"]
    assert len(stale) == 1
    assert stale[0]["issue_number"] == 1
    assert stale[0]["inactive_days"] == 20
    assert stale[0]["activity_source"] == "updated_at"
    assert "activity_tracking_limitation" in stale[0]


def test_stale_issue_threshold_boundary():
    issues = [
        {
            "number": 1,
            "state": "open",
            "updated_at": timestamp(days_ago=14),
            "labels": [],
        },
        {
            "number": 2,
            "state": "open",
            "updated_at": timestamp(days_ago=15),
            "labels": [],
        },
    ]

    result = detect_stale_issues(issues, now=NOW)

    assert [issue["issue_number"] for issue in result["stale_issues"]] == [2]


@pytest.mark.parametrize(
    "labels",
    [
        ["on-hold"],
        ["deferred"],
        ["ON-HOLD"],
        [{"name": "Deferred"}],
        ["bug", "on-hold"],
    ],
)
def test_stale_issue_excludes_on_hold_and_deferred(labels):
    issues = [{
        "number": 1,
        "state": "open",
        "updated_at": timestamp(days_ago=30),
        "labels": labels,
    }]

    assert detect_stale_issues(issues, now=NOW)["stale_issues"] == []


def test_stale_issue_does_not_exclude_similar_labels():
    issues = [{
        "number": 1,
        "state": "open",
        "updated_at": timestamp(days_ago=30),
        "labels": ["not-on-hold", "deferred-work"],
    }]

    result = detect_stale_issues(issues, now=NOW)

    assert len(result["stale_issues"]) == 1


def test_stale_issue_ignores_closed_issues():
    issues = [{
        "number": 1,
        "state": "closed",
        "updated_at": timestamp(days_ago=30),
        "labels": [],
    }]

    assert detect_stale_issues(issues, now=NOW)["stale_issues"] == []


@pytest.mark.parametrize(
    "updated_at",
    [
        None,
        "invalid-date",
        "2026-11-10T12:00:00",
        timestamp(days_ago=-2),
    ],
)
def test_stale_issue_ignores_invalid_or_future_dates(updated_at):
    issues = [{
        "number": 1,
        "state": "open",
        "updated_at": updated_at,
        "labels": [],
    }]

    assert detect_stale_issues(issues, now=NOW)["stale_issues"] == []


def test_stale_issue_custom_threshold_and_empty_input():
    issues = [{
        "number": 1,
        "state": "open",
        "updated_at": timestamp(days_ago=5),
        "labels": [],
    }]

    assert len(
        detect_stale_issues(issues, threshold_days=3, now=NOW)["stale_issues"]
    ) == 1

    assert detect_stale_issues([], now=NOW) == {"stale_issues": []}
    assert detect_stale_issues(None, now=NOW) == {"stale_issues": []}


@pytest.mark.parametrize("threshold", [0, -1, True, "14"])
def test_stale_issue_rejects_invalid_threshold(threshold):
    with pytest.raises(ValueError):
        detect_stale_issues([], threshold_days=threshold, now=NOW)


def test_stale_issue_requires_timezone_aware_now():
    with pytest.raises(ValueError):
        detect_stale_issues([], now=datetime(2026, 11, 16, 12, 0))


# -------------------- Invalid input tests --------------------

def test_engines_ignore_non_dictionary_items():
    assert detect_aging_prs([None, "invalid"], now=NOW) == []
    assert detect_review_queue_congestion([None, "invalid"]) == []
    assert detect_stale_issues(
        [None, "invalid"], now=NOW
    ) == {"stale_issues": []}
