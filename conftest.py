"""
Root-level test configuration.

Sets environment variables required by Backend.database before any test
module imports trigger the database module's initialization logic.
Mocks MongoClient so tests run without a live MongoDB instance.
"""

import os
from unittest.mock import MagicMock, patch

# Provide a dummy MONGO_URI so that Backend.database does not raise
# EnvironmentError during test collection.  All database operations are
# mocked at the collection level in individual tests, so no real
# connection is established.
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/test_project_health")
os.environ.setdefault("MONGO_DATABASE", "test_project_health")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-ci-only-32ch!")

# ---------------------------------------------------------------------------
# Patch MongoClient at the module level so that importing Backend.database
# never attempts a real TCP connection (the ping that blocks without a
# live MongoDB).  Individual tests override collection-level attributes
# with their own mocks via monkeypatch / fixture.
# ---------------------------------------------------------------------------
_mock_client = MagicMock()
_mock_client.admin.command.return_value = {"ok": 1}  # Simulate successful ping
_mock_db = MagicMock()
_mock_client.__getitem__.return_value = _mock_db

_mongo_patcher = patch("pymongo.MongoClient", return_value=_mock_client)
_mongo_patcher.start()
