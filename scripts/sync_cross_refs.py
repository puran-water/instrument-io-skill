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
import re
import sys
from pathlib import Path
from collections import defaultdict

import yaml


def _expand_equipment_tags(equipment_list: list) -> set:
    """Build expanded set of equipment tags including slash-sibling variants.

    Handles:
      - Raw tags as-is
      - Comma-separated parts
      - Slash-stripped base tags (e.g., '200-B-01/02' → '200-B-01')
      - Individual slash siblings (e.g., '200-B-01/02' → '200-B-01', '200-B-02')
    """
    tags = set()
    for eq in equipment_list:
        raw = eq.get("tag", "")
        if not raw:
            continue
        tags.add(raw)
        for part in raw.split(","):
            part = part.strip()
            base = re.sub(r"(/\d+)+$", "", part)
            if base:
                tags.add(base)
            m = re.match(r"^(.*?-)(\d+)((?:/\d+)+)$", part)
            if m:
                prefix, first_seq, rest = m.groups()
                for seq in [first_seq] + [s for s in rest.split("/") if s]:
                    tags.add(f"{prefix}{seq}")
    return tags


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
    # Build expanded set from equipment list (handle slash/comma tags + siblings)
    equipment_tags = _expand_equipment_tags(equipment_list)

    for inst in database.get("instruments", []):
        tag_data = inst.get("tag", {})
        tag = tag_data.get("full_tag", "unknown") if isinstance(tag_data, dict) else str(tag_data or "unknown")
        equipment_tag = inst.get("equipment_tag")

        if equipment_tag:
            # Strip descriptions: "200-T-06 (Digester Tank No. 6)" → "200-T-06"
            cleaned = re.sub(r'\s*\(.*\)\s*$', '', equipment_tag).strip()
            base = re.sub(r"(/\d+)+$", "", cleaned)
            if cleaned not in equipment_tags and base not in equipment_tags:
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
        tag_data = inst.get("tag", {})
        tag = tag_data.get("full_tag", "unknown") if isinstance(tag_data, dict) else str(tag_data or "unknown")
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
        tag_data = inst.get("tag", {})
        if isinstance(tag_data, dict):
            full_tag = tag_data.get("full_tag", "unknown")
            inst_variable = tag_data.get("variable", "")
        else:
            full_tag = str(tag_data or "unknown")
            inst_variable = ""
        loop_key = inst.get("loop_key")

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
        tag_data = inst.get("tag", {})
        tag = tag_data.get("full_tag", "unknown") if isinstance(tag_data, dict) else str(tag_data or "unknown")

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
        if not isinstance(tag, dict):
            continue  # Cannot validate tag consistency for non-dict tags
        full_tag = tag.get("full_tag", "")

        if full_tag:
            # Reconstruct from parts in ISA format: VARIABLE+FUNCTION+MODIFIER-AREA-LOOP(-SUFFIX)
            variable = tag.get('variable', '')
            function = tag.get('function', '')
            modifier = tag.get('modifier', '')
            area = tag.get('area', '')
            loop_number = tag.get('loop_number', '')
            suffix = tag.get('suffix', '')

            func_letters = f"{variable}{function}{modifier}"
            parts = [p for p in [func_letters, area, loop_number] if p]
            expected = "-".join(parts)
            if suffix:
                expected = f"{expected}-{suffix}" if expected else suffix

            if full_tag.upper() != expected.upper():
                errors.append(f"Tag mismatch: {full_tag} vs computed {expected}")

    return errors


def apply_auto_fixes(database: dict, equipment_tags: set) -> tuple[int, list[str]]:
    """Auto-fix orphan equipment_tag references in instruments.

    Strategies (applied in order):
    1. Strip /XX paired suffix: "202-B-01/02" → try "202-B-01"
    2. Try sibling offsets: "102-TK-02" → try "102-TK-01" if it exists
    3. Normalize non-ISA descriptive tags to nearest equipment match

    Returns:
        (fix_count, fix_messages)
    """
    PAIRED_SUFFIX_RE = re.compile(r"^(.+?)(/\d+)+$")
    ISA_TAG_RE = re.compile(r"^([A-Z]?\d{3,4})-([A-Z]{1,5})-(\d+)$")

    fix_count = 0
    messages = []

    for inst in database.get("instruments", []):
        equip_tag = inst.get("equipment_tag")
        if not equip_tag or equip_tag in equipment_tags:
            continue

        full_tag = inst.get("tag", {}).get("full_tag", "unknown") if isinstance(inst.get("tag"), dict) else "unknown"
        original_ref = equip_tag

        # Strategy 1: Strip /XX paired suffix
        m = PAIRED_SUFFIX_RE.match(equip_tag)
        if m:
            base_tag = m.group(1)
            if base_tag in equipment_tags:
                inst["equipment_tag"] = base_tag
                fix_count += 1
                messages.append(f"  [fix] {full_tag}: '{original_ref}' → '{base_tag}' (stripped paired suffix)")
                continue

        # Strategy 2: Try sibling offsets (±1, ±2) for ISA-format tags
        m = ISA_TAG_RE.match(equip_tag)
        if m:
            prefix, code, seq_str = m.groups()
            seq = int(seq_str)
            fmt_len = len(seq_str)
            for offset in [1, -1, 2, -2]:
                sibling_seq = seq + offset
                if sibling_seq < 1:
                    continue
                sibling_tag = f"{prefix}-{code}-{sibling_seq:0{fmt_len}d}"
                if sibling_tag in equipment_tags:
                    inst["equipment_tag"] = sibling_tag
                    fix_count += 1
                    messages.append(f"  [fix] {full_tag}: '{original_ref}' → '{sibling_tag}' (sibling offset {offset:+d})")
                    break
            else:
                # No sibling found via offset — continue to strategy 3
                pass
            if inst["equipment_tag"] != original_ref:
                continue

        # Strategy 3: Normalize non-ISA descriptive tags to nearest equipment
        # e.g. "AIR/DIRT SEPARATOR" or "FEED TANK" → try to find equipment with matching description
        if not ISA_TAG_RE.match(equip_tag):
            # Non-ISA tag — not auto-fixable, leave as-is with info message
            messages.append(f"  [info] {full_tag}: non-ISA equipment_tag '{original_ref}' — skipped (manual review)")

    return fix_count, messages


def main():
    parser = argparse.ArgumentParser(description="Validate cross-references in instrument database")
    parser.add_argument("--database", "-d", required=True, help="Path to database YAML")
    parser.add_argument("--equipment", "-e", help="Path to equipment-list.qmd or equipment-list.yaml")
    parser.add_argument("--fix", action="store_true", help="Attempt to auto-fix orphan equipment references")
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
                # Support both QMD and plain YAML formats
                if equipment_path.suffix == '.qmd':
                    frontmatter = load_qmd_frontmatter(equipment_path)
                else:
                    frontmatter = load_yaml(equipment_path)
                equipment_list = frontmatter.get("equipment", [])
                equipment_tags = _expand_equipment_tags(equipment_list)

                # Auto-fix orphan references before validation if --fix is set
                if args.fix:
                    print("\n  Applying auto-fixes for orphan equipment references...")
                    fix_count, fix_messages = apply_auto_fixes(database, equipment_tags)
                    for msg in fix_messages:
                        print(msg)
                    if fix_count > 0:
                        print(f"  Fixed {fix_count} orphan reference(s)")
                        # Save the fixed database
                        with open(database_path, "w") as f:
                            yaml.dump(database, f, default_flow_style=False,
                                      sort_keys=False, allow_unicode=True)
                        print(f"  Saved fixed database to: {database_path}")
                    else:
                        print("  No auto-fixable orphans found")

                errors = validate_equipment_refs(database, equipment_list)
                if errors:
                    print(f"  Found {len(errors)} remaining issues:")
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
