import os
import logging
from pymongo import MongoClient
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

client = MongoClient(MONGO_URI)
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
    to prevent duplicate commits within the same project.
    """
    contributors_collection.create_index(
        [("projectId", 1), ("github_username", 1)],
        unique=True,
        background=True,
    )
    commits_collection.create_index(
        [("projectId", 1), ("sha", 1)],
        unique=True,
        background=True,
    )
    logger.info("Database indexes ensured.")
