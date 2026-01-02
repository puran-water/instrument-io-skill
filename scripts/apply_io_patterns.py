#!/usr/bin/env python3
"""
Apply IO patterns to instrument database based on equipment list.

Reads equipment list from QMD frontmatter and generates io_signals[]
entries based on explicit feeder_type field.

Usage:
    python apply_io_patterns.py --database database.yaml --equipment equipment-list.qmd
    python apply_io_patterns.py -d database.yaml -e equipment-list.qmd --output updated.yaml
"""

import argparse
import re
import sys
import uuid
from pathlib import Path

import yaml


# =============================================================================
# FEEDER TYPE TO PATTERN MAPPING
# =============================================================================
# This is the single source of truth for equipment type + feeder type -> IO pattern.
# Equipment types from tag prefix (P, PU, BL, MX, CV, MOV, SOV, etc.)
# Feeder types from equipment-list-skill (DOL, VFD, VFD-EXT, SOFT-STARTER, VENDOR, etc.)

MOTOR_PATTERNS = {
    "DOL": "pump_dol",
    "VFD": "pump_vfd",
    "VFD-EXT": "pump_vfd_extended",
    "VFD_EXTENDED": "pump_vfd_extended",
    "SOFT-STARTER": "motor_soft_starter",
    "SOFT_STARTER": "motor_soft_starter",
    "VENDOR": "pump_dol",  # Vendor packages get minimal IO
    "VENDOR_PANEL": "pump_dol",
}

PUMP_PATTERNS = {
    "DOL": "pump_dol",
    "VFD": "pump_vfd",
    "VFD-EXT": "pump_vfd_extended",
    "SOFT-STARTER": "motor_soft_starter",
    "VENDOR": "pump_dol",
    "AODD": "aodd_pump",
    "METERING": "metering_pump_speed",
    "METERING-FULL": "metering_pump_full",
}

VALVE_PATTERNS = {
    # Control valves - need valve_type in equipment list
    "MOD-ELECTRIC": "valve_modulating_electric",
    "MOD-PNEUMATIC": "valve_modulating_pneumatic",
    "ONOFF-ELECTRIC": "valve_onoff_electric",
    "ONOFF-PNEUMATIC": "valve_onoff_pneumatic",
    "POSITIONER": "valve_positioner",
    "SOLENOID": "solenoid_valve",
}

# Equipment type code -> pattern lookup table
EQUIPMENT_PATTERN_MAP = {
    # Motors and rotating equipment
    "P": PUMP_PATTERNS,
    "PU": PUMP_PATTERNS,
    "BL": MOTOR_PATTERNS,
    "MX": MOTOR_PATTERNS,
    "AG": MOTOR_PATTERNS,  # Agitator
    "CP": MOTOR_PATTERNS,  # Compressor
    "FN": MOTOR_PATTERNS,  # Fan
    # Valves
    "CV": VALVE_PATTERNS,
    "MOV": {"DEFAULT": "valve_onoff_electric"},
    "SOV": {"DEFAULT": "solenoid_valve"},
    "BV": VALVE_PATTERNS,  # Ball valve
    "GV": VALVE_PATTERNS,  # Gate valve
}

# Feeder type display names (for output)
FEEDER_DISPLAY = {
    "DOL": "DOL",
    "VFD": "VFD",
    "VFD-EXT": "VFD",
    "VFD_EXTENDED": "VFD",
    "SOFT-STARTER": "Soft-Starter",
    "SOFT_STARTER": "Soft-Starter",
    "VENDOR": "Vendor Panel",
    "VENDOR_PANEL": "Vendor Panel",
    "AODD": "DOL",
    "METERING": "DOL",
    "METERING-FULL": "DOL",
    "MOD-ELECTRIC": "Direct",
    "MOD-PNEUMATIC": "Direct",
    "ONOFF-ELECTRIC": "Direct",
    "ONOFF-PNEUMATIC": "Direct",
    "POSITIONER": "Direct",
    "SOLENOID": "Direct",
    "DEFAULT": "Direct",
}


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
        raise ValueError(f"Invalid QMD format in {path}: no YAML frontmatter found")

    return yaml.safe_load(parts[1])


def load_io_patterns(patterns_path: Path) -> dict:
    """Load IO patterns from templates/io-patterns.yaml."""
    with open(patterns_path) as f:
        return yaml.safe_load(f)


def extract_equipment_type(tag: str) -> str:
    """Extract equipment type code from tag (e.g., '200-P-01' -> 'P')."""
    match = re.match(r"\d{3}-([A-Z]+)-\d+", tag)
    return match.group(1) if match else ""


def get_pattern_for_equipment(equipment: dict) -> tuple[str | None, str | None]:
    """
    Determine IO pattern from equipment's feeder_type field.

    Args:
        equipment: Equipment entry with required 'feeder_type' field

    Returns:
        Tuple of (pattern_name, feeder_display) or (None, None) if not mappable
    """
    tag = equipment.get("tag", "")
    feeder_type = equipment.get("feeder_type", "").upper().strip()

    if not feeder_type:
        return (None, None)

    eq_type = extract_equipment_type(tag)
    if not eq_type:
        return (None, None)

    # Look up pattern table for this equipment type
    pattern_table = EQUIPMENT_PATTERN_MAP.get(eq_type)
    if not pattern_table:
        return (None, None)

    # Find pattern for this feeder type
    pattern_name = pattern_table.get(feeder_type) or pattern_table.get("DEFAULT")
    if not pattern_name:
        return (None, None)

    feeder_display = FEEDER_DISPLAY.get(feeder_type, feeder_type)
    return (pattern_name, feeder_display)


def generate_io_signals(pattern: dict, base_tag: str, feeder_type: str) -> list:
    """
    Generate io_signals list from pattern definition.

    Args:
        pattern: Pattern definition from io-patterns.yaml
        base_tag: Base instrument tag
        feeder_type: Electrical feeder type display name

    Returns:
        List of io_signal entries
    """
    signals = []
    for sig in pattern.get("signals", []):
        suffix = sig.get("suffix", "")
        signal = {
            "io_point_id": str(uuid.uuid4()),
            "signal_function": sig.get("function", "Status"),
            "io_type": sig.get("io_type", "DI"),
            "signal_type": sig.get("signal_type", "24V DC"),
            "termination": "PLC",
            "component_type": sig.get("component", ""),
            "plc_tag": f"{base_tag}-{suffix}" if suffix else base_tag,
            "field_tag": f"{base_tag}-{suffix}" if suffix else base_tag,
            "suffix": suffix,
            "description": sig.get("description", ""),
            "protocol": sig.get("protocol"),
            "marshalling": None,
            "pattern_source": None,  # Set by caller
            "electrical": {"feeder_type": feeder_type},
        }
        signals.append(signal)
    return signals


def apply_patterns(
    database: dict, equipment_list: list, patterns: dict, strict: bool = True
) -> tuple[dict, list[str]]:
    """
    Apply IO patterns to instruments based on equipment list.

    Args:
        database: Instrument database
        equipment_list: List of equipment from equipment-list.qmd
        patterns: IO patterns dictionary
        strict: If True, report missing feeder_type as errors

    Returns:
        Tuple of (updated database, list of warnings/errors)
    """
    warnings = []

    # Build equipment tag -> equipment mapping
    equipment_map = {eq.get("tag"): eq for eq in equipment_list if eq.get("tag")}

    # Check for missing feeder_type in equipment list
    for eq in equipment_list:
        tag = eq.get("tag", "unknown")
        if not eq.get("feeder_type"):
            eq_type = extract_equipment_type(tag)
            if eq_type in EQUIPMENT_PATTERN_MAP:
                warnings.append(f"Missing feeder_type for {tag} (required for IO generation)")

    # Process each instrument
    applied_count = 0
    skipped_count = 0

    for inst in database.get("instruments", []):
        equipment_tag = inst.get("equipment_tag")
        if not equipment_tag:
            continue

        # Find matching equipment
        equipment = equipment_map.get(equipment_tag)
        if not equipment:
            continue

        # Skip if instrument already has io_signals
        if inst.get("io_signals"):
            skipped_count += 1
            continue

        # Get pattern for this equipment
        pattern_name, feeder_type = get_pattern_for_equipment(equipment)
        if not pattern_name:
            continue

        pattern = patterns.get(pattern_name)
        if not pattern:
            warnings.append(f"Pattern '{pattern_name}' not found in io-patterns.yaml")
            continue

        # Generate IO signals
        base_tag = inst.get("tag", {}).get("full_tag", "")
        io_signals = generate_io_signals(pattern, base_tag, feeder_type)

        # Set pattern source on all signals
        for sig in io_signals:
            sig["pattern_source"] = pattern_name

        inst["io_signals"] = io_signals
        applied_count += 1

        print(f"  {base_tag}: {pattern_name} [{feeder_type}] ({len(io_signals)} IO)")

    print(f"\nApplied: {applied_count} | Skipped (existing): {skipped_count}")

    return database, warnings


def main():
    parser = argparse.ArgumentParser(
        description="Apply IO patterns to instrument database based on equipment feeder_type"
    )
    parser.add_argument("--database", "-d", required=True, help="Path to instrument database YAML")
    parser.add_argument("--equipment", "-e", required=True, help="Path to equipment-list.qmd")
    parser.add_argument("--patterns", "-p", help="Path to io-patterns.yaml (default: auto-detect)")
    parser.add_argument("--output", "-o", help="Output path (default: overwrite input)")
    parser.add_argument("--strict", action="store_true", help="Exit with error if feeder_type missing")
    args = parser.parse_args()

    database_path = Path(args.database)
    equipment_path = Path(args.equipment)

    if not database_path.exists():
        print(f"Error: Database file not found: {database_path}")
        sys.exit(1)

    if not equipment_path.exists():
        print(f"Error: Equipment file not found: {equipment_path}")
        sys.exit(1)

    # Find patterns file
    if args.patterns:
        patterns_path = Path(args.patterns)
    else:
        script_dir = Path(__file__).parent.parent
        patterns_path = script_dir / "templates" / "io-patterns.yaml"

    if not patterns_path.exists():
        print(f"Error: Patterns file not found: {patterns_path}")
        sys.exit(1)

    # Load data
    print(f"Loading database: {database_path}")
    database = load_yaml(database_path)

    print(f"Loading equipment list: {equipment_path}")
    frontmatter = load_qmd_frontmatter(equipment_path)
    equipment_list = frontmatter.get("equipment", [])
    print(f"  Found {len(equipment_list)} equipment entries")

    print(f"Loading IO patterns: {patterns_path}")
    patterns = load_io_patterns(patterns_path)
    print(f"  Found {len(patterns)} patterns")

    # Apply patterns
    print("\nApplying IO patterns...")
    database, warnings = apply_patterns(database, equipment_list, patterns, args.strict)

    # Report warnings
    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")
        if args.strict:
            print("\nStrict mode: Exiting due to warnings.")
            sys.exit(1)

    # Save output
    output_path = Path(args.output) if args.output else database_path
    with open(output_path, "w") as f:
        yaml.dump(database, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()
