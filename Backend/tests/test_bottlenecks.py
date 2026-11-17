
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from Backend.analysis.bottleneck_engine import detect_bottlenecks
from Backend.analysis.stale_issues_engine import detect_stale_issues


UTC = timezone.utc
NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


def time_ago(hours=0, days=0):
    return (NOW - timedelta(hours=hours, days=days)).isoformat()


class TestBottleneckEngine:

    def test_old_open_pr_without_review(self):
        prs = [{
            "number": 1,
            "title": "Old PR",
            "state": "open",
            "created_at": time_ago(hours=60),
            "reviews": [],
            "requested_reviewers": [],
        }]

        result = detect_bottlenecks(prs, now=NOW)

        assert len(result["aging_prs"]) == 1
        assert result["aging_prs"][0]["number"] == 1

    def test_pr_exactly_48_hours_is_not_aging(self):
        prs = [{
            "number": 1,
            "state": "open",
            "created_at": time_ago(hours=48),
            "reviews": [],
            "requested_reviewers": [],
        }]

        result = detect_bottlenecks(prs, now=NOW)

        assert len(result["aging_prs"]) == 0

    def test_submitted_review_suppresses_aging(self):
        prs = [{
            "number": 1,
            "state": "open",
            "created_at": time_ago(hours=60),
            "reviews": [{
                "state": "APPROVED",
                "submitted_at": time_ago(hours=2),
            }],
            "requested_reviewers": [],
        }]

        result = detect_bottlenecks(prs, now=NOW)

        assert len(result["aging_prs"]) == 0

    def test_pending_review_does_not_suppress_aging(self):
        prs = [{
            "number": 1,
            "state": "open",
            "created_at": time_ago(hours=60),
            "reviews": [{
                "state": "PENDING",
                "submitted_at": time_ago(hours=2),
            }],
            "requested_reviewers": [],
        }]

        result = detect_bottlenecks(prs, now=NOW)

        assert len(result["aging_prs"]) == 1

    def test_closed_pr_is_ignored(self):
        prs = [{
            "number": 1,
            "state": "closed",
            "created_at": time_ago(hours=100),
            "reviews": [],
            "requested_reviewers": [],
        }]

        result = detect_bottlenecks(prs, now=NOW)

        assert len(result["aging_prs"]) == 0

    def test_merged_pr_is_ignored(self):
        prs = [{
            "number": 1,
            "state": "closed",
            "merged": True,
            "merged_at": time_ago(hours=1),
            "created_at": time_ago(hours=100),
            "reviews": [],
            "requested_reviewers": [],
        }]

        result = detect_bottlenecks(prs, now=NOW)

        assert len(result["aging_prs"]) == 0

    def test_more_than_five_pending_prs_triggers_queue(self):
        prs = []

        for number in range(1, 7):
            prs.append({
                "number": number,
                "state": "open",
                "created_at": time_ago(hours=10),
                "reviews": [],
                "requested_reviewers": [{"login": "reviewer1"}],
            })

        result = detect_bottlenecks(prs, now=NOW)

        assert len(result["review_queue_congestion"]) == 1
        assert result["review_queue_congestion"][0]["pending_prs_count"] == 6

    def test_exactly_five_pending_prs_does_not_trigger_queue(self):
        prs = []

        for number in range(1, 6):
            prs.append({
                "number": number,
                "state": "open",
                "created_at": time_ago(hours=10),
                "reviews": [],
                "requested_reviewers": [{"login": "reviewer1"}],
            })

        result = detect_bottlenecks(prs, now=NOW)

        assert len(result["review_queue_congestion"]) == 0

    def test_duplicate_reviewer_assignment_is_counted_once(self):
        prs = []

        for number in range(1, 7):
            prs.append({
                "number": number,
                "state": "open",
                "created_at": time_ago(hours=10),
                "reviews": [],
                "requested_reviewers": [
                    {"login": "reviewer1"},
                    {"login": "REVIEWER1"},
                ],
            })

        result = detect_bottlenecks(prs, now=NOW)

        assert len(result["review_queue_congestion"]) == 1
        assert result["review_queue_congestion"][0]["pending_prs_count"] == 6

    def test_historical_review_does_not_clear_current_assignment(self):
        prs = []

        for number in range(1, 7):
            prs.append({
                "number": number,
                "state": "open",
                "created_at": time_ago(hours=10),
                "reviews": [{
                    "state": "APPROVED",
                    "submitted_at": time_ago(hours=2),
                }],
                "requested_reviewers": [{"login": "reviewer1"}],
            })

        result = detect_bottlenecks(prs, now=NOW)

        assert len(result["review_queue_congestion"]) == 1
        assert result["review_queue_congestion"][0]["pending_prs_count"] == 6

    def test_missing_and_invalid_pr_timestamps(self):
        prs = [
            {
                "number": 1,
                "state": "open",
                "reviews": [],
                "requested_reviewers": [],
            },
            {
                "number": 2,
                "state": "open",
                "created_at": "invalid",
                "reviews": [],
                "requested_reviewers": [],
            },
        ]

        result = detect_bottlenecks(prs, now=NOW)

        assert len(result["aging_prs"]) == 0

    def test_timezone_aware_pr_timestamp(self):
        created_at = datetime(
            2026, 11, 15, 12, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))
        )

        prs = [{
            "number": 1,
            "state": "open",
            "created_at": created_at.isoformat(),
            "reviews": [],
            "requested_reviewers": [],
        }]

        result = detect_bottlenecks(prs, now=NOW)

        assert len(result["aging_prs"]) == 1

    def test_empty_and_none_inputs(self):
        assert detect_bottlenecks([], now=NOW)["aging_prs"] == []
        assert detect_bottlenecks(None, now=NOW)["aging_prs"] == []

    def test_custom_aging_threshold(self):
        prs = [{
            "number": 1,
            "state": "open",
            "created_at": time_ago(hours=30),
            "reviews": [],
            "requested_reviewers": [],
        }]

        result = detect_bottlenecks(
            prs,
            now=NOW,
            aging_threshold_hours=24,
        )

        assert len(result["aging_prs"]) == 1

    def test_custom_reviewer_queue_threshold(self):
        prs = []

        for number in range(1, 5):
            prs.append({
                "number": number,
                "state": "open",
                "created_at": time_ago(hours=10),
                "reviews": [],
                "requested_reviewers": [{"login": "reviewer1"}],
            })

        result = detect_bottlenecks(
            prs,
            now=NOW,
            reviewer_queue_threshold=3,
        )

        assert len(result["review_queue_congestion"]) == 1

    def test_input_is_not_modified(self):
        prs = [{
            "number": 1,
            "state": "open",
            "created_at": time_ago(hours=60),
            "reviews": [],
            "requested_reviewers": [],
        }]

        original = deepcopy(prs)

        detect_bottlenecks(prs, now=NOW)

        assert prs == original

    def test_structured_flag_contains_evidence(self):
        prs = [{
            "number": 10,
            "title": "Test PR",
            "state": "open",
            "created_at": time_ago(hours=60),
            "reviews": [],
            "requested_reviewers": [],
        }]

        result = detect_bottlenecks(prs, now=NOW)

        flag = next(
            flag for flag in result["flags"]
            if flag["type"] == "aging_pull_request"
        )

        assert flag["pr_number"] == 10
        assert flag["type"] == "aging_pull_request"
        assert "evidence" in flag


class TestStaleIssuesEngine:

    def make_issue(self, number=1, days=30, labels=None):
        return {
            "number": number,
            "title": f"Issue {number}",
            "state": "open",
            "created_at": time_ago(days=days),
            "updated_at": time_ago(days=days),
            "labels": labels or [],
        }

    def test_issue_older_than_fourteen_days_is_stale(self):
        result = detect_stale_issues(
            [self.make_issue()],
            now=NOW,
        )

        assert len(result["stale_issues"]) == 1

    def test_issue_exactly_fourteen_days_is_not_stale(self):
        result = detect_stale_issues(
            [self.make_issue(days=14)],
            now=NOW,
        )

        assert len(result["stale_issues"]) == 0

    def test_recent_comment_resets_inactivity(self):
        issue = self.make_issue()

        comments = [{
            "issue_number": 1,
            "created_at": time_ago(days=2),
        }]

        result = detect_stale_issues(
            [issue],
            comment_events=comments,
            now=NOW,
        )

        assert len(result["stale_issues"]) == 0

    def test_recent_associated_commit_resets_inactivity(self):
        issue = self.make_issue()

        commits = [{
            "issue_number": 1,
            "timestamp": time_ago(days=2),
        }]

        result = detect_stale_issues(
            [issue],
            commits=commits,
            now=NOW,
        )

        assert len(result["stale_issues"]) == 0

    def test_recent_label_event_resets_inactivity(self):
        issue = self.make_issue()

        events = [{
            "issue_number": 1,
            "created_at": time_ago(days=2),
        }]

        result = detect_stale_issues(
            [issue],
            label_events=events,
            now=NOW,
        )

        assert len(result["stale_issues"]) == 0

    def test_latest_activity_is_selected(self):
        issue = self.make_issue()

        comments = [{
            "issue_number": 1,
            "created_at": time_ago(days=5),
        }]

        commits = [{
            "issue_number": 1,
            "timestamp": time_ago(days=2),
        }]

        result = detect_stale_issues(
            [issue],
            commits=commits,
            comment_events=comments,
            now=NOW,
        )

        assert len(result["stale_issues"]) == 0

    @pytest.mark.parametrize("label", ["on-hold", "ON-HOLD", " on-hold "])
    def test_on_hold_issue_is_excluded(self, label):
        result = detect_stale_issues(
            [self.make_issue(labels=[label])],
            now=NOW,
        )

        assert len(result["stale_issues"]) == 0
        assert result["excluded_issues_count"] == 1

    def test_deferred_issue_is_excluded(self):
        result = detect_stale_issues(
            [self.make_issue(labels=["deferred"])],
            now=NOW,
        )

        assert len(result["stale_issues"]) == 0
        assert result["excluded_issues_count"] == 1

    def test_dictionary_labels_are_supported(self):
        result = detect_stale_issues(
            [self.make_issue(labels=[{"name": "ON-HOLD"}])],
            now=NOW,
        )

        assert result["excluded_issues_count"] == 1

    def test_custom_excluded_label(self):
        result = detect_stale_issues(
            [self.make_issue(labels=["blocked"])],
            now=NOW,
            excluded_labels=("blocked",),
        )

        assert result["excluded_issues_count"] == 1

    def test_closed_issue_is_ignored(self):
        issue = self.make_issue()
        issue["state"] = "closed"

        result = detect_stale_issues([issue], now=NOW)

        assert len(result["stale_issues"]) == 0

    def test_commit_explicit_issue_number(self):
        issue = self.make_issue()

        commits = [{
            "issue_number": 1,
            "timestamp": time_ago(days=2),
        }]

        result = detect_stale_issues(
            [issue],
            commits=commits,
            now=NOW,
        )

        assert len(result["stale_issues"]) == 0

    def test_commit_message_issue_reference(self):
        issue = self.make_issue()

        commits = [{
            "message": "Fixes #1",
            "timestamp": time_ago(days=2),
        }]

        result = detect_stale_issues(
            [issue],
            commits=commits,
            now=NOW,
        )

        assert len(result["stale_issues"]) == 0

    def test_unrelated_commit_is_not_associated(self):
        issue = self.make_issue()

        commits = [{
            "message": "Update documentation",
            "timestamp": time_ago(days=2),
        }]

        result = detect_stale_issues(
            [issue],
            commits=commits,
            now=NOW,
        )

        assert len(result["stale_issues"]) == 1

    def test_invalid_event_timestamp_is_ignored(self):
        issue = self.make_issue()

        comments = [{
            "issue_number": 1,
            "created_at": "invalid",
        }]

        result = detect_stale_issues(
            [issue],
            comment_events=comments,
            now=NOW,
        )

        assert len(result["stale_issues"]) == 1
        assert result["stale_issues"][0]["is_proxy"] is True

    def test_missing_activity_timestamps(self):
        issue = {
            "number": 1,
            "title": "Missing dates",
            "state": "open",
            "labels": [],
        }

        result = detect_stale_issues([issue], now=NOW)

        assert len(result["stale_issues"]) == 0
        assert result["activity_data_quality"]["missing_activity_count"] == 1

    def test_updated_at_is_marked_as_proxy(self):
        issue = self.make_issue()

        result = detect_stale_issues([issue], now=NOW)

        stale_issue = result["stale_issues"][0]

        assert stale_issue["activity_source"] == "issue_updated_at_proxy"
        assert stale_issue["is_proxy"] is True

    def test_empty_and_none_inputs(self):
        assert detect_stale_issues([], now=NOW)["stale_issues"] == []
        assert detect_stale_issues(None, now=NOW)["stale_issues"] == []

    def test_injected_now_is_used(self):
        issue = self.make_issue()

        result = detect_stale_issues([issue], now=NOW)

        assert result["analyzed_at"] == NOW.isoformat()

    def test_invalid_threshold_is_rejected(self):
        for threshold in (0, -1, 1.5, True):
            with pytest.raises(ValueError):
                detect_stale_issues(
                    [self.make_issue()],
                    now=NOW,
                    stale_after_days=threshold,
                )

    def test_timezone_aware_event_is_supported(self):
        issue = self.make_issue()

        event_time = (
            NOW - timedelta(days=2)
        ).astimezone(timezone(timedelta(hours=5, minutes=30)))

        comments = [{
            "issue_number": 1,
            "created_at": event_time.isoformat(),
        }]

        result = detect_stale_issues(
            [issue],
            comment_events=comments,
            now=NOW,
        )

        assert len(result["stale_issues"]) == 0

    def test_input_is_not_modified(self):
        issues = [self.make_issue()]
        original = deepcopy(issues)

        detect_stale_issues(issues, now=NOW)

        assert issues == original

    def test_structured_flag_contains_evidence(self):
        result = detect_stale_issues(
            [self.make_issue()],
            now=NOW,
        )

        flag = result["flags"][0]

        assert flag["type"] == "stale_issue"
        assert flag["issue_number"] == 1
        assert "evidence" in flag
        assert "activity_source" in flag
