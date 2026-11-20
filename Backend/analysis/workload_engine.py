"""
Workload & Bus Factor Risk Engine — AI Software Project Health & Risk Analyzer
-----------------------------------------------------------------------------
Task: TASK-SP2-09 (Issue #73)

Deterministic, pure Python calculations to evaluate contributor activity
distribution and concentration across commits and pull requests over a
trailing analysis window (default: trailing 30 days).

Pure analytical module:
  - Zero database / MongoDB dependencies.
  - Zero GitHub API / network dependencies.
  - Zero environment variable requirements.
  - Immutable handling of all supplied input collections.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

# Mandatory disclaimer for all workload analysis results
WORKLOAD_DISCLAIMER: str = (
    "Activity is a proxy indicator, not a definitive performance evaluation."
)

DEFAULT_ANALYSIS_WINDOW_DAYS: int = 30
DEFAULT_BUS_FACTOR_THRESHOLD: float = 0.60


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


def _extract_contributor_identity(
    item: Dict[str, Any],
) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract and normalize contributor identity from a commit or PR dict.

    Priority order:
      1. github_username (if present, string, non-empty)
      2. author (if string or dict)

    Handles:
      - String author: "Alice"
      - Dict author: {"login": "alice", "name": "Alice Developer", ...}
      - Normalization:
          - Display name: trimmed string as provided
          - Normalized key: trimmed and lowercased for case-insensitive aggregation
            (e.g., 'Alice' and 'alice' group together).

    Returns:
      (normalized_key, display_name) or (None, None) if unidentified.
    """
    if not isinstance(item, dict):
        return None, None

    # 1. github_username field
    gh_user = item.get("github_username")
    if isinstance(gh_user, str) and gh_user.strip():
        clean = gh_user.strip()
        return clean.lower(), clean

    # 2. author field
    author_val = item.get("author")
    if isinstance(author_val, str) and author_val.strip():
        clean = author_val.strip()
        # Avoid treating raw 'Unknown' or empty string as an identified contributor
        if clean.lower() == "unknown":
            return None, None
        return clean.lower(), clean

    if isinstance(author_val, dict):
        # author as a dict (GitHub commit/PR payload)
        # Check login first, then name, then email
        for k in ("login", "name", "email"):
            candidate = author_val.get(k)
            if isinstance(candidate, str) and candidate.strip():
                clean = candidate.strip()
                if clean.lower() != "unknown":
                    return clean.lower(), clean

    # 3. Fallback author_name
    author_name = item.get("author_name")
    if isinstance(author_name, str) and author_name.strip():
        clean = author_name.strip()
        if clean.lower() != "unknown":
            return clean.lower(), clean

    # 4. Fallback user login (e.g., PR raw user object)
    user_val = item.get("user")
    if isinstance(user_val, dict):
        user_login = user_val.get("login")
        if isinstance(user_login, str) and user_login.strip():
            clean = user_login.strip()
            if clean.lower() != "unknown":
                return clean.lower(), clean

    return None, None


def _calculate_activity_distribution(
    items: List[Dict[str, Any]],
    timestamp_field: str,
    window_start: datetime,
    window_end: datetime,
    activity_type: str,
    threshold: float,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Calculate workload distribution for an activity type (commits or PRs)
    over the trailing analysis window [window_start, window_end].

    Returns:
      (distribution_dict, bus_factor_flag_or_none)
    """
    eligible_items: List[Dict[str, Any]] = []

    # 1. Trailing window filtering
    for item in items:
        if not isinstance(item, dict):
            continue
        ts_val = item.get(timestamp_field)
        # Also check alternative casing e.g. createdAt for created_at
        if ts_val is None and timestamp_field == "created_at":
            ts_val = item.get("createdAt")
        elif ts_val is None and timestamp_field == "timestamp":
            ts_val = item.get("date")

        dt = _parse_iso_datetime(ts_val)
        if dt is None:
            # Exclude records with missing or invalid timestamps
            continue

        if window_start <= dt <= window_end:
            eligible_items.append(item)

    total_events = len(eligible_items)

    # 2. Contributor aggregation
    # Map normalized_key -> {"display_name": str, "count": int}
    counts: Dict[str, Dict[str, Any]] = {}
    unattributed_count = 0

    for item in eligible_items:
        norm_key, display_name = _extract_contributor_identity(item)
        if norm_key is None or display_name is None:
            unattributed_count += 1
        else:
            if norm_key not in counts:
                counts[norm_key] = {"display_name": display_name, "count": 0}
            counts[norm_key]["count"] += 1

    attributed_events = total_events - unattributed_count

    # 3. Compute individual shares and rankings
    contributors_list: List[Dict[str, Any]] = []
    top_contributor: Optional[str] = None
    top_contributor_count: int = 0
    top_contributor_percentage: float = 0.0

    if total_events > 0:
        # Sort contributors by count descending, then display_name ascending for determinism
        sorted_contribs = sorted(
            counts.values(),
            key=lambda x: (-x["count"], x["display_name"].lower()),
        )

        for entry in sorted_contribs:
            c_name = entry["display_name"]
            c_count = entry["count"]
            # Percentage uses total_events as denominator so unattributed events
            # do not artificially inflate identified contributors' share
            c_pct = round((c_count / total_events) * 100.0, 2)
            contributors_list.append({
                "contributor": c_name,
                "count": c_count,
                "percentage": c_pct,
            })

        if contributors_list:
            top_contributor = contributors_list[0]["contributor"]
            top_contributor_count = contributors_list[0]["count"]
            top_contributor_percentage = contributors_list[0]["percentage"]

    distribution: Dict[str, Any] = {
        "activity_type": activity_type,
        "total_events": total_events,
        "attributed_events": attributed_events,
        "unattributed_events": unattributed_count,
        "contributor_count": len(contributors_list),
        "contributors": contributors_list,
        "top_contributor": top_contributor,
        "top_contributor_count": top_contributor_count,
        "top_contributor_percentage": top_contributor_percentage,
    }

    # 4. Bus Factor Risk detection: STRICTLY GREATER THAN threshold (e.g. > 60.0%)
    flag: Optional[Dict[str, Any]] = None
    threshold_pct = round(threshold * 100.0, 2)

    if top_contributor is not None and total_events > 0:
        actual_ratio = top_contributor_count / total_events
        # Check strict inequality: actual_ratio > threshold
        if actual_ratio > threshold:
            flag = {
                "id": f"flag_bus_factor_{activity_type.lower()}",
                "type": "bus_factor_risk",
                "severity": "high",
                "activity_type": activity_type,
                "contributor": top_contributor,
                "contributor_count": top_contributor_count,
                "total_events": total_events,
                "percentage": top_contributor_percentage,
                "threshold_percentage": threshold_pct,
                "message": (
                    f"Bus Factor Risk: Contributor '{top_contributor}' accounts for "
                    f"{top_contributor_percentage}% of {activity_type} "
                    f"({top_contributor_count}/{total_events}), exceeding the "
                    f"{threshold_pct}% threshold."
                ),
            }

    return distribution, flag


def compute_workload_distribution(
    commits: Optional[List[Dict[str, Any]]] = None,
    pull_requests: Optional[List[Dict[str, Any]]] = None,
    now: Optional[datetime] = None,
    window_days: int = DEFAULT_ANALYSIS_WINDOW_DAYS,
    bus_factor_threshold: float = DEFAULT_BUS_FACTOR_THRESHOLD,
) -> Dict[str, Any]:
    """
    Compute contributor workload and activity distribution for commits and pull requests
    over a trailing analysis window.

    Args:
      commits: List of commit dictionaries with 'timestamp', 'author', and/or 'github_username'.
      pull_requests: List of PR dictionaries with 'created_at', 'author', and/or 'github_username'.
      now: Injectable current UTC datetime for deterministic calculations (default: now UTC).
      window_days: Number of days in the trailing analysis window (default: 30, must be a positive integer).
      bus_factor_threshold: Concentration threshold proportion (default: 0.60 for > 60%, must be finite numeric between 0.01 and 1.0).

    Returns:
      Structured, JSON-serializable dictionary with:
        - analysis_window: window bounds and duration
        - commit_distribution: detailed commit metrics & contributors
        - pr_distribution: detailed PR metrics & contributors
        - bus_factor_risk: overall bus factor risk status (boolean)
        - flags: list of structured Bus Factor Risk flags
        - disclaimer: mandatory proxy indicator disclaimer
    """
    # 1. Validate window_days: must be positive integer (reject bools, floats, strings, non-positive)
    if isinstance(window_days, bool) or not isinstance(window_days, int) or window_days <= 0:
        raise ValueError("window_days must be a positive integer greater than 0.")

    # 2. Validate bus_factor_threshold: must be finite numeric between 0.01 and 1.0 (reject bools, NaN, inf)
    if (
        isinstance(bus_factor_threshold, bool)
        or not isinstance(bus_factor_threshold, (int, float))
        or math.isnan(bus_factor_threshold)
        or math.isinf(bus_factor_threshold)
        or bus_factor_threshold < 0.01
        or bus_factor_threshold > 1.0
    ):
        raise ValueError("bus_factor_threshold must be a finite numeric value between 0.01 and 1.0.")

    # 3. Establish time window
    current_time = _parse_iso_datetime(now) or datetime.now(timezone.utc)
    window_start = current_time - timedelta(days=window_days)

    safe_commits = commits if commits is not None else []
    safe_prs = pull_requests if pull_requests is not None else []

    # 4. Calculate distributions independently
    commit_dist, commit_flag = _calculate_activity_distribution(
        items=safe_commits,
        timestamp_field="timestamp",
        window_start=window_start,
        window_end=current_time,
        activity_type="commits",
        threshold=bus_factor_threshold,
    )

    pr_dist, pr_flag = _calculate_activity_distribution(
        items=safe_prs,
        timestamp_field="created_at",
        window_start=window_start,
        window_end=current_time,
        activity_type="pull_requests",
        threshold=bus_factor_threshold,
    )

    # 5. Aggregate flags
    flags: List[Dict[str, Any]] = []
    if commit_flag is not None:
        flags.append(commit_flag)
    if pr_flag is not None:
        flags.append(pr_flag)

    has_bus_factor_risk = len(flags) > 0

    return {
        "analysis_window": {
            "window_days": window_days,
            "window_start": window_start.isoformat(),
            "window_end": current_time.isoformat(),
        },
        "commit_distribution": commit_dist,
        "pr_distribution": pr_dist,
        "bus_factor_risk": has_bus_factor_risk,
        "flags": flags,
        "disclaimer": WORKLOAD_DISCLAIMER,
    }
