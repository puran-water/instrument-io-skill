#!/usr/bin/env python3
"""
ISA-5.1 Tag Decoder.

Parses instrument tags into structured components.

Usage:
    python decode_isa_tag.py 200-FIT-01A
    python decode_isa_tag.py --tag "200-FIT-01A" --json
"""

import argparse
import json
import re
import sys
from typing import Optional


# ISA-5.1 First Letters (Measured Variable)
FIRST_LETTERS = {
    "A": "Analysis",
    "B": "Burner/Combustion",
    "C": "Conductivity",
    "D": "Density",
    "E": "Voltage",
    "F": "Flow Rate",
    "G": "Gaging/Position",
    "H": "Hand/Manual",
    "I": "Current",
    "J": "Power",
    "K": "Time",
    "L": "Level",
    "M": "Moisture",
    "N": "User Choice",
    "O": "User Choice",
    "P": "Pressure",
    "Q": "Quantity",
    "R": "Radiation",
    "S": "Speed",
    "T": "Temperature",
    "U": "Multivariable",
    "V": "Vibration",
    "W": "Weight",
    "X": "Unclassified",
    "Y": "Event/State",
    "Z": "Position",
}

# ISA-5.1 Succeeding Letters (Function)
SUCCEEDING_LETTERS = {
    "A": "Alarm",
    "B": "User Choice",
    "C": "Control",
    "D": "Differential",
    "E": "Sensing Element",
    "G": "Glass/Viewing",
    "H": "High",
    "I": "Indicate",
    "K": "Control Station",
    "L": "Low/Light",
    "M": "Middle",
    "N": "User Choice",
    "O": "Orifice",
    "P": "Point/Test",
    "Q": "Integrate/Totalize",
    "R": "Record",
    "S": "Switch/Safety",
    "T": "Transmit",
    "U": "Multifunction",
    "V": "Valve",
    "W": "Well",
    "X": "Unclassified",
    "Y": "Relay/Compute",
    "Z": "Driver/Actuator",
}

# Category classification based on function letters
CATEGORY_RULES = {
    "E": "primary",
    "T": "transmitting",
    "I": "indicating",
    "R": "recording",
    "C": "controlling",
    "S": "switching",
    "A": "safety",  # when combined with S (SIS)
}


def decode_tag(tag: str) -> Optional[dict]:
    """
    Decode an ISA-5.1 instrument tag.

    Args:
        tag: Full instrument tag (e.g., "200-FIT-01A")

    Returns:
        Dictionary with decoded components, or None if invalid
    """
    # Pattern: {AREA}-{LETTERS}-{NUMBER}{SUFFIX}
    pattern = r"^(\d{3})-([A-Z]+)-(\d+)([A-Z]?)$"
    match = re.match(pattern, tag.upper())

    if not match:
        return None

    area, letters, loop_number, suffix = match.groups()

    # Parse letters into variable + function + modifier
    if len(letters) < 2:
        return None

    variable = letters[0]
    function = ""
    modifier = ""

    # Extract function letters (IT, IC, T, etc.)
    remaining = letters[1:]
    i = 0
    while i < len(remaining):
        char = remaining[i]
        # Check if this is a modifier (H, L, A at the end)
        if char in ["H", "L", "A"] and i == len(remaining) - 1:
            modifier = char
        else:
            function += char
        i += 1

    # Get variable name
    variable_name = FIRST_LETTERS.get(variable, "Unknown")

    # Get function names
    function_names = [SUCCEEDING_LETTERS.get(c, "Unknown") for c in function]

    # Determine category
    category = "primary"
    for func_char in function:
        if func_char in CATEGORY_RULES:
            category = CATEGORY_RULES[func_char]
            break

    # Construct loop_id
    loop_id = f"{variable}{function}-{loop_number}"

    return {
        "area": area,
        "variable": variable,
        "variable_name": variable_name,
        "function": function,
        "function_names": function_names,
        "modifier": modifier,
        "loop_number": loop_number,
        "suffix": suffix,
        "category": category,
        "loop_id": loop_id,
        "full_tag": tag.upper(),
    }


def validate_tag(tag: str) -> tuple[bool, str]:
    """
    Validate an ISA-5.1 tag.

    Returns:
        Tuple of (is_valid, error_message)
    """
    result = decode_tag(tag)
    if result is None:
        return False, f"Invalid tag format: {tag}"

    if result["variable"] not in FIRST_LETTERS:
        return False, f"Invalid first letter: {result['variable']}"

    for c in result["function"]:
        if c not in SUCCEEDING_LETTERS:
            return False, f"Invalid function letter: {c}"

    return True, ""


def generate_tag(area: str, variable: str, function: str, loop_number: str,
                 modifier: str = "", suffix: str = "") -> str:
    """
    Generate a full tag from components.
    """
    parts = f"{area}-{variable}{function}{modifier}-{loop_number}{suffix}"
    return parts.upper()


def main():
    parser = argparse.ArgumentParser(description="Decode ISA-5.1 instrument tags")
    parser.add_argument("tag", nargs="?", help="Tag to decode")
    parser.add_argument("--tag", "-t", dest="tag_opt", help="Tag to decode (alternative)")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument("--validate", "-v", action="store_true", help="Validate only")
    args = parser.parse_args()

    tag = args.tag or args.tag_opt
    if not tag:
        parser.print_help()
        sys.exit(1)

    if args.validate:
        is_valid, error = validate_tag(tag)
        if is_valid:
            print(f"Valid: {tag}")
            sys.exit(0)
        else:
            print(f"Invalid: {error}")
            sys.exit(1)

    result = decode_tag(tag)
    if result is None:
        print(f"Error: Could not parse tag '{tag}'")
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Tag: {result['full_tag']}")
        print(f"  Area: {result['area']}")
        print(f"  Variable: {result['variable']} ({result['variable_name']})")
        print(f"  Function: {result['function']} ({', '.join(result['function_names'])})")
        if result['modifier']:
            print(f"  Modifier: {result['modifier']}")
        print(f"  Loop: {result['loop_number']}")
        if result['suffix']:
            print(f"  Suffix: {result['suffix']}")
        print(f"  Category: {result['category']}")
        print(f"  Loop ID: {result['loop_id']}")


if __name__ == "__main__":
    main()
