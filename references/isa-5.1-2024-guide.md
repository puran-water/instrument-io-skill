# ISA-5.1-2024 Function Letters Reference

Quick reference for ISA instrument tag interpretation and construction.

## Tag Structure

```
{AREA}-{VARIABLE}{FUNCTION}{MODIFIER}-{LOOP}{SUFFIX}

Example: 200-FIT-01A
- Area: 200
- Variable: F (Flow)
- Function: IT (Indicating Transmitter)
- Loop: 01
- Suffix: A (redundant unit)
```

## First Letter (Measured Variable)

| Letter | Variable |
|--------|----------|
| A | Analysis (composition, pH, conductivity) |
| B | Burner, Combustion |
| C | Conductivity (or User's choice) |
| D | Density, Specific Gravity |
| E | Voltage |
| F | Flow Rate |
| G | Gaging, Position, Length |
| H | Hand (manual) |
| I | Current (electrical) |
| J | Power |
| K | Time, Time Schedule |
| L | Level |
| M | Moisture, Humidity |
| N | User's Choice |
| O | User's Choice |
| P | Pressure, Vacuum |
| Q | Quantity, Totalizer |
| R | Radiation |
| S | Speed, Frequency |
| T | Temperature |
| U | Multivariable |
| V | Vibration |
| W | Weight, Force |
| X | Unclassified |
| Y | Event, State, Presence |
| Z | Position, Dimension |

## Succeeding Letters (Function)

| Letter | Function | Typical Use |
|--------|----------|-------------|
| A | Alarm | Audible/visual alarm |
| B | User's Choice | - |
| C | Control | Controller function |
| D | Differential | Differential measurement |
| E | Sensing Element | Primary element |
| G | Glass, Viewing | Sight glass |
| H | High | High limit |
| I | Indicate | Local indication |
| K | Control Station | HMI panel |
| L | Low, Light | Low limit |
| M | Middle, Intermediate | Mid-range |
| N | User's Choice | - |
| O | Orifice, Restriction | Flow element |
| P | Point (test) | Test connection |
| Q | Integrate, Totalize | Totalizer function |
| R | Record | Recording function |
| S | Switch, Safety | Discrete switch |
| T | Transmit | Transmitter |
| U | Multifunction | Combined functions |
| V | Valve, Damper | Final control element |
| W | Well | Thermowell |
| X | Unclassified | Special |
| Y | Relay, Compute | Logic/compute |
| Z | Driver, Actuator | Final element |

## Common Tag Patterns

| Tag | Meaning | IO Pattern |
|-----|---------|------------|
| FIT | Flow Indicating Transmitter | transmitter_4_20 |
| FIC | Flow Indicating Controller | transmitter_4_20 + valve |
| FCV | Flow Control Valve | valve_modulating_* |
| FE | Flow Element (orifice) | - (no IO) |
| FT | Flow Transmitter | transmitter_4_20 |
| LIT | Level Indicating Transmitter | transmitter_4_20 |
| LSH | Level Switch High | level_switch |
| LSL | Level Switch Low | level_switch |
| PIT | Pressure Indicating Transmitter | transmitter_4_20 |
| PSH | Pressure Switch High | pressure_switch |
| PSL | Pressure Switch Low | pressure_switch |
| TIT | Temperature Indicating Transmitter | transmitter_4_20 |
| AIT | Analyzer Indicating Transmitter | transmitter_4_20 or analyzer_modbus |
| ZSO | Position Switch Open | (part of valve pattern) |
| ZSC | Position Switch Closed | (part of valve pattern) |

## Modifier Letters

| Modifier | Meaning |
|----------|---------|
| H | High |
| L | Low |
| HH | High-High |
| LL | Low-Low |
| A | Alarm |
| S | Safety |
| D | Differential |

## Category Classification

Use `tag.category` to classify instruments:

| Category | Description | Example |
|----------|-------------|---------|
| primary | Measurement/sensing | FE, TE, PE |
| indicating | Local display | FI, LI, PI |
| recording | Trend recording | FR, LR, PR |
| transmitting | Remote signal | FIT, LIT, PIT |
| controlling | Loop control | FIC, LIC, PIC |
| switching | Discrete logic | FSH, LSL, PSH |
| safety | SIS/ESD | FSL, LSHH, PSLL |

## Tag Decoder Logic

Use `scripts/decode_isa_tag.py` for programmatic parsing:

```python
from decode_isa_tag import decode_tag

result = decode_tag("200-FIT-01A")
# Returns:
# {
#     "area": "200",
#     "variable": "F",
#     "variable_name": "Flow Rate",
#     "function": "IT",
#     "function_names": ["Indicate", "Transmit"],
#     "modifier": "",
#     "loop_number": "01",
#     "suffix": "A",
#     "category": "transmitting",
#     "full_tag": "200-FIT-01A"
# }
```

## WWTP-Specific Tags

Common tags in wastewater applications:

| Tag | Application |
|-----|-------------|
| FIT-xxx | Influent/effluent flow |
| LIT-xxx | Tank level |
| PIT-xxx | Pressure monitoring |
| TIT-xxx | Temperature |
| AIT-xxx | pH, DO, turbidity, chlorine |
| MLSS | Mixed liquor suspended solids |
| ORP | Oxidation-reduction potential |
