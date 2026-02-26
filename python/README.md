# Python Layer — Observation, API, and LLM Integration

The Python layer wraps the standalone COBOL banking system with three capabilities:

1. **Bridge + Integrity** (Layer 2) — Subprocess execution, DAT file I/O, SQLite sync, SHA-256 hash chains
2. **REST API** (Layer 3) — FastAPI endpoints exposing all banking, codegen, and chain operations
3. **LLM Tool-Use** (Layer 3) — AI chatbot with RBAC-gated tool execution (Ollama local / Anthropic cloud)

## Module Overview

| Package | Files | Purpose |
|---------|-------|---------|
| `python/` | `bridge.py`, `integrity.py`, `settlement.py`, `cross_verify.py`, `simulator.py`, `cli.py`, `auth.py` | Core bridge, integrity, settlement, RBAC |
| `python/api/` | `app.py`, `models.py`, `dependencies.py`, `routes_*.py` | FastAPI REST layer |
| `python/llm/` | `tools.py`, `tool_executor.py`, `providers.py`, `conversation.py`, `audit.py` | LLM tool-use architecture |
| `python/cobol_codegen/` | `ast_nodes.py`, `parser.py`, `generator.py`, `templates.py`, `editor.py`, `validator.py` | AST-based COBOL code generation |
| `python/tests/` | 12 test files | 274 automated tests |

## Quick Start

### CLI

```bash
# Seed all 6 nodes with demo data
python -m python.cli seed

# Process a transaction
python -m python.cli transact BANK_A ACT-A-001 D 1000 "Deposit"

# Verify all chains
python -m python.cli verify --all

# Run full demo (compile → seed → settle → verify → tamper → detect)
./scripts/prove.sh
```

### API Server

```bash
pip install -e ".[dev]"
uvicorn python.api.app:app --reload
# Open http://localhost:8000/docs for interactive API explorer
```

### Tests

```bash
python -m pytest python/tests/ -v    # 274 tests, all green
```

## Architecture

```
┌─────────────────────────────────────────────┐
│  Layer 3: REST API + LLM Tool-Use           │
│  FastAPI endpoints, Pydantic models,        │
│  Ollama/Anthropic providers, RBAC tools     │
├─────────────────────────────────────────────┤
│  Layer 2: Python Bridge + Integrity         │
│  COBOLBridge (Mode A/B), IntegrityChain,    │
│  SettlementCoordinator, CrossNodeVerifier   │
├─────────────────────────────────────────────┤
│  Layer 1: COBOL Banking System              │
│  10 programs, 5 copybooks, DAT files        │
│  SHA-256 chain per node                     │
└─────────────────────────────────────────────┘
```

See [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) for the full topology, data flow, and integrity model.
