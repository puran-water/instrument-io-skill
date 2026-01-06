# DEXPI to Instrument Schema Mapping

Maps DEXPI XML elements (via pyDEXPI) to instrument-database schema fields.

## DEXPI Classes for Instrumentation

DEXPI uses Proteus XML schema. Key classes for instrumentation:

```
ProcessInstrumentationFunction
├── ProcessInstrumentationFunctionNumber
├── ProcessInstrumentationFunctionCategory
├── ProcessInstrumentationFunctionModifier
├── ProcessInstrumentationFunctionClass
└── Associations
    ├── Equipment
    ├── PipingComponent
    └── SignalLine
```

## Field Mappings

### Identification Fields

| Schema Field | DEXPI Source | Notes |
|--------------|--------------|-------|
| `tag.full_tag` | `ProcessInstrumentationFunction.TagName` | Primary tag |
| `tag.area` | Parse from TagName | First 3 digits |
| `tag.variable` | `ProcessInstrumentationFunctionCategory.FirstLetter` | ISA variable |
| `tag.function` | `ProcessInstrumentationFunctionCategory.SucceedingLetters` | ISA function |
| `tag.modifier` | `ProcessInstrumentationFunctionModifier` | H, L, A, etc. |
| `tag.loop_number` | Parse from TagName | Numeric portion |
| `loop_key` | Computed | `{area}-{variable}-{loop_number}` (e.g., "200-F-01") |

### Equipment Association

| Schema Field | DEXPI Source |
|--------------|--------------|
| `equipment_tag` | `Association[@type='Equipment'].TagName` |
| `pipeline_tag` | `Association[@type='PipingComponent'].TagName` |

### Service Description

| Schema Field | DEXPI Source |
|--------------|--------------|
| `service_description` | `ProcessInstrumentationFunction.Remarks` or computed |

### Location

| Schema Field | DEXPI Source |
|--------------|--------------|
| `location.pid_reference` | Drawing number from file metadata |
| `location.physical_location` | `PanelIdentificationCode` → "Panel", else "Field" |

### Device Specification

| Schema Field | DEXPI Source |
|--------------|--------------|
| `device.type` | `ProcessInstrumentationFunctionClass` mapping |
| `device.manufacturer` | `ManufacturerIdentificationCode` |
| `device.model` | `ModelNumber` |

### Measurement

| Schema Field | DEXPI Source |
|--------------|--------------|
| `measurement.measured_variable` | Derived from `tag.variable` |
| `measurement.range_min` | `NormalOperatingMinimum.Value` |
| `measurement.range_max` | `NormalOperatingMaximum.Value` |
| `measurement.range_unit` | `NormalOperatingMinimum.Units` |

## ProcessInstrumentationFunctionClass Mapping

| DEXPI Class | device.type |
|-------------|-------------|
| FlowMeter | Electromagnetic Flow Meter |
| LevelTransmitter | Level Transmitter |
| PressureTransmitter | Pressure Transmitter |
| TemperatureTransmitter | Temperature Transmitter |
| AnalyzerTransmitter | Analyzer |
| ControlValve | Control Valve |
| OnOffValve | On/Off Valve |
| PressureSwitch | Pressure Switch |
| LevelSwitch | Level Switch |
| TemperatureSwitch | Temperature Switch |

## pyDEXPI Access Pattern

```python
from pydexpi import ProteusSerializer

# Load DEXPI file
model = ProteusSerializer.from_file("pid.xml")

# Get all instrumentation
for pif in model.get_elements_by_type("ProcessInstrumentationFunction"):
    tag = pif.TagName
    category = pif.ProcessInstrumentationFunctionCategory

    # Get equipment association
    equipment = pif.get_associated_equipment()

    # Build instrument entry
    instrument = {
        "tag": {
            "full_tag": tag,
            "area": tag.split("-")[0],
            # ... parse remaining fields
        },
        "equipment_tag": equipment.TagName if equipment else None,
        # ...
    }
```

## Signal Line Extraction

DEXPI SignalLine elements can indicate IO type:

| SignalLine.SignalType | io_type | signal_type |
|-----------------------|---------|-------------|
| Electrical.Analog | AI/AO | 4-20mA |
| Electrical.Binary | DI/DO | 24V DC |
| Pneumatic | - | - |
| Fieldbus.HART | PI | HART |
| Fieldbus.Modbus | PI | Modbus RTU |

## Unsupported Elements

Flag these for manual entry:

- Custom instrument classes not in mapping
- Instruments without `ProcessInstrumentationFunctionCategory`
- Signal lines without `SignalType` attribute
- Multi-variable instruments (split into multiple entries)

## Integration with engineering-mcp-server

Use MCP tools for extraction:

```
dexpi_load_model --input pid.xml
dexpi_get_instrumentation --model-id <id>
```

Returns structured JSON that maps directly to instrument schema.
