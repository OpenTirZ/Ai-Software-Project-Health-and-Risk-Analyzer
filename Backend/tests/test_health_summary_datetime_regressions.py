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
