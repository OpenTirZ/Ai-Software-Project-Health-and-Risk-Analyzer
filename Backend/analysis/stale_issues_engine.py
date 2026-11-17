
from datetime import datetime, timezone
import re


DEFAULT_STALE_AFTER_DAYS = 14
DEFAULT_EXCLUDED_LABELS = ("on-hold", "deferred")


def parse_datetime(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None

    if not isinstance(value, datetime) or value.tzinfo is None:
        return None

    try:
        return value.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def format_datetime(value):
    return value.astimezone(timezone.utc).isoformat()


def get_label_name(label):
    if isinstance(label, str):
        return label.strip().lower()

    if isinstance(label, dict):
        name = label.get("name")
        if isinstance(name, str):
            return name.strip().lower()

    return ""


def get_issue_number(issue):
    number = issue.get("number")

    if isinstance(number, bool):
        return None

    if isinstance(number, int) and number > 0:
        return number

    if isinstance(number, str) and number.strip().isdigit():
        number = int(number.strip())
        return number if number > 0 else None

    return None


def get_event_issue_numbers(event):
    numbers = set()

    number = event.get("issue_number")

    if isinstance(number, int) and not isinstance(number, bool):
        if number > 0:
            numbers.add(number)
    elif isinstance(number, str) and number.strip().isdigit():
        number = int(number.strip())
        if number > 0:
            numbers.add(number)

    issue_numbers = event.get("issue_numbers", [])

    if isinstance(issue_numbers, (list, tuple, set)):
        for number in issue_numbers:
            if isinstance(number, bool):
                continue

            if isinstance(number, int) and number > 0:
                numbers.add(number)
            elif isinstance(number, str) and number.strip().isdigit():
                number = int(number.strip())
                if number > 0:
                    numbers.add(number)

    message = event.get("message", "")

    if isinstance(message, str):
        for number in re.findall(r"#(\d+)", message):
            numbers.add(int(number))

    return numbers


def get_event_timestamp(event, fields):
    for field in fields:
        timestamp = parse_datetime(event.get(field))
        if timestamp is not None:
            return timestamp

    return None


def detect_stale_issues(
    issues,
    commits=None,
    comment_events=None,
    label_events=None,
    now=None,
    stale_after_days=DEFAULT_STALE_AFTER_DAYS,
    excluded_labels=DEFAULT_EXCLUDED_LABELS,
):
    if (
        isinstance(stale_after_days, bool)
        or not isinstance(stale_after_days, int)
        or stale_after_days <= 0
    ):
        raise ValueError("stale_after_days must be a positive integer")

    if now is None:
        now = datetime.now(timezone.utc)
    else:
        now = parse_datetime(now)
        if now is None:
            raise ValueError("Invalid now value")

    now = now.astimezone(timezone.utc)

    if not isinstance(issues, (list, tuple)):
        issues = []

    if not isinstance(commits, (list, tuple)):
        commits = []

    if not isinstance(comment_events, (list, tuple)):
        comment_events = []

    if not isinstance(label_events, (list, tuple)):
        label_events = []

    if excluded_labels is None:
        excluded_labels = DEFAULT_EXCLUDED_LABELS

    if isinstance(excluded_labels, str):
        excluded_labels = (excluded_labels,)

    try:
        excluded_labels = {
            label.strip().lower()
            for label in excluded_labels
            if isinstance(label, str) and label.strip()
        }
    except TypeError:
        raise ValueError("excluded_labels must be an iterable of strings")

    activity = {}

    def add_activity(issue_number, timestamp, source):
        if timestamp is None or timestamp > now:
            return

        activity.setdefault(issue_number, []).append({
            "timestamp": timestamp,
            "source": source,
            "is_proxy": False,
        })

    for event in comment_events:
        if not isinstance(event, dict):
            continue

        timestamp = get_event_timestamp(
            event, ("created_at", "timestamp", "submitted_at")
        )

        for number in get_event_issue_numbers(event):
            add_activity(number, timestamp, "comment_event")

    for event in label_events:
        if not isinstance(event, dict):
            continue

        timestamp = get_event_timestamp(
            event, ("created_at", "timestamp")
        )

        for number in get_event_issue_numbers(event):
            add_activity(number, timestamp, "label_event")

    for commit in commits:
        if not isinstance(commit, dict):
            continue

        timestamp = get_event_timestamp(
            commit, ("timestamp", "created_at", "committed_at")
        )

        for number in get_event_issue_numbers(commit):
            add_activity(number, timestamp, "associated_commit")

    stale_issues = []
    flags = []
    excluded_count = 0
    analyzed_count = 0
    proxy_count = 0
    missing_count = 0
    seen_numbers = set()

    for issue in issues:
        if not isinstance(issue, dict):
            continue

        if "pull_request" in issue or issue.get("is_pull_request") is True:
            continue

        state = issue.get("state")
        if not isinstance(state, str) or state.lower().strip() != "open":
            continue

        number = get_issue_number(issue)

        if number is None or number in seen_numbers:
            continue

        seen_numbers.add(number)
        analyzed_count += 1

        labels = issue.get("labels", [])

        if not isinstance(labels, (list, tuple, set)):
            labels = []

        current_labels = [
            name for name in (get_label_name(label) for label in labels)
            if name
        ]

        if excluded_labels.intersection(current_labels):
            excluded_count += 1
            continue

        created_at = parse_datetime(issue.get("created_at"))

        if created_at is not None and created_at > now:
            created_at = None

        activities = []

        if created_at is not None:
            activities.append({
                "timestamp": created_at,
                "source": "issue_created_at",
                "is_proxy": False,
            })

        issue_activity = activity.get(number, [])
        activities.extend(issue_activity)

        if not issue_activity:
            updated_at = parse_datetime(issue.get("updated_at"))

            if updated_at is not None and updated_at <= now:
                activities.append({
                    "timestamp": updated_at,
                    "source": "issue_updated_at_proxy",
                    "is_proxy": True,
                })

        if not activities:
            missing_count += 1
            continue

        priority = {
            "issue_created_at": 0,
            "issue_updated_at_proxy": 1,
            "comment_event": 2,
            "label_event": 2,
            "associated_commit": 2,
        }

        latest = max(
            activities,
            key=lambda item: (
                item["timestamp"],
                priority.get(item["source"], 0),
            ),
        )

        last_activity = latest["timestamp"]
        inactive_seconds = (now - last_activity).total_seconds()
        inactive_days = round(inactive_seconds / 86400, 2)

        if latest["is_proxy"]:
            proxy_count += 1

        if inactive_seconds <= stale_after_days * 86400:
            continue

        title = issue.get("title")
        if not isinstance(title, str):
            title = ""

        url = issue.get("html_url")
        if not isinstance(url, str):
            url = None

        flag_id = f"flag_stale_issue_{number}"

        explanation = (
            f"Issue #{number} has had no known activity for "
            f"{inactive_days} days, exceeding the "
            f"{stale_after_days}-day threshold."
        )

        evidence = [
            {
                "timestamp": format_datetime(item["timestamp"]),
                "source": item["source"],
                "is_proxy": item["is_proxy"],
            }
            for item in sorted(
                activities, key=lambda item: item["timestamp"]
            )
        ]

        result = {
            "id": flag_id,
            "type": "stale_issue",
            "issue_number": number,
            "title": title,
            "inactivity_days": inactive_days,
            "last_activity_at": format_datetime(last_activity),
            "activity_source": latest["source"],
            "is_proxy": latest["is_proxy"],
            "threshold_days": stale_after_days,
            "labels": current_labels,
            "html_url": url,
            "explanation": explanation,
            "evidence": evidence,
        }

        stale_issues.append(result)
        flags.append(result.copy())

    return {
        "data_status": "available",
        "analyzed_at": format_datetime(now),
        "stale_after_days": stale_after_days,
        "stale_issues": stale_issues,
        "excluded_issues_count": excluded_count,
        "flags": flags,
        "summary": {
            "analyzed_issues_count": analyzed_count,
            "stale_issues_count": len(stale_issues),
            "excluded_issues_count": excluded_count,
            "has_stale_issues": bool(stale_issues),
        },
        "activity_data_quality": {
            "proxy_activity_count": proxy_count,
            "missing_activity_count": missing_count,
            "detailed_history_available": bool(activity),
            "limitations": [
                "Current labels do not provide historical label events.",
                "The comments field is a count, not timestamped comment history.",
                "Commits are associated only through explicit issue references.",
                "updated_at does not identify the exact type of activity.",
            ],
        },
        "messages": [
            "Only open GitHub issues are analyzed.",
            "Issues with excluded labels are skipped.",
            "An issue is stale only when inactivity is strictly greater than the configured threshold.",
            "Missing historical activity is not invented.",
        ],
    }
