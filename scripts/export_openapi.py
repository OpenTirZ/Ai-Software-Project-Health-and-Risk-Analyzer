#!/usr/bin/env python3
"""
OpenAPI Schema Exporter — AI Software Project Health & Risk Analyzer
--------------------------------------------------------------------
Exports the FastAPI application's OpenAPI 3.1.0 specification into
JSON and YAML files for documentation, testing, and client SDK generation.

Usage:
    python scripts/export_openapi.py
    python scripts/export_openapi.py --format json --output documents/openapi.json
    python scripts/export_openapi.py --format yaml --output documents/openapi.yaml
"""

import argparse
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Safe defaults for required environment variables during offline schema export
os.environ.setdefault("JWT_SECRET_KEY", "openapi-export-secret-key-minimum-32-chars-long")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/openapi_export")
os.environ.setdefault("MONGO_DATABASE", "openapi_export")

# Mock MongoDB client before Backend modules initialize
import pymongo
pymongo.MongoClient = lambda *args, **kwargs: MagicMock(
    admin=MagicMock(command=lambda *a, **k: {"ok": 1})
)

# Mock optional heavy libraries if not installed in current environment
for mod in ["xhtml2pdf", "xhtml2pdf.pisa"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()


def export_openapi(output_path: str, fmt: str = "json"):
    """Extract and write OpenAPI schema from FastAPI application."""
    from Backend.main import app

    schema = app.openapi()
    target_file = Path(output_path)
    target_file.parent.mkdir(parents=True, exist_ok=True)

    if fmt.lower() == "yaml":
        try:
            import yaml
            with open(target_file, "w", encoding="utf-8") as f:
                yaml.dump(schema, f, sort_keys=False, allow_unicode=True)
            print(f"[SUCCESS] Exported OpenAPI schema in YAML format to: {target_file}")
        except ImportError:
            print("[WARNING] PyYAML not installed. Falling back to JSON export.")
            with open(target_file.with_suffix(".json"), "w", encoding="utf-8") as f:
                json.dump(schema, f, indent=2)
            print(f"[SUCCESS] Exported OpenAPI schema in JSON format to: {target_file.with_suffix('.json')}")
    else:
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2)
        print(f"[SUCCESS] Exported OpenAPI schema ({len(schema.get('paths', {}))} endpoints) to: {target_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export FastAPI OpenAPI specification.")
    parser.add_argument(
        "--output",
        "-o",
        default=str(PROJECT_ROOT / "documents" / "openapi.json"),
        help="Target output file path (default: documents/openapi.json)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["json", "yaml"],
        default="json",
        help="Export format (json or yaml)",
    )
    args = parser.parse_args()
    export_openapi(args.output, args.format)
