# 03_PYTHON_BACKEND

Python bridge, integrity engine, authentication, and API layer for Phase 1.

---

## Overview

The Python backend consists of four layers:

| Layer | File | Purpose |
|-------|------|---------|
| **Bridge** | `bridge.py` | COBOL subprocess execution, flat-file parsing, SQLite sync |
| **Integrity** | `integrity.py` | SHA-256 hash chain, HMAC signatures, verification |
| **Auth** | `auth.py` | Role-based API keys, permission checks |
| **API** | (Phase 2) | FastAPI endpoints (not in Phase 1) |

Phase 1 delivers the bridge, integrity, and auth layers. Phase 2 adds the HTTP API.

---

## requirements.txt

**File location:** `python/requirements.txt`

```
fastapi==0.109.0
uvicorn==0.27.0
click==8.1.7
pydantic==2.5.0
```

**Why these four?**
- `fastapi` — HTTP framework (imported but not used in Phase 1; included for Phase 2)
- `uvicorn` — ASGI server (same; for Phase 2)
- `click` — CLI framework (used for Phase 1 CLI)
- `pydantic` — data validation (used for bridge return types)

**Installation:**
```bash
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows
pip install -r requirements.txt
```

---

## SQLite Schema

The bridge syncs COBOL flat files to SQLite for fast querying. Three main tables:

### accounts

```sql
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    account_type TEXT NOT NULL DEFAULT 'C',  -- 'C'=checking, 'S'=savings
    balance REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'A',  -- 'A'=active, 'C'=closed, 'F'=frozen
    opened_at TEXT,  -- YYYYMMDD
    last_activity TEXT  -- YYYYMMDD
);

CREATE INDEX idx_accounts_status ON accounts(status);
CREATE INDEX idx_accounts_opened_at ON accounts(opened_at);
```

**Populated by:** `bridge.load_accounts_from_cobol(node)` or `generate_demo_data()`

---

### transactions

```sql
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    type TEXT NOT NULL,  -- 'D'=deposit, 'W'=withdraw, 'T'=transfer, 'I'=interest, 'F'=fee
    amount REAL NOT NULL,
    date TEXT,  -- YYYYMMDD
    time_str TEXT,  -- HHMMSS
    description TEXT,
    status TEXT NOT NULL DEFAULT '00',  -- '00'=success, '01'=NSF, etc.
    batch_id TEXT,  -- which batch run this came from
    balance_after REAL,  -- account balance after transaction
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tx_account ON transactions(account_id);
CREATE INDEX idx_tx_batch ON transactions(batch_id);
CREATE INDEX idx_tx_date ON transactions(date);
CREATE INDEX idx_tx_status ON transactions(status);
```

**Populated by:** `bridge.process_transaction()` or batch runs

---

### chain_entries

```sql
CREATE TABLE IF NOT EXISTS chain_entries (
    chain_index INTEGER PRIMARY KEY,
    tx_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    tx_type TEXT NOT NULL,
    amount REAL NOT NULL,
    timestamp TEXT NOT NULL,  -- YYYYMMDDHHMM SS
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    tx_hash TEXT NOT NULL,  -- SHA-256(contents + prev_hash)
    prev_hash TEXT NOT NULL,  -- hash of previous entry
    signature TEXT NOT NULL  -- HMAC-SHA256(tx_hash, secret_key)
);

CREATE INDEX idx_chain_account ON chain_entries(account_id);
```

**Populated by:** `integrity.append()` during each transaction

---

### api_keys

```sql
CREATE TABLE IF NOT EXISTS api_keys (
    key_id TEXT PRIMARY KEY,
    key_hash TEXT NOT NULL,
    role TEXT NOT NULL,  -- 'teller', 'auditor', 'admin'
    label TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Populated by:** `auth.initialize_default_keys()` on first run

---

## integrity.py (Implement from Interface Specification)

**Implementation:** Implement the interface specification below. No external source needed — the full API contract is defined here.

**Key classes:**
- `ChainedTransaction` — dataclass representing one chain entry
- `IntegrityChain` — manages SHA-256 hash chain + HMAC signing

**Key methods:**
- `__init__(db_connection, secret_key)` — initialize chain, create table if needed
- `get_latest_hash()` — return the hash of the most recent entry (or GENESIS_HASH if empty)
- `append(tx_id, account_id, tx_type, amount, timestamp, description, status)` → ChainedTransaction
- `verify_chain()` → dict with `{valid, entries_checked, time_ms, first_break, break_type, details}`
- `simulate_tamper(chain_index)` → dict showing tamper injection and detection
- `get_chain_for_display(limit, offset)` → list of chain entries formatted for UI

**Secret key generation:**
```python
# On first initialization:
key_path = data_dir / ".server_key"
if not key_path.exists():
    secret_key = secrets.token_hex(32)  # 64-char hex string
    key_path.write_text(secret_key)
    key_path.chmod(0o600)  # Unix permissions: owner read-write only
```

---

## auth.py (Implement from Specification)

**Implementation:** Implement from the specification below with the PERMISSIONS dict shown (AI permissions already excluded).

**Result (after stripping):**

```python
PERMISSIONS = {
    Role.TELLER: {
        "accounts.read", "accounts.create",
        "transactions.read", "transactions.create",
        "batch.run",
    },
    Role.AUDITOR: {
        "accounts.read", "transactions.read",
        "chain.verify", "chain.view", "batch.read",
        "cobol.read",
    },
    Role.ADMIN: {
        "accounts.read", "accounts.create",
        "accounts.update", "accounts.close",
        "transactions.read", "transactions.create",
        "batch.run", "batch.read",
        "chain.verify", "chain.view", "chain.tamper_demo",
        "cobol.read", "cobol.compile",
        "system.status", "system.keys",
    },
}
```

**Key classes:**
- `Role` — enum: TELLER, AUDITOR, ADMIN
- `AuthContext` — dataclass: (role, key_id, label)
- `AuthManager` — manages API keys and permission checks

**Key methods:**
- `__init__(db_connection, data_dir)` — initialize auth, create table if needed
- `initialize_default_keys()` → dict mapping role names to plaintext keys
- `authenticate(api_key)` → AuthContext or None
- `check_permission(auth, permission)` → bool
- `get_role_permissions(role)` → set of permission strings
- `list_keys()` → list of {key_id, role, label, created_at}
- `load_key_for_role(role)` → plaintext key from `.api_keys` file

---

## bridge.py (Implement as COBOLBridge Class)

**Implementation:** Implement as COBOLBridge class per the interface specification below. If adapting from v1 code, remove these AI-only methods before using:
- `translate_cobol(filename, mode)`
- `get_cobol_diff(filename, modified_source)`
- `apply_cobol_edit(filename, modified_source)`

**Constructor update:** Ensure constructor uses `node` parameter instead of hardcoded bank:

```python
class COBOLBridge:
    def __init__(self, node="BANK_A", bin_dir="./bin", data_dir="./data",
                 cobol_src_dir="./cobol/src", db_path=None):
        # ... existing init code ...
        self.node = node  # NEW: track which node this bridge instance is connected to
```

### Core Interface

#### Initialization

```python
from bridge import COBOLBridge

# Create bridge for a specific node
bridge_bank_a = COBOLBridge(node="BANK_A", db_path="./data/bank-a.db")
bridge_clearing = COBOLBridge(node="CLEARING", db_path="./data/clearing.db")
```

**Constructor args:**
- `node` — which node to operate on (BANK_A, BANK_B, ..., CLEARING)
- `bin_dir` — where compiled COBOL binaries live (default: `./bin`)
- `data_dir` — where SQLite database lives (default: `./data`)
- `cobol_src_dir` — where COBOL source files live (default: `./cobol/src`)
- `db_path` — SQLite database file path.
  - **Default (when None):** `{data_dir}/{node.lower().replace("-","_")}.db`
  - **Examples:** `./data/bank_a.db`, `./data/bank_b.db`, `./data/clearing.db`
  - **Rationale:** Each node has its own integrity chain in its own database. A shared database would require a node column on every table and complicate Phase 2 cross-node verification. One file per node is the correct architecture.

**Usage examples:**
```python
bridge_bank_a = COBOLBridge(node="BANK_A")   # → ./data/bank_a.db (automatic)
bridge_clearing = COBOLBridge(node="CLEARING")  # → ./data/clearing.db (automatic)
```

**Phase 2 note:** `verifier.py` instantiates one `COBOLBridge` per node to compare chains across the network.

---

#### Account Operations

```python
# Create an account
result = bridge.create_account(
    account_id="ACT-A-001",
    name="Maria Santos",
    account_type="C",  # 'C' or 'S'
    initial_balance=15420.50
)
# Returns: {"id": "ACT-A-001", "name": "Maria Santos", ...} or {"error": "..."}

# Get an account by ID
account = bridge.get_account("ACT-A-001")
# Returns: {"id": "ACT-A-001", "name": "Maria Santos", "balance": 15420.50, ...}
# or None if not found

# List all accounts for this node
accounts = bridge.list_accounts()
# Returns: [{"id": "...", "name": "...", ...}, ...]

# Update account (name or status only)
result = bridge.update_account("ACT-A-001", name="New Name", status="F")
# Returns: updated account dict or {"error": "..."}
```

---

#### Transaction Operations

```python
# Process a single transaction
result = bridge.process_transaction(
    account_id="ACT-A-001",
    tx_type="D",  # 'D'=deposit, 'W'=withdraw, 'T'=transfer, 'I'=interest, 'F'=fee
    amount=3200.00,
    description="Direct deposit - Employer payroll",
    target_id="ACT-A-002",  # only for transfers
    batch_id="BAT20240102"  # optional
)
# Returns:
# {
#     "tx_id": "TRX-20240102...",
#     "status": "00",  # or "01" (NSF), "02" (limit), "03" (invalid), "04" (frozen)
#     "account_id": "ACT-A-001",
#     "account_name": "Maria Santos",
#     "type": "D",
#     "amount": 3200.00,
#     "balance_before": 15420.50,
#     "balance_after": 18620.50,
#     "description": "Direct deposit...",
#     "trace": [
#         "PERFORM PROCESS-DEPOSIT",
#         "MOVE 3200.00 TO TRANS-AMOUNT",
#         "ADD TRANS-AMOUNT TO ACCT-BALANCE",
#         "WRITE TRANSACTION-RECORD",
#         "Status: 00 (SUCCESS)"
#     ],
#     "chain": {
#         "index": 47,
#         "hash": "a1b2c3...",
#         "prev_hash": "9z8y7x...",
#         "short_hash": "a1b2c3d4",
#         "short_prev": "9z8y7x8w"
#     }
# }

# Get transactions (with optional filters)
transactions = bridge.get_transactions(
    account_id="ACT-A-001",
    batch_id="BAT20240102",
    limit=100
)
# Returns: list of transaction dicts
```

---

#### Batch Processing

```python
# Run a batch of transactions
batch_transactions = [
    {"account_id": "ACT-A-001", "type": "D", "amount": 3200.00,
     "description": "Direct deposit - Employer payroll"},
    {"account_id": "ACT-A-002", "type": "I", "amount": 210.50,
     "description": "Quarterly interest payment"},
    # ... up to 30-40 per batch
]

result = bridge.run_batch(batch_transactions, batch_id="BAT20240102EOD")
# Returns:
# {
#     "batch_id": "BAT20240102EOD",
#     "total": 15,
#     "success": 14,
#     "failed": 1,
#     "started_at": "2024-01-02T08:00:00",
#     "completed_at": "2024-01-02T08:00:04",
#     "results": [
#         {
#             "index": 1,
#             "tx_id": "TRX-...",
#             "status": "00",
#             "account_id": "ACT-A-001",
#             ...
#         },
#         ...
#     ]
# }

# Get all batch runs
batch_runs = bridge.get_batch_runs()
# Returns: list of {"batch_id": "...", "started_at": "...", "total": 15, ...}
```

---

#### Integrity Chain

```python
# Verify the integrity chain (all entries must be unbroken)
verification = bridge.chain.verify_chain()
# Returns:
# {
#     "valid": True,
#     "entries_checked": 47,
#     "time_ms": 1.2,
#     "first_break": None,
#     "break_type": None,
#     "details": "All 47 entries verified. Chain intact in 1.2ms."
# }
# or if tampered:
# {
#     "valid": False,
#     "entries_checked": 23,
#     "time_ms": 0.8,
#     "first_break": 23,
#     "break_type": "hash_mismatch",
#     "details": "Entry 23 (tx TRX-xxx): hash mismatch — data was modified. ..."
# }

# Get chain entries for display
chain_display = bridge.chain.get_chain_for_display(limit=50, offset=0)
# Returns: list of {"chain_index": 0, "tx_id": "...", "hash": "...", ...}

# Demo: inject tamper and detect it
tamper_result = bridge.chain.simulate_tamper(chain_index=10)
# Returns:
# {
#     "tampered_index": 10,
#     "original_amount": 1500.00,
#     "tampered_amount": 51500.00,
#     "detection": {
#         "valid": False,
#         "entries_checked": 11,
#         "break_type": "hash_mismatch",
#         ...
#     },
#     "restored": True
# }
```

---

#### COBOL Source Management

```python
# List available COBOL programs
sources = bridge.list_cobol_sources()
# Returns:
# [
#     {"name": "ACCOUNTS.cob", "lines": 381, "size_bytes": 9840},
#     {"name": "TRANSACT.cob", "lines": 708, "size_bytes": 18272},
#     ...
# ]

# Read a COBOL source file
source_code = bridge.get_cobol_source("ACCOUNTS.cob")
# Returns: full source code as string, or None if not found
```

---

#### System Status

```python
# Get system health summary
status = bridge.get_status()
# Returns:
# {
#     "cobol_sources": 4,
#     "cobol_binaries": 4,
#     "accounts": 8,  # for this node
#     "transactions": 47,  # for this node
#     "chain_entries": 47,
#     "auth_keys": 3,
#     "db_path": "/path/to/ledger.db",
#     "data_dir": "/path/to/data",
# }
```

---

#### COBOL Subprocess Execution (Internal)

The bridge executes COBOL programs as subprocesses. Key implementation detail:

```python
def run_cobol(self, program: str, operation: str, args: list = None) -> dict:
    """
    Execute a COBOL program as subprocess.

    Args:
        program: program name ('ACCOUNTS' or 'TRANSACT')
        operation: operation code ('CREATE', 'DEPOSIT', etc.)
        args: list of arguments to pass via stdin/command-line

    Returns:
        {
            "exit_code": 0,
            "stdout": full output from COBOL program,
            "stderr": any error messages,
            "parsed": parsed output (program-specific)
        }
    """
    # Binary path must be absolute to prevent CWD-relative issues
    # (bin_dir is resolved to absolute path in __init__)
    binary_path = self.bin_dir / program

    # Set working directory to this node's data dir (also resolve for safety)
    # COBOL programs open data files (ACCOUNTS.DAT, TRANSACT.DAT) with
    # relative paths from their working directory. This is why cwd must be
    # set to the node's data directory — and why the binary path must be absolute.
    cwd = Path(f"banks/{self.node}").resolve()

    # Execute: ./bin/PROGRAM OPERATION arg1 arg2 ...
    result = subprocess.run(
        [str(binary_path), operation] + (args or []),
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30
    )

    # Parse output (program-specific)
    # Remove TRACE lines, parse result codes, handle errors

    return {
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "parsed": parse_cobol_output(result.stdout)
    }
```

**Path Resolution Critical Detail:**
- `self.bin_dir` is resolved to absolute path in `__init__()` to prevent CWD-relative issues
- `cwd` is also resolved to absolute path so working directory is unambiguous
- COBOL programs open relative-path files from their working directory

---

#### Demo Data Generation

```python
# Seed the database with demo accounts (8 per bank, 5 nostro for clearing)
demo = generate_demo_data(bridge)
# Returns:
# {
#     "accounts_created": 8,
#     "accounts": [
#         {"id": "ACT-A-001", "name": "Maria Santos", ...},
#         ...
#     ]
# }

# Get pre-authored demo batch (30-40 transactions)
batch = get_demo_batch()
# Returns:
# [
#     {"account_id": "ACT-A-001", "type": "D", "amount": 3200.00, ...},
#     {"account_id": "ACT-A-002", "type": "I", "amount": 210.50, ...},
#     ...
# ]
```

---

## Seeding Strategy: With and Without COBOL

The system is designed to work in two modes:

### Mode A: With GnuCOBOL (cobc available)
1. `seed.sh` writes ACCOUNTS.DAT files in fixed-width ACCTREC format
2. `bridge.load_accounts_from_cobol(node)` executes ACCOUNTS binary as subprocess
3. Parses pipe-delimited stdout output into account dicts
4. Syncs parsed accounts to SQLite

### Mode B: Without GnuCOBOL (cobc not available)
1. `seed.sh` still writes ACCOUNTS.DAT files (pure Python writes fixed-width format)
2. `generate_demo_data(bridge)` reads ACCOUNTS.DAT directly (Python file I/O)
3. Parses fixed-width records manually (using record layout from ACCTREC.cpy)
4. Inserts parsed accounts into SQLite directly

The bridge must detect whether COBOL binaries exist (check `self.bin_dir` for executable files) and fall back to Mode B if they don't. Both modes produce identical SQLite state, so Phase 1 testing works either way.

---

## Phase 1 Verification

The Python bridge must pass these three checks:

```python
# Check 1: Can import and initialize
from bridge import COBOLBridge
b = COBOLBridge(node="BANK_A")
print(f"Bridge initialized for {b.node}")

# Check 2: Can read demo accounts
accounts = b.list_accounts()
print(f"BANK_A: {len(accounts)} accounts")
assert len(accounts) == 8

# Check 3: Can perform a transaction
result = b.process_transaction(
    account_id=accounts[0]["id"],
    tx_type="D",
    amount=1000.00,
    description="Test deposit"
)
assert result["status"] == "00"
print(f"Transaction succeeded: {result['tx_id']}")
```

---

## Testing

**File location:** `python/tests/`

### test_integrity.py

Tests for `integrity.py`:
- `test_chain_append_and_retrieve` — append entry, verify retrieval
- `test_chain_verification_passes_when_valid` — verify chain with no tampering
- `test_chain_verification_detects_hash_mismatch` — corrupt one entry, detection
- `test_chain_verification_detects_signature_fraud` — invalid HMAC, detection
- `test_chain_verification_detects_linkage_break` — break chain link, detection
- `test_tamper_simulation` — inject and restore tamper, verify detection

### test_bridge.py

Tests for `bridge.py`:
- `test_bridge_initialization` — create bridge instance
- `test_create_account` — add account, verify in SQLite
- `test_list_accounts` — retrieve seeded accounts
- `test_process_deposit` — deposit transaction
- `test_process_withdraw_nsf` — withdraw with insufficient funds
- `test_process_transfer` — transfer between accounts
- `test_run_batch` — batch processing loop
- `test_chain_integrated_with_transactions` — verify each transaction is in chain
- `test_get_status` — system health summary

---

## CLI (Phase 1)

**File location:** `python/cli.py` (rewritten from v1, AI references removed)

**Commands:**
```bash
python cli.py init-db          # Initialize SQLite schema
python cli.py seed-demo        # Populate with demo accounts and batch
python cli.py list-nodes       # Show all 6 nodes and account counts
python cli.py verify-chain     # Run chain verification on a node
python cli.py run-batch NODE   # Execute pre-authored batch for NODE
python cli.py status           # Show system health
```

**Example:**
```bash
# Initialize
python cli.py init-db

# Seed demo data
python cli.py seed-demo

# List nodes
python cli.py list-nodes
# Output:
# BANK_A: 8 accounts
# BANK_B: 7 accounts
# BANK_C: 8 accounts
# BANK_D: 6 accounts
# BANK_E: 8 accounts
# CLEARING: 5 nostro accounts

# Run batch on BANK_A
python cli.py run-batch BANK_A
# Output: Batch processing begins...

# Verify chains
python cli.py verify-chain BANK_A
# Output: BANK_A chain: 47 entries, verified in 1.2ms ✓

# Check status
python cli.py status
# Output: System health summary
```

---

## Phase 2 Additions (Not in Phase 1)

- `settlement.py` — inter-bank settlement coordinator (netting, nostro routing)
- `verifier.py` — cross-node chain verification (hub-and-spoke)
- FastAPI endpoints in `api/main.py` — REST API, SSE for live batch

These will be documented in Phase 2 handoff.

---

## Scripts (Phase 1)

### setup.sh — Python Environment Setup

**File location:** `scripts/setup.sh`

```bash
#!/bin/bash
set -e

python3 -m venv python/venv
source python/venv/bin/activate
pip install --quiet -r python/requirements.txt
echo "Python environment ready: python/venv/"
echo "To activate: source python/venv/bin/activate"
```

This script creates an isolated Python virtual environment and installs dependencies. Run this once before any Python work.

---

## Next Steps

1. Implement `bridge.py` (adapt from v1 if available, or build from specification)
2. Implement `integrity.py` from interface specification
3. Implement `auth.py` from specification (stripped of AI permissions)
4. Implement `cli.py` from specification in `04_FRONTEND_AND_DEMO.md`
5. Implement tests and CLI
6. Verify Phase 1 gate passes

**Next document:** `04_FRONTEND_AND_DEMO.md` for demo script and Phase 3 console.
