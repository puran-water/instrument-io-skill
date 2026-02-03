# Instrument Index & IO List Skill

Claude Code skill for generating instrument indexes and IO lists from P&ID sources (DEXPI XML or PDF).

## Quick Start

### Prerequisites

1. P&ID source: DEXPI XML (via dexpi-sfiles-mcp-server) or PDF
2. Equipment list from `equipment-list-skill` (optional, for IO pattern auto-generation)

### Basic Workflow

1. Extract instruments from P&ID source
2. Define loops as ISA 5.1 entities
3. Auto-generate IO patterns: `python scripts/apply_io_patterns.py`
4. Generate Excel deliverables

## Documentation

See [SKILL.md](SKILL.md) for complete documentation including:

- Loop entity model (ISA 5.1)
- Instrument tagging conventions
- IO pattern catalog
- Valve tagging rules
- DEXPI extraction mapping

## Workflow Integration

This skill is part of the puran-water instrumentation and control workflow:

```
                                ┌──────────────────────────┐
                                │  P&ID Source             │
                                │  (DEXPI XML or PDF)      │
                                └──────────────────────────┘
                                             │
                                             ▼
┌─────────────────────────┐     ┌──────────────────────────┐     ┌─────────────────────┐
│  equipment-list-skill   │ ──► │  instrument-io-skill     │ ──► │  csa-diagram-skill  │
│  (feeder_type for IO)   │     │  (this skill)            │     │  (CSA generation)   │
└─────────────────────────┘     └──────────────────────────┘     └─────────────────────┘
                                             │
                                             ▼
                                ┌──────────────────────────┐
                                │ Outputs:                 │
                                │ - database.yaml          │
                                │ - instrument-index.xlsx  │
                                │ - io-list.xlsx           │
                                │ - io-summary.xlsx        │
                                └──────────────────────────┘
```

## Related

### Upstream
- [equipment-list-skill](https://github.com/puran-water/equipment-list-skill) - Equipment lists with feeder types for IO pattern generation
- [dexpi-sfiles-mcp-server](https://github.com/puran-water/dexpi-sfiles-mcp-server) - DEXPI extraction tools

### Downstream
- [csa-diagram-skill](https://github.com/puran-water/csa-diagram-skill) - Control System Architecture diagrams
- [plantuml-csa-mcp-server](https://github.com/puran-water/plantuml-csa-mcp-server) - CSA MCP server

## License

MIT License - Puran Water
