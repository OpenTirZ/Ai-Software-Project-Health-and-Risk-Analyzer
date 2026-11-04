import os
import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, ConfigurationError
import certifi
from dotenv import load_dotenv

# Load environment variables from .env file (project root, one level above Backend/)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection configuration — driven by environment variables
# ---------------------------------------------------------------------------

MONGO_URI = os.environ.get("MONGO_URI")
if not MONGO_URI:
    raise EnvironmentError(
        "MONGO_URI environment variable is required. "
        "Set it in your .env file: MONGO_URI=mongodb+srv://..."
    )

MONGO_DATABASE = os.environ.get("MONGO_DATABASE", "project_health")

# Only enable TLS when using a MongoDB Atlas SRV URI (mongodb+srv://).
# Plain mongodb:// URIs (local instances) don't support TLS by default and
# will fail with an SSL handshake error if tls=True is forced.
_use_tls = MONGO_URI.startswith("mongodb+srv://")

try:
    client = MongoClient(
        MONGO_URI,
        tls=_use_tls,
        tlsCAFile=certifi.where() if _use_tls else None,
        serverSelectionTimeoutMS=10000,
    )
    # Trigger a lightweight command to validate connectivity at startup.
    client.admin.command("ping")
    logger.info("MongoDB connection established successfully.")
except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
    raise EnvironmentError(
        "Cannot reach MongoDB. Check that MONGO_URI is correct and the "
        "database server is reachable."
    ) from exc
except ConfigurationError as exc:
    raise EnvironmentError(
        f"MongoDB configuration error: {exc}"
    ) from exc

db = client[MONGO_DATABASE]

# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------

users_collection = db["users"]
projects_collection = db["projects"]
commits_collection = db["commits"]
pull_requests_collection = db["pull_requests"]
issues_collection = db["issues"]
sprints_collection = db["sprints"]
flags_collection = db["flags"]
reports_collection = db["reports"]
integration_credentials_collection = db["integration_credentials"]
org_settings_collection = db["org_settings"]
audit_logs_collection = db["audit_logs"]
contributors_collection = db["contributors"]
milestones_collection = db["milestones"]
metric_snapshots_collection = db["metric_snapshots"]


# ---------------------------------------------------------------------------
# Index management
# ---------------------------------------------------------------------------

def ensure_indexes():
    """
    Create required database indexes.
    Call once at application startup (e.g. in FastAPI lifespan).

    Contributors: unique compound index on (projectId, github_username)
    to prevent duplicate contributors within the same project while
    allowing the same GitHub user across different projects.

    Commits: unique compound index on (projectId, sha)
    Pull Requests: unique compound index on (projectId, number) [UNIQUE]
    Issues: unique compound index on (projectId, number) [UNIQUE]
    Milestones: unique compound index on (projectId, milestone_id) [UNIQUE]
    Metric Snapshots: compound index on (projectId, calculatedAt)
    to prevent duplicate commits within the same project.
    """
    try:
        contributors_collection.create_index(
            [("projectId", 1), ("github_username", 1)],
            unique=True,
            background=True,
        )
        pull_requests_collection.create_index(
            [("projectId", 1), ("number", 1)],
            unique=True,
            background=True,
        )
        issues_collection.create_index(
            [("projectId", 1), ("number", 1)],
            unique=True,
            background=True,
        )
        milestones_collection.create_index(
            [("projectId", 1), ("milestone_id", 1)],
            unique=True,
            background=True,
        )
        metric_snapshots_collection.create_index(
            [("projectId", 1), ("calculatedAt", 1)],
            background=True,
        )
        commits_collection.create_index(
            [("projectId", 1), ("sha", 1)],
            unique=True,
            background=True,
        )
        projects_collection.create_index(
            [("ownerId", 1)],
            background=True,
        )
        projects_collection.create_index(
            [("members.userId", 1)],
            background=True,
        )
        logger.info("Database indexes ensured.")
    except Exception as exc:  # pragma: no cover
        # Non-fatal: indexes may already exist or be created on the next startup.
        logger.warning("Could not ensure database indexes: %s", exc)
