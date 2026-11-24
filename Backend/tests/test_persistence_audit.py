"""
Unit & Integration Tests for Audit Logs Persistence Layer and Indexing.
-----------------------------------------------------------------------
Tests:
  1. Single append-only audit event logging with full schema validation
  2. Dictionary-based drop-in compatibility (create_audit_log)
  3. High-throughput bulk append (log_audit_events_batch)
  4. Querying and filtering (by resourceType, userId, action, status, timestamp range)
  5. Fetch by ID and count operations
  6. Immutability & validation error handling
  7. PyMongoError mapping to DatabaseError
  8. Index verification in ensure_indexes() (Compound & 90-day TTL index)
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId
from pymongo.errors import PyMongoError

# Mock MongoClient to isolate persistence testing from real networks
_mock_client = MagicMock()
_mock_client.admin.command.return_value = {"ok": 1}
_mock_db = MagicMock()
_mock_client.__getitem__.return_value = _mock_db

with patch("pymongo.MongoClient", return_value=_mock_client):
    from Backend.database import audit_logs_collection, ensure_indexes
    from Backend.persistence import DatabaseError
    from Backend.persistence_audit import (
        count_audit_logs,
        create_audit_log,
        get_audit_log_by_id,
        get_audit_logs,
        log_audit_event,
        log_audit_events_batch,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_audit_collection(monkeypatch):
    """Provide an in-memory mock collection for audit_logs_collection."""
    storage = []

    def fake_insert_one(doc):
        doc_copy = dict(doc)
        if "_id" not in doc_copy:
            doc_copy["_id"] = ObjectId()
        storage.append(doc_copy)
        mock_res = MagicMock()
        mock_res.inserted_id = doc_copy["_id"]
        return mock_res

    def fake_insert_many(docs, ordered=True):
        inserted_ids = []
        for d in docs:
            doc_copy = dict(d)
            if "_id" not in doc_copy:
                doc_copy["_id"] = ObjectId()
            storage.append(doc_copy)
            inserted_ids.append(doc_copy["_id"])
        mock_res = MagicMock()
        mock_res.inserted_ids = inserted_ids
        return mock_res

    def fake_find(filter_query=None):
        query = filter_query or {}
        results = []
        for item in storage:
            match = True
            for k, v in query.items():
                if k == "timestamp" and isinstance(v, dict):
                    ts = item.get("timestamp")
                    if "$gte" in v and ts < v["$gte"]:
                        match = False
                    if "$lte" in v and ts > v["$lte"]:
                        match = False
                elif item.get(k) != v:
                    match = False
                    break
            if match:
                results.append(item)

        class FakeCursor:
            def __init__(self, data):
                self._data = list(data)

            def sort(self, key, direction=-1):
                reverse = direction == -1
                self._data.sort(key=lambda x: x.get(key) or datetime.min.replace(tzinfo=timezone.utc), reverse=reverse)
                return self

            def skip(self, count):
                self._data = self._data[count:]
                return self

            def limit(self, count):
                self._data = self._data[:count]
                return self

            def __iter__(self):
                return iter(self._data)

        return FakeCursor(results)

    def fake_find_one(filter_query):
        cursor = fake_find(filter_query)
        for item in cursor:
            return item
        return None

    def fake_count_documents(filter_query=None):
        cursor = fake_find(filter_query)
        return len(list(cursor))

    mock_col = MagicMock()
    mock_col.insert_one.side_effect = fake_insert_one
    mock_col.insert_many.side_effect = fake_insert_many
    mock_col.find.side_effect = fake_find
    mock_col.find_one.side_effect = fake_find_one
    mock_col.count_documents.side_effect = fake_count_documents
    mock_col.storage = storage

    monkeypatch.setattr("Backend.persistence_audit.audit_logs_collection", mock_col)
    return mock_col


# ---------------------------------------------------------------------------
# Tests: Append-Only Logging
# ---------------------------------------------------------------------------

class TestAuditAppendOnlyWrites:
    def test_log_audit_event_full_schema(self, mock_audit_collection):
        """Verify all schema fields are persisted cleanly."""
        fixed_time = datetime(2026, 11, 23, 10, 30, 0, tzinfo=timezone.utc)
        log_id = log_audit_event(
            action="role_change",
            resource_type="user",
            user_id="user_admin_01",
            user_role="admin",
            resource_id="user_dev_02",
            status="SUCCESS",
            details={"previous_role": "developer", "new_role": "admin"},
            ip_address="192.168.1.100",
            timestamp=fixed_time,
        )

        assert log_id is not None
        assert len(mock_audit_collection.storage) == 1
        stored = mock_audit_collection.storage[0]

        assert stored["_id"] == ObjectId(log_id)
        assert stored["userId"] == "user_admin_01"
        assert stored["userRole"] == "admin"
        assert stored["action"] == "role_change"
        assert stored["resourceType"] == "user"
        assert stored["resourceId"] == "user_dev_02"
        assert stored["status"] == "SUCCESS"
        assert stored["details"] == {"previous_role": "developer", "new_role": "admin"}
        assert stored["ipAddress"] == "192.168.1.100"
        assert stored["timestamp"] == fixed_time

    def test_log_audit_event_defaults(self, mock_audit_collection):
        """Verify defaults for optional fields (status, timestamp, details)."""
        before = datetime.now(timezone.utc)
        log_id = log_audit_event(
            action="project_created",
            resource_type="project",
            resource_id="proj_101",
        )
        after = datetime.now(timezone.utc)

        stored = mock_audit_collection.storage[0]
        assert stored["status"] == "SUCCESS"
        assert stored["userId"] is None
        assert stored["userRole"] is None
        assert stored["ipAddress"] is None
        assert stored["details"] == {}
        assert before <= stored["timestamp"] <= after

    def test_create_audit_log_dict_compatibility(self, mock_audit_collection):
        """Verify create_audit_log supports dict with snake_case and camelCase."""
        log_id_1 = create_audit_log({
            "action": "login",
            "resource_type": "auth",
            "user_id": "u123",
            "user_role": "developer",
            "ip_address": "10.0.0.1",
            "status": "SUCCESS",
            "details": "User session established",
        })

        log_id_2 = create_audit_log({
            "action": "sync_commits",
            "resourceType": "repository",
            "userId": "u123",
            "userRole": "developer",
            "resourceId": "repo_456",
            "status": "SUCCESS",
            "details": {"commits_fetched": 42},
        })

        assert log_id_1 is not None
        assert log_id_2 is not None
        assert len(mock_audit_collection.storage) == 2
        assert mock_audit_collection.storage[0]["resourceType"] == "auth"
        assert mock_audit_collection.storage[1]["resourceType"] == "repository"

    def test_log_audit_events_batch(self, mock_audit_collection):
        """Verify high-throughput bulk append with insert_many."""
        events = [
            {
                "action": f"metric_evaluated_{i}",
                "resource_type": "project",
                "resource_id": f"proj_{i}",
                "status": "SUCCESS",
                "details": {"score": 80 + i},
            }
            for i in range(5)
        ]

        ids = log_audit_events_batch(events)
        assert len(ids) == 5
        assert len(mock_audit_collection.storage) == 5

    def test_log_audit_events_batch_empty(self, mock_audit_collection):
        """Verify empty batch returns empty list immediately."""
        ids = log_audit_events_batch([])
        assert ids == []
        assert len(mock_audit_collection.storage) == 0

    def test_validation_errors(self, mock_audit_collection):
        """Verify ValueError is raised if action or resourceType are empty."""
        with pytest.raises(ValueError, match="action"):
            log_audit_event(action="", resource_type="project")

        with pytest.raises(ValueError, match="resourceType"):
            log_audit_event(action="login", resource_type="")


# ---------------------------------------------------------------------------
# Tests: Querying & Indexed Reads
# ---------------------------------------------------------------------------

class TestAuditQueries:
    def test_get_audit_logs_and_filtering(self, mock_audit_collection):
        """Verify get_audit_logs filters by resourceType, action, and user."""
        t1 = datetime(2026, 11, 23, 8, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 11, 23, 9, 0, 0, tzinfo=timezone.utc)
        t3 = datetime(2026, 11, 23, 10, 0, 0, tzinfo=timezone.utc)

        log_audit_event(action="login", resource_type="user", user_id="u1", timestamp=t1)
        log_audit_event(action="create_project", resource_type="project", user_id="u1", timestamp=t2)
        log_audit_event(action="role_change", resource_type="user", user_id="u2", timestamp=t3)

        # Filter by resource_type
        user_logs = get_audit_logs(resource_type="user")
        assert len(user_logs) == 2
        # Check newest-first sorting
        assert user_logs[0]["action"] == "role_change"
        assert user_logs[1]["action"] == "login"

        # Filter by user_id
        u1_logs = get_audit_logs(user_id="u1")
        assert len(u1_logs) == 2

        # Filter by action
        role_logs = get_audit_logs(action="role_change")
        assert len(role_logs) == 1
        assert role_logs[0]["userId"] == "u2"

    def test_get_audit_logs_time_range(self, mock_audit_collection):
        """Verify time range filtering."""
        t1 = datetime(2026, 11, 23, 8, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 11, 23, 9, 0, 0, tzinfo=timezone.utc)
        t3 = datetime(2026, 11, 23, 10, 0, 0, tzinfo=timezone.utc)

        log_audit_event(action="a1", resource_type="sys", timestamp=t1)
        log_audit_event(action="a2", resource_type="sys", timestamp=t2)
        log_audit_event(action="a3", resource_type="sys", timestamp=t3)

        mid_logs = get_audit_logs(
            start_time=datetime(2026, 11, 23, 8, 30, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 11, 23, 9, 30, 0, tzinfo=timezone.utc),
        )
        assert len(mid_logs) == 1
        assert mid_logs[0]["action"] == "a2"

    def test_get_audit_log_by_id(self, mock_audit_collection):
        """Verify fetch by ID and non-existent ID handling."""
        log_id = log_audit_event(action="audit_test", resource_type="test")
        doc = get_audit_log_by_id(log_id)
        assert doc is not None
        assert doc["_id"] == log_id
        assert doc["action"] == "audit_test"

        # Non-existent valid ObjectId
        missing = get_audit_log_by_id(str(ObjectId()))
        assert missing is None

        # Invalid string
        invalid = get_audit_log_by_id("invalid-id-format")
        assert invalid is None

    def test_count_audit_logs(self, mock_audit_collection):
        """Verify count with and without filters."""
        log_audit_event(action="login", resource_type="user", status="SUCCESS")
        log_audit_event(action="login", resource_type="user", status="FAILURE")
        log_audit_event(action="sync", resource_type="repo", status="SUCCESS")

        assert count_audit_logs() == 3
        assert count_audit_logs(resource_type="user") == 2
        assert count_audit_logs(status="FAILURE") == 1
        assert count_audit_logs(action="sync") == 1


# ---------------------------------------------------------------------------
# Tests: Database Error Mapping
# ---------------------------------------------------------------------------

class TestAuditErrorHandling:
    def test_insert_raises_database_error(self, monkeypatch):
        mock_col = MagicMock()
        mock_col.insert_one.side_effect = PyMongoError("Connection refused")
        monkeypatch.setattr("Backend.persistence_audit.audit_logs_collection", mock_col)

        with pytest.raises(DatabaseError, match="Audit log write failed"):
            log_audit_event(action="test", resource_type="test")

    def test_query_raises_database_error(self, monkeypatch):
        mock_col = MagicMock()
        mock_col.find.side_effect = PyMongoError("Query timeout")
        monkeypatch.setattr("Backend.persistence_audit.audit_logs_collection", mock_col)

        with pytest.raises(DatabaseError, match="Failed to query audit logs"):
            get_audit_logs()

    def test_bulk_insert_raises_database_error(self, monkeypatch):
        mock_col = MagicMock()
        mock_col.insert_many.side_effect = PyMongoError("Bulk write failed")
        monkeypatch.setattr("Backend.persistence_audit.audit_logs_collection", mock_col)

        with pytest.raises(DatabaseError, match="Bulk audit log write failed"):
            log_audit_events_batch([{"action": "a", "resource_type": "r"}])


# ---------------------------------------------------------------------------
# Tests: Index Registration in ensure_indexes()
# ---------------------------------------------------------------------------

class TestAuditIndexRegistration:
    def test_audit_indexes_created(self, monkeypatch):
        """Verify compound index and 90-day TTL index are created."""
        created_indexes = []

        mock_audit = MagicMock()
        def fake_create_index(keys, **kwargs):
            created_indexes.append((keys, kwargs))
        mock_audit.create_index.side_effect = fake_create_index

        monkeypatch.setattr("Backend.database.audit_logs_collection", mock_audit)

        ensure_indexes()

        # Check compound index: (timestamp: -1, resourceType: 1)
        compound_found = any(
            keys == [("timestamp", -1), ("resourceType", 1)]
            for keys, _ in created_indexes
        )
        assert compound_found, "Compound index (timestamp: -1, resourceType: 1) was not created"

        # Check TTL index: (timestamp: 1) with 90 days = 7776000s
        ttl_found = any(
            keys == [("timestamp", 1)] and kwargs.get("expireAfterSeconds") == 90 * 24 * 60 * 60
            for keys, kwargs in created_indexes
        )
        assert ttl_found, "TTL index on timestamp with 90-day retention was not created"
