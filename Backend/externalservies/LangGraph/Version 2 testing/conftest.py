"""Pytest configuration for the LangGraph V2 test folder.

1. Adds the LangGraph directory to sys.path so the standalone pipeline module
   (pipeline_v2.py) can be imported, mirroring `python pipeline_v2.py` usage.
2. Provides a dummy MONGO_URI and pre-imports the Backend persistence modules
   with a mocked MongoClient, so the persistence-bridge tests never open a
   real database connection no matter where pytest is invoked from.
"""

import os
import sys
from unittest.mock import MagicMock, patch

LANGGRAPH_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if LANGGRAPH_DIR not in sys.path:
    sys.path.insert(0, LANGGRAPH_DIR)

# Project root (two levels up from LangGraph/) so `Backend` is importable.
PROJECT_ROOT = os.path.dirname(os.path.dirname(LANGGRAPH_DIR))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/test_project_health")
os.environ.setdefault("MONGO_DATABASE", "test_project_health")

# Import Backend persistence modules once with a mocked MongoClient so the
# modules cached in sys.modules never hold a real connection.
if "Backend.database" not in sys.modules:
    _mock_client = MagicMock()
    _mock_client.admin.command.return_value = {"ok": 1}
    _mock_client.__getitem__.return_value = MagicMock()
    with patch("pymongo.MongoClient", return_value=_mock_client):
        import Backend.database  # noqa: F401
        import Backend.persistence  # noqa: F401
        import Backend.persistence_telemetry  # noqa: F401
        import Backend.persistence_reports  # noqa: F401
