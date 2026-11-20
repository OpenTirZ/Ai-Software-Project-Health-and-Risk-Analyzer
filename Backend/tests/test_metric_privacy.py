
import copy

import pytest

from Backend.auth.privacy_filter import (
    filter_appeal_history,
    filter_workload_metrics,
)


@pytest.fixture
def workload_metrics():
    return {
        "commit_distribution": {
            "activity_type": "commits",
            "total_events": 100,
            "attributed_events": 100,
            "unattributed_events": 0,
            "contributor_count": 3,
            "contributors": [
                {"contributor": "alice", "count": 40, "percentage": 40},
                {"contributor": "bob", "count": 35, "percentage": 35},
                {"contributor": "charlie", "count": 25, "percentage": 25},
            ],
            "top_contributor": "alice",
            "top_contributor_count": 40,
            "top_contributor_percentage": 40,
            "flags": ["alice has the highest contribution"],
        },
        "pr_distribution": {
            "activity_type": "pull_requests",
            "total_events": 20,
            "attributed_events": 20,
            "unattributed_events": 0,
            "contributor_count": 2,
            "contributors": [
                {"contributor": "alice", "count": 12, "percentage": 60},
                {"contributor": "bob", "count": 8, "percentage": 40},
            ],
            "top_contributor": "alice",
            "top_contributor_count": 12,
            "top_contributor_percentage": 60,
        },
    }


def test_admin_can_see_full_workload_metrics(workload_metrics):
    user = {"id": "1", "role": "admin"}

    result = filter_workload_metrics(workload_metrics, user)

    assert len(result["commit_distribution"]["contributors"]) == 3
    assert result["commit_distribution"]["top_contributor"] == "alice"


def test_lead_can_see_full_workload_metrics(workload_metrics):
    user = {"id": "2", "role": "lead"}

    result = filter_workload_metrics(workload_metrics, user)

    assert len(result["commit_distribution"]["contributors"]) == 3


def test_project_owner_can_see_full_workload_metrics(workload_metrics):
    user = {"id": "10", "role": "developer"}
    project = {"ownerId": "10"}

    result = filter_workload_metrics(
        workload_metrics,
        user,
        project=project,
    )

    assert len(result["commit_distribution"]["contributors"]) == 3


def test_member_sees_own_metrics_and_aggregated_peers(workload_metrics):
    user = {
        "id": "3",
        "role": "developer",
        "github_username": "alice",
    }

    result = filter_workload_metrics(workload_metrics, user)

    commits = result["commit_distribution"]

    assert commits["contributors"] == [
        {"contributor": "alice", "count": 40, "percentage": 40}
    ]

    assert commits["peer_activity"] == {
        "contributor_count": 2,
        "total_events": 60,
        "percentage": 60,
    }

    assert "top_contributor" not in commits
    assert "flags" not in commits


def test_member_without_identity_does_not_see_named_contributors(
    workload_metrics,
):
    user = {"id": "4", "role": "developer"}

    result = filter_workload_metrics(workload_metrics, user)

    commits = result["commit_distribution"]

    assert commits["contributors"] == []
    assert commits["peer_activity"]["total_events"] == 100


def test_appeal_history_is_limited_to_current_user():
    appeals = [
        {"user_id": "1", "message": "Appeal A"},
        {"userId": "2", "message": "Appeal B"},
        {"user_id": "1", "message": "Appeal C"},
    ]

    user = {"id": "1", "role": "developer"}

    result = filter_appeal_history(appeals, user)

    assert result == [
        {"user_id": "1", "message": "Appeal A"},
        {"user_id": "1", "message": "Appeal C"},
    ]


def test_filtering_does_not_modify_original_metrics(workload_metrics):
    original = copy.deepcopy(workload_metrics)

    user = {
        "id": "3",
        "role": "developer",
        "github_username": "alice",
    }

    filter_workload_metrics(workload_metrics, user)

    assert workload_metrics == original
