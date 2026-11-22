"""
Seed Script: Realistic Demo Project Data for कVaच (AI Project Health & Risk Analyzer)
-------------------------------------------------------------------------------------
Usage:
    python -m Backend.seed_demo_data

Seeds a fully-populated realistic demo project into MongoDB with:
  - Realistic GitHub repository configuration
  - Commits history with realistic churn and velocity
  - Open & closed issues across bug, feature, and security categories
  - Pull requests with review cycle telemetry
  - Health & Risk score metrics snapshots
"""

import logging
from datetime import datetime, timedelta, timezone
from bson import ObjectId

from Backend.database import (
    commits_collection,
    issues_collection,
    metric_snapshots_collection,
    milestones_collection,
    projects_collection,
    pull_requests_collection,
    users_collection,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def seed_demo_project():
    now = datetime.now(timezone.utc)

    # 1. Ensure a demo user exists
    demo_user = users_collection.find_one({"email": "demo@kavach.ai"})
    if not demo_user:
        user_res = users_collection.insert_one({
            "name": "Demo Admin",
            "email": "demo@kavach.ai",
            "role": "admin",
            "password_hash": "$2b$12$eXampleHashedPasswordForDemoOnlySeed1234567890",
            "created_at": now - timedelta(days=90),
            "is_active": True,
        })
        user_id = user_res.inserted_id
        logger.info("Created demo user: %s", user_id)
    else:
        user_id = demo_user["_id"]

    # 2. Check or create demo project
    demo_project = projects_collection.find_one({"name": "कVaच Core Engine"})
    if not demo_project:
        project_doc = {
            "name": "कVaच Core Engine",
            "description": "AI-powered real-time software project risk detection and engineering health intelligence.",
            "repo_url": "https://github.com/OpenTirZ/Ai-Software-Project-Health-and-Risk-Analyzer",
            "repository": "OpenTirZ/Ai-Software-Project-Health-and-Risk-Analyzer",
            "status": "active",
            "is_active": True,
            "owner_id": user_id,
            "members": [
                {"userId": str(user_id), "role": "admin"},
            ],
            "risk_score": 38.5,
            "health_score": 82.0,
            "overall_status": "Healthy",
            "created_at": now - timedelta(days=60),
            "updated_at": now,
        }
        res = projects_collection.insert_one(project_doc)
        project_id = res.inserted_id
        logger.info("Created demo project: %s (_id: %s)", project_doc["name"], project_id)
    else:
        project_id = demo_project["_id"]
        logger.info("Using existing demo project: %s", project_id)

    # 3. Seed realistic commits
    sample_commits = [
        {"sha": "a1c7e92b3f", "message": "feat: integrate LangGraph risk scoring agent", "author": "Tirth Patel", "days_ago": 1},
        {"sha": "b2d8f03c4a", "message": "fix: RBAC permission check on data sync router", "author": "Shah Varshil", "days_ago": 2},
        {"sha": "c3e9a14d5b", "message": "style: redesign dashboard UI to Deep Teal and Crimson palette", "author": "Designer", "days_ago": 3},
        {"sha": "d4f0b25e6c", "message": "test: add 100+ comprehensive integration test suites", "author": "Shah Varshil", "days_ago": 5},
        {"sha": "e5a1c36f7d", "message": "chore: setup Docker production container & Render deployment", "author": "DevOps", "days_ago": 7},
    ]

    for c in sample_commits:
        commits_collection.update_one(
            {"projectId": project_id, "sha": c["sha"]},
            {"$set": {
                "projectId": project_id,
                "sha": c["sha"],
                "message": c["message"],
                "author": c["author"],
                "timestamp": now - timedelta(days=c["days_ago"]),
                "created_at": now - timedelta(days=c["days_ago"]),
            }},
            upsert=True,
        )

    # 4. Seed realistic issues
    sample_issues = [
        {"number": 101, "title": "Memory bottleneck during high-volume telemetry ingestion", "state": "closed", "author": "Tirth Patel", "days_ago": 15},
        {"number": 102, "title": "Refactor token storage to aegis_token across frontend API calls", "state": "closed", "author": "Shah Varshil", "days_ago": 4},
        {"number": 103, "title": "Implement multi-tenant RBAC admin controls for team invitations", "state": "open", "author": "Product Manager", "days_ago": 2},
        {"number": 104, "title": "Add automated PDF report scheduling worker with email dispatch", "state": "open", "author": "DevOps", "days_ago": 1},
    ]

    for iss in sample_issues:
        issues_collection.update_one(
            {"projectId": project_id, "number": iss["number"]},
            {"$set": {
                "projectId": project_id,
                "number": iss["number"],
                "title": iss["title"],
                "state": iss["state"],
                "author": iss["author"],
                "comments_count": 4,
                "created_at": now - timedelta(days=iss["days_ago"]),
                "updated_at": now,
            }},
            upsert=True,
        )

    # 5. Seed pull requests
    sample_prs = [
        {"number": 42, "title": "feat: Render deployment blueprint and GitHub Actions CI", "state": "merged", "author": "Shah Varshil", "additions": 450, "deletions": 30},
        {"number": 43, "title": "fix: persistence telemetry duplicate find_one query", "state": "merged", "author": "Shah Varshil", "additions": 18, "deletions": 6},
        {"number": 44, "title": "ui: incorporate कVaच branding and responsive palette", "state": "open", "author": "Frontend Team", "additions": 220, "deletions": 45},
    ]

    for pr in sample_prs:
        pull_requests_collection.update_one(
            {"projectId": project_id, "number": pr["number"]},
            {"$set": {
                "projectId": project_id,
                "number": pr["number"],
                "title": pr["title"],
                "state": pr["state"],
                "author": pr["author"],
                "additions": pr["additions"],
                "deletions": pr["deletions"],
                "created_at": now - timedelta(days=3),
                "updated_at": now,
            }},
            upsert=True,
        )

    # 6. Seed metric snapshots
    metric_snapshots_collection.update_one(
        {"projectId": project_id},
        {"$set": {
            "projectId": project_id,
            "calculatedAt": now,
            "riskScore": 38.5,
            "healthScore": 82.0,
            "velocity": 14.2,
            "codeChurn": 280,
            "burnoutRisk": "Low",
            "deliveryPredictability": "High",
            "bottlenecks": [
                {"name": "Code Review Turnaround", "severity": "Medium", "metric": "26.4h"},
            ],
        }},
        upsert=True,
    )

    logger.info("Demo data seeding completed successfully for project: %s", project_id)
    return str(project_id)


if __name__ == "__main__":
    seed_demo_project()
