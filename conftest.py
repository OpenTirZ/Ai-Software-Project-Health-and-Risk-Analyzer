"""
Root-level test configuration.

Sets environment variables required by Backend.database before any test
module imports trigger the database module's initialization logic.
"""

import os

# Provide a dummy MONGO_URI so that Backend.database does not raise
# EnvironmentError during test collection.  All database operations are
# mocked at the collection level in individual tests, so no real
# connection is established.
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/test_project_health")
os.environ.setdefault("MONGO_DATABASE", "test_project_health")
