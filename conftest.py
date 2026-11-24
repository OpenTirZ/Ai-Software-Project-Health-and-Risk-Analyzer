"""
Root-level test configuration.

Sets environment variables required by Backend.database before any test
module imports trigger the database module's initialization logic.
Mocks MongoClient so tests run without a live MongoDB instance.
Stubs optional heavy dependencies (e.g. xhtml2pdf) that may not be
installed in CI / sandbox environments.
"""

import sys
import os
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub xhtml2pdf only when it is genuinely not installed.  A real import is
# attempted first; the MagicMock fallback is installed only on ImportError so
# that an installed package is never silently replaced.  Any other import
# error (e.g. a missing transitive dependency inside xhtml2pdf itself) is
# intentionally re-raised so it is not hidden.
# ---------------------------------------------------------------------------
try:
    import xhtml2pdf.pisa  # noqa: F401 — real package available, nothing to stub
except ModuleNotFoundError as exc:
    # Re-raise if the missing module is a transitive dependency inside xhtml2pdf,
    # not xhtml2pdf itself — that failure should not be hidden.
    if exc.name not in {"xhtml2pdf", "xhtml2pdf.pisa"}:
        raise
    # xhtml2pdf is not installed; register lightweight stubs so modules that
    # import it at the top level (e.g. pdf_generator) can be collected.
    import unittest.mock as _mock
    sys.modules.setdefault("xhtml2pdf", _mock.MagicMock())
    sys.modules.setdefault("xhtml2pdf.pisa", _mock.MagicMock())

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
_mock_users_collection = MagicMock()
_mock_users_collection.list_indexes.return_value = [
    {"name": "_id_", "key": {"_id": 1}},
    {"name": "uniq_users_email_normalized", "key": {"email_normalized": 1}, "unique": True},
]
_collections = {"users": _mock_users_collection}
_mock_db.__getitem__.side_effect = lambda coll_name: _collections.setdefault(coll_name, MagicMock())
_mock_client.__getitem__.return_value = _mock_db

_mongo_patcher = patch("pymongo.MongoClient", return_value=_mock_client)
_mongo_patcher.start()
