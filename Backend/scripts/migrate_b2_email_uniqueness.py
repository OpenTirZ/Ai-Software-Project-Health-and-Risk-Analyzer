"""
Migration Script: B2 Email Uniqueness and Canonical Backfill.
=============================================================

Audits the users collection for:
  1. Missing or empty email addresses.
  2. Invalid email addresses violating Pydantic EmailStr validation.
  3. Duplicate canonical email groups (via normalize_email).
  4. Stale or inconsistent email_normalized fields.
  5. Backfill collision hazards against existing indexes.

Modes:
  --dry-run (default): Report-only mode. Does not modify database.
  --apply: Backfills email_normalized, creates the unique index, and verifies it.
           ABORTS immediately before writing if any duplicates or invalid records exist.

Usage:
  python -m Backend.scripts.migrate_b2_email_uniqueness --dry-run
  python -m Backend.scripts.migrate_b2_email_uniqueness --apply
"""

import argparse
import logging
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, EmailStr, ValidationError
from pymongo import UpdateOne
from pymongo.collection import Collection

from Backend.auth.normalization import canonicalize_email, normalize_email

logger = logging.getLogger("b2_migration")


def is_valid_email_str(raw_email: Any) -> bool:
    """Validate email using the strict canonicalize_email helper."""
    try:
        canonicalize_email(raw_email)
        return True
    except (ValueError, TypeError):
        return False


class AuditResult:
    def __init__(self):
        self.total_scanned: int = 0
        self.already_normalized_clean: int = 0
        self.missing_emails: List[Dict[str, Any]] = []
        self.invalid_emails: List[Dict[str, Any]] = []
        self.duplicate_groups: Dict[str, List[Dict[str, Any]]] = {}
        self.stale_fields: List[Tuple[Dict[str, Any], str]] = []  # (doc, expected_canonical)
        self.pending_backfill: List[Tuple[Dict[str, Any], str]] = []  # (doc, expected_canonical)
        self.collision_hazards: List[Dict[str, Any]] = []
        self.incompatible_indexes: List[Dict[str, Any]] = []

    @property
    def has_blocking_conflicts(self) -> bool:
        return bool(
            self.missing_emails
            or self.invalid_emails
            or self.duplicate_groups
            or self.collision_hazards
            or self.incompatible_indexes
        )


def audit_users_collection(collection: Collection) -> AuditResult:
    """
    Perform a complete non-destructive audit of all user documents and indexes.
    1. Inspects existing indexes for incompatible or conflicting definitions.
    2. Normalizes emails first (matching SignupRequest sequence), then validates via EmailStr.
    3. Detects canonical duplicate groups, stale fields, and backfill collision hazards.
    """
    result = AuditResult()
    canonical_to_docs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    existing_normalized_map: Dict[str, Any] = {}  # email_normalized -> doc_id

    # Preflight: inspect existing indexes using list_indexes()
    try:
        existing_indexes = list(collection.list_indexes())
    except Exception as exc:
        result.incompatible_indexes.append({
            "name": "N/A",
            "key": {},
            "reason": f"Failed to list collection indexes: {exc}",
        })
        existing_indexes = []

    for idx in existing_indexes:
        idx_name = idx.get("name", "")
        key_dict = dict(idx.get("key", {}))
        unique = idx.get("unique", False)

        # Check index named uniq_users_email_normalized
        if idx_name == "uniq_users_email_normalized":
            if key_dict != {"email_normalized": 1} or unique is not True:
                result.incompatible_indexes.append({
                    "name": idx_name,
                    "key": key_dict,
                    "unique": unique,
                    "reason": (
                        "Index 'uniq_users_email_normalized' exists but has incorrect key or unique flag. "
                        "Expected key {'email_normalized': 1} and unique=True."
                    ),
                })
            elif idx.get("sparse", False):
                result.incompatible_indexes.append({
                    "name": idx_name,
                    "key": key_dict,
                    "unique": unique,
                    "sparse": True,
                    "reason": (
                        "Index 'uniq_users_email_normalized' has sparse=True. "
                        "A sparse unique index does not enforce uniqueness on documents where "
                        "email_normalized is absent, violating the B2 uniqueness guarantee."
                    ),
                })
            elif "partialFilterExpression" in idx:
                result.incompatible_indexes.append({
                    "name": idx_name,
                    "key": key_dict,
                    "unique": unique,
                    "partialFilterExpression": idx["partialFilterExpression"],
                    "reason": (
                        "Index 'uniq_users_email_normalized' has a partialFilterExpression. "
                        "A partial unique index does not enforce uniqueness across all documents, "
                        "violating the B2 uniqueness guarantee."
                    ),
                })
        elif "email_normalized" in key_dict:
            # Different index involving email_normalized
            result.incompatible_indexes.append({
                "name": idx_name,
                "key": key_dict,
                "unique": unique,
                "reason": (
                    f"Conflicting index '{idx_name}' involves 'email_normalized'. "
                    "Expected single unique index named 'uniq_users_email_normalized'."
                ),
            })

    documents = list(collection.find())
    result.total_scanned = len(documents)

    # First pass: categorize individual documents
    for doc in documents:
        doc_id = doc.get("_id")
        raw_email = doc.get("email")
        existing_normalized = doc.get("email_normalized")

        if existing_normalized:
            existing_normalized_map[str(existing_normalized)] = str(doc_id)

        # 1. Missing or empty
        if raw_email is None or str(raw_email).strip() == "":
            result.missing_emails.append(doc)
            continue

        raw_email_str = str(raw_email)

        # 2. Canonicalize email using strict shared canonicalize_email helper
        try:
            canonical = canonicalize_email(raw_email_str)
        except ValueError:
            if not normalize_email(raw_email_str):
                result.missing_emails.append(doc)
            else:
                result.invalid_emails.append(doc)
            continue

        canonical_to_docs[canonical].append(doc)

        # 4. Check email_normalized state
        if existing_normalized is None:
            result.pending_backfill.append((doc, canonical))
        elif existing_normalized != canonical:
            result.stale_fields.append((doc, canonical))
        else:
            result.already_normalized_clean += 1

    # Second pass: group duplicates
    for canonical, docs in canonical_to_docs.items():
        if len(docs) > 1:
            result.duplicate_groups[canonical] = docs

    # Third pass: check collision hazards during backfill or stale updates
    planned_updates = result.pending_backfill + result.stale_fields
    for doc, canonical in planned_updates:
        target_holder_id = existing_normalized_map.get(canonical)
        if target_holder_id and target_holder_id != str(doc.get("_id")):
            result.collision_hazards.append({
                "source_doc_id": str(doc.get("_id")),
                "source_email": doc.get("email"),
                "target_canonical": canonical,
                "colliding_holder_id": target_holder_id,
            })

    return result


def print_audit_report(result: AuditResult) -> None:
    """Print human-readable audit diagnostics."""
    print("=" * 70)
    print("B2 DATABASE AUDIT REPORT: User Email Uniqueness")
    print("=" * 70)
    print(f"Total user records scanned:         {result.total_scanned}")
    print(f"Already correctly normalized:       {result.already_normalized_clean}")
    print(f"Pending backfill (missing field):   {len(result.pending_backfill)}")
    print(f"Stale/Inconsistent fields:          {len(result.stale_fields)}")
    print(f"Missing/empty email records:        {len(result.missing_emails)}")
    print(f"Invalid email format records:       {len(result.invalid_emails)}")
    print(f"Duplicate canonical email groups:   {len(result.duplicate_groups)}")
    print(f"Update collision hazards:           {len(result.collision_hazards)}")
    print(f"Incompatible / Conflicting indexes: {len(result.incompatible_indexes)}")
    print("-" * 70)

    if result.incompatible_indexes:
        print("\n[!] INCOMPATIBLE / CONFLICTING INDEXES DETECTED:")
        for idx in result.incompatible_indexes:
            print(f"    Index: {idx.get('name')} | key: {idx.get('key')} | unique: {idx.get('unique')} | reason: {idx.get('reason')}")
        print("    Operator Action: Inspect and resolve conflicting indexes manually in MongoDB before migration.")

    if result.missing_emails:
        print("\n[!] MISSING / EMPTY EMAIL RECORDS:")
        for doc in result.missing_emails:
            print(f"    _id: {doc.get('_id')} | name: {doc.get('name')!r}")

    if result.invalid_emails:
        print("\n[!] INVALID EMAIL RECORDS (Failed Pydantic EmailStr validation):")
        for doc in result.invalid_emails:
            print(f"    _id: {doc.get('_id')} | email: {doc.get('email')!r} | name: {doc.get('name')!r}")

    if result.duplicate_groups:
        print("\n[!] DUPLICATE CANONICAL EMAIL GROUPS (Uniqueness Violations):")
        for canonical, docs in result.duplicate_groups.items():
            print(f"    Canonical: {canonical}")
            for d in docs:
                print(f"      - _id: {d.get('_id')} | email: {d.get('email')!r} | created: {d.get('createdAt') or d.get('created_at')}")

    if result.collision_hazards:
        print("\n[!] BACKFILL UPDATE COLLISION HAZARDS:")
        for hazard in result.collision_hazards:
            print(f"    Doc {hazard['source_doc_id']} (email: {hazard['source_email']!r}) cannot update to '{hazard['target_canonical']}' because doc {hazard['colliding_holder_id']} already claims it.")

    print("=" * 70)


def run_migration(
    collection: Collection,
    apply: bool = False,
    verbose: bool = True,
) -> int:
    """
    Execute migration in dry-run or apply mode.
    Returns:
      0 on success (clean dry-run or successful apply).
      1 if dry-run detected blocking conflicts.
      2 if apply was aborted due to blocking conflicts.
      3 if apply failed during database write/index creation.
    """
    result = audit_users_collection(collection)

    if verbose:
        print_audit_report(result)

    if not apply:
        if result.has_blocking_conflicts:
            if verbose:
                print("\n[DRY RUN RESULT] Blocking conflicts detected. Manual operator resolution required.")
            return 1
        if verbose:
            print("\n[DRY RUN RESULT] Database is clean. Safe to proceed with --apply.")
        return 0

    # APPLY MODE
    if result.has_blocking_conflicts:
        print("\n[ERROR] Migration aborted! Refusing to modify database while conflicts exist.", file=sys.stderr)
        print("Operator Action Required:", file=sys.stderr)
        print("  1. Review the duplicate groups and invalid records listed above.", file=sys.stderr)
        print("  2. Manually archive, merge, or correct conflicting accounts in MongoDB.", file=sys.stderr)
        print("  3. Re-run with --dry-run until 0 conflicts are reported before applying.", file=sys.stderr)
        return 2

    # Perform backfill safely
    records_to_update = result.pending_backfill + result.stale_fields
    if records_to_update:
        if verbose:
            print(f"\n[APPLY] Backfilling email_normalized on {len(records_to_update)} records...")

        # Idempotent and recoverable updates: filter explicitly on _id and changed field
        bulk_ops = [
            UpdateOne(
                {"_id": doc["_id"], "email_normalized": {"$ne": canonical}},
                {"$set": {"email_normalized": canonical}},
            )
            for doc, canonical in records_to_update
        ]

        try:
            # Note: MongoDB bulk_write is not multi-document atomic across collections,
            # but is idempotent and safe to re-run if interrupted.
            write_result = collection.bulk_write(bulk_ops, ordered=False)
            if verbose:
                print(f"[APPLY] Modified {write_result.modified_count} user document(s).")
        except Exception as exc:
            print(f"\n[FATAL] Database write error during backfill: {exc}", file=sys.stderr)
            return 3
    else:
        if verbose:
            print("\n[APPLY] All user documents already have valid email_normalized fields. No backfill needed.")

    # Sole owner of unique index creation: create and verify index
    if verbose:
        print("[APPLY] Ensuring unique index 'uniq_users_email_normalized'...")

    try:
        collection.create_index(
            [("email_normalized", 1)],
            unique=True,
            name="uniq_users_email_normalized",
            background=False,
        )
    except Exception as exc:
        print(f"\n[FATAL] Failed to create unique index 'uniq_users_email_normalized': {exc}", file=sys.stderr)
        return 3

    # Verification via list_indexes
    indexes = list(collection.list_indexes())
    verified = False
    for idx in indexes:
        if (
            idx.get("name") == "uniq_users_email_normalized"
            and dict(idx.get("key", {})) == {"email_normalized": 1}
            and idx.get("unique") is True
            and not idx.get("sparse", False)
            and "partialFilterExpression" not in idx
        ):
            verified = True
            break

    if not verified:
        print("\n[FATAL] Index verification failed after creation!", file=sys.stderr)
        return 3

    if verbose:
        print("[APPLY] Unique index 'uniq_users_email_normalized' verified successfully.")
        print("[APPLY] Migration completed successfully.")

    return 0


def main(argv: Optional[List[str]] = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description="B2 Email Uniqueness Audit & Migration Tool",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Audit database and print report without making changes (default).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply backfill and create unique index. Aborts if conflicts exist.",
    )

    args = parser.parse_args(argv)
    apply_mode = bool(args.apply)

    from Backend.database import users_collection
    exit_code = run_migration(users_collection, apply=apply_mode, verbose=True)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
