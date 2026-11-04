"""
Composite Health Score Engine — AI Software Project Health & Risk Analyzer
--------------------------------------------------------------------------
Normalizes indicators from:
  1. Bottlenecks & Blockers (PR review queues, aging PRs)
  2. Workload Imbalance / Bus Factor (Commit/PR concentration)
  3. Stale Issues (Inactivity against project threshold)
  4. Schedule Risk (Milestone & sprint task velocity)

Aggregates indicators into a single explainable 0–100 Composite Health Index:
  - Good: Score >= 75
  - Caution: 50 <= Score < 75
  - At Risk: Score < 50
  - Insufficient Data: When essential telemetry is missing/empty

Handles 'Insufficient Data' states gracefully by dynamically re-weighting
available indicators instead of penalizing missing sources with fake zero scores.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default Configuration Thresholds
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLDS: Dict[str, Any] = {
    "aging_pr_hours": 48.0,
    "stale_issue_days": 14,
    "bus_factor_ratio": 0.70,
    "workload_caution_ratio": 0.50,
    "review_latency_hours": 24.0,
}

STATUS_GOOD = "Good"
STATUS_CAUTION = "Caution"
STATUS_AT_RISK = "At Risk"
STATUS_INSUFFICIENT = "Insufficient Data"


def _parse_datetime(val: Any) -> Optional[datetime]:
    """Parse various datetime representations into a timezone-aware UTC datetime."""
    if isinstance(val, datetime):
        return val if val.tzinfo is not None else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        try:
            cleaned = val.replace("Z", "+00:00")
            dt = datetime.fromisoformat(cleaned)
            return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _classify_score(score: Optional[float]) -> str:
    """Map a 0-100 score to Good / Caution / At Risk / Insufficient Data."""
    if score is None:
        return STATUS_INSUFFICIENT
    if score >= 75.0:
        return STATUS_GOOD
    if score >= 50.0:
        return STATUS_CAUTION
    return STATUS_AT_RISK


# ---------------------------------------------------------------------------
# 1. Bottlenecks Indicator (Pull Requests & Reviews)
# ---------------------------------------------------------------------------

def compute_bottlenecks_indicator(
    pull_requests: Optional[List[Dict[str, Any]]],
    thresholds: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Evaluate development bottlenecks from pull request telemetry.
    If pull request data is missing, returns an 'Insufficient Data' state.
    """
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    aging_limit_hours = float(t.get("aging_pr_hours", 48.0))
    current_time = now or datetime.now(timezone.utc)

    if pull_requests is None:
        return {
            "score": None,
            "status": STATUS_INSUFFICIENT,
            "data_status": "insufficient_data",
            "weight": 0.25,
            "details": {
                "message": "No pull request data available.",
                "open_prs_count": 0,
                "aging_prs_count": 0,
            },
            "flags": [],
        }

    # If repository has zero PRs synced
    if len(pull_requests) == 0:
        return {
            "score": None,
            "status": STATUS_INSUFFICIENT,
            "data_status": "insufficient_data",
            "weight": 0.25,
            "details": {
                "message": "Pull request synchronization has not been performed or no PRs exist.",
                "open_prs_count": 0,
                "aging_prs_count": 0,
            },
            "flags": [],
        }

    open_prs = [pr for pr in pull_requests if str(pr.get("state", "")).lower() == "open"]
    aging_prs = []
    total_age_hours = 0.0

    for pr in open_prs:
        created_dt = _parse_datetime(pr.get("created_at") or pr.get("createdAt"))
        if created_dt:
            age_hours = max(0.0, (current_time - created_dt).total_seconds() / 3600.0)
        else:
            age_hours = float(pr.get("open_duration_hours", 0.0))
        total_age_hours += age_hours

        if age_hours > aging_limit_hours:
            aging_prs.append({
                "number": pr.get("number") or pr.get("pr_number"),
                "title": pr.get("title", "Untitled PR"),
                "age_hours": round(age_hours, 1),
            })

    open_count = len(open_prs)
    avg_age = round(total_age_hours / open_count, 1) if open_count > 0 else 0.0
    aging_count = len(aging_prs)

    # Base score computation (0 - 100)
    score = 100.0
    flags = []

    if aging_count > 0:
        penalty = min(50.0, aging_count * 15.0)
        score -= penalty
        severity = "high" if aging_count >= 3 else "medium"
        flags.append({
            "id": "flag_bottleneck_aging_prs",
            "type": "bottleneck",
            "severity": severity,
            "message": f"{aging_count} pull request(s) open for longer than {aging_limit_hours}h without review or merge.",
            "evidence": {"aging_prs": aging_prs},
        })

    if open_count > 10:
        score -= 10.0
        flags.append({
            "id": "flag_pr_queue_congestion",
            "type": "bottleneck",
            "severity": "medium",
            "message": f"High open pull request volume ({open_count} open PRs) may indicate review backlog.",
            "evidence": {"open_prs_count": open_count},
        })

    score = max(0.0, min(100.0, round(score, 1)))

    return {
        "score": score,
        "status": _classify_score(score),
        "data_status": "available",
        "weight": 0.25,
        "details": {
            "total_prs_tracked": len(pull_requests),
            "open_prs_count": open_count,
            "aging_prs_count": aging_count,
            "avg_pr_age_hours": avg_age,
            "aging_threshold_hours": aging_limit_hours,
        },
        "flags": flags,
    }


# ---------------------------------------------------------------------------
# 2. Workload Imbalance Indicator (Commit & Contributor Concentration)
# ---------------------------------------------------------------------------

def compute_workload_indicator(
    commits: Optional[List[Dict[str, Any]]],
    contributors: Optional[List[Dict[str, Any]]] = None,
    thresholds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluate activity distribution across project contributors.
    Identifies high concentration or potential Bus Factor risks.
    Domain Note: GitHub activity is a proxy, not a direct measure of effort.
    """
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    bus_factor_limit = float(t.get("bus_factor_ratio", 0.70))
    caution_limit = float(t.get("workload_caution_ratio", 0.50))

    if not commits and not contributors:
        return {
            "score": None,
            "status": STATUS_INSUFFICIENT,
            "data_status": "insufficient_data",
            "weight": 0.25,
            "details": {
                "message": "No commit or contributor activity data available.",
                "total_contributors": 0,
                "disclaimer": "GitHub activity is a proxy indicator, not a direct measure of individual workload, performance, or effort.",
            },
            "flags": [],
        }

    # Aggregate contributions by author/username
    contribution_counts: Dict[str, int] = {}

    if commits:
        for c in commits:
            author = c.get("author") or {}
            author_key = (
                author.get("name")
                or author.get("login")
                or author.get("email")
                or c.get("author_name")
                or "Unknown"
            )
            contribution_counts[author_key] = contribution_counts.get(author_key, 0) + 1
    elif contributors:
        for contrib in contributors:
            name = contrib.get("github_username") or contrib.get("name") or "Unknown"
            contribution_counts[name] = contrib.get("contributions", 1)

    total_activity = sum(contribution_counts.values())
    active_contributors_count = len(contribution_counts)

    if total_activity == 0 or active_contributors_count == 0:
        return {
            "score": None,
            "status": STATUS_INSUFFICIENT,
            "data_status": "insufficient_data",
            "weight": 0.25,
            "details": {
                "message": "Zero activity recorded for contributors.",
                "total_contributors": 0,
            },
            "flags": [],
        }

    sorted_contributors = sorted(
        contribution_counts.items(), key=lambda x: x[1], reverse=True
    )
    top_contributor, top_count = sorted_contributors[0]
    top_share = round(top_count / total_activity, 3)

    flags = []
    score = 100.0

    if active_contributors_count == 1:
        # Single developer project
        score = 65.0
        flags.append({
            "id": "flag_single_contributor",
            "type": "workload_imbalance",
            "severity": "low",
            "message": "All repository activity originates from a single active contributor (Bus Factor = 1).",
            "evidence": {
                "top_contributor": top_contributor,
                "contribution_percentage": 100.0,
            },
        })
    elif top_share >= bus_factor_limit:
        score = max(25.0, round(100.0 - (top_share * 85.0), 1))
        flags.append({
            "id": "flag_workload_concentration_high",
            "type": "workload_imbalance",
            "severity": "high",
            "message": f"High workload concentration: {top_contributor} accounts for {round(top_share * 100, 1)}% of all recorded activity.",
            "evidence": {
                "top_contributor": top_contributor,
                "contribution_percentage": round(top_share * 100, 1),
                "threshold": round(bus_factor_limit * 100, 1),
            },
        })
    elif top_share >= caution_limit:
        score = round(100.0 - (top_share * 50.0), 1)
        flags.append({
            "id": "flag_workload_concentration_caution",
            "type": "workload_imbalance",
            "severity": "medium",
            "message": f"Moderate activity concentration: {top_contributor} accounts for {round(top_share * 100, 1)}% of recorded activity.",
            "evidence": {
                "top_contributor": top_contributor,
                "contribution_percentage": round(top_share * 100, 1),
            },
        })
    else:
        score = 92.0

    score = max(0.0, min(100.0, round(score, 1)))

    return {
        "score": score,
        "status": _classify_score(score),
        "data_status": "available",
        "weight": 0.25,
        "details": {
            "total_contributors": active_contributors_count,
            "total_activity_events": total_activity,
            "top_contributor": top_contributor,
            "top_contributor_share": top_share,
            "top_contributor_percentage": round(top_share * 100, 1),
            "disclaimer": "GitHub activity is a proxy indicator, not a direct measure of individual workload, performance, or effort.",
        },
        "flags": flags,
    }


# ---------------------------------------------------------------------------
# 3. Stale Issues Indicator (Inactivity Thresholds)
# ---------------------------------------------------------------------------

def compute_stale_issues_indicator(
    issues: Optional[List[Dict[str, Any]]],
    thresholds: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Evaluate issue staleness based on inactivity exceeding configured days.
    """
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    stale_limit_days = int(t.get("stale_issue_days", 14))
    current_time = now or datetime.now(timezone.utc)

    if issues is None:
        return {
            "score": None,
            "status": STATUS_INSUFFICIENT,
            "data_status": "insufficient_data",
            "weight": 0.25,
            "details": {
                "message": "No issue tracking data available.",
                "open_issues_count": 0,
                "stale_issues_count": 0,
            },
            "flags": [],
        }

    if len(issues) == 0:
        return {
            "score": 100.0,
            "status": STATUS_GOOD,
            "data_status": "no_issues",
            "weight": 0.25,
            "details": {
                "message": "No issues found in repository tracking.",
                "open_issues_count": 0,
                "stale_issues_count": 0,
            },
            "flags": [],
        }

    open_issues = [i for i in issues if str(i.get("state", "")).lower() == "open"]
    stale_issues = []

    for issue in open_issues:
        last_activity = (
            _parse_datetime(issue.get("updated_at") or issue.get("updatedAt"))
            or _parse_datetime(issue.get("created_at") or issue.get("createdAt"))
        )
        if last_activity:
            inactive_days = max(0, (current_time - last_activity).days)
        else:
            inactive_days = 0

        if inactive_days >= stale_limit_days:
            stale_issues.append({
                "number": issue.get("number") or issue.get("issue_number"),
                "title": issue.get("title", "Untitled Issue"),
                "inactive_days": inactive_days,
            })

    open_count = len(open_issues)
    stale_count = len(stale_issues)

    if open_count == 0:
        return {
            "score": 100.0,
            "status": STATUS_GOOD,
            "data_status": "available",
            "weight": 0.25,
            "details": {
                "open_issues_count": 0,
                "stale_issues_count": 0,
                "stale_issue_percentage": 0.0,
                "stale_threshold_days": stale_limit_days,
            },
            "flags": [],
        }

    stale_ratio = stale_count / open_count
    score = 100.0 - (stale_ratio * 70.0) - min(stale_count, 6) * 3.0
    score = max(0.0, min(100.0, round(score, 1)))

    flags = []
    if stale_count > 0:
        severity = "high" if stale_ratio >= 0.50 else "medium"
        flags.append({
            "id": "flag_stale_issues_detected",
            "type": "stale_issues",
            "severity": severity,
            "message": f"{stale_count} open issue(s) have not had activity in over {stale_limit_days} days.",
            "evidence": {"stale_issues": stale_issues},
        })

    return {
        "score": score,
        "status": _classify_score(score),
        "data_status": "available",
        "weight": 0.25,
        "details": {
            "open_issues_count": open_count,
            "stale_issues_count": stale_count,
            "stale_issue_percentage": round(stale_ratio * 100, 1),
            "stale_threshold_days": stale_limit_days,
        },
        "flags": flags,
    }


# ---------------------------------------------------------------------------
# 4. Schedule Risk Indicator (Milestones & Sprint Velocity)
# ---------------------------------------------------------------------------

def compute_schedule_risk_indicator(
    sprints: Optional[List[Dict[str, Any]]] = None,
    milestones: Optional[List[Dict[str, Any]]] = None,
    issues: Optional[List[Dict[str, Any]]] = None,
    thresholds: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Evaluate indicative schedule risk from sprints or milestones.
    Gracefully handles 'Insufficient Data' states when milestone or sprint
    tracking is not configured or data is missing.
    """
    current_time = now or datetime.now(timezone.utc)
    sprints_list = sprints or []
    milestones_list = milestones or []

    # If neither sprints nor milestones are configured, return Insufficient Data
    if not sprints_list and not milestones_list:
        return {
            "score": None,
            "status": STATUS_INSUFFICIENT,
            "data_status": "insufficient_data",
            "weight": 0.25,
            "details": {
                "message": "No milestone, sprint, or velocity tracking data configured for this repository.",
                "milestones_count": 0,
                "sprints_count": 0,
            },
            "flags": [],
        }

    overdue_milestones = []
    total_planned = 0
    total_completed = 0

    for ms in milestones_list:
        open_issues = int(ms.get("open_issues", 0))
        closed_issues = int(ms.get("closed_issues", 0))
        total_planned += (open_issues + closed_issues)
        total_completed += closed_issues

        due_on = _parse_datetime(ms.get("due_on") or ms.get("due_date"))
        state = str(ms.get("state", "open")).lower()
        if due_on and due_on < current_time and state == "open" and open_issues > 0:
            overdue_milestones.append({
                "title": ms.get("title", "Milestone"),
                "due_on": due_on.isoformat(),
                "open_issues": open_issues,
            })

    for sp in sprints_list:
        total_planned += int(sp.get("total_points") or sp.get("planned_tasks") or 0)
        total_completed += int(sp.get("completed_points") or sp.get("completed_tasks") or 0)
        end_date = _parse_datetime(sp.get("end_date"))
        if end_date and end_date < current_time and str(sp.get("status", "")).lower() == "active":
            overdue_milestones.append({
                "title": sp.get("name", "Sprint"),
                "due_on": end_date.isoformat(),
                "open_issues": total_planned - total_completed,
            })

    flags = []
    score = 100.0

    if overdue_milestones:
        score = max(20.0, round(100.0 - (len(overdue_milestones) * 35.0), 1))
        flags.append({
            "id": "flag_schedule_slippage_overdue",
            "type": "schedule_risk",
            "severity": "high",
            "message": f"{len(overdue_milestones)} active milestone(s) or sprint(s) are past their target delivery date with uncompleted work.",
            "evidence": {"overdue_items": overdue_milestones},
        })
    elif total_planned > 0:
        completion_ratio = total_completed / total_planned
        score = round(completion_ratio * 100.0, 1)
        if completion_ratio < 0.40:
            flags.append({
                "id": "flag_slow_sprint_velocity",
                "type": "schedule_risk",
                "severity": "medium",
                "message": f"Milestone task completion velocity is currently low ({round(completion_ratio * 100, 1)}% complete).",
                "evidence": {
                    "completed_tasks": total_completed,
                    "total_tasks": total_planned,
                },
            })
    else:
        # Milestones exist but contain no tasks
        score = 80.0

    score = max(0.0, min(100.0, round(score, 1)))

    return {
        "score": score,
        "status": _classify_score(score),
        "data_status": "available",
        "weight": 0.25,
        "details": {
            "milestones_count": len(milestones_list),
            "sprints_count": len(sprints_list),
            "total_planned_items": total_planned,
            "total_completed_items": total_completed,
            "overdue_count": len(overdue_milestones),
        },
        "flags": flags,
    }


# ---------------------------------------------------------------------------
# 5. Composite Health Aggregator (Dynamic Re-weighting Engine)
# ---------------------------------------------------------------------------

def aggregate_health_score(
    bottlenecks: Dict[str, Any],
    workload: Dict[str, Any],
    stale_issues: Dict[str, Any],
    schedule_risk: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Combines individual indicators into a composite 0-100 Health Index.
    Gracefully re-weights available indicators when optional/missing data
    (such as milestones or PRs) reports 'insufficient_data'.
    """
    indicators = {
        "bottlenecks": bottlenecks,
        "workload": workload,
        "stale_issues": stale_issues,
        "schedule_risk": schedule_risk,
    }

    # Find indicators with valid scores
    valid_indicators = {
        name: ind for name, ind in indicators.items() if ind.get("score") is not None
    }

    weights_used: Dict[str, float] = {}
    active_flags: List[Dict[str, Any]] = []

    for name, ind in indicators.items():
        active_flags.extend(ind.get("flags", []))

    if not valid_indicators:
        return {
            "health_score": None,
            "status": STATUS_INSUFFICIENT,
            "summary_statement": "Insufficient Data: Repository activity telemetry has not been synchronized.",
            "weights_used": {k: 0.0 for k in indicators},
            "active_flags": active_flags,
            "indicators": indicators,
        }

    # Normalize weights so they sum to 1.0 across available indicators
    num_valid = len(valid_indicators)
    normalized_weight = round(1.0 / num_valid, 4)

    weighted_score = 0.0
    for name in indicators:
        if name in valid_indicators:
            weights_used[name] = normalized_weight
            weighted_score += valid_indicators[name]["score"] * normalized_weight
        else:
            weights_used[name] = 0.0

    final_score = max(0.0, min(100.0, round(weighted_score, 1)))
    status = _classify_score(final_score)

    # Compose summary narrative statement
    if status == STATUS_GOOD:
        summary_statement = f"Project health is Good (Score: {int(final_score)}/100). Telemetry indicates steady velocity with no critical delivery blockers."
    elif status == STATUS_CAUTION:
        summary_statement = f"Project health is under Caution (Score: {int(final_score)}/100). Review queues, activity concentration, or stale items warrant attention."
    else:
        summary_statement = f"Project health is At Risk (Score: {int(final_score)}/100). Severe delivery bottlenecks, high workload concentration, or overdue milestones detected."

    missing_keys = [k for k, ind in indicators.items() if ind.get("score") is None]
    if missing_keys:
        summary_statement += f" Note: {', '.join(missing_keys)} data currently insufficient."

    return {
        "health_score": final_score,
        "status": status,
        "summary_statement": summary_statement,
        "weights_used": weights_used,
        "active_flags": active_flags,
        "indicators": indicators,
    }


# ---------------------------------------------------------------------------
# 6. High-Level Orchestrators
# ---------------------------------------------------------------------------

def build_health_summary(
    project: Dict[str, Any],
    commits: Optional[List[Dict[str, Any]]] = None,
    contributors: Optional[List[Dict[str, Any]]] = None,
    pull_requests: Optional[List[Dict[str, Any]]] = None,
    issues: Optional[List[Dict[str, Any]]] = None,
    sprints: Optional[List[Dict[str, Any]]] = None,
    thresholds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Construct high-level health summary response for a project.
    Matches GET /api/projects/{id}/health-summary specification.
    """
    # Extract project settings thresholds if available
    merged_thresholds = {
        **DEFAULT_THRESHOLDS,
        **(project.get("settings", {}).get("thresholds", {}) if isinstance(project.get("settings"), dict) else {}),
        **(thresholds or {}),
    }

    bottlenecks = compute_bottlenecks_indicator(pull_requests, merged_thresholds)
    workload = compute_workload_indicator(commits, contributors, merged_thresholds)
    stale_issues = compute_stale_issues_indicator(issues, merged_thresholds)
    schedule_risk = compute_schedule_risk_indicator(sprints=sprints, issues=issues, thresholds=merged_thresholds)

    composite = aggregate_health_score(bottlenecks, workload, stale_issues, schedule_risk)

    # Determine data freshness
    last_synced_at = (
        project.get("lastSyncedAt")
        or project.get("last_synced_at")
        or project.get("updatedAt")
    )
    last_synced_dt = _parse_datetime(last_synced_at)
    if last_synced_dt:
        now = datetime.now(timezone.utc)
        freshness = "fresh" if (now - last_synced_dt).total_seconds() < 86400 else "stale"
        last_synced_str = last_synced_dt.isoformat()
    else:
        freshness = "unknown"
        last_synced_str = None

    flags = composite["active_flags"]
    flags_count = {
        "total": len(flags),
        "high": sum(1 for f in flags if f.get("severity") == "high"),
        "medium": sum(1 for f in flags if f.get("severity") == "medium"),
        "low": sum(1 for f in flags if f.get("severity") == "low"),
    }

    data_availability = {
        "commits": "available" if commits else "insufficient_data",
        "contributors": "available" if contributors else "insufficient_data",
        "pull_requests": bottlenecks["data_status"],
        "issues": stale_issues["data_status"],
        "schedule_risk": schedule_risk["data_status"],
    }

    project_id = str(project.get("_id") or project.get("id") or "")

    return {
        "project_id": project_id,
        "project_name": project.get("name", "Project"),
        "health_score": composite["health_score"],
        "status": composite["status"],
        "last_synced_at": last_synced_str,
        "data_freshness": freshness,
        "data_availability": data_availability,
        "summary_statement": composite["summary_statement"],
        "flags_count": flags_count,
        "active_flags": flags,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_metrics_breakdown(
    project: Dict[str, Any],
    commits: Optional[List[Dict[str, Any]]] = None,
    contributors: Optional[List[Dict[str, Any]]] = None,
    pull_requests: Optional[List[Dict[str, Any]]] = None,
    issues: Optional[List[Dict[str, Any]]] = None,
    sprints: Optional[List[Dict[str, Any]]] = None,
    thresholds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Construct granular indicator breakdown response for a project.
    Matches GET /api/projects/{id}/metrics/breakdown specification.
    """
    merged_thresholds = {
        **DEFAULT_THRESHOLDS,
        **(project.get("settings", {}).get("thresholds", {}) if isinstance(project.get("settings"), dict) else {}),
        **(thresholds or {}),
    }

    bottlenecks = compute_bottlenecks_indicator(pull_requests, merged_thresholds)
    workload = compute_workload_indicator(commits, contributors, merged_thresholds)
    stale_issues = compute_stale_issues_indicator(issues, merged_thresholds)
    schedule_risk = compute_schedule_risk_indicator(sprints=sprints, issues=issues, thresholds=merged_thresholds)

    composite = aggregate_health_score(bottlenecks, workload, stale_issues, schedule_risk)
    project_id = str(project.get("_id") or project.get("id") or "")

    return {
        "project_id": project_id,
        "project_name": project.get("name", "Project"),
        "health_score": composite["health_score"],
        "status": composite["status"],
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "weights_used": composite["weights_used"],
        "indicators": {
            "bottlenecks": bottlenecks,
            "workload": workload,
            "stale_issues": stale_issues,
            "schedule_risk": schedule_risk,
        },
    }

