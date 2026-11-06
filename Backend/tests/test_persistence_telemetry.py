"""
Tests for telemetry persistence layer.

Fully offline test suite using mongomock to verify upsert idempotency,
index enforcement, query behavior, validation, race-condition retries,
and metric snapshots.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from bson import ObjectId
import mongomock
from pymongo.errors import DuplicateKeyError
import pytest

from Backend import persistence_telemetry


@pytest.fixture
def fake_db():
    """
    Provide an isolated, in-memory MongoDB instance with required telemetry indexes.
    """
    client = mongomock.MongoClient()
    db = client["test_telemetry"]

    # Declare the identical compound/unique indexes as database.py
    db["pull_requests"].create_index(
        [("projectId", 1), ("number", 1)],
        unique=True,
        name="uniq_project_number",
    )
    db["issues"].create_index(
        [("projectId", 1), ("number", 1)],
        unique=True,
        name="uniq_project_number",
    )
    db["milestones"].create_index(
        [("projectId", 1), ("milestone_id", 1)],
        unique=True,
        name="uniq_project_milestone",
    )
    db["metric_snapshots"].create_index(
        [("projectId", 1), ("calculatedAt", -1)],
        name="project_calculatedAt",
    )
    return db


# Parametrization configuration for PRs, Issues, and Milestones
ENTITY_CONFIGS = [
    (
        "pull_requests",
        "number",
        persistence_telemetry.upsert_pull_request,
        persistence_telemetry.get_project_prs,
    ),
    (
        "issues",
        "number",
        persistence_telemetry.upsert_issue,
        persistence_telemetry.get_project_issues,
    ),
    (
        "milestones",
        "milestone_id",
        persistence_telemetry.upsert_milestone,
        persistence_telemetry.get_project_milestones,
    ),
]


# ---------------------------------------------------------------------------
# 1. First upsert inserts: created=True, createdAt and updatedAt set
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("coll_name, key_name, upsert_fn, _", ENTITY_CONFIGS)
def test_first_upsert_creates_document(fake_db, coll_name, key_name, upsert_fn, _):
    project_id = str(ObjectId())
    payload = {key_name: 101, "title": "Initial Title", "state": "open"}

    result = upsert_fn(project_id, payload, db=fake_db)

    assert result["created"] is True
    assert result["modified"] is False
    assert result["projectId"] == project_id
    assert result[key_name] == 101

    collection = fake_db[coll_name]
    doc = collection.find_one({key_name: 101})
    assert doc is not None
    assert doc["title"] == "Initial Title"
    assert doc["state"] == "open"
    assert isinstance(doc["createdAt"], datetime)
    assert isinstance(doc["updatedAt"], datetime)


# ---------------------------------------------------------------------------
# 2. Second upsert updates in place: count stays 1, createdAt unchanged
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("coll_name, key_name, upsert_fn, _", ENTITY_CONFIGS)
def test_second_upsert_updates_in_place(fake_db, coll_name, key_name, upsert_fn, _):
    project_id = str(ObjectId())
    payload_1 = {key_name: 202, "title": "Version 1", "state": "open"}

    upsert_fn(project_id, payload_1, db=fake_db)
    collection = fake_db[coll_name]
    doc_before = collection.find_one({key_name: 202})
    created_at_before = doc_before["createdAt"]
    updated_at_before = doc_before["updatedAt"]

    payload_2 = {key_name: 202, "title": "Version 2", "state": "closed"}
    result_2 = upsert_fn(project_id, payload_2, db=fake_db)

    assert result_2["created"] is False
    assert result_2["modified"] is True

    assert collection.count_documents({key_name: 202}) == 1
    doc_after = collection.find_one({key_name: 202})
    assert doc_after["title"] == "Version 2"
    assert doc_after["state"] == "closed"
    assert doc_after["createdAt"] == created_at_before
    assert doc_after["updatedAt"] >= updated_at_before


# ---------------------------------------------------------------------------
# 3. Same number/milestone_id under different projectId creates separate doc
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("coll_name, key_name, upsert_fn, _", ENTITY_CONFIGS)
def test_different_projects_isolate_documents(fake_db, coll_name, key_name, upsert_fn, _):
    project_a = str(ObjectId())
    project_b = str(ObjectId())
    key_val = 303

    upsert_fn(project_a, {key_name: key_val, "title": "Project A Doc"}, db=fake_db)
    upsert_fn(project_b, {key_name: key_val, "title": "Project B Doc"}, db=fake_db)

    collection = fake_db[coll_name]
    assert collection.count_documents({key_name: key_val}) == 2
    assert collection.count_documents({"projectId": ObjectId(project_a), key_name: key_val}) == 1
    assert collection.count_documents({"projectId": ObjectId(project_b), key_name: key_val}) == 1


# ---------------------------------------------------------------------------
# 4. Unique index enforcement: raw duplicate insert raises DuplicateKeyError
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("coll_name, key_name, _, __", ENTITY_CONFIGS)
def test_unique_index_enforces_no_duplicate_inserts(fake_db, coll_name, key_name, _, __):
    norm_project_id = ObjectId()
    collection = fake_db[coll_name]

    collection.insert_one({"projectId": norm_project_id, key_name: 404})
    with pytest.raises(DuplicateKeyError):
        collection.insert_one({"projectId": norm_project_id, key_name: 404})


# ---------------------------------------------------------------------------
# 5. get_* filtering, stable sort, limit/skip, _id exclusion, unknown project
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("_, key_name, upsert_fn, get_fn", ENTITY_CONFIGS)
def test_get_entities_queries_correctly(fake_db, _, key_name, upsert_fn, get_fn):
    project_id = str(ObjectId())
    other_project_id = str(ObjectId())

    # Insert documents with keys 10, 20, 30, 40, 50
    for k, st in [(10, "open"), (20, "closed"), (30, "open"), (40, "closed"), (50, "open")]:
        upsert_fn(project_id, {key_name: k, "state": st, "tag": f"doc_{k}"}, db=fake_db)

    # Insert document for another project
    upsert_fn(other_project_id, {key_name: 999, "state": "open"}, db=fake_db)

    # 5a: Returns only that project's documents, newest/highest key first (DESC)
    all_docs = get_fn(project_id, db=fake_db)
    assert len(all_docs) == 5
    assert [d[key_name] for d in all_docs] == [50, 40, 30, 20, 10]
    for d in all_docs:
        assert "_id" not in d

    # 5b: State filter works
    open_docs = get_fn(project_id, state="open", db=fake_db)
    assert len(open_docs) == 3
    assert [d[key_name] for d in open_docs] == [50, 30, 10]

    closed_docs = get_fn(project_id, state="closed", db=fake_db)
    assert len(closed_docs) == 2
    assert [d[key_name] for d in closed_docs] == [40, 20]

    # 5c: Limit and skip pagination
    paginated = get_fn(project_id, limit=2, skip=1, db=fake_db)
    assert len(paginated) == 2
    assert [d[key_name] for d in paginated] == [40, 30]

    # 5d: Unknown project returns empty list []
    unknown_pid = str(ObjectId())
    assert get_fn(unknown_pid, db=fake_db) == []


# ---------------------------------------------------------------------------
# 6. Validation: missing/empty/bool projectId, missing/bool/non-int key -> ValueError
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("_, key_name, upsert_fn, get_fn", ENTITY_CONFIGS)
def test_validation_errors(fake_db, _, key_name, upsert_fn, get_fn):
    valid_pid = str(ObjectId())

    # Missing / None projectId
    with pytest.raises(ValueError):
        upsert_fn(None, {key_name: 1}, db=fake_db)
    with pytest.raises(ValueError):
        get_fn(None, db=fake_db)

    # Empty string projectId
    with pytest.raises(ValueError):
        upsert_fn("", {key_name: 1}, db=fake_db)
    with pytest.raises(ValueError):
        get_fn("", db=fake_db)

    # Whitespace projectId
    with pytest.raises(ValueError):
        upsert_fn("   ", {key_name: 1}, db=fake_db)
    with pytest.raises(ValueError):
        get_fn("   ", db=fake_db)

    # Boolean projectId
    with pytest.raises(ValueError):
        upsert_fn(True, {key_name: 1}, db=fake_db)
    with pytest.raises(ValueError):
        get_fn(False, db=fake_db)

    # Invalid type projectId (e.g., int)
    with pytest.raises(ValueError):
        upsert_fn(12345, {key_name: 1}, db=fake_db)

    # Missing key in dict
    with pytest.raises(ValueError):
        upsert_fn(valid_pid, {"title": "Missing key"}, db=fake_db)

    # None key in dict
    with pytest.raises(ValueError):
        upsert_fn(valid_pid, {key_name: None}, db=fake_db)

    # Boolean key in dict (reject bool)
    with pytest.raises(ValueError):
        upsert_fn(valid_pid, {key_name: True}, db=fake_db)
    with pytest.raises(ValueError):
        upsert_fn(valid_pid, {key_name: False}, db=fake_db)

    # Non-integer key in dict
    with pytest.raises(ValueError):
        upsert_fn(valid_pid, {key_name: "123"}, db=fake_db)
    with pytest.raises(ValueError):
        upsert_fn(valid_pid, {key_name: 3.14}, db=fake_db)


# ---------------------------------------------------------------------------
# 7. Input dict is not mutated; an _id in the input is ignored
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("coll_name, key_name, upsert_fn, _", ENTITY_CONFIGS)
def test_input_immutability_and_id_ignored(fake_db, coll_name, key_name, upsert_fn, _):
    project_id = str(ObjectId())
    user_id = ObjectId()
    input_dict = {
        "_id": user_id,
        key_name: 505,
        "title": "Immutability Test",
        "nested": {"a": 1},
    }
    input_copy = dict(input_dict)

    result = upsert_fn(project_id, input_dict, db=fake_db)
    assert result["created"] is True

    # Caller's dict was NOT modified
    assert input_dict == input_copy
    assert "_id" in input_dict
    assert input_dict["_id"] == user_id

    # The doc stored in Mongo has a different _id or does not conflict
    stored = fake_db[coll_name].find_one({key_name: 505})
    assert stored is not None
    assert stored["title"] == "Immutability Test"


# ---------------------------------------------------------------------------
# 8. Race handling: DuplicateKeyError on first attempt, then succeeds on retry
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("coll_name, key_name, upsert_fn, _", ENTITY_CONFIGS)
def test_upsert_retry_on_duplicate_key_error(fake_db, coll_name, key_name, upsert_fn, _):
    project_id = str(ObjectId())
    payload = {key_name: 606, "title": "Race Test"}
    collection = fake_db[coll_name]
    real_update_one = collection.update_one

    first_attempt = True

    def flaky_update_one(*args, **kwargs):
        nonlocal first_attempt
        if first_attempt:
            first_attempt = False
            raise DuplicateKeyError("E11000 duplicate key error collection")
        return real_update_one(*args, **kwargs)

    collection.update_one = flaky_update_one

    # The upsert should catch the DuplicateKeyError, retry, and succeed
    result = upsert_fn(project_id, payload, db=fake_db)
    assert result[key_name] == 606
    assert first_attempt is False


# ---------------------------------------------------------------------------
# 9. Metric snapshots: newest-first ordering, limit, exclusion of _id
# ---------------------------------------------------------------------------
def test_metric_snapshots_crud_and_ordering(fake_db):
    project_id = str(ObjectId())
    other_pid = str(ObjectId())

    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Insert 3 snapshots for project_id with different calculatedAt
    s1 = {"calculatedAt": base_time, "healthScore": 75}
    s2 = {"calculatedAt": base_time + timedelta(hours=1), "healthScore": 80}
    s3 = {"calculatedAt": base_time + timedelta(hours=2), "healthScore": 90}

    r1 = persistence_telemetry.insert_metric_snapshot(project_id, s1, db=fake_db)
    r2 = persistence_telemetry.insert_metric_snapshot(project_id, s2, db=fake_db)
    r3 = persistence_telemetry.insert_metric_snapshot(project_id, s3, db=fake_db)

    assert r1["inserted"] is True
    assert r2["inserted"] is True
    assert r3["inserted"] is True

    # Snapshot for other project
    persistence_telemetry.insert_metric_snapshot(other_pid, {"healthScore": 50}, db=fake_db)

    # Query with default limit: newest first
    snapshots = persistence_telemetry.get_project_metric_snapshots(project_id, db=fake_db)
    assert len(snapshots) == 3
    assert snapshots[0]["healthScore"] == 90
    assert snapshots[1]["healthScore"] == 80
    assert snapshots[2]["healthScore"] == 75

    for s in snapshots:
        assert "_id" not in s

    # Query with limit
    limited = persistence_telemetry.get_project_metric_snapshots(project_id, limit=2, db=fake_db)
    assert len(limited) == 2
    assert [s["healthScore"] for s in limited] == [90, 80]

    # Input immutability
    user_snap = {"_id": ObjectId(), "healthScore": 88}
    snap_copy = dict(user_snap)
    persistence_telemetry.insert_metric_snapshot(project_id, user_snap, db=fake_db)
    assert user_snap == snap_copy

    # Validation
    with pytest.raises(ValueError):
        persistence_telemetry.insert_metric_snapshot(None, {"healthScore": 90}, db=fake_db)
    with pytest.raises(ValueError):
        persistence_telemetry.get_project_metric_snapshots("", db=fake_db)


# ---------------------------------------------------------------------------
# 10. ensure_indexes() declares all 4 new indexes on fake db
# ---------------------------------------------------------------------------
def test_ensure_indexes_declares_telemetry_indexes():
    fake_client = mongomock.MongoClient()
    test_db = fake_client["test_project_health"]

    # We patch the database module collections to run ensure_indexes against test_db
    with patch("pymongo.MongoClient", MagicMock()):
        import Backend.database as db_mod

    with patch.object(db_mod, "pull_requests_collection", test_db["pull_requests"]), \
         patch.object(db_mod, "issues_collection", test_db["issues"]), \
         patch.object(db_mod, "contributors_collection", test_db["contributors"]), \
         patch.object(db_mod, "commits_collection", test_db["commits"]), \
         patch.object(db_mod, "projects_collection", test_db["projects"]), \
         patch.object(db_mod, "db", test_db):
        db_mod.ensure_indexes()

    pr_indexes = test_db["pull_requests"].index_information()
    issues_indexes = test_db["issues"].index_information()
    milestones_indexes = test_db["milestones"].index_information()
    snapshots_indexes = test_db["metric_snapshots"].index_information()

    assert "uniq_project_number" in pr_indexes
    assert pr_indexes["uniq_project_number"]["unique"] is True
    assert pr_indexes["uniq_project_number"]["key"] == [("projectId", 1), ("number", 1)]

    assert "uniq_project_number" in issues_indexes
    assert issues_indexes["uniq_project_number"]["unique"] is True
    assert issues_indexes["uniq_project_number"]["key"] == [("projectId", 1), ("number", 1)]

    assert "uniq_project_milestone" in milestones_indexes
    assert milestones_indexes["uniq_project_milestone"]["unique"] is True
    assert milestones_indexes["uniq_project_milestone"]["key"] == [("projectId", 1), ("milestone_id", 1)]

    assert "project_calculatedAt" in snapshots_indexes
    assert snapshots_indexes["project_calculatedAt"]["key"] == [("projectId", 1), ("calculatedAt", -1)]
