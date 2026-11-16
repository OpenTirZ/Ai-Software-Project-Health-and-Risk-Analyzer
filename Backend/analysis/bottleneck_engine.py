
from datetime import datetime, timezone

DEFAULT_STALE_PR_HOURS = 48
DEFAULT_MAX_PENDING_PRS_PER_REVIEWER = 5


def _parse_datetime(value):
    """Parse an ISO timestamp or datetime into UTC."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    if not isinstance(value, datetime) or value.tzinfo is None:
        return None

    return value.astimezone(timezone.utc)


def _reviewer_login(reviewer):
    """Extract reviewer login from a string or dictionary."""
    if isinstance(reviewer, str):
        return reviewer.strip().lower()

    if isinstance(reviewer, dict):
        login = reviewer.get("login")
        if isinstance(login, str):
            return login.strip().lower()

    return ""


def _reviewed_by(review, reviewer_login):
    """Check whether a reviewer has already reviewed a PR."""
    if not isinstance(review, dict):
        return False

    reviewer = review.get("user") or review.get("reviewer")
    return _reviewer_login(reviewer) == reviewer_login


def detect_aging_prs(
    pull_requests,
    threshold_hours=DEFAULT_STALE_PR_HOURS,
    now=None,
):
    """
    Find open, unreviewed PRs older than the configured threshold.
    """
    if (
        isinstance(threshold_hours, bool)
        or not isinstance(threshold_hours, (int, float))
        or threshold_hours <= 0
    ):
        raise ValueError("threshold_hours must be a positive number")

    if now is None:
        now = datetime.now(timezone.utc)

    now = _parse_datetime(now)
    if now is None:
        raise ValueError("now must be a timezone-aware datetime")

    if not pull_requests:
        return []

    aging_prs = []

    for pr in pull_requests:
        if not isinstance(pr, dict):
            continue

        # Ignore closed and merged PRs.
        if (
            pr.get("state", "open") != "open"
            or pr.get("merged") is True
            or pr.get("merged_at") is not None
        ):
            continue

        reviews = pr.get("reviews") or []

        # Ignore PRs that already have reviews.
        if reviews or pr.get("reviews_count", 0) > 0:
            continue

        created_at = _parse_datetime(pr.get("created_at"))
        if created_at is None:
            continue

        age_hours = (now - created_at).total_seconds() / 3600

        if age_hours < 0 or age_hours <= threshold_hours:
            continue

        pr_number = pr.get("number")

        aging_prs.append({
            "type": "aging_pr",
            "pr_number": pr_number,
            "title": pr.get("title"),
            "age_hours": round(age_hours, 2),
            "threshold_hours": threshold_hours,
            "created_at": created_at.isoformat(),
            "html_url": pr.get("html_url"),
            "reason": (
                f"PR #{pr_number} has been open without a review "
                f"for {round(age_hours, 2)} hours."
            ),
        })

    return aging_prs


def detect_review_queue_congestion(
    pull_requests,
    max_pending_prs=DEFAULT_MAX_PENDING_PRS_PER_REVIEWER,
):
    """
    Find reviewers assigned to more than max_pending_prs pending PRs.
    """
    if (
        isinstance(max_pending_prs, bool)
        or not isinstance(max_pending_prs, int)
        or max_pending_prs < 0
    ):
        raise ValueError("max_pending_prs must be a non-negative integer")

    if not pull_requests:
        return []

    reviewer_prs = {}

    for pr in pull_requests:
        if not isinstance(pr, dict):
            continue

        if (
            pr.get("state", "open") != "open"
            or pr.get("merged") is True
            or pr.get("merged_at") is not None
        ):
            continue

        reviewers = pr.get("requested_reviewers") or []
        reviews = pr.get("reviews") or []

        # Count each reviewer at most once per PR.
        seen_reviewers = set()

        for reviewer in reviewers:
            login = _reviewer_login(reviewer)

            if not login or login in seen_reviewers:
                continue

            seen_reviewers.add(login)

            # A reviewer who has reviewed this PR is no longer pending.
            if any(_reviewed_by(review, login) for review in reviews):
                continue

            reviewer_prs.setdefault(login, []).append(pr.get("number"))

    congestion = []

    for reviewer, pr_numbers in sorted(reviewer_prs.items()):
        pending_count = len(pr_numbers)

        if pending_count > max_pending_prs:
            congestion.append({
                "type": "review_queue_congestion",
                "reviewer": reviewer,
                "pending_count": pending_count,
                "threshold": max_pending_prs,
                "pull_requests": pr_numbers,
                "pr_numbers": pr_numbers,
                "reason": (
                    f"Reviewer {reviewer} has {pending_count} pending "
                    f"PRs, exceeding the limit of {max_pending_prs}."
                ),
            })

    return congestion


def detect_bottlenecks(
    pull_requests,
    thresholds=None,
    now=None,
    max_pending_prs=DEFAULT_MAX_PENDING_PRS_PER_REVIEWER,
):
    """
    Run both bottleneck detectors and return structured results.
    """
    thresholds = thresholds or {}

    stale_pr_hours = thresholds.get(
        "stale_pr_hours",
        thresholds.get(
            "aging_pr_hours",
            DEFAULT_STALE_PR_HOURS,
        ),
    )

    return {
        "aging_prs": detect_aging_prs(
            pull_requests,
            threshold_hours=stale_pr_hours,
            now=now,
        ),
        "review_queue_congestion": detect_review_queue_congestion(
            pull_requests,
            max_pending_prs=max_pending_prs,
        ),
    }
