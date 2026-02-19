#!/usr/bin/env python3
"""
Validate instrument database against schema.

Usage:
    python validate_database.py --database database.yaml
    python validate_database.py --database database.yaml --strict
"""

import argparse
import sys
from pathlib import Path
import yaml

try:
    from jsonschema import validate, ValidationError, Draft202012Validator
except ImportError:
    print("Error: jsonschema not installed. Run: pip install jsonschema")
    sys.exit(1)


def load_yaml(path: Path) -> dict:
    """Load YAML file."""
    with open(path) as f:
        return yaml.safe_load(f)


def validate_database(database_path: Path, schema_path: Path, strict: bool = False) -> list:
    """
    Validate database against schema.

    Args:
        database_path: Path to instrument database YAML
        schema_path: Path to schema YAML
        strict: If True, fail on warnings

    Returns:
        List of validation errors/warnings
    """
    errors = []

    # Load files
    try:
        database = load_yaml(database_path)
    except Exception as e:
        return [f"Failed to load database: {e}"]

    try:
        schema = load_yaml(schema_path)
    except Exception as e:
        return [f"Failed to load schema: {e}"]

    # JSON Schema validation
    validator = Draft202012Validator(schema)
    for error in validator.iter_errors(database):
        path = ".".join(str(p) for p in error.absolute_path)
        errors.append(f"Schema error at {path}: {error.message}")

    if errors:
        return errors

    # Additional semantic validations
    instruments = database.get("instruments", [])

    # Check for duplicate instrument_ids
    ids = [i.get("instrument_id") for i in instruments if i.get("instrument_id")]
    duplicates = set(x for x in ids if ids.count(x) > 1)
    for dup in duplicates:
        errors.append(f"Duplicate instrument_id: {dup}")

    # Check for duplicate full_tags
    tags = [i.get("tag", {}).get("full_tag") for i in instruments if isinstance(i.get("tag"), dict)]
    dup_tags = set(x for x in tags if x and tags.count(x) > 1)
    for dup in dup_tags:
        errors.append(f"Duplicate full_tag: {dup}")

    # Validate tag structure matches full_tag
    for inst in instruments:
        tag = inst.get("tag", {})
        if not isinstance(tag, dict):
            continue
        full_tag = tag.get("full_tag", "")
        if full_tag:
            expected = f"{tag.get('area', '')}-{tag.get('variable', '')}{tag.get('function', '')}{tag.get('modifier', '')}-{tag.get('loop_number', '')}{tag.get('suffix', '')}"
            if full_tag != expected:
                errors.append(f"Tag mismatch for {full_tag}: computed {expected}")

    # Validate io_signals have unique io_point_ids
    for inst in instruments:
        tag_data = inst.get("tag", {})
        tag = tag_data.get("full_tag", "unknown") if isinstance(tag_data, dict) else str(tag_data)
        io_ids = [s.get("io_point_id") for s in inst.get("io_signals", []) if s.get("io_point_id")]
        dup_io = set(x for x in io_ids if io_ids.count(x) > 1)
        for dup in dup_io:
            errors.append(f"Duplicate io_point_id in {tag}: {dup}")

    # Validate equipment_tag references (warning)
    equipment_tags = set()
    for inst in instruments:
        eq = inst.get("equipment_tag")
        if eq:
            equipment_tags.add(eq)

    # Check source_pids references
    source_pids = {p.get("pid_number") for p in database.get("source_pids", [])}
    for inst in instruments:
        pid_ref = inst.get("location", {}).get("pid_reference")
        if pid_ref and pid_ref not in source_pids:
            tag_data = inst.get("tag", {})
            full_tag = tag_data.get("full_tag") if isinstance(tag_data, dict) else str(tag_data)
            msg = f"Warning: P&ID {pid_ref} referenced by {full_tag} not in source_pids"
            if strict:
                errors.append(msg)
            else:
                print(msg)

    # Validate io_type consistency
    valid_io_types = {"DI", "DO", "AI", "AO", "PI", "PO"}
    for inst in instruments:
        tag_data = inst.get("tag", {})
        tag = tag_data.get("full_tag", "unknown") if isinstance(tag_data, dict) else str(tag_data)
        for sig in inst.get("io_signals", []):
            io_type = sig.get("io_type")
            if io_type and io_type not in valid_io_types:
                errors.append(f"Invalid io_type '{io_type}' in {tag}")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate instrument database")
    parser.add_argument("--database", "-d", required=True, help="Path to database YAML")
    parser.add_argument("--schema", "-s", help="Path to schema (default: auto-detect)")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    args = parser.parse_args()

    database_path = Path(args.database)
    if not database_path.exists():
        print(f"Error: Database file not found: {database_path}")
        sys.exit(1)

    # Find schema
    if args.schema:
        schema_path = Path(args.schema)
    else:
        # Try relative path from script location
        script_dir = Path(__file__).parent.parent
        schema_path = script_dir / "schemas" / "instrument-database.schema.yaml"

    if not schema_path.exists():
        print(f"Error: Schema file not found: {schema_path}")
        sys.exit(1)

    print(f"Validating {database_path}...")
    errors = validate_database(database_path, schema_path, args.strict)

    if errors:
        print(f"\nValidation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("Validation passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
