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
    "PU": PUMP_PATTERNS,  # Alias for P (legacy)
    "B": MOTOR_PATTERNS,
    "BL": MOTOR_PATTERNS,  # Alias for B (legacy)
    "MX": MOTOR_PATTERNS,
    "AG": MOTOR_PATTERNS,  # Agitator
    "CP": MOTOR_PATTERNS,  # Compressor
    "FN": MOTOR_PATTERNS,  # Fan
    "SC": MOTOR_PATTERNS,  # Screen
    "CN": MOTOR_PATTERNS,  # Conveyor
    "CL": MOTOR_PATTERNS,  # Clarifier mechanism
    "TH": MOTOR_PATTERNS,  # Thickener mechanism
    "CF": MOTOR_PATTERNS,  # Centrifuge
    "BF": MOTOR_PATTERNS,  # Belt filter
    "WC": MOTOR_PATTERNS,  # Washer/compactor
    "CT": MOTOR_PATTERNS,  # Cooling tower
    "C": MOTOR_PATTERNS,   # Compressor (alt code)
    "COMP": MOTOR_PATTERNS, # Compressor
    "G": MOTOR_PATTERNS,   # Grinder (single-letter code)
    "GR": MOTOR_PATTERNS,  # Grinder
    "SP": MOTOR_PATTERNS,  # Screw Press
    "FP": MOTOR_PATTERNS,  # Filter Press
    "SM": MOTOR_PATTERNS,  # Static Mixer
    "DR": MOTOR_PATTERNS,  # Dryer
    "MP": PUMP_PATTERNS,   # Metering pump
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
    """Extract equipment type code from tag (e.g., '200-P-01' -> 'P', 'W501-P-01' -> 'P')."""
    # Standard: NNN-XXX-NN or XNNN-XXX-NN (W-prefix)
    match = re.match(r"[A-Z]?\d{3,4}-([A-Z]+)-\d+", tag)
    if match:
        return match.group(1)
    # Short form: XXX-NN (e.g., SM-02)
    match = re.match(r"([A-Z]{1,5})-\d+", tag)
    return match.group(1) if match else ""


def normalize_equipment_tag(raw_tag: str) -> list[str]:
    """Normalize paired/multi equipment tags to individual canonical tags.

    Handles:
      - '202-P-03/04' -> ['202-P-03']
      - '500-P-01/02/03' -> ['500-P-01']
      - 'SM-02, 401-F-01/02' -> ['SM-02', '401-F-01']
      - '101-P-01' -> ['101-P-01']
    """
    results = []
    # Split on comma
    parts = [t.strip() for t in raw_tag.split(",")]
    for part in parts:
        # Strip ALL paired suffixes: NNN-XX-NN/NN/NN -> NNN-XX-NN
        cleaned = re.sub(r"(/\d+)+$", "", part)
        if cleaned:
            results.append(cleaned)
    return results


def get_pattern_for_equipment(equipment: dict) -> tuple[str | None, str | None]:
    """
    Determine IO pattern from equipment's feeder_type field.

    Args:
        equipment: Equipment entry with required 'feeder_type' field

    Returns:
        Tuple of (pattern_name, feeder_display) or (None, None) if not mappable
    """
    tag = equipment.get("tag", "")
    feeder_type = (equipment.get("feeder_type") or "").upper().strip()

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


def is_local_instrument(inst: dict) -> bool:
    """Check if an instrument is local (no PLC IO).

    Local instruments include:
      - PG (Pressure Gauge) — local indication only
      - TG (Temperature Gauge) — local indication only
      - FG (Flow Gauge/Glass) — local indication only
      - LG (Level Gauge/Glass) — local indication only
      - PI (Pressure Indicator, local) — when no transmitter function
      - VB (Ball Valve) — manual valve, no actuation
      - V-RN (manual valve) — manual valve
      - BFV (Butterfly Valve, manual) — manual valve
      - GV (Gate Valve, manual) — manual valve unless actuated
      - ST (Strainer) — passive device
    """
    tag_data = inst.get("tag", {}) if isinstance(inst.get("tag"), dict) else {}
    full_tag = (tag_data.get("full_tag", "") or "").strip()
    functions = tag_data.get("functions", [])
    variable = tag_data.get("variable", "")
    inst_type = (inst.get("instrument_type") or "").lower()

    # Local gauges: function is G (Gauge/Glass) only — no transmit/switch function
    if "G" in functions and "T" not in functions and "S" not in functions:
        return True

    # Explicit local gauge tags
    tag_upper = full_tag.upper().split("--")[0].split("-")[0] if full_tag else ""
    local_prefixes = ("PG", "TG", "FG", "LG", "SG")
    if tag_upper in local_prefixes:
        return True
    if any(full_tag.upper().startswith(p) for p in local_prefixes):
        # But not PG that is part of a longer tag like PG-AIT
        rest = full_tag.upper()[2:]
        if not rest or rest.startswith("-") or rest.startswith(" "):
            return True

    # Manual valves: VB (ball), BFV (butterfly), GV (gate), V-RN
    manual_valve_prefixes = ("VB", "BFV", "GV", "V-RN", "NRV", "CV-M")
    if any(full_tag.upper().startswith(p) for p in manual_valve_prefixes):
        return True
    if inst_type in ("ball valve", "manual valve", "gate valve", "butterfly valve",
                      "check valve", "non-return valve"):
        return True

    # Strainers
    if tag_upper in ("ST",) or inst_type == "strainer":
        return True

    return False


def infer_field_instrument_pattern(inst: dict) -> str | None:
    """Infer IO pattern for a field instrument based on its tag functions/variable.

    Returns None for local instruments (gauges, manual valves) that have no PLC IO.

    Rules:
      - Functions contain 'I' and 'T' (transmitter: AIT, LIT, FIT, TIT, PIT) -> transmitter_4_20
      - Functions contain 'S' + variable 'L' (LSH, LSL) -> level_switch
      - Functions contain 'S' + variable 'P' (PSH, PSL) -> pressure_switch
      - Variable 'X' + function 'V' (XV) -> valve_onoff_electric
      - Local gauges (PG, TG, FG, LG) -> None (no IO)
      - Manual valves (VB, BFV, GV) -> None (no IO)
    """
    # Exclude local instruments
    if is_local_instrument(inst):
        return None

    tag_data = inst.get("tag", {}) if isinstance(inst.get("tag"), dict) else {}
    functions = tag_data.get("functions", [])
    variable = tag_data.get("variable", "")
    full_tag = tag_data.get("full_tag", "")

    # Transmitters: function list contains I and T, or instrument_type is Transmitter
    inst_type = (inst.get("instrument_type") or "").lower()
    if "T" in functions and "I" in functions:
        return "transmitter_4_20"
    if inst_type == "transmitter":
        return "transmitter_4_20"

    # Switches — classify by measured variable
    if "S" in functions:
        if variable == "L":
            return "level_switch"
        if variable == "P":
            return "pressure_switch"
        if variable == "T":
            return "temperature_switch"
        if variable == "F":
            return "flow_switch"
        # Generic switch — default to level_switch as most common
        return "level_switch"

    # Valves: XV (actuated shut-off valve)
    if variable == "X" and "V" in functions:
        return "valve_onoff_electric"

    # Analyzers
    if inst_type == "analyzer":
        return "transmitter_4_20"

    return None


def generate_motor_instruments(
    equipment_list: list, database: dict, patterns: dict
) -> tuple[int, list[str]]:
    """Generate motor IO instruments for motorized equipment missing them.

    For each motorized equipment with feeder_type and no existing motor IO instrument
    in the database, create a new instrument entry with tag {equipment_tag}-M and
    apply the appropriate motor pattern.

    Returns:
        Tuple of (count_generated, warnings)
    """
    warnings = []
    generated = 0

    # Build set of equipment tags that already have motor instruments
    existing_motor_tags = set()
    for inst in database.get("instruments", []):
        eq_tag = inst.get("equipment_tag", "")
        tag_data = inst.get("tag", {})
        full_tag = tag_data.get("full_tag", "") if isinstance(tag_data, dict) else ""
        # Motor instruments have -M suffix or type "Motor Control"
        if full_tag.endswith("-M") or (inst.get("instrument_type") or "").lower() in ("motor control", "motor"):
            # Normalize the equipment tag
            for normalized in normalize_equipment_tag(eq_tag):
                existing_motor_tags.add(normalized)

    for eq in equipment_list:
        tag = eq.get("tag", "")
        feeder_type = (eq.get("feeder_type") or "").upper().strip()
        if not feeder_type:
            continue

        eq_type = extract_equipment_type(tag)
        if eq_type not in EQUIPMENT_PATTERN_MAP:
            continue

        # Skip if motor instrument already exists (normalize to match slash/comma variants)
        normalized_variants = normalize_equipment_tag(tag)
        if any(nt in existing_motor_tags for nt in normalized_variants):
            continue

        # Determine pattern
        pattern_name, feeder_display = get_pattern_for_equipment(eq)
        if not pattern_name:
            continue

        pattern = patterns.get(pattern_name)
        if not pattern:
            warnings.append(f"Pattern '{pattern_name}' not found for motor instrument on {tag}")
            continue

        motor_tag = f"{tag}-M"
        io_signals = generate_io_signals(pattern, motor_tag, feeder_display)
        for sig in io_signals:
            sig["pattern_source"] = pattern_name

        # Create new instrument entry
        new_inst = {
            "instrument_id": str(uuid.uuid4()),
            "equipment_tag": tag,
            "instrument_type": "Motor Control",
            "tag": {
                "full_tag": motor_tag,
                "variable": "",
                "function": "M",
                "functions": ["M"],
                "area": str(eq.get("area", "")),
                "loop_number": "",
                "suffix": "M",
                "analyte": None,
            },
            "service_description": f"Motor control for {eq.get('description', tag)}",
            "io_signals": io_signals,
            "primary_signal_type": None,
            "provenance": {
                "source_type": "auto_generated",
                "extraction_source": "motor_instrument_gen",
                "confidence": 1.0,
            },
        }
        database.setdefault("instruments", []).append(new_inst)
        generated += 1
        print(f"  [motor] {motor_tag}: {pattern_name} [{feeder_display}] ({len(io_signals)} IO)")

    return generated, warnings


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

    # Build equipment tag -> equipment mapping with bidirectional pair resolution.
    # When a tag is paired (e.g. "202-B-01/02"), map both individual siblings
    # so instruments referencing either "202-B-01" or "202-B-02" resolve correctly.
    equipment_map = {}
    _paired_tag_re = re.compile(r"^([A-Z]?\d{3,4}-[A-Z]{1,5}-)(\d+)((?:/\d+)+)$")
    for eq in equipment_list:
        tag = eq.get("tag", "")
        if not tag:
            continue
        equipment_map[tag] = eq

        # Index ALL normalized variants (comma-split + slash-stripped base tags)
        # so instruments referencing any variant resolve correctly (C2 fix)
        for norm_tag in normalize_equipment_tag(tag):
            equipment_map.setdefault(norm_tag, eq)

        # Expand paired/triple tags: "202-B-01/02" → map "202-B-01", "202-B-02"
        # Also handles triple+: "500-P-01/02/03" → map "500-P-01", "500-P-02", "500-P-03"
        m = _paired_tag_re.match(tag)
        if m:
            prefix, first_seq, suffix_group = m.groups()
            all_seqs = [first_seq] + [s for s in suffix_group.split("/") if s]
            fmt_len = max(len(s) for s in all_seqs)
            for seq in all_seqs:
                individual_tag = f"{prefix}{seq.zfill(fmt_len)}"
                equipment_map.setdefault(individual_tag, eq)

        # Also check quantity_note for sister sequences (e.g. "1W + 1S" with tag 102-G-01)
        # and create alias for the inferred sibling (102-G-02)
        qty_note = str(eq.get("quantity_note") or "")
        quantity = eq.get("quantity", 1)
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            quantity = 1
        if quantity >= 2 and "S" in qty_note.upper():
            # Infer sibling by incrementing the sequence number
            sibling_match = re.match(r"^([A-Z]?\d{3,4}-[A-Z]{1,5}-)(\d+)$", tag)
            if sibling_match:
                sib_prefix, sib_seq = sibling_match.groups()
                for offset in range(1, quantity):
                    sib_tag = f"{sib_prefix}{(int(sib_seq) + offset):0{len(sib_seq)}d}"
                    equipment_map.setdefault(sib_tag, eq)

    # Check for missing feeder_type in equipment list
    for eq in equipment_list:
        tag = eq.get("tag", "unknown")
        if not eq.get("feeder_type"):
            eq_type = extract_equipment_type(tag)
            if eq_type in EQUIPMENT_PATTERN_MAP:
                warnings.append(f"Missing feeder_type for {tag} (required for IO generation)")

    # Phase 0: Deduplicate instruments by full_tag (same instrument on multiple P&ID pages)
    # Keep the first occurrence (earliest page / highest confidence)
    instruments = database.get("instruments", [])
    seen_tags: dict[str, int] = {}
    dedup_removed = 0
    for i, inst in enumerate(instruments):
        tag_data = inst.get("tag", {})
        ft = tag_data.get("full_tag", "") if isinstance(tag_data, dict) else str(tag_data)
        if ft and ft in seen_tags:
            dedup_removed += 1
        elif ft:
            seen_tags[ft] = i
    if dedup_removed > 0:
        database["instruments"] = [
            inst for i, inst in enumerate(instruments)
            if (inst.get("tag", {}).get("full_tag", "") if isinstance(inst.get("tag"), dict) else str(inst.get("tag", ""))) not in seen_tags
            or seen_tags.get(inst.get("tag", {}).get("full_tag", "") if isinstance(inst.get("tag"), dict) else str(inst.get("tag", ""))) == i
        ]
        print(f"Dedup: removed {dedup_removed} duplicate instrument tags")

    # Phase 1: Generate motor instruments for motorized equipment
    print("\nGenerating motor instruments...")
    motor_count, motor_warnings = generate_motor_instruments(equipment_list, database, patterns)
    warnings.extend(motor_warnings)
    print(f"  Generated: {motor_count} motor instruments")

    # Phase 2: Apply patterns to existing field instruments
    print("\nApplying IO patterns to field instruments...")
    applied_count = 0
    skipped_count = 0
    field_fallback_count = 0

    for inst in database.get("instruments", []):
        # Skip motor instruments we just generated
        if (inst.get("provenance") or {}).get("extraction_source") == "motor_instrument_gen":
            continue

        equipment_tag = inst.get("equipment_tag")

        # Skip if instrument already has io_signals
        if inst.get("io_signals"):
            skipped_count += 1
            continue

        # Find matching equipment (try exact match, then normalized)
        equipment = None
        if equipment_tag:
            equipment = equipment_map.get(equipment_tag)
            if not equipment:
                # Try normalizing paired tags
                for normalized_tag in normalize_equipment_tag(equipment_tag):
                    equipment = equipment_map.get(normalized_tag)
                    if equipment:
                        break

        base_tag = inst.get("tag", {}).get("full_tag", "") if isinstance(inst.get("tag"), dict) else ""

        # Skip local instruments (PG, VB, etc.) — no PLC IO
        if is_local_instrument(inst):
            continue

        # Determine if this is a field instrument (transmitter, switch, valve)
        # vs. a motor-type instrument. Field instruments should NOT get motor patterns.
        is_field_instrument = False
        inst_type = (inst.get("instrument_type") or "").lower()
        tag_data = inst.get("tag", {}) if isinstance(inst.get("tag"), dict) else {}
        variable = tag_data.get("variable", "")
        functions = tag_data.get("functions", [])

        if inst_type in ("transmitter", "analyzer", "switch", "indicator", "gauge"):
            is_field_instrument = True
        elif variable in ("P", "T", "L", "F", "A", "S", "C", "Q"):
            # ISA variable letters for field measurements
            is_field_instrument = True
        elif any(f in functions for f in ["I", "T", "S"]):
            # I=Indicate, T=Transmit, S=Switch -> field instrument
            is_field_instrument = True

        if equipment and not is_field_instrument:
            # Get pattern for this equipment (motor-type instruments only)
            pattern_name, feeder_type = get_pattern_for_equipment(equipment)
            if pattern_name:
                pattern = patterns.get(pattern_name)
                if pattern:
                    io_signals = generate_io_signals(pattern, base_tag, feeder_type)
                    for sig in io_signals:
                        sig["pattern_source"] = pattern_name
                    inst["io_signals"] = io_signals
                    applied_count += 1
                    print(f"  {base_tag}: {pattern_name} [{feeder_type}] ({len(io_signals)} IO)")
                    continue
                else:
                    warnings.append(f"Pattern '{pattern_name}' not found in io-patterns.yaml")

        # Field instruments and fallback: infer from instrument type/functions
        # This also handles instruments with no equipment_tag (XV valves, TC controllers)
        fallback_pattern_name = infer_field_instrument_pattern(inst)
        if fallback_pattern_name:
            pattern = patterns.get(fallback_pattern_name)
            if pattern:
                io_signals = generate_io_signals(pattern, base_tag, "Direct")
                for sig in io_signals:
                    sig["pattern_source"] = fallback_pattern_name
                inst["io_signals"] = io_signals
                field_fallback_count += 1
                print(f"  {base_tag}: {fallback_pattern_name} [field-fallback] ({len(io_signals)} IO)")
                continue
            else:
                warnings.append(f"Inferred pattern '{fallback_pattern_name}' for '{base_tag}' not found in io-patterns.yaml — 0 IO assigned")

    print(f"\nEquipment-matched: {applied_count} | Field-fallback: {field_fallback_count} | Skipped (existing): {skipped_count}")

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
