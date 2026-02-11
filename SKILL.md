---
name: instrument-io-skill
description: |
  Generate Instrument Index and IO List from P&ID sources (DEXPI XML or PDF).
  Unified YAML database as source of truth with Excel deliverables.
  Supports auto-generation of IO patterns for motors, pumps, valves.
  Use when: (1) Creating instrument index from P&ID, (2) Generating IO list for PLC,
  (3) Calculating DI/DO/AI/AO/PI/PO counts with spare capacity, (4) Cross-referencing
  instruments with equipment list, (5) Extracting instrumentation from DEXPI XML.
---

# Instrument Index & IO List Skill

Tier 2 skill: Generate Instrument Index and IO List using YAML as source of truth.

## Workflow

1. **Extract instruments** from DEXPI XML or PDF P&ID
2. **Define loops** as first-class entities (ISA 5.1)
3. **Auto-generate IO patterns** from equipment list (DOL/VFD/valves)
4. **Validate database** using `scripts/validate_project.py`
5. **Generate Excel deliverables**
6. **Register artifacts** in project registry

## Input Requirements

- DEXPI XML files (from engineering-mcp-server) OR
- PDF P&ID (Claude Code extracts via vision)
- `equipment-list.qmd` for IO pattern auto-generation (optional)

## Output Artifacts

| Artifact | Path | Description |
|----------|------|-------------|
| Database | `instruments/database.yaml` | Source of truth |
| Index | `instruments/instrument-index.xlsx` | 19-column Excel |
| IO List | `instruments/io-list.xlsx` | 17-column Excel |
| Summary | `instruments/io-summary.xlsx` | DI/DO/AI/AO/PI/PO counts |

## Quick Start

### From DEXPI XML (via MCP Server)

Use the engineering-mcp-server DEXPI tools:

```
1. Load DEXPI file: dexpi_import_proteus_xml(directory_path="pids", filename="PID-001.xml")
2. Query model: model_id from step 1
3. Extract instruments via: search_by_type(model_id=model_id, component_type="ProcessInstrumentationFunction")
   OR search the model's conceptualModel.processInstrumentationFunctions directly
4. Extract to YAML using the mapping in references/dexpi-mapping.md
```

Note: `dexpi_get_instrumentation()` was deprecated. Use `search_by_type()` with component_type="ProcessInstrumentationFunction" instead.

### From PDF P&ID

Prompt Claude Code:
> "Extract instruments from /path/to/project/pids/PID-001.pdf to database.yaml"

### Auto-generate Motor/Pump IO

```bash
python scripts/apply_io_patterns.py --database database.yaml --equipment submittals/equipment-list.qmd
python scripts/apply_io_patterns.py -d database.yaml -e equipment-list.qmd --strict
```

**Requires**: Equipment list with `feeder_type` field (from `equipment-list-skill`).

### Validate Database

```bash
python scripts/validate_project.py --instruments database.yaml --loops loops.yaml --strict
```

### Generate Excel Outputs

```bash
python scripts/generate_instrument_index.py --database database.yaml
python scripts/generate_io_list.py --database database.yaml
python scripts/generate_io_summary.py --database database.yaml --spare-pct 20
```

## Loop Entity (ISA 5.1 Compliance)

**Critical concept:** A Loop is the first-class entity per ISA 5.1. All instruments/valves in a control loop share the same loop number.

### Loop Definition

```yaml
# First, define loops
loops:
  - loop_key: "200-F-01"
    tag_area: 200
    loop_number: 1
    variable: "F"
    process_unit_type: "secondary_treatment.aerobic_biological_treatment.aeration_tank"
    service: "Permeate Flow"

  - loop_key: "300-L-05"
    tag_area: 300
    loop_number: 5
    variable: "L"
    process_unit_type: "tertiary_treatment.reverse_osmosis.conventional_ro"
    service: "RO Feed Tank Level"
```

### Instruments Reference Loops

```yaml
instruments:
  # Transmitter
  - instrument_id: "uuid-1"
    loop_key: "200-F-01"      # FK to Loop
    functions: ["I", "T"]     # ISA succeeding letters → "FIT"
    full_tag: "200-FIT-01"    # Rendered from loop + functions
    equipment_tag: "200-P-01"
    process_unit_type: "secondary_treatment.aerobic_biological_treatment.aeration_tank"

  # Controller
  - instrument_id: "uuid-2"
    loop_key: "200-F-01"      # Same loop!
    functions: ["I", "C"]     # → "FIC"
    full_tag: "200-FIC-01"

  # Valve (IS an instrument with function V)
  - instrument_id: "uuid-3"
    loop_key: "200-F-01"      # Same loop!
    functions: ["V"]          # → "FV"
    full_tag: "200-FV-01"
    valve_body_type: "butterfly"   # Metadata only
    fail_position: "closed"
```

**All devices in same loop share `loop_key`**. Tag is rendered: `{tag_area}-{variable}{functions}-{loop_number}`

## Valves ARE Instruments

Per ISA 5.1, valves are tagged by **controlled variable**, NOT by body type.

| Tag | Meaning | Controlled Variable |
|-----|---------|---------------------|
| `200-FV-01` | Flow Valve | F = Flow |
| `200-LCV-01` | Level Control Valve | L = Level |
| `200-PV-01` | Pressure Valve | P = Pressure |
| `200-XV-01` | On/Off Valve | X = Unclassified |
| `200-HV-01` | Hand Valve | H = Manual |

Body type (butterfly, ball, gate) stored in `valve_body_type` metadata field.

See `assets/catalogs/valve_catalog.yaml` for body types and roles.

## Schema Structure

Database follows `schemas/instrument-database.schema.yaml`:

```yaml
project_id: "PRJ-2025-001-MBR-12MLD"
revision:
  number: "A"
  date: "2025-01-02"
  by: "HVK"

loops:
  - loop_key: "200-F-01"
    tag_area: 200
    loop_number: 1
    variable: "F"
    service: "Permeate Flow"
    process_unit_type: "secondary_treatment.aerobic_biological_treatment.secondary_clarification.submerged_membrane_bioreactor"

instruments:
  - instrument_id: "uuid"
    loop_key: "200-F-01"
    functions: ["I", "T"]
    full_tag: "200-FIT-01"
    equipment_tag: "200-P-01"
    service_description: "Permeate Flow"
    process_unit_type: "secondary_treatment.aerobic_biological_treatment.secondary_clarification.submerged_membrane_bioreactor"
    primary_signal_type: "4-20mA"
    io_signals:
      - io_point_id: "uuid"
        signal_function: "Measurement"
        io_type: "AI"
        signal_type: "4-20mA"
```

Key fields:
- `loop_key`: FK to Loop entity (replaces legacy `loop_id`)
- `functions`: Array of ISA succeeding letters
- `full_tag`: Rendered tag (for display)
- `process_unit_type`: FK to taxonomy
- `marshalling`: cabinet/card/channel/terminal
- `analyte`: For analyzers (pH, DO, Conductivity, etc.)

## Analyzer Tagging (ISA-compliant)

Use ISA first letter `A` for all analyzers. Store analyte type in metadata:

| Tag | Analyte | Service |
|-----|---------|---------|
| `200-AIT-01` | pH | Effluent pH |
| `200-AIT-02` | DO | Aeration DO |
| `200-AIT-03` | Conductivity | Permeate quality |
| `200-AIT-04` | Turbidity | Effluent turbidity |

```yaml
- instrument_id: "uuid"
  loop_key: "200-A-01"
  functions: ["I", "T"]
  full_tag: "200-AIT-01"
  analyte: "pH"                    # What's being measured
  measurement_method: "electrode"   # Optional
```

See `assets/catalogs/instrument_letter_extensions.yaml` for analyte types.

## IO Patterns

20 standard patterns for auto-generation. See `templates/io-patterns.yaml`.

| Pattern | IO Count | Use For |
|---------|----------|---------|
| pump_dol | 4 (3DI, 1DO) | DOL started motors |
| pump_vfd | 6 (3DI, 1DO, 1AI, 1AO) | VFD controlled motors |
| pump_vfd_extended | 8 (4DI, 1DO, 2AI, 1AO) | VFD with current feedback |
| motor_soft_starter | 5 (4DI, 1DO) | Soft-starter motors |
| metering_pump_speed | 5 (3DI, 1DO, 1AO) | Chemical dosing (speed only) |
| metering_pump_full | 6 (3DI, 1DO, 2AO) | Chemical dosing (speed+stroke) |
| valve_onoff_pneumatic | 3 (2DI, 1DO) | Pneumatic on/off valves |
| valve_onoff_electric | 4 (2DI, 2DO) | Electric on/off valves |
| valve_modulating_pneumatic | 3 (1DI, 1AI, 1AO) | Pneumatic modulating valves |
| valve_modulating_electric | 3 (1DI, 1AI, 1AO) | Electric modulating valves |
| valve_positioner | 4 (2DI, 1AI, 1AO) | Valves with positioner |
| transmitter_4_20 | 1 AI | Standard 4-20mA transmitters |
| transmitter_hart | 1 PI | HART protocol devices |
| analyzer_modbus | 1 PI | Modbus analyzers |
| level_switch | 1 DI | Level switches |

Pattern mapping uses explicit `feeder_type` values from equipment list.
See `assets/catalogs/feeder_types.yaml` for complete mapping.

## Validation

Run before generating deliverables:

```bash
python scripts/validate_project.py \
  --instruments database.yaml \
  --loops loops.yaml \
  --strict
```

Validates:
- Instrument tags follow ISA letter grammar
- All devices in same loop share loop_key
- loop_key format: `^[0-9]{3}-[A-Z]-[0-9]{2,4}$`
- process_unit_type exists in taxonomy
- Equipment cross-references resolve

## References

| Reference | Content |
|-----------|---------|
| `references/isa-5.1-2024-guide.md` | ISA function letters + decoder |
| `references/dexpi-mapping.md` | DEXPI to schema field mapping |
| `references/io-patterns-guide.md` | Pattern selection guide |
| `references/engineering-units.yaml` | Unit normalization catalog |

## Dependencies

```bash
pip install pyyaml openpyxl jsonschema
```

For DEXPI extraction, use `engineering-mcp-server` (includes pyDEXPI tools).

## Integration

**Upstream (required input)**:
- `equipment-list-skill` → provides `equipment-list.qmd` with `feeder_type` field
- `engineering-mcp-server` → DEXPI extraction tools (for XML P&IDs)

**Downstream (outputs)**:
- Excel artifacts for procurement/control system design
- `control-philosophy-skill` consumes `instruments/database.yaml`

**Handoff contract**: Equipment list must include `feeder_type` for all motors, pumps, blowers, mixers, and control valves. Missing values will generate warnings (or errors with `--strict`).

## Bundled Resources

### Scripts
- `scripts/apply_io_patterns.py` - Auto-generate IO from equipment
- `scripts/generate_instrument_index.py` - Create instrument index Excel
- `scripts/generate_io_list.py` - Create IO list Excel
- `scripts/generate_io_summary.py` - IO count summary
- `scripts/decode_isa_tag.py` - Decode ISA tag letters
- `scripts/validate_project.py` - Validate tags, loops, cross-refs

### References
- `references/isa-5.1-2024-guide.md` - ISA letter reference
- `references/dexpi-mapping.md` - DEXPI extraction mapping
- `references/io-patterns-guide.md` - Pattern selection

### Assets
- `assets/catalogs/isa_5_1_instrument_letters.yaml` - ISA letters
- `assets/catalogs/valve_catalog.yaml` - Valve body types
- `assets/catalogs/feeder_types.yaml` - IO patterns
- `assets/schemas/loop.schema.yaml` - Loop entity schema
- `assets/schemas/tag-format.schema.yaml` - Tag patterns
