"""
Schedule Risk Engine — AI Software Project Health & Risk Analyzer
-----------------------------------------------------------------
Task: TASK-SP2-09 (Issue #73)

Pure analytical module to estimate indicative project and milestone-level
schedule drift by comparing remaining open tasks against recent completion
velocity.

Pure analytical module:
  - Zero database / MongoDB dependencies.
  - Zero GitHub API / network dependencies.
  - Zero environment variable requirements.
  - Immutable handling of all supplied input collections.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

DEFAULT_VELOCITY_WINDOW_DAYS: int = 30

SCHEDULE_DISCLAIMER: str = (
    "Project-wide velocity applied to milestone aggregates is an indicative estimate, "
    "not a precise milestone-specific forecast."
)


def _parse_iso_datetime(val: Any) -> Optional[datetime]:
    """
    Parse ISO-8601 or datetime representation into a timezone-aware UTC datetime.

    Handles:
      - None, non-string/non-datetime -> None
      - datetime with tzinfo -> normalized to UTC via astimezone(timezone.utc)
      - datetime without tzinfo (naive) -> assumed UTC (replace(tzinfo=timezone.utc))
      - ISO-8601 strings with 'Z' or offset (e.g. +05:30, -04:00) -> parsed and normalized to UTC
      - Malformed or invalid strings -> None
    """
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is not None:
            return val.astimezone(timezone.utc)
        return val.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        cleaned = val.strip()
        if not cleaned:
            return None
        try:
            cleaned_z = cleaned.replace("Z", "+00:00")
            dt = datetime.fromisoformat(cleaned_z)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            return None
    return None


def _is_pull_request(issue: Dict[str, Any]) -> bool:
    """
    Determine if an issue object represents a pull request.
    In GitHub API, pull requests returned in issue endpoints have a 'pull_request' key.
    """
    if not isinstance(issue, dict):
        return False
    if "pull_request" in issue and issue.get("pull_request") is not None:
        return True
    return False


def _safe_int_or_none(val: Any) -> Optional[int]:
    """
    Safely extract a non-negative integer from a field value, or return None if
    the field is missing, None, or empty.
    """
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, str) and not val.strip():
        return None
    try:
        res = int(val)
        return max(0, res)
    except (ValueError, TypeError):
        return None


def compute_schedule_drift(
    issues: Optional[List[Dict[str, Any]]] = None,
    milestones: Optional[List[Dict[str, Any]]] = None,
    now: Optional[datetime] = None,
    velocity_window_days: int = DEFAULT_VELOCITY_WINDOW_DAYS,
) -> Dict[str, Any]:
    """
    Compare remaining open tasks against recent completion velocity and
    calculate indicative schedule drift.

    Args:
      issues: List of issue dictionaries (state, created_at, closed_at, etc.).
              Pull requests (items containing 'pull_request') are excluded.
      milestones: List of milestone dictionaries (milestone_id, title, state, due_on, open_issues, closed_issues).
      now: Injectable current UTC datetime for deterministic calculations (default: now UTC).
      velocity_window_days: Trailing window in days to measure closed task velocity (default: 30, must be a positive integer).

    Returns:
      Structured, JSON-serializable dictionary with:
        - data_status: 'available', 'no_open_tasks', 'insufficient_velocity', 'no_target_date', 'no_data'
        - remaining_open_tasks: int count of open issues
        - recently_completed_tasks: int count of issues closed in the trailing window
        - velocity_window_days: int window duration
        - completion_velocity_per_day: float velocity (tasks/day, rounded for display)
        - estimated_completion_days: Optional[float] estimated days to complete (rounded for display)
        - estimated_completion_date: Optional[str] ISO UTC timestamp
        - schedule_drift_days: Optional[float] drift in days (worst positive drift if multiple milestones)
        - milestones: List of milestone-level drift estimates
        - flags: List of structured schedule risk flags
        - messages: List of human-readable explanations of status and data sufficiency
        - disclaimer: Indicative estimate disclaimer
    """
    # 1. Validate velocity_window_days: must be positive integer (reject bools, floats, strings, non-positive)
    if isinstance(velocity_window_days, bool) or not isinstance(velocity_window_days, int) or velocity_window_days <= 0:
        raise ValueError("velocity_window_days must be a positive integer greater than 0.")

    current_time = _parse_iso_datetime(now) or datetime.now(timezone.utc)
    window_start = current_time - timedelta(days=velocity_window_days)

    safe_issues = issues if issues is not None else []
    safe_milestones = milestones if milestones is not None else []

    # 2. Filter genuine issues (drop pull requests)
    genuine_issues = [
        issue for issue in safe_issues
        if isinstance(issue, dict) and not _is_pull_request(issue)
    ]

    # Open tasks
    open_tasks = [
        issue for issue in genuine_issues
        if str(issue.get("state") or "").strip().lower() == "open"
    ]
    remaining_open_tasks = len(open_tasks)

    # Recently closed tasks in trailing window
    recently_closed_tasks: List[Dict[str, Any]] = []
    for issue in genuine_issues:
        state_str = str(issue.get("state") or "").strip().lower()
        if state_str == "closed":
            # Must have valid closed_at
            closed_at_raw = issue.get("closed_at")
            closed_dt = _parse_iso_datetime(closed_at_raw)
            if closed_dt is not None:
                if window_start <= closed_dt <= current_time:
                    recently_closed_tasks.append(issue)

    completed_in_window_count = len(recently_closed_tasks)

    # Use raw full precision internally for all calculations
    raw_velocity: float = completed_in_window_count / float(velocity_window_days)
    display_velocity_per_day: float = round(raw_velocity, 4)

    # 3. Handle applicable milestones (state == "open")
    applicable_milestones: List[Dict[str, Any]] = []
    for ms in safe_milestones:
        if not isinstance(ms, dict):
            continue
        ms_state = str(ms.get("state") or "open").strip().lower()
        if ms_state == "open":
            applicable_milestones.append(ms)

    messages: List[Dict[str, Any]] = []
    flags: List[Dict[str, Any]] = []

    # Default result structure initialization
    estimated_days: Optional[float] = None
    estimated_date_str: Optional[str] = None
    project_drift_days: Optional[float] = None
    data_status: str = "available"

    # 4. Check data sufficiency cases

    # Case A: No issue records provided
    if not genuine_issues:
        data_status = "no_data"
        messages.append({
            "code": "NO_ISSUES_DATA",
            "message": "No issue data available for schedule drift calculation.",
        })

    # Case B: No open tasks remaining
    elif remaining_open_tasks == 0:
        data_status = "no_open_tasks"
        estimated_days = 0.0
        estimated_date_str = current_time.isoformat()
        messages.append({
            "code": "NO_OPEN_TASKS",
            "message": "All project tasks are closed. No remaining open tasks to complete.",
        })

    # Case C: Open tasks exist, but zero completion velocity in window
    elif completed_in_window_count == 0 or raw_velocity == 0.0:
        data_status = "insufficient_velocity"
        messages.append({
            "code": "ZERO_VELOCITY",
            "message": (
                f"{remaining_open_tasks} open task(s) remain, but zero tasks were completed "
                f"in the trailing {velocity_window_days}-day window. Schedule drift cannot be "
                "quantified without recent completion velocity."
            ),
        })
        flags.append({
            "id": "flag_schedule_stalled_velocity",
            "type": "schedule_risk",
            "severity": "high",
            "remaining_open_tasks": remaining_open_tasks,
            "completion_velocity_per_day": 0.0,
            "message": (
                f"Schedule Risk: {remaining_open_tasks} open tasks remain with 0 tasks completed "
                f"in the last {velocity_window_days} days. Project velocity is stalled."
            ),
        })

    # Case D: Open tasks exist and velocity > 0
    else:
        # Calculate projected days and date using raw_velocity
        calc_days = remaining_open_tasks / raw_velocity
        estimated_days = round(calc_days, 2)
        proj_dt = current_time + timedelta(days=calc_days)
        estimated_date_str = proj_dt.isoformat()

    # 5. Milestone-level drift calculation
    milestone_estimates: List[Dict[str, Any]] = []
    positive_drifts: List[float] = []

    for ms in applicable_milestones:
        ms_id = str(ms.get("milestone_id") or ms.get("number") or ms.get("id") or "")
        ms_title = ms.get("title") or "Untitled Milestone"
        ms_due_raw = ms.get("due_on") or ms.get("due_date")
        ms_due_dt = _parse_iso_datetime(ms_due_raw)

        raw_open_issues = _safe_int_or_none(ms.get("open_issues"))
        ms_closed_issues = _safe_int_or_none(ms.get("closed_issues")) or 0

        # Milestone open tasks logic:
        # If open_issues is explicitly supplied (including 0): use it!
        # If open_issues is genuinely missing/None: fall back to remaining_open_tasks
        if raw_open_issues is not None:
            tasks_for_ms = raw_open_issues
            ms_open_issues_display = raw_open_issues
        else:
            tasks_for_ms = remaining_open_tasks
            ms_open_issues_display = remaining_open_tasks

        ms_est_days: Optional[float] = None
        ms_est_date: Optional[str] = None
        ms_drift_days: Optional[float] = None
        ms_status: str = "ok"

        # Case 1: Milestone has 0 open tasks
        if tasks_for_ms == 0:
            ms_est_days = 0.0
            ms_est_date = current_time.isoformat()
            if ms_due_dt is not None:
                # If target was in the past and 0 tasks remain, drift is based on current_time vs due_dt
                drift_seconds = (current_time - ms_due_dt).total_seconds()
                ms_drift_days = round(drift_seconds / 86400.0, 2)
                # Completed on time if current_time <= ms_due_dt
                if ms_drift_days > 0.0:
                    ms_status = "delayed"
                    positive_drifts.append(ms_drift_days)
                else:
                    ms_status = "on_time"
            else:
                ms_status = "no_target_date"

        # Case 2: Positive velocity and tasks_for_ms > 0
        elif raw_velocity > 0.0:
            m_days = tasks_for_ms / raw_velocity
            ms_est_days = round(m_days, 2)
            m_proj_dt = current_time + timedelta(days=m_days)
            ms_est_date = m_proj_dt.isoformat()

            if ms_due_dt is not None:
                drift_seconds = (m_proj_dt - ms_due_dt).total_seconds()
                ms_drift_days = round(drift_seconds / 86400.0, 2)
                if ms_drift_days > 0.0:
                    ms_status = "delayed"
                    positive_drifts.append(ms_drift_days)
                else:
                    ms_status = "on_time"
            else:
                ms_status = "no_target_date"

        # Case 3: Zero velocity and tasks_for_ms > 0
        else:
            ms_status = "insufficient_velocity"

        milestone_estimates.append({
            "milestone_id": ms_id,
            "title": ms_title,
            "state": str(ms.get("state") or "open").lower(),
            "due_on": ms_due_dt.isoformat() if ms_due_dt else None,
            "open_issues": ms_open_issues_display,
            "closed_issues": ms_closed_issues,
            "estimated_completion_days": ms_est_days,
            "estimated_completion_date": ms_est_date,
            "schedule_drift_days": ms_drift_days,
            "status": ms_status,
        })

    # 6. Overall schedule drift & target date evaluation
    if not applicable_milestones:
        if data_status == "available":
            data_status = "no_target_date"
            messages.append({
                "code": "NO_MILESTONES",
                "message": (
                    f"Project has {remaining_open_tasks} open tasks with velocity of {display_velocity_per_day} "
                    f"tasks/day (est. {estimated_days} days to complete), but no active milestones "
                    "or target delivery dates are configured to quantify schedule drift."
                ),
            })
    else:
        # Check if any applicable milestone has a valid due date
        has_due_dates = any(m["due_on"] is not None for m in milestone_estimates)
        if not has_due_dates:
            if data_status == "available":
                data_status = "no_target_date"
                messages.append({
                    "code": "MISSING_DUE_DATES",
                    "message": (
                        "Milestones exist but lack target due dates (`due_on`). "
                        "Schedule drift cannot be quantified."
                    ),
                })
        elif data_status == "available":
            # We have valid velocity and at least one target due date
            # Report worst positive drift (maximum drift among delayed milestones)
            if positive_drifts:
                project_drift_days = max(positive_drifts)
                delayed_count = len(positive_drifts)
                flags.append({
                    "id": "flag_schedule_drift_detected",
                    "type": "schedule_risk",
                    "severity": "high" if project_drift_days > 14.0 else "medium",
                    "schedule_drift_days": project_drift_days,
                    "delayed_milestones_count": delayed_count,
                    "message": (
                        f"Schedule Drift: Current velocity projects a delay of "
                        f"{project_drift_days} days past milestone delivery target."
                    ),
                })
            else:
                # All milestones projected on or before due date: report worst drift (which is <= 0)
                all_drifts = [m["schedule_drift_days"] for m in milestone_estimates if m["schedule_drift_days"] is not None]
                if all_drifts:
                    project_drift_days = max(all_drifts)

    return {
        "data_status": data_status,
        "remaining_open_tasks": remaining_open_tasks,
        "recently_completed_tasks": completed_in_window_count,
        "velocity_window_days": velocity_window_days,
        "completion_velocity_per_day": display_velocity_per_day,
        "estimated_completion_days": estimated_days,
        "estimated_completion_date": estimated_date_str,
        "schedule_drift_days": project_drift_days,
        "milestones": milestone_estimates,
        "flags": flags,
        "messages": messages,
        "disclaimer": SCHEDULE_DISCLAIMER,
    }
