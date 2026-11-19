"""Tests for the standalone advisory recommendation service."""

import json

from Backend.ai.recommendation_service import (
    ADVISORY_DISCLAIMER,
    generate_recommendations,
)


def _metrics(*flags):
    return {
        "project_id": "demo-1",
        "project_name": "Demo Project",
        "health_score": 61.5,
        "status": "Caution",
        "indicators": {
            "bottlenecks": {
                "score": 50,
                "status": "At Risk",
                "flags": list(flags),
            }
        },
    }


def test_maps_aging_pull_request_flag_to_advisory_recommendation():
    metrics = _metrics({
        "id": "flag_bottleneck_aging_prs",
        "type": "bottleneck",
        "severity": "high",
        "message": "2 pull requests are awaiting review.",
        "evidence": {"aging_prs": [{"number": 12, "age_hours": 72}]},
    })

    recommendations = generate_recommendations(metrics, api_key="")

    assert len(recommendations) == 1
    recommendation = recommendations[0]
    assert recommendation.category == "code_review"
    assert "24-hour" in recommendation.action
    assert recommendation.priority == "HIGH"
    assert recommendation.is_advisory is True
    assert recommendation.disclaimer == ADVISORY_DISCLAIMER


def test_returns_empty_list_when_there_are_no_active_flags():
    assert generate_recommendations(_metrics(), api_key="") == []


def test_llm_can_personalize_grounded_recommendation():
    def fake_llm(prompt):
        assert "Demo Project" in prompt
        return json.dumps({
            "recommendations": [{
                "category": "code_review",
                "condition": "One or more pull requests have remained open beyond the review threshold without a submitted review. Observed: 2 PRs exceed the review threshold.",
                "action": "Consider a daily review rotation for the two aging pull requests.",
                "rationale": "The supplied evidence identifies two aging pull requests.",
                "priority": "HIGH",
                "target_role": "Team Lead",
                "is_advisory": True,
                "disclaimer": ADVISORY_DISCLAIMER,
            }]
        })

    metrics = _metrics({
        "id": "flag_bottleneck_aging_prs",
        "message": "2 PRs exceed the review threshold.",
        "evidence": {"aging_prs": [{"number": 12}, {"number": 13}]},
    })
    recommendations = generate_recommendations(metrics, llm_client=fake_llm)

    assert len(recommendations) == 1
    assert "daily review rotation" in recommendations[0].action


def test_invalid_llm_output_falls_back_to_grounded_advice():
    metrics = _metrics({
        "id": "flag_schedule_stalled_velocity",
        "message": "No tasks completed in the last 30 days.",
    })

    recommendations = generate_recommendations(
        metrics,
        llm_client=lambda prompt: '{"recommendations": [{"is_advisory": false}]}',
    )

    assert len(recommendations) == 1
    assert recommendations[0].is_advisory is True
    assert recommendations[0].category == "delivery_planning"


def test_unknown_flag_does_not_create_ungrounded_recommendation():
    metrics = _metrics({
        "id": "flag_unknown_new_metric",
        "message": "Some unknown condition.",
    })

    assert generate_recommendations(metrics, api_key="") == []
