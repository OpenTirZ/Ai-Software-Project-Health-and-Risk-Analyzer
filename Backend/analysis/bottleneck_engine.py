"""
Bottleneck Detection Engine — AI Software Project Health & Risk Analyzer
-------------------------------------------------------------------------
Task: TASK-SP2-07 (Issue #71) — Part A: Bottleneck Detection Engine

Deterministic, pure Python calculations to evaluate development bottlenecks
from pull request telemetry:
  1. Aging Pull Requests: Detect open pull requests open longer than a configured
     threshold (default: 48 hours) without a genuinely submitted review.
  2. Review Queue Congestion: Detect individual reviewers assigned to more than
     a configured threshold (default: 5) of concurrent pending pull request reviews
     based on current requested_reviewers.

Pure analytical module:
  - Zero database / MongoDB dependencies.
  - Zero GitHub API / network dependencies.
  - Zero environment variable requirements.
  - Zero filesystem reading or writing.
  - Immutable handling of all supplied input collections.
  - Deterministic calculations with injectable now.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union

DEFAULT_AGING_THRESHOLD_HOURS: float = 48.0
DEFAULT_REVIEWER_QUEUE_THRESHOLD: int = 5


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


def _extract_reviewer_login(reviewer: Any) -> Optional[str]:
    """
    Extract and clean reviewer login/username.
    Handles:
      - string: "octocat"
      - dict: {"login": "octocat", ...}
    Returns cleaned username or None.
    """
    if isinstance(reviewer, str):
        clean = reviewer.strip()
        return clean if clean else None
    if isinstance(reviewer, dict):
        login = reviewer.get("login") or reviewer.get("username")
        if isinstance(login, str):
            clean = login.strip()
            return clean if clean else None
    return None


def _extract_submitted_reviews(pr: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract valid submitted review records from a PR dict.

    Requirements:
      - Must be a dictionary inside the 'reviews' list.
      - A review with state 'PENDING' (case-insensitive) must NOT count as submitted.
      - A review without a valid 'submitted_at' timestamp must NOT count as submitted.
      - Uses GitHub review field 'submitted_at' (does not use generic created_at as proof of submission).

    Returns:
      List of genuinely submitted review dicts with valid submitted_at timestamps.
    """
    raw_reviews = pr.get("reviews")
    if not isinstance(raw_reviews, list):
        return []

    submitted: List[Dict[str, Any]] = []
    for r in raw_reviews:
        if not isinstance(r, dict):
            continue

        # Check state: PENDING reviews are unsubmitted drafts
        state = str(r.get("state") or "").strip().upper()
        if state == "PENDING":
            continue

        # Check submitted_at timestamp
        submitted_at_raw = r.get("submitted_at")
        if not submitted_at_raw:
            continue

        submitted_dt = _parse_iso_datetime(submitted_at_raw)
        if submitted_dt is None:
            continue

        submitted.append(r)

    return submitted


def _has_submitted_review(pr: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Determine if a PR has received at least one genuinely submitted review.

    Requirements:
      - Evaluates only genuinely submitted reviews with valid 'submitted_at'.
      - Does NOT use generic 'reviews_count' > 0 to suppress an Aging PR flag when
        submitted review details are unavailable (since normalizer sets reviews_count
        to len(reviews), which includes pending/draft reviews).

    Returns:
      (has_submitted_review: bool, latest_submitted_at_iso: Optional[str])
    """
    submitted_reviews = _extract_submitted_reviews(pr)
    if not submitted_reviews:
        return False, None

    latest_dt: Optional[datetime] = None
    latest_str: Optional[str] = None

    for r in submitted_reviews:
        submitted_at_raw = r.get("submitted_at")
        dt = _parse_iso_datetime(submitted_at_raw)
        if dt is not None:
            if latest_dt is None or dt > latest_dt:
                latest_dt = dt
                latest_str = dt.isoformat()

    return True, latest_str


def _check_aging_prs(
    open_prs: List[Dict[str, Any]],
    current_time: datetime,
    aging_threshold_hours: float,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Evaluate open pull requests against the aging threshold.

    An aging PR is an open PR that:
      - Has a valid created_at timestamp.
      - Has NOT received a completed submitted review (with valid submitted_at).
      - Its age in hours from created_at to current_time is strictly greater than aging_threshold_hours.

    Returns:
      (aging_prs_list, flags_list)
    """
    aging_prs: List[Dict[str, Any]] = []
    flags: List[Dict[str, Any]] = []

    for pr in open_prs:
        pr_number = pr.get("number")
        title = pr.get("title") or f"PR #{pr_number}"

        created_raw = pr.get("created_at") or pr.get("createdAt")
        created_dt = _parse_iso_datetime(created_raw)
        if created_dt is None:
            # Cannot determine age without valid creation timestamp; skip
            continue

        has_review, latest_review_ts = _has_submitted_review(pr)
        if has_review:
            # PR has received a genuinely submitted review; not unreviewed/aging
            continue

        # Calculate age in hours
        total_seconds = (current_time - created_dt).total_seconds()
        age_hours = total_seconds / 3600.0

        # Strict greater-than threshold comparison
        if age_hours > aging_threshold_hours:
            rounded_age = round(age_hours, 2)
            evidence = {
                "number": pr_number,
                "title": title,
                "created_at": created_dt.isoformat(),
                "age_hours": rounded_age,
                "threshold_hours": float(aging_threshold_hours),
                "author": pr.get("author") or pr.get("github_username") or "Unknown",
                "html_url": pr.get("html_url"),
            }
            aging_prs.append(evidence)

            flags.append({
                "id": f"flag_aging_pr_{pr_number}",
                "type": "aging_pull_request",
                "severity": "high" if age_hours > (aging_threshold_hours * 2.0) else "medium",
                "pr_number": pr_number,
                "created_at": created_dt.isoformat(),
                "age_hours": rounded_age,
                "threshold_hours": float(aging_threshold_hours),
                "message": (
                    f"Pull Request #{pr_number} ('{title}') has been open for {rounded_age} hours "
                    f"without receiving a submitted review, exceeding the {aging_threshold_hours}h threshold."
                ),
                "evidence": evidence,
            })

    # Sort aging_prs by age_hours descending
    aging_prs.sort(key=lambda x: x["age_hours"], reverse=True)
    flags.sort(key=lambda x: x["age_hours"], reverse=True)

    return aging_prs, flags


def _check_review_queue_congestion(
    open_prs: List[Dict[str, Any]],
    reviewer_queue_threshold: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Evaluate reviewer workload across open PRs using current requested_reviewers.

    Identifies reviewers assigned to strictly more than reviewer_queue_threshold
    concurrent pending pull request reviews.

    Requirements:
      - Uses current requested_reviewers as the source of truth for pending assignments.
      - Counts unique PR assignments per reviewer.
      - Excludes closed and merged PRs (input is already filtered to open PRs).
      - Deduplicates reviewer assignments within the same PR.
      - Does NOT remove a currently requested reviewer merely because they have a
        historical submitted review on that PR (re-requested reviews are still pending!).
      - Normalizes usernames case-insensitively while preserving original display name.
      - Strict greater-than comparison (> threshold).

    Returns:
      (congested_reviewers_list, flags_list)
    """
    # Map normalized_reviewer_login -> {"display_name": str, "pending_prs": Set[int]}
    reviewer_pending_prs: Dict[str, Dict[str, Any]] = {}

    for pr in open_prs:
        pr_number = pr.get("number")
        if pr_number is None:
            continue

        raw_req = pr.get("requested_reviewers")
        if not isinstance(raw_req, list):
            continue

        # Unique requested reviewers for this PR
        pr_requested_logins: Set[str] = set()
        for r_entry in raw_req:
            login = _extract_reviewer_login(r_entry)
            if login:
                norm_login = login.lower()
                if norm_login in pr_requested_logins:
                    continue
                pr_requested_logins.add(norm_login)

                if norm_login not in reviewer_pending_prs:
                    reviewer_pending_prs[norm_login] = {
                        "reviewer": login,  # preserve original casing
                        "pending_prs": set(),
                    }
                reviewer_pending_prs[norm_login]["pending_prs"].add(pr_number)

    congested_reviewers: List[Dict[str, Any]] = []
    flags: List[Dict[str, Any]] = []

    for norm_login, data in reviewer_pending_prs.items():
        reviewer_name = data["reviewer"]
        pr_set: Set[int] = data["pending_prs"]
        count = len(pr_set)

        # Strict greater-than threshold comparison
        if count > reviewer_queue_threshold:
            sorted_prs = sorted(list(pr_set))
            entry = {
                "reviewer": reviewer_name,
                "pending_prs_count": count,
                "pending_prs": sorted_prs,
                "threshold": reviewer_queue_threshold,
            }
            congested_reviewers.append(entry)

            flags.append({
                "id": f"flag_review_queue_congestion_{norm_login}",
                "type": "review_queue_congestion",
                "severity": "high" if count > (reviewer_queue_threshold * 2) else "medium",
                "reviewer": reviewer_name,
                "pending_prs_count": count,
                "pending_prs": sorted_prs,
                "threshold": reviewer_queue_threshold,
                "message": (
                    f"Reviewer '{reviewer_name}' is assigned to {count} concurrent pending "
                    f"pull request reviews ({sorted_prs}), exceeding the threshold of {reviewer_queue_threshold}."
                ),
                "evidence": entry,
            })

    # Sort congested reviewers by pending_prs_count descending
    congested_reviewers.sort(key=lambda x: (-x["pending_prs_count"], x["reviewer"].lower()))
    flags.sort(key=lambda x: (-x["pending_prs_count"], x["reviewer"].lower()))

    return congested_reviewers, flags


def detect_bottlenecks(
    pull_requests: Optional[List[Dict[str, Any]]] = None,
    now: Optional[datetime] = None,
    aging_threshold_hours: float = DEFAULT_AGING_THRESHOLD_HOURS,
    reviewer_queue_threshold: int = DEFAULT_REVIEWER_QUEUE_THRESHOLD,
) -> Dict[str, Any]:
    """
    Detect development bottlenecks from pull request telemetry:
      1. Aging Pull Requests (> aging_threshold_hours without submitted review).
      2. Review Queue Congestion (> reviewer_queue_threshold pending reviews per reviewer).

    Args:
      pull_requests: List of normalized pull request dictionaries.
                     Expected keys include 'number', 'state', 'created_at',
                     'requested_reviewers', 'reviews', 'reviews_count'.
      now: Injectable current UTC datetime for deterministic calculations (default: now UTC).
      aging_threshold_hours: Maximum allowable age in hours for an unreviewed open PR
                             before flagging (default: 48, must be a finite positive number).
      reviewer_queue_threshold: Maximum allowable concurrent pending PR assignments for a
                                single reviewer before flagging (default: 5, must be a positive integer).

    Returns:
      Structured, JSON-serializable dictionary with:
        - data_status: 'available', 'no_open_prs', 'no_data'
        - analyzed_at: ISO-8601 UTC timestamp of analysis
        - thresholds: configured thresholds used for detection
        - total_prs_evaluated: int total PRs in input
        - open_prs_count: int count of open PRs analyzed
        - aging_prs: list of detailed aging PR records
        - review_queue_congestion: list of congested reviewer records
        - flags: consolidated list of structured bottleneck flags
        - summary: high-level summary counts and status
    """
    # 1. Validate aging_threshold_hours
    if (
        isinstance(aging_threshold_hours, bool)
        or not isinstance(aging_threshold_hours, (int, float))
        or math.isnan(aging_threshold_hours)
        or math.isinf(aging_threshold_hours)
        or aging_threshold_hours <= 0.0
    ):
        raise ValueError(
            "aging_threshold_hours must be a finite positive numeric value greater than 0."
        )

    # 2. Validate reviewer_queue_threshold
    if (
        isinstance(reviewer_queue_threshold, bool)
        or not isinstance(reviewer_queue_threshold, int)
        or reviewer_queue_threshold <= 0
    ):
        raise ValueError(
            "reviewer_queue_threshold must be a positive integer greater than 0."
        )

    # 3. Establish deterministic analysis timestamp
    current_time = _parse_iso_datetime(now) or datetime.now(timezone.utc)

    safe_prs = pull_requests if pull_requests is not None else []

    # 4. Filter open PRs (exclude closed and merged PRs)
    open_prs: List[Dict[str, Any]] = []
    for pr in safe_prs:
        if not isinstance(pr, dict):
            continue
        state = str(pr.get("state") or "").strip().lower()
        if state == "open":
            open_prs.append(pr)

    total_prs = len(safe_prs)
    open_prs_count = len(open_prs)

    # 5. Determine data status
    if total_prs == 0:
        data_status = "no_data"
    elif open_prs_count == 0:
        data_status = "no_open_prs"
    else:
        data_status = "available"

    # 6. Rule A: Detect aging open PRs
    aging_prs, aging_flags = _check_aging_prs(
        open_prs=open_prs,
        current_time=current_time,
        aging_threshold_hours=float(aging_threshold_hours),
    )

    # 7. Rule B: Detect review queue congestion
    congested_reviewers, congestion_flags = _check_review_queue_congestion(
        open_prs=open_prs,
        reviewer_queue_threshold=reviewer_queue_threshold,
    )

    # 8. Consolidate flags
    all_flags = aging_flags + congestion_flags

    # 9. Build summary
    summary = {
        "has_bottlenecks": len(all_flags) > 0,
        "aging_prs_count": len(aging_prs),
        "congested_reviewers_count": len(congested_reviewers),
        "total_flags_count": len(all_flags),
    }

    return {
        "data_status": data_status,
        "analyzed_at": current_time.isoformat(),
        "thresholds": {
            "aging_threshold_hours": float(aging_threshold_hours),
            "reviewer_queue_threshold": reviewer_queue_threshold,
        },
        "total_prs_evaluated": total_prs,
        "open_prs_count": open_prs_count,
        "aging_prs": aging_prs,
        "review_queue_congestion": congested_reviewers,
        "flags": all_flags,
        "summary": summary,
    }
