#!/usr/bin/env python3
"""
Validate cross-references in instrument database.

Checks:
- Equipment tags referenced by instruments exist
- P&ID references are consistent
- Loop keys are valid and instruments reference existing loops
- IO signals have unique identifiers
- Instruments share loop_key with their parent loop

Usage:
    python sync_cross_refs.py --database database.yaml
    python sync_cross_refs.py -d database.yaml --equipment equipment-list.qmd --fix
"""

import argparse
import sys
from pathlib import Path
from collections import defaultdict

import yaml


def load_yaml(path: Path) -> dict:
    """Load YAML file."""
    with open(path) as f:
        return yaml.safe_load(f)


def load_qmd_frontmatter(path: Path) -> dict:
    """Load QMD frontmatter directly as YAML."""
    with open(path) as f:
        content = f.read()

    parts = content.split("---")
    if len(parts) < 3:
        raise ValueError(f"Invalid QMD format in {path}")

    return yaml.safe_load(parts[1])


def validate_equipment_refs(database: dict, equipment_list: list) -> list:
    """
    Validate equipment tag references.

    Args:
        database: Instrument database
        equipment_list: Equipment entries from QMD

    Returns:
        List of validation errors
    """
    errors = []
    equipment_tags = {eq.get("tag") for eq in equipment_list if eq.get("tag")}

    for inst in database.get("instruments", []):
        tag = inst.get("tag", {}).get("full_tag", "unknown")
        equipment_tag = inst.get("equipment_tag")

        if equipment_tag and equipment_tag not in equipment_tags:
            errors.append(f"{tag}: References unknown equipment '{equipment_tag}'")

    return errors


def validate_pid_refs(database: dict) -> list:
    """
    Validate P&ID references.

    Args:
        database: Instrument database

    Returns:
        List of validation errors
    """
    errors = []
    source_pids = {p.get("pid_number") for p in database.get("source_pids", [])}

    for inst in database.get("instruments", []):
        tag = inst.get("tag", {}).get("full_tag", "unknown")
        pid_ref = inst.get("location", {}).get("pid_reference")

        if pid_ref and pid_ref not in source_pids:
            errors.append(f"{tag}: P&ID '{pid_ref}' not in source_pids")

    return errors


def validate_loop_keys(database: dict) -> list:
    """
    Validate loop_key references and loop entity integrity.

    Checks:
    - All loops have unique loop_key
    - All instruments reference existing loops
    - Instruments in same loop share consistent variable

    Args:
        database: Instrument database

    Returns:
        List of validation errors
    """
    errors = []

    # Build set of valid loop_keys from loops collection
    loops = database.get("loops", [])
    valid_loop_keys = set()
    loop_variables = {}

    for loop in loops:
        loop_key = loop.get("loop_key")
        if not loop_key:
            errors.append("Loop missing required loop_key field")
            continue

        if loop_key in valid_loop_keys:
            errors.append(f"Duplicate loop_key: {loop_key}")
        else:
            valid_loop_keys.add(loop_key)
            loop_variables[loop_key] = loop.get("variable", "")

    # Validate instrument references to loops
    for inst in database.get("instruments", []):
        tag = inst.get("tag", {})
        full_tag = tag.get("full_tag", "unknown")
        loop_key = inst.get("loop_key")
        inst_variable = tag.get("variable", "")

        if not loop_key:
            errors.append(f"{full_tag}: Missing required loop_key field")
            continue

        if loop_key not in valid_loop_keys:
            errors.append(f"{full_tag}: References non-existent loop_key '{loop_key}'")
            continue

        # Check variable consistency
        expected_variable = loop_variables.get(loop_key, "")
        if expected_variable and inst_variable != expected_variable:
            errors.append(
                f"{full_tag}: Variable '{inst_variable}' doesn't match loop variable '{expected_variable}'"
            )

    return errors


def validate_io_points(database: dict) -> list:
    """
    Validate IO point IDs are unique.

    Args:
        database: Instrument database

    Returns:
        List of validation errors
    """
    errors = []
    io_point_ids = {}

    for inst in database.get("instruments", []):
        tag = inst.get("tag", {}).get("full_tag", "unknown")

        for signal in inst.get("io_signals", []):
            io_id = signal.get("io_point_id")
            if io_id:
                if io_id in io_point_ids:
                    errors.append(f"Duplicate io_point_id '{io_id}' in {tag} (also in {io_point_ids[io_id]})")
                else:
                    io_point_ids[io_id] = tag

    return errors


def validate_tag_consistency(database: dict) -> list:
    """
    Validate tag structure matches full_tag.

    Args:
        database: Instrument database

    Returns:
        List of validation errors
    """
    errors = []

    for inst in database.get("instruments", []):
        tag = inst.get("tag", {})
        full_tag = tag.get("full_tag", "")

        if full_tag:
            # Reconstruct from parts
            expected = f"{tag.get('area', '')}-{tag.get('variable', '')}{tag.get('function', '')}{tag.get('modifier', '')}-{tag.get('loop_number', '')}{tag.get('suffix', '')}"

            if full_tag.upper() != expected.upper():
                errors.append(f"Tag mismatch: {full_tag} vs computed {expected}")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate cross-references in instrument database")
    parser.add_argument("--database", "-d", required=True, help="Path to database YAML")
    parser.add_argument("--equipment", "-e", help="Path to equipment-list.qmd")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix issues")
    args = parser.parse_args()

    database_path = Path(args.database)
    if not database_path.exists():
        print(f"Error: Database file not found: {database_path}")
        sys.exit(1)

    print(f"Loading database: {database_path}")
    database = load_yaml(database_path)

    all_errors = []

    # Validate P&ID references
    print("\nValidating P&ID references...")
    errors = validate_pid_refs(database)
    if errors:
        print(f"  Found {len(errors)} issues:")
        for e in errors:
            print(f"    - {e}")
    else:
        print("  OK")
    all_errors.extend(errors)

    # Validate equipment references if equipment list provided
    if args.equipment:
        equipment_path = Path(args.equipment)
        if equipment_path.exists():
            print(f"\nValidating equipment references...")
            try:
                frontmatter = load_qmd_frontmatter(equipment_path)
                equipment_list = frontmatter.get("equipment", [])
                errors = validate_equipment_refs(database, equipment_list)
                if errors:
                    print(f"  Found {len(errors)} issues:")
                    for e in errors:
                        print(f"    - {e}")
                else:
                    print("  OK")
                all_errors.extend(errors)
            except Exception as e:
                print(f"  Warning: Could not load equipment list: {e}")
        else:
            print(f"Warning: Equipment file not found: {equipment_path}")

    # Validate loop keys
    print("\nValidating loop keys...")
    errors = validate_loop_keys(database)
    if errors:
        print(f"  Found {len(errors)} issues:")
        for e in errors:
            print(f"    - {e}")
    else:
        print("  OK")
    all_errors.extend(errors)

    # Validate IO points
    print("\nValidating IO point IDs...")
    errors = validate_io_points(database)
    if errors:
        print(f"  Found {len(errors)} issues:")
        for e in errors:
            print(f"    - {e}")
    else:
        print("  OK")
    all_errors.extend(errors)

    # Validate tag consistency
    print("\nValidating tag consistency...")
    errors = validate_tag_consistency(database)
    if errors:
        print(f"  Found {len(errors)} issues:")
        for e in errors:
            print(f"    - {e}")
    else:
        print("  OK")
    all_errors.extend(errors)

    # Summary
    print(f"\n{'=' * 50}")
    if all_errors:
        print(f"Validation completed with {len(all_errors)} issue(s)")
        sys.exit(1)
    else:
        print("Validation passed - no issues found")
        sys.exit(0)


if __name__ == "__main__":
    main()
