# IO Patterns Selection Guide

Select the appropriate IO pattern based on equipment type and control requirements.

## Pattern Selection Decision Tree

```
Is it a motor/pump?
├── Yes → What starter type?
│   ├── DOL (Direct-On-Line) → pump_dol (4 IO)
│   ├── Soft-Starter → motor_soft_starter (5 IO)
│   ├── VFD (basic) → pump_vfd (6 IO)
│   ├── VFD (with current feedback) → pump_vfd_extended (8 IO)
│   ├── AODD (air-operated) → aodd_pump (3 IO)
│   └── Metering pump?
│       ├── Speed control only → metering_pump_speed (5 IO)
│       └── Speed + stroke length → metering_pump_full (6 IO)
│
├── Is it a valve?
│   ├── ON/OFF valve?
│   │   ├── Electric actuator → valve_onoff_electric (4 IO)
│   │   ├── Pneumatic actuator → valve_onoff_pneumatic (3 IO)
│   │   └── Solenoid (simple) → solenoid_valve (2 IO)
│   └── Modulating valve?
│       ├── Electric actuator → valve_modulating_electric (3 IO)
│       ├── Pneumatic with I/P → valve_modulating_pneumatic (3 IO)
│       └── With positioner + limits → valve_positioner (4 IO)
│
├── Is it a transmitter?
│   ├── Standard 4-20mA → transmitter_4_20 (1 AI)
│   ├── HART enabled → transmitter_hart (1 PI)
│   └── Modbus protocol → analyzer_modbus (1 PI)
│
├── Is it an analyzer?
│   ├── Single output → transmitter_4_20 (1 AI)
│   ├── Modbus output → analyzer_modbus (1 PI)
│   └── Multi-signal (with temp) → analyzer_multi (3 IO)
│
├── Is it a discrete switch?
│   ├── Level switch → level_switch (1 DI)
│   └── Pressure switch → pressure_switch (1 DI)
│
└── Is it a safety device?
    └── ESD/Interlock → esd_interlock (3 IO)
```

## Patterns by IO Count

| IO Count | Patterns |
|----------|----------|
| 1 | transmitter_4_20, transmitter_hart, analyzer_modbus, level_switch, pressure_switch |
| 2 | solenoid_valve |
| 3 | aodd_pump, valve_onoff_pneumatic, valve_modulating_electric, valve_modulating_pneumatic, analyzer_multi, esd_interlock |
| 4 | pump_dol, valve_onoff_electric, valve_positioner |
| 5 | metering_pump_speed, motor_soft_starter |
| 6 | pump_vfd, metering_pump_full |
| 8 | pump_vfd_extended |

## Pattern Details

### Motor Patterns

| Pattern | When to Use |
|---------|-------------|
| `pump_dol` | Standard DOL-started motors without speed control |
| `pump_vfd` | VFD-controlled motors with speed feedback |
| `pump_vfd_extended` | VFD motors requiring current monitoring (high-power) |
| `motor_soft_starter` | Soft-starter equipped motors |
| `aodd_pump` | Air-operated diaphragm pumps |
| `metering_pump_speed` | Chemical dosing pumps with stroke speed control |
| `metering_pump_full` | Chemical dosing pumps with speed + stroke length |

### Valve Patterns

| Pattern | When to Use |
|---------|-------------|
| `valve_onoff_electric` | MOV (motor-operated valve) with open/close commands |
| `valve_onoff_pneumatic` | Pneumatic actuator with single solenoid |
| `valve_modulating_electric` | Electric actuator with analog position control |
| `valve_modulating_pneumatic` | Pneumatic actuator with I/P positioner |
| `valve_positioner` | Any valve with smart positioner and limit switches |
| `solenoid_valve` | Simple 2-way solenoid valves |

### Transmitter Patterns

| Pattern | When to Use |
|---------|-------------|
| `transmitter_4_20` | Standard analog transmitters (flow, level, pressure, temp) |
| `transmitter_hart` | HART-enabled transmitters with digital communication |
| `analyzer_modbus` | Process analyzers with Modbus serial/TCP |
| `analyzer_multi` | Analyzers with multiple outputs (primary + compensation) |

### Discrete Patterns

| Pattern | When to Use |
|---------|-------------|
| `level_switch` | High/low level alarms |
| `pressure_switch` | High/low pressure alarms |
| `esd_interlock` | Emergency shutdown devices, safety interlocks |

## Equipment Type to Pattern Mapping

Used by `apply_io_patterns.py` when reading from equipment list:

| Equipment Type Code | Default Pattern | Override Conditions |
|---------------------|-----------------|---------------------|
| P (Pump) | pump_dol | If VFD in description → pump_vfd |
| B (Blower) | pump_vfd | High power → pump_vfd_extended |
| MX (Mixer) | pump_dol | If VFD → pump_vfd |
| CV (Control Valve) | valve_modulating_pneumatic | If electric → valve_modulating_electric |
| MOV | valve_onoff_electric | - |
| SOV | solenoid_valve | - |
| FIT, LIT, PIT, TIT | transmitter_4_20 | If HART → transmitter_hart |
| AIT | analyzer_modbus | If 4-20mA → transmitter_4_20 |
| LSH, LSL | level_switch | - |
| PSH, PSL | pressure_switch | - |

## Override Examples

When equipment list says "VFD" but you need extended monitoring:

```yaml
# In database.yaml, after apply_io_patterns.py:
instruments:
  - tag:
      full_tag: "200-P-01"
    io_signals:
      # ... generated from pump_vfd ...
      # Add current feedback manually:
      - io_point_id: "uuid"
        suffix: "II"
        function: Measurement
        io_type: AI
        signal_type: "4-20mA"
        description: "Current Feedback"
```

## Composite Patterns

Some equipment requires multiple patterns:

| Equipment | Patterns Needed |
|-----------|-----------------|
| Flow control loop | transmitter_4_20 + valve_modulating_* |
| Level control with high alarm | transmitter_4_20 + level_switch |
| VFD pump with pressure trip | pump_vfd + pressure_switch |
