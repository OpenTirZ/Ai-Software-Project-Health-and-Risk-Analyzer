"""
Unit and Integration Tests for Workload & Schedule Risk Engines
---------------------------------------------------------------
Task: TASK-SP2-09 (Issue #73)

Tests:
  Part 1: Workload Engine (compute_workload_distribution)
    1. Normal distribution across multiple contributors
    2. One contributor accounting for > 60% of commits (Bus Factor triggered)
    3. One contributor accounting for > 60% of PRs (Bus Factor triggered)
    4. Exactly 60% should NOT trigger a flag (strictly greater than check)
    5. Balanced contributor distribution (e.g. 33%, 33%, 34%)
    6. Commit and PR distributions must be independent
    7. Only records within trailing 30 days counted
    8. Records outside window excluded
    9. Different timezone representations (UTC, Z, offsets)
   10. Invalid and missing timestamps
   11. Missing contributor identities (unattributed count visible, not inflating shares)
   12. Single contributor scenario
   13. Empty input list
   14. None input
   15. Custom analysis time for deterministic testing
   16. Mandatory disclaimer present
   17. Author as string or dict representation
   18. Strict validation: reject booleans and non-integer window_days
   19. Strict validation: reject NaN, infinity, booleans, and out-of-range thresholds

  Part 2: Schedule Risk Engine (compute_schedule_drift)
    1. Open task count calculation
    2. Recent completion velocity calculation (formula: closed / 30)
    3. Projected completion date calculation
    4. Positive schedule drift (projected delay)
    5. On-time projected completion (zero or negative drift)
    6. No recent completed tasks (insufficient velocity, no fake drift)
    7. Zero completion velocity handled without DivisionByZero
    8. Missing milestone deadline handled gracefully
    9. Missing issue data handled gracefully
   10. No remaining open tasks (0 days remaining)
   11. Multiple milestones: individual estimates and worst positive drift
   12. Invalid timestamps and date handling
   13. Pull requests in issues input are excluded
   14. Indicative estimate disclaimer present
   15. Pure analytical nature: no mutation of inputs, zero external calls
   16. Milestone open_issues = 0 explicitly preserved (does not fall back to project tasks)
   17. Milestone open_issues missing/None falls back to project remaining tasks
   18. Velocity precision regression test: 1 closed task, 1 open task, 30 days window -> exactly 30 days
   19. Strict validation: reject booleans and non-integer velocity_window_days
   20. Timezone normalization: datetime with non-UTC offset normalized to UTC
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
import pytest

from Backend.analysis.workload_engine import (
    DEFAULT_ANALYSIS_WINDOW_DAYS,
    DEFAULT_BUS_FACTOR_THRESHOLD,
    WORKLOAD_DISCLAIMER,
    compute_workload_distribution,
)
from Backend.analysis.schedule_risk_engine import (
    DEFAULT_VELOCITY_WINDOW_DAYS,
    SCHEDULE_DISCLAIMER,
    compute_schedule_drift,
)

# Fixed deterministic baseline time
BASE_NOW = datetime(2026, 11, 15, 12, 0, 0, tzinfo=timezone.utc)


# ===========================================================================
# PART 1: WORKLOAD ENGINE TESTS
# ===========================================================================

class TestWorkloadEngine:
    def test_normal_distribution_multiple_contributors(self):
        """Case 1: Normal distribution across multiple contributors."""
        commits = [
            {"sha": "c1", "author": "Alice", "timestamp": "2026-11-10T10:00:00Z"},
            {"sha": "c2", "author": "Bob", "timestamp": "2026-11-11T11:00:00Z"},
            {"sha": "c3", "author": "Charlie", "timestamp": "2026-11-12T12:00:00Z"},
            {"sha": "c4", "author": "Alice", "timestamp": "2026-11-13T13:00:00Z"},
        ]
        prs = [
            {"number": 1, "author": "Bob", "created_at": "2026-11-10T10:00:00Z"},
            {"number": 2, "author": "Alice", "created_at": "2026-11-11T11:00:00Z"},
        ]

        result = compute_workload_distribution(commits=commits, pull_requests=prs, now=BASE_NOW)

        # 4 commits total: Alice=2 (50%), Bob=1 (25%), Charlie=1 (25%)
        c_dist = result["commit_distribution"]
        assert c_dist["total_events"] == 4
        assert c_dist["attributed_events"] == 4
        assert c_dist["unattributed_events"] == 0
        assert c_dist["top_contributor"] == "Alice"
        assert c_dist["top_contributor_percentage"] == 50.0

        # No bus factor triggered (50% < 60%)
        assert result["bus_factor_risk"] is False
        assert len(result["flags"]) == 0

    def test_bus_factor_commits_greater_than_60_percent(self):
        """Case 2: One contributor accounting for strictly > 60% of commits."""
        # 7 out of 10 commits by Alice = 70% > 60%
        commits = [
            {"sha": f"c{i}", "author": "Alice", "timestamp": "2026-11-05T00:00:00Z"}
            for i in range(7)
        ] + [
            {"sha": f"cb{i}", "author": "Bob", "timestamp": "2026-11-06T00:00:00Z"}
            for i in range(3)
        ]

        result = compute_workload_distribution(commits=commits, now=BASE_NOW)

        assert result["bus_factor_risk"] is True
        assert len(result["flags"]) == 1
        flag = result["flags"][0]
        assert flag["type"] == "bus_factor_risk"
        assert flag["activity_type"] == "commits"
        assert flag["contributor"] == "Alice"
        assert flag["percentage"] == 70.0
        assert flag["threshold_percentage"] == 60.0

    def test_bus_factor_prs_greater_than_60_percent(self):
        """Case 3: One contributor accounting for strictly > 60% of PRs."""
        # 4 out of 5 PRs by Bob = 80% > 60%
        prs = [
            {"number": i, "github_username": "bob", "created_at": "2026-11-05T00:00:00Z"}
            for i in range(1, 5)
        ] + [
            {"number": 5, "github_username": "charlie", "created_at": "2026-11-06T00:00:00Z"}
        ]

        result = compute_workload_distribution(pull_requests=prs, now=BASE_NOW)

        assert result["bus_factor_risk"] is True
        assert len(result["flags"]) == 1
        flag = result["flags"][0]
        assert flag["activity_type"] == "pull_requests"
        assert flag["contributor"] == "bob"
        assert flag["percentage"] == 80.0

    def test_exactly_60_percent_does_not_trigger_flag(self):
        """Case 4: Exactly 60% must NOT trigger a flag (strict inequality check)."""
        # 3 out of 5 commits by Alice = exactly 60.0%
        commits = [
            {"sha": f"c{i}", "author": "Alice", "timestamp": "2026-11-05T00:00:00Z"}
            for i in range(3)
        ] + [
            {"sha": "cb1", "author": "Bob", "timestamp": "2026-11-06T00:00:00Z"},
            {"sha": "cb2", "author": "Charlie", "timestamp": "2026-11-07T00:00:00Z"},
        ]

        result = compute_workload_distribution(commits=commits, now=BASE_NOW)

        c_dist = result["commit_distribution"]
        assert c_dist["top_contributor"] == "Alice"
        assert c_dist["top_contributor_percentage"] == 60.0
        # Must be strictly greater than 60% -> False
        assert result["bus_factor_risk"] is False
        assert len(result["flags"]) == 0

    def test_balanced_contributor_distribution(self):
        """Case 5: Balanced contributor distribution."""
        commits = [
            {"sha": "c1", "author": "DevA", "timestamp": "2026-11-01T00:00:00Z"},
            {"sha": "c2", "author": "DevB", "timestamp": "2026-11-02T00:00:00Z"},
            {"sha": "c3", "author": "DevC", "timestamp": "2026-11-03T00:00:00Z"},
        ]
        result = compute_workload_distribution(commits=commits, now=BASE_NOW)

        c_dist = result["commit_distribution"]
        assert c_dist["contributor_count"] == 3
        for contrib in c_dist["contributors"]:
            assert contrib["count"] == 1
            assert pytest.approx(contrib["percentage"], 0.1) == 33.33

        assert result["bus_factor_risk"] is False

    def test_commit_and_pr_distributions_are_independent(self):
        """Case 6: Commit and PR distributions are calculated independently."""
        # Alice dominates commits (100% -> flag)
        commits = [
            {"sha": "c1", "author": "Alice", "timestamp": "2026-11-01T00:00:00Z"},
            {"sha": "c2", "author": "Alice", "timestamp": "2026-11-02T00:00:00Z"},
        ]
        # PRs are split evenly (Bob 50%, Charlie 50% -> no PR flag)
        prs = [
            {"number": 1, "author": "Bob", "created_at": "2026-11-01T00:00:00Z"},
            {"number": 2, "author": "Charlie", "created_at": "2026-11-02T00:00:00Z"},
        ]

        result = compute_workload_distribution(commits=commits, pull_requests=prs, now=BASE_NOW)

        assert result["commit_distribution"]["top_contributor"] == "Alice"
        assert result["commit_distribution"]["top_contributor_percentage"] == 100.0

        assert result["pr_distribution"]["top_contributor"] in ("Bob", "Charlie")
        assert result["pr_distribution"]["top_contributor_percentage"] == 50.0

        assert result["bus_factor_risk"] is True
        assert len(result["flags"]) == 1
        assert result["flags"][0]["activity_type"] == "commits"

    def test_trailing_window_filtering(self):
        """Case 7 & 8: Trailing 30-day filtering excludes older records."""
        # BASE_NOW = 2026-11-15T12:00:00Z
        # 30 days prior = 2026-10-16T12:00:00Z
        commits = [
            # Inside window
            {"sha": "c_recent_1", "author": "Alice", "timestamp": "2026-11-10T10:00:00Z"},
            {"sha": "c_recent_2", "author": "Bob", "timestamp": "2026-10-17T12:00:00Z"},
            # Outside window (older than 30 days)
            {"sha": "c_old_1", "author": "Charlie", "timestamp": "2026-10-10T00:00:00Z"},
            {"sha": "c_old_2", "author": "Alice", "timestamp": "2025-01-01T00:00:00Z"},
            # Future timestamp past now
            {"sha": "c_future", "author": "Alice", "timestamp": "2026-11-20T00:00:00Z"},
        ]

        result = compute_workload_distribution(commits=commits, now=BASE_NOW)

        c_dist = result["commit_distribution"]
        assert c_dist["total_events"] == 2
        contributors = {c["contributor"]: c["count"] for c in c_dist["contributors"]}
        assert "Alice" in contributors
        assert "Bob" in contributors
        assert "Charlie" not in contributors

    def test_timezone_representations(self):
        """Case 9: Correctly parses diverse timezone representations and normalizes to UTC."""
        commits = [
            # UTC with 'Z'
            {"sha": "c1", "author": "Alice", "timestamp": "2026-11-10T10:00:00Z"},
            # Offset +05:30
            {"sha": "c2", "author": "Alice", "timestamp": "2026-11-10T15:30:00+05:30"},
            # Offset -04:00
            {"sha": "c3", "author": "Bob", "timestamp": "2026-11-10T06:00:00-04:00"},
            # Native datetime with timezone offset
            {"sha": "c4", "author": "Charlie", "timestamp": datetime(2026, 11, 10, 15, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))},
        ]

        result = compute_workload_distribution(commits=commits, now=BASE_NOW)
        assert result["commit_distribution"]["total_events"] == 4

    def test_invalid_and_missing_timestamps(self):
        """Case 10: Gracefully handles invalid and missing timestamps."""
        commits = [
            {"sha": "c1", "author": "Alice", "timestamp": "2026-11-10T10:00:00Z"},
            {"sha": "c2", "author": "Bob", "timestamp": "not-a-valid-date"},
            {"sha": "c3", "author": "Charlie", "timestamp": None},
            {"sha": "c4", "author": "Dan"},  # missing timestamp key
        ]

        result = compute_workload_distribution(commits=commits, now=BASE_NOW)
        assert result["commit_distribution"]["total_events"] == 1
        assert result["commit_distribution"]["top_contributor"] == "Alice"

    def test_unattributed_contributor_identities(self):
        """Case 11: Missing identities reported separately; do not inflate shares."""
        commits = [
            {"sha": "c1", "author": "Alice", "timestamp": "2026-11-10T10:00:00Z"},
            {"sha": "c2", "author": "Unknown", "timestamp": "2026-11-11T10:00:00Z"},
            {"sha": "c3", "author": None, "timestamp": "2026-11-12T10:00:00Z"},
            {"sha": "c4", "timestamp": "2026-11-13T10:00:00Z"},
        ]

        result = compute_workload_distribution(commits=commits, now=BASE_NOW)

        c_dist = result["commit_distribution"]
        assert c_dist["total_events"] == 4
        assert c_dist["attributed_events"] == 1
        assert c_dist["unattributed_events"] == 3
        # Alice has 1 event out of 4 total events = 25.0% (not 100%)
        assert c_dist["top_contributor"] == "Alice"
        assert c_dist["top_contributor_percentage"] == 25.0
        # No fake 'Unknown' contributor added to contributor list
        contrib_names = [c["contributor"] for c in c_dist["contributors"]]
        assert "Unknown" not in contrib_names
        assert contrib_names == ["Alice"]

    def test_contributor_normalization_case_insensitivity(self):
        """Ensure case variations like 'Alice' and 'alice' merge into one contributor."""
        commits = [
            {"sha": "c1", "author": "Alice", "timestamp": "2026-11-10T10:00:00Z"},
            {"sha": "c2", "author": "alice", "timestamp": "2026-11-11T10:00:00Z"},
            {"sha": "c3", "github_username": "ALICE", "timestamp": "2026-11-12T10:00:00Z"},
        ]

        result = compute_workload_distribution(commits=commits, now=BASE_NOW)

        c_dist = result["commit_distribution"]
        assert c_dist["contributor_count"] == 1
        assert c_dist["total_events"] == 3
        assert c_dist["top_contributor_percentage"] == 100.0

    def test_author_dict_representation(self):
        """Verify author dictionary format is supported."""
        commits = [
            {
                "sha": "c1",
                "author": {"login": "gh_alice", "name": "Alice Developer"},
                "timestamp": "2026-11-10T10:00:00Z",
            },
            {
                "sha": "c2",
                "author": {"name": "Bob Builder", "email": "bob@example.com"},
                "timestamp": "2026-11-11T10:00:00Z",
            },
        ]
        result = compute_workload_distribution(commits=commits, now=BASE_NOW)
        c_dist = result["commit_distribution"]
        assert c_dist["total_events"] == 2
        names = [c["contributor"] for c in c_dist["contributors"]]
        assert "gh_alice" in names
        assert "Bob Builder" in names

    def test_single_contributor_triggers_bus_factor(self):
        """Case 12: Single contributor accounts for 100% -> Bus Factor flag."""
        commits = [
            {"sha": "c1", "author": "SoloDev", "timestamp": "2026-11-10T10:00:00Z"},
            {"sha": "c2", "author": "SoloDev", "timestamp": "2026-11-11T10:00:00Z"},
        ]

        result = compute_workload_distribution(commits=commits, now=BASE_NOW)

        assert result["bus_factor_risk"] is True
        assert len(result["flags"]) == 1
        assert result["flags"][0]["percentage"] == 100.0

    def test_empty_and_none_input(self):
        """Case 13 & 14: Handles empty and None inputs without exceptions."""
        result_none = compute_workload_distribution(commits=None, pull_requests=None, now=BASE_NOW)
        assert result_none["commit_distribution"]["total_events"] == 0
        assert result_none["pr_distribution"]["total_events"] == 0
        assert result_none["bus_factor_risk"] is False
        assert len(result_none["flags"]) == 0

        result_empty = compute_workload_distribution(commits=[], pull_requests=[], now=BASE_NOW)
        assert result_empty["commit_distribution"]["total_events"] == 0
        assert result_empty["pr_distribution"]["total_events"] == 0

    def test_mandatory_disclaimer_present(self):
        """Case 16: Mandatory disclaimer exact text is present."""
        result = compute_workload_distribution(commits=[], now=BASE_NOW)
        assert result["disclaimer"] == WORKLOAD_DISCLAIMER
        assert "Activity is a proxy indicator, not a definitive performance evaluation." in result["disclaimer"]

    def test_strict_input_validation_window_days(self):
        """Case 18: Reject booleans, floats, non-positives, strings for window_days."""
        with pytest.raises(ValueError, match="window_days must be a positive integer greater than 0"):
            compute_workload_distribution(window_days=0)

        with pytest.raises(ValueError, match="window_days must be a positive integer greater than 0"):
            compute_workload_distribution(window_days=-5)

        with pytest.raises(ValueError, match="window_days must be a positive integer greater than 0"):
            compute_workload_distribution(window_days=30.5)  # float

        with pytest.raises(ValueError, match="window_days must be a positive integer greater than 0"):
            compute_workload_distribution(window_days=True)  # bool

        with pytest.raises(ValueError, match="window_days must be a positive integer greater than 0"):
            compute_workload_distribution(window_days="30")  # string

    def test_strict_input_validation_bus_factor_threshold(self):
        """Case 19: Reject booleans, NaN, Inf, out-of-range for bus_factor_threshold."""
        with pytest.raises(ValueError, match="bus_factor_threshold must be a finite numeric value"):
            compute_workload_distribution(bus_factor_threshold=0.0)

        with pytest.raises(ValueError, match="bus_factor_threshold must be a finite numeric value"):
            compute_workload_distribution(bus_factor_threshold=1.5)

        with pytest.raises(ValueError, match="bus_factor_threshold must be a finite numeric value"):
            compute_workload_distribution(bus_factor_threshold=float("nan"))

        with pytest.raises(ValueError, match="bus_factor_threshold must be a finite numeric value"):
            compute_workload_distribution(bus_factor_threshold=float("inf"))

        with pytest.raises(ValueError, match="bus_factor_threshold must be a finite numeric value"):
            compute_workload_distribution(bus_factor_threshold=True)


# ===========================================================================
# PART 2: SCHEDULE RISK ENGINE TESTS
# ===========================================================================

class TestScheduleRiskEngine:
    def test_open_task_count_and_pr_exclusion(self):
        """Case 1 & 13: Counts genuine open tasks and excludes PRs."""
        issues = [
            {"number": 1, "title": "Issue 1", "state": "open"},
            {"number": 2, "title": "Issue 2", "state": "open"},
            {"number": 3, "title": "Issue 3", "state": "closed", "closed_at": "2026-11-10T00:00:00Z"},
            # PR item in issues list
            {"number": 4, "title": "PR 4", "state": "open", "pull_request": {"url": "http://..."}},
        ]

        result = compute_schedule_drift(issues=issues, now=BASE_NOW)

        # 2 genuine open tasks (#1, #2)
        assert result["remaining_open_tasks"] == 2
        # PR #4 excluded

    def test_completion_velocity_calculation(self):
        """Case 2: Velocity formula: closed_tasks / window_days."""
        # 6 tasks closed within the 30-day window
        # velocity = 6 / 30 = 0.20 tasks/day
        issues = [
            {
                "number": i,
                "state": "closed",
                "closed_at": (BASE_NOW - timedelta(days=i * 3)).isoformat(),
            }
            for i in range(1, 7)
        ] + [
            # 1 task closed 40 days ago (outside window)
            {
                "number": 99,
                "state": "closed",
                "closed_at": (BASE_NOW - timedelta(days=40)).isoformat(),
            },
            # 1 open task
            {"number": 100, "state": "open"},
        ]

        result = compute_schedule_drift(issues=issues, now=BASE_NOW, velocity_window_days=30)

        assert result["recently_completed_tasks"] == 6
        assert result["completion_velocity_per_day"] == 0.2
        # remaining = 1, days = 1 / 0.2 = 5.0 days
        assert result["estimated_completion_days"] == 5.0
        expected_date = (BASE_NOW + timedelta(days=5)).isoformat()
        assert result["estimated_completion_date"] == expected_date

    def test_velocity_precision_regression(self):
        """Case 18: Regression test for full precision internal calculations."""
        # Analysis window = 30 days
        # 1 recently completed task -> raw_velocity = 1/30
        # 1 remaining open task -> est days = 1 / (1/30) = 30.0 days (exactly)
        issues = [
            {"number": 1, "state": "open"},
            {"number": 2, "state": "closed", "closed_at": (BASE_NOW - timedelta(days=5)).isoformat()},
        ]

        result = compute_schedule_drift(issues=issues, now=BASE_NOW, velocity_window_days=30)

        assert result["recently_completed_tasks"] == 1
        assert result["remaining_open_tasks"] == 1
        # Display velocity rounded to 4 decimals = 0.0333
        assert result["completion_velocity_per_day"] == 0.0333
        # Duration calculated with raw precision = exactly 30.0 days
        assert result["estimated_completion_days"] == 30.0
        expected_date = (BASE_NOW + timedelta(days=30)).isoformat()
        assert result["estimated_completion_date"] == expected_date

    def test_milestone_open_issues_explicit_zero(self):
        """Case 16: Milestone with open_issues = 0 explicitly preserved."""
        # Project has 10 remaining open tasks, but Milestone M1 has 0 open tasks
        issues = [
            {"number": f"open_{i}", "state": "open"}
            for i in range(10)
        ] + [
            {"number": "c1", "state": "closed", "closed_at": (BASE_NOW - timedelta(days=2)).isoformat()}
        ]
        # M1 due in the future (due in 5 days) with 0 open issues
        milestones = [
            {
                "milestone_id": "m1",
                "title": "Completed Milestone",
                "state": "open",
                "open_issues": 0,
                "due_on": (BASE_NOW + timedelta(days=5)).isoformat(),
            }
        ]

        result = compute_schedule_drift(issues=issues, milestones=milestones, now=BASE_NOW)

        # M1 should NOT fall back to 10 tasks and create artificial delay!
        m1_est = result["milestones"][0]
        assert m1_est["open_issues"] == 0
        assert m1_est["estimated_completion_days"] == 0.0
        assert m1_est["estimated_completion_date"] == BASE_NOW.isoformat()
        assert m1_est["schedule_drift_days"] == -5.0  # completed 5 days before due date
        assert m1_est["status"] == "on_time"
        # No delay flags generated
        assert len(result["flags"]) == 0

    def test_milestone_open_issues_missing_falls_back_to_project_tasks(self):
        """Case 17: Milestone with open_issues missing or None falls back to project remaining tasks."""
        issues = [
            {"number": "o1", "state": "open"},
            {"number": "o2", "state": "open"},
        ] + [
            # 30 closed tasks in 30 days = 1 task/day
            {
                "number": f"c_{i}",
                "state": "closed",
                "closed_at": (BASE_NOW - timedelta(days=1)).isoformat(),
            }
            for i in range(30)
        ]
        # Milestone has open_issues missing or None
        milestones = [
            {
                "milestone_id": "m_fallback",
                "title": "Milestone Without Task Count",
                "state": "open",
                "open_issues": None,
                "due_on": (BASE_NOW + timedelta(days=5)).isoformat(),
            }
        ]

        result = compute_schedule_drift(issues=issues, milestones=milestones, now=BASE_NOW)

        m_est = result["milestones"][0]
        # Falls back to 2 project open tasks
        assert m_est["open_issues"] == 2
        assert m_est["estimated_completion_days"] == 2.0
        assert m_est["status"] == "on_time"

    def test_positive_schedule_drift_delay_flag(self):
        """Case 4: Positive drift indicates projected delay past milestone due date."""
        # Remaining tasks = 10
        # Velocity = 10 closed in 30 days = 10 / 30 = 0.3333 tasks/day
        # Estimated days to complete = 10 / (10/30) = 30 days exactly
        # Milestone due in 10 days
        # Projected delay = 30 - 10 = +20 days
        issues = [
            {"number": f"open_{i}", "state": "open"}
            for i in range(10)
        ] + [
            {
                "number": f"closed_{i}",
                "state": "closed",
                "closed_at": (BASE_NOW - timedelta(days=i * 2)).isoformat(),
            }
            for i in range(10)
        ]
        milestones = [
            {
                "milestone_id": "m1",
                "title": "Release 1.0",
                "state": "open",
                "due_on": (BASE_NOW + timedelta(days=10)).isoformat(),
                "open_issues": 10,
                "closed_issues": 5,
            }
        ]

        result = compute_schedule_drift(issues=issues, milestones=milestones, now=BASE_NOW)

        assert result["data_status"] == "available"
        assert result["schedule_drift_days"] is not None
        assert result["schedule_drift_days"] > 0.0
        # Approx 20 days delay
        assert pytest.approx(result["schedule_drift_days"], 0.1) == 20.0

        assert len(result["flags"]) == 1
        flag = result["flags"][0]
        assert flag["type"] == "schedule_risk"
        assert flag["severity"] == "high"  # > 14 days delay
        assert "Schedule Drift" in flag["message"]

    def test_on_time_projected_completion(self):
        """Case 5: On-time projected completion (zero or negative drift)."""
        # Remaining tasks = 2, velocity = 2 tasks/day (est duration = 1 day)
        # Milestone due in 10 days -> drift = 1 - 10 = -9 days (on time)
        issues = [
            {"number": 1, "state": "open"},
            {"number": 2, "state": "open"},
        ] + [
            {
                "number": f"closed_{i}",
                "state": "closed",
                "closed_at": (BASE_NOW - timedelta(days=1)).isoformat(),
            }
            for i in range(60)  # 60 closed in 30 days = 2 tasks/day
        ]
        milestones = [
            {
                "milestone_id": "m1",
                "title": "Quick Sprint",
                "state": "open",
                "due_on": (BASE_NOW + timedelta(days=10)).isoformat(),
                "open_issues": 2,
            }
        ]

        result = compute_schedule_drift(issues=issues, milestones=milestones, now=BASE_NOW)

        assert result["data_status"] == "available"
        assert result["schedule_drift_days"] is not None
        assert result["schedule_drift_days"] <= 0.0
        # No delay flags generated
        assert len(result["flags"]) == 0
        assert result["milestones"][0]["status"] == "on_time"

    def test_no_recent_completed_tasks_zero_velocity(self):
        """Case 6 & 7: Tasks remain but zero completed tasks in window."""
        issues = [
            {"number": 1, "state": "open"},
            {"number": 2, "state": "open"},
        ]
        milestones = [
            {"milestone_id": "m1", "title": "M1", "due_on": "2026-12-01T00:00:00Z", "open_issues": 2}
        ]

        result = compute_schedule_drift(issues=issues, milestones=milestones, now=BASE_NOW)

        assert result["data_status"] == "insufficient_velocity"
        assert result["completion_velocity_per_day"] == 0.0
        assert result["estimated_completion_days"] is None
        assert result["estimated_completion_date"] is None
        assert result["schedule_drift_days"] is None

        # Check explanation message
        msg_codes = [m["code"] for m in result["messages"]]
        assert "ZERO_VELOCITY" in msg_codes

        # Stalled velocity risk flag
        assert len(result["flags"]) == 1
        assert result["flags"][0]["id"] == "flag_schedule_stalled_velocity"

    def test_no_remaining_open_tasks(self):
        """Case 10: No open tasks remaining (project complete)."""
        issues = [
            {"number": 1, "state": "closed", "closed_at": "2026-11-10T00:00:00Z"},
            {"number": 2, "state": "closed", "closed_at": "2026-11-12T00:00:00Z"},
        ]

        result = compute_schedule_drift(issues=issues, now=BASE_NOW)

        assert result["data_status"] == "no_open_tasks"
        assert result["remaining_open_tasks"] == 0
        assert result["estimated_completion_days"] == 0.0
        assert result["estimated_completion_date"] == BASE_NOW.isoformat()

    def test_missing_milestones_and_missing_due_dates(self):
        """Case 8: Missing milestone deadline or no milestones."""
        issues = [
            {"number": 1, "state": "open"},
        ] + [
            {"number": 2, "state": "closed", "closed_at": "2026-11-10T00:00:00Z"}
        ]

        # Scenario A: No milestones provided
        res_no_ms = compute_schedule_drift(issues=issues, milestones=[], now=BASE_NOW)
        assert res_no_ms["data_status"] == "no_target_date"
        assert res_no_ms["estimated_completion_days"] is not None
        assert res_no_ms["schedule_drift_days"] is None
        codes = [m["code"] for m in res_no_ms["messages"]]
        assert "NO_MILESTONES" in codes

        # Scenario B: Milestone has no due_on
        milestones = [{"milestone_id": "m1", "title": "No Deadline", "open_issues": 1}]
        res_no_due = compute_schedule_drift(issues=issues, milestones=milestones, now=BASE_NOW)
        assert res_no_due["data_status"] == "no_target_date"
        assert res_no_due["schedule_drift_days"] is None
        codes = [m["code"] for m in res_no_due["messages"]]
        assert "MISSING_DUE_DATES" in codes

    def test_empty_and_none_issue_data(self):
        """Case 9: Missing or empty issue data."""
        res_none = compute_schedule_drift(issues=None, milestones=None, now=BASE_NOW)
        assert res_none["data_status"] == "no_data"
        assert res_none["remaining_open_tasks"] == 0
        assert res_none["completion_velocity_per_day"] == 0.0

        res_empty = compute_schedule_drift(issues=[], milestones=[], now=BASE_NOW)
        assert res_empty["data_status"] == "no_data"

    def test_multiple_milestones_worst_positive_drift(self):
        """Case 11: Retains individual estimates and reports worst positive drift."""
        # 30 open tasks total, 30 closed in 30 days = 1 task/day
        issues = [
            {"number": f"open_{i}", "state": "open"}
            for i in range(30)
        ] + [
            {
                "number": f"closed_{i}",
                "state": "closed",
                "closed_at": (BASE_NOW - timedelta(days=1)).isoformat(),
            }
            for i in range(30)
        ]
        milestones = [
            # M1: 5 tasks -> 5 days. Due in 10 days -> drift = -5 days (on time)
            {
                "milestone_id": "m1",
                "title": "Milestone 1",
                "state": "open",
                "open_issues": 5,
                "due_on": (BASE_NOW + timedelta(days=10)).isoformat(),
            },
            # M2: 20 tasks -> 20 days. Due in 5 days -> drift = +15 days (delayed)
            {
                "milestone_id": "m2",
                "title": "Milestone 2",
                "state": "open",
                "open_issues": 20,
                "due_on": (BASE_NOW + timedelta(days=5)).isoformat(),
            },
            # M3: 15 tasks -> 15 days. Due in 10 days -> drift = +5 days (delayed)
            {
                "milestone_id": "m3",
                "title": "Milestone 3",
                "state": "open",
                "open_issues": 15,
                "due_on": (BASE_NOW + timedelta(days=10)).isoformat(),
            },
        ]

        result = compute_schedule_drift(issues=issues, milestones=milestones, now=BASE_NOW)

        assert len(result["milestones"]) == 3
        # Worst positive drift between +15 and +5 is +15
        assert pytest.approx(result["schedule_drift_days"], 0.1) == 15.0
        assert len(result["flags"]) == 1
        assert result["flags"][0]["delayed_milestones_count"] == 2

    def test_invalid_timestamps_and_closed_at(self):
        """Case 12: Handles invalid timestamps and missing closed_at."""
        issues = [
            {"number": 1, "state": "open", "created_at": "invalid-date"},
            # Closed without closed_at -> cannot be verified in window
            {"number": 2, "state": "closed", "closed_at": None},
            {"number": 3, "state": "closed", "closed_at": "malformed"},
            {"number": 4, "state": "closed", "closed_at": (BASE_NOW - timedelta(days=5)).isoformat()},
        ]

        result = compute_schedule_drift(issues=issues, now=BASE_NOW)
        assert result["remaining_open_tasks"] == 1
        assert result["recently_completed_tasks"] == 1

    def test_disclaimer_present(self):
        """Case 14: Indicative estimate disclaimer is present."""
        result = compute_schedule_drift(issues=[], now=BASE_NOW)
        assert result["disclaimer"] == SCHEDULE_DISCLAIMER
        assert "indicative estimate" in result["disclaimer"]

    def test_pure_analytical_immutability(self):
        """Case 15: Input collections are never mutated."""
        issues = [
            {"number": 1, "state": "open", "title": "Task 1"},
            {"number": 2, "state": "closed", "closed_at": "2026-11-10T00:00:00Z"},
        ]
        milestones = [
            {"milestone_id": "m1", "title": "M1", "open_issues": 1, "due_on": "2026-12-01T00:00:00Z"}
        ]

        issues_copy = [dict(x) for x in issues]
        milestones_copy = [dict(x) for x in milestones]

        compute_schedule_drift(issues=issues, milestones=milestones, now=BASE_NOW)

        assert issues == issues_copy
        assert milestones == milestones_copy

    def test_strict_input_validation_velocity_window_days(self):
        """Case 19: Reject booleans, floats, non-positives, strings for velocity_window_days."""
        with pytest.raises(ValueError, match="velocity_window_days must be a positive integer greater than 0"):
            compute_schedule_drift(velocity_window_days=0)

        with pytest.raises(ValueError, match="velocity_window_days must be a positive integer greater than 0"):
            compute_schedule_drift(velocity_window_days=-10)

        with pytest.raises(ValueError, match="velocity_window_days must be a positive integer greater than 0"):
            compute_schedule_drift(velocity_window_days=15.5)  # float

        with pytest.raises(ValueError, match="velocity_window_days must be a positive integer greater than 0"):
            compute_schedule_drift(velocity_window_days=True)  # bool

        with pytest.raises(ValueError, match="velocity_window_days must be a positive integer greater than 0"):
            compute_schedule_drift(velocity_window_days="30")  # string

    def test_timezone_normalization_datetime_offset(self):
        """Case 20: Datetime with non-UTC offset is normalized to UTC."""
        tz_offset = timezone(timedelta(hours=5, minutes=30))
        now_with_offset = datetime(2026, 11, 15, 17, 30, 0, tzinfo=tz_offset)

        # In UTC, 17:30 +05:30 is 12:00 UTC
        issues = [
            {"number": 1, "state": "open"},
            {"number": 2, "state": "closed", "closed_at": "2026-11-15T10:00:00Z"},
        ]
        result = compute_schedule_drift(issues=issues, now=now_with_offset)

        assert result["remaining_open_tasks"] == 1
        assert result["recently_completed_tasks"] == 1
