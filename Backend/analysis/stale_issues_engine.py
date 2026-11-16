
from datetime import datetime, timezone

DEFAULT_STALE_ISSUE_DAYS = 14


def _parse_datetime(value):
    """Parse an ISO timestamp or datetime and return an aware UTC datetime."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    if not isinstance(value, datetime):
        return None

    if value.tzinfo is None:
        return None

    return value.astimezone(timezone.utc)


def _label_name(label):
    """Get a normalized label name from a string or GitHub label object."""
    if isinstance(label, str):
        return label.strip().lower()

    if isinstance(label, dict):
        name = label.get("name")
        if isinstance(name, str):
            return name.strip().lower()

    return ""


def detect_stale_issues(
    issues,
    threshold_days=DEFAULT_STALE_ISSUE_DAYS,
    now=None,
):
    """
    Detect open issues that have not been updated for more than threshold_days.

    GitHub's updated_at timestamp is used as a general inactivity proxy.
    The current data source does not separately track comment, commit, and
    label-update timestamps, so those activity types cannot be verified
    independently.
    """
    if (
        isinstance(threshold_days, bool)
        or not isinstance(threshold_days, (int, float))
        or threshold_days <= 0
    ):
        raise ValueError("threshold_days must be a positive number")

    if now is None:
        now = datetime.now(timezone.utc)

    now = _parse_datetime(now)
    if now is None:
        raise ValueError("now must be a timezone-aware datetime")

    if not issues:
        return {"stale_issues": []}

    stale_issues = []

    for issue in issues:
        if not isinstance(issue, dict):
            continue

        if issue.get("state", "open") != "open":
            continue

        labels = issue.get("labels") or []
        label_names = {_label_name(label) for label in labels}

        if {"on-hold", "deferred"} & label_names:
            continue

        updated_at = _parse_datetime(issue.get("updated_at"))
        if updated_at is None:
            continue

        inactive_days = (now - updated_at).total_seconds() / 86400

        if inactive_days < 0 or inactive_days <= threshold_days:
            continue

        issue_number = issue.get("number")
        title = issue.get("title", "")

        stale_issues.append({
            "type": "stale_issue",
            "issue_number": issue_number,
            "title": title,
            "inactive_days": round(inactive_days, 2),
            "threshold_days": threshold_days,
            "updated_at": updated_at.isoformat(),
            "activity_timestamp": updated_at.isoformat(),
            "activity_source": "updated_at",
            "activity_tracking_limitation": (
                "updated_at is used as a general inactivity proxy; "
                "comment, commit, and label-update timestamps are not "
                "tracked separately by the current data source."
            ),
            "html_url": issue.get("html_url"),
            "reason": (
                f"Issue #{issue_number} has not been updated for "
                f"{round(inactive_days, 2)} days."
            ),
        })

    return {"stale_issues": stale_issues}
