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
2. **Auto-generate IO patterns** from equipment list (DOL/VFD/valves)
3. **Validate database** against schema
4. **Generate Excel deliverables**
5. **Register artifacts** in project registry

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
1. Load DEXPI file: dexpi_import_proteus_xml(file_path="pids/PID-001.xml")
2. Query instruments: dexpi_get_instrumentation()
3. Extract to YAML using the mapping in references/dexpi-mapping.md
```

See `references/dexpi-mapping.md` for DEXPI class to schema field mapping.

### From PDF P&ID

Prompt Claude Code:
> "Extract instruments from /path/to/project/pids/PID-001.pdf to database.yaml"

Claude reads the PDF directly and generates YAML entries.

### Auto-generate Motor/Pump IO

```bash
python scripts/apply_io_patterns.py --database database.yaml --equipment submittals/equipment-list.qmd
python scripts/apply_io_patterns.py -d database.yaml -e equipment-list.qmd --strict  # Fail on missing feeder_type
```

**Requires**: Equipment list with `feeder_type` field (from `equipment-list-skill`).

Pattern mapping uses explicit `feeder_type` values:
- Motors/Pumps: `DOL`, `VFD`, `VFD-EXT`, `SOFT-STARTER`, `VENDOR`, `AODD`, `METERING`
- Valves: `MOD-ELECTRIC`, `MOD-PNEUMATIC`, `ONOFF-ELECTRIC`, `ONOFF-PNEUMATIC`, `POSITIONER`

See `equipment-list-skill` for complete feeder type reference.

### Validate Database

```bash
python scripts/validate_database.py --database database.yaml
python scripts/sync_cross_refs.py --database database.yaml --equipment equipment-list.qmd
```

### Generate Excel Outputs

```bash
python scripts/generate_instrument_index.py --database database.yaml
python scripts/generate_io_list.py --database database.yaml
python scripts/generate_io_summary.py --database database.yaml --spare-pct 20
```

### Decode ISA Tags

```bash
python scripts/decode_isa_tag.py 200-FIT-01
```

## IO Patterns

20 standard patterns for auto-generation. See `templates/io-patterns.yaml`.

| Pattern | IO Count | Use For |
|---------|----------|---------|
| pump_dol | 4 (3DI, 1DO) | DOL started motors |
| pump_vfd | 6 (3DI, 1DO, 1AI, 1AO) | VFD controlled motors |
| pump_vfd_extended | 8 (4DI, 1DO, 2AI, 1AO) | VFD with current feedback |
| motor_soft_starter | 5 (4DI, 1DO) | Soft-starter motors |
| aodd_pump | 3 (2DI, 1DO) | Air-operated diaphragm pumps |
| metering_pump_speed | 5 (3DI, 1DO, 1AO) | Chemical dosing (speed only) |
| metering_pump_full | 6 (3DI, 1DO, 2AO) | Chemical dosing (speed+stroke) |
| valve_onoff_pneumatic | 3 (2DI, 1DO) | Pneumatic on/off valves |
| valve_onoff_electric | 4 (2DI, 2DO) | Electric on/off valves |
| valve_modulating_electric | 3 (1DI, 1AI, 1AO) | Electric modulating valves |
| valve_modulating_pneumatic | 3 (1DI, 1AI, 1AO) | Pneumatic modulating valves |
| valve_positioner | 4 (2DI, 1AI, 1AO) | Valves with positioner |
| solenoid_valve | 2 (1DI, 1DO) | Simple solenoid valves |
| transmitter_4_20 | 1 AI | Standard 4-20mA transmitters |
| transmitter_hart | 1 PI | HART protocol devices |
| analyzer_modbus | 1 PI | Modbus analyzers |
| analyzer_multi | 3 (1DI, 2AI) | Multi-signal analyzers |
| level_switch | 1 DI | Level switches |
| pressure_switch | 1 DI | Pressure switches |
| esd_interlock | 3 (2DI, 1DO) | Safety/ESD devices |

See `references/io-patterns-guide.md` for selection guidance.

## Schema Structure

Database follows `schemas/instrument-database.schema.yaml`:

```yaml
project_id: "PRJ-2025-001-MBR-12MLD"
revision:
  number: "A"
  date: "2025-01-02"
  by: "HVK"
instruments:
  - instrument_id: "uuid"
    loop_id: "FIT-01"
    tag:
      area: "200"
      variable: "F"
      function: "IT"
      loop_number: "01"
      full_tag: "200-FIT-01"
    equipment_tag: "200-P-01"
    service_description: "Permeate Flow"
    primary_signal_type: "4-20mA"
    io_signals:
      - io_point_id: "uuid"
        signal_function: "Measurement"
        io_type: "AI"
        signal_type: "4-20mA"
```

Key fields per Codex review:
- `io_point_id` / `loop_id` for unique identification
- `marshalling` (cabinet/card/channel/terminal)
- `primary_signal_type` (required, explicit - not derived from io_signals)
- `pipeline_tag` for line-mounted instruments
- `electrical.feeder_type` (DOL, VFD, Soft-Starter, Vendor Panel)

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
- Does NOT emit `plant_state_out` (Tier 2 deliverable skill)

**Handoff contract**: Equipment list must include `feeder_type` for all motors, pumps, blowers, mixers, and control valves. Missing values will generate warnings (or errors with `--strict`).
