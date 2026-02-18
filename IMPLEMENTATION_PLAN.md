# cobol-legacy-ledger: Multi-Phase Implementation Plan

**Project:** COBOL-first inter-bank settlement system with cryptographic integrity verification
**Status:** Phase 1 planning
**Last Updated:** 2026-02-17

---

## Executive Summary

This plan breaks the cobol-legacy-ledger into three controlled phases, each with clear gates and deliverables:

| Phase | Scope | Gate | Duration |
|-------|-------|------|----------|
| **1** | COBOL foundation, Python bridge, integrity chain, seeding | `demo.sh` runs end-to-end, all 6 nodes verified | 3-4 weeks |
| **2** | Settlement coordinator, cross-node verification, FastAPI | Corrupt BANK_C, detect in <100ms, netting works | 2-3 weeks |
| **3** | Static HTML console, live demo visualization, deployment | Full system runs end-to-end with UI, GitHub Pages live | 1-2 weeks |

---

## PHASE 1: Foundation (COBOL + Bridge + Integrity)

### Objectives
- Implement 4 COBOL programs and 3 copybooks (copy v1 exactly, no modifications)
- Seed 6 nodes with 37 accounts
- Build Python bridge to execute COBOL and parse output
- Implement integrity chain (SHA-256 hash linking + HMAC signing)
- Create CLI demo script to verify system works
- Document all COBOL bugs in KNOWN_ISSUES.md

### Deliverables
1. **COBOL Layer** (`cobol/src/`, `cobol/copybooks/`)
   - ACCOUNTS.cob (381 lines)
   - TRANSACT.cob (708 lines)
   - VALIDATE.cob (~200 lines)
   - REPORTS.cob (~150 lines)
   - ACCTREC.cpy, TRANSREC.cpy, COMCODE.cpy
   - KNOWN_ISSUES.md (document A1, A2, T1-T12)

2. **Data Seeding** (`banks/*/ACCOUNTS.DAT`)
   - BANK_A: 8 customer accounts
   - BANK_B: 7 customer accounts
   - BANK_C: 8 customer accounts (tamper target)
   - BANK_D: 6 customer accounts
   - BANK_E: 8 customer accounts
   - CLEARING: 5 nostro accounts
   - BATCH-INPUT.DAT per node (30-40 sample transactions)

3. **Python Bridge** (`python/bridge.py`)
   - COBOLBridge class
   - `__init__(node, bin_dir, data_dir, db_path)`
   - Account operations: create, read, list, update
   - Transaction operations: process, get, batch
   - COBOL subprocess execution with output parsing
   - SQLite sync (accounts, transactions, chain_entries tables)

4. **Integrity Engine** (`python/integrity.py`)
   - Copy from v1 unchanged
   - ChainedTransaction dataclass
   - IntegrityChain class
   - SHA-256 hash chaining
   - HMAC-SHA256 signing
   - Verification and tamper simulation

5. **Auth Layer** (`python/auth.py`)
   - Copy from v1, strip AI permissions
   - Role enum (TELLER, AUDITOR, ADMIN)
   - AuthManager with API key management
   - Permission checks for roles

6. **CLI** (`python/cli.py`)
   - Commands: init-db, seed-demo, list-nodes, verify-chain, run-batch, status
   - Click framework for CLI
   - Human-readable output

7. **Tests** (`python/tests/`)
   - test_integrity.py: chain append, verification, tamper detection
   - test_bridge.py: account ops, transactions, batches, integration
   - test_auth.py: key management, permissions

8. **Scripts**
   - `scripts/build.sh` — compile COBOL (or gracefully skip)
   - `scripts/setup.sh` — Python venv + pip install
   - `scripts/seed.sh` — populate all 6 nodes with accounts
   - `scripts/demo.sh` — Phase 1 verification walkthrough

9. **Documentation**
   - `docs/README.md` — project overview
   - `docs/ARCHITECTURE.md` — 90-second architecture for senior dev
   - `cobol/KNOWN_ISSUES.md` — all bugs documented

### Acceptance Criteria
```bash
# All three must pass:

# 1. Build succeeds
./scripts/build.sh
# Output: COBOL compiled (or skipped with clear message)

# 2. Seeding succeeds
./scripts/seed.sh
# Output: Seeded BANK_A: 8 accounts ✓, etc.

# 3. Bridge reads all nodes
cd python && python -c "
from bridge import COBOLBridge
for node in ['BANK_A', 'BANK_B', 'BANK_C', 'BANK_D', 'BANK_E', 'CLEARING']:
    b = COBOLBridge(node=node)
    accounts = b.list_accounts()
    print(f'{node}: {len(accounts)} accounts')
"
# Output: BANK_A: 8 accounts, BANK_B: 7, BANK_C: 8, BANK_D: 6, BANK_E: 8, CLEARING: 5

# 4. Demo runs end-to-end
./scripts/demo.sh
# Output: Full walkthrough with transaction processing and chain verification
```

### Task Breakdown

#### Phase 1.A: COBOL Layer (Week 1)
- [ ] Create `cobol/src/` directory
- [ ] Copy ACCOUNTS.cob from v1 (381 lines, exact)
- [ ] Copy TRANSACT.cob from v1 (708 lines, exact)
- [ ] Copy VALIDATE.cob from v1 (or create minimal stub)
- [ ] Copy REPORTS.cob from v1 (or create minimal stub)
- [ ] Create `cobol/copybooks/ACCTREC.cpy` (from spec)
- [ ] Create `cobol/copybooks/TRANSREC.cpy` (from spec)
- [ ] Create `cobol/copybooks/COMCODE.cpy` (from spec)
- [ ] Create `cobol/KNOWN_ISSUES.md` (document A1, A2, T1-T12)
- [ ] Test: `cobc -x -free cobol/src/ACCOUNTS.cob`

#### Phase 1.B: Data Seeding (Week 1)
- [ ] Create `banks/BANK_A/ACCOUNTS.DAT` (8 accounts, fixed-width ACCTREC format)
- [ ] Create `banks/BANK_B/ACCOUNTS.DAT` (7 accounts)
- [ ] Create `banks/BANK_C/ACCOUNTS.DAT` (8 accounts, tamper target)
- [ ] Create `banks/BANK_D/ACCOUNTS.DAT` (6 accounts)
- [ ] Create `banks/BANK_E/ACCOUNTS.DAT` (8 accounts)
- [ ] Create `banks/CLEARING/ACCOUNTS.DAT` (5 nostro accounts)
- [ ] Create `banks/*/BATCH-INPUT.DAT` (30-40 transactions per node)
- [ ] Create `scripts/seed.sh` (bash script to generate DAT files)
- [ ] Test: `bash scripts/seed.sh` produces all 6 nodes with correct accounts

#### Phase 1.C: Python Foundation (Week 1-2)
- [ ] Create `python/requirements.txt` (fastapi, uvicorn, click, pydantic)
- [ ] Create `python/integrity.py` (copy from v1 unchanged)
- [ ] Create `python/auth.py` (copy from v1, strip AI permissions)
- [ ] Create SQLite schema (accounts, transactions, chain_entries, api_keys tables)
- [ ] Create `python/__init__.py` (package marker)

#### Phase 1.D: Python Bridge (Week 2)
- [ ] Create `python/bridge.py` (COBOLBridge class, copy v1 cobol_bridge.py)
  - [ ] `__init__(node, bin_dir, data_dir, db_path)` constructor
  - [ ] `create_account(account_id, name, account_type, initial_balance)`
  - [ ] `get_account(account_id)`
  - [ ] `list_accounts()`
  - [ ] `update_account(account_id, name, status)`
  - [ ] `process_transaction(account_id, tx_type, amount, description, target_id, batch_id)`
  - [ ] `get_transactions(account_id, batch_id, limit)`
  - [ ] `run_batch(batch_transactions, batch_id)`
  - [ ] `get_batch_runs()`
  - [ ] `get_status()`
  - [ ] `run_cobol(program, operation, args)` (subprocess execution)
  - [ ] SQLite sync functions
- [ ] Test: Bridge can list accounts from all 6 nodes
- [ ] Test: Bridge can execute COBOL programs and parse output

#### Phase 1.E: CLI & Demo (Week 2-3)
- [ ] Create `python/cli.py` (Click-based CLI)
  - [ ] `init-db` command
  - [ ] `seed-demo` command
  - [ ] `list-nodes` command
  - [ ] `verify-chain` command
  - [ ] `run-batch` command
  - [ ] `status` command
- [ ] Create `scripts/build.sh` (compile all 4 COBOL programs)
- [ ] Create `scripts/setup.sh` (venv + pip install)
- [ ] Create `scripts/demo.sh` (Phase 1 verification walkthrough)
- [ ] Test: `python cli.py status` works
- [ ] Test: `bash scripts/demo.sh` completes end-to-end

#### Phase 1.F: Tests & Docs (Week 3)
- [ ] Create `python/tests/test_integrity.py`
- [ ] Create `python/tests/test_bridge.py`
- [ ] Create `python/tests/test_auth.py`
- [ ] Create `docs/README.md` (project overview)
- [ ] Create `docs/ARCHITECTURE.md` (90-second read)
- [ ] Update root `.gitignore` (ignore `cobol/bin/`, `data/`, `python/venv/`)
- [ ] Test: `pytest python/tests/` passes all tests

#### Phase 1.G: Gate Verification (Week 3)
- [ ] Run `./scripts/build.sh` → ✓
- [ ] Run `./scripts/seed.sh` → ✓ (all 6 nodes)
- [ ] Run bridge account listing → ✓ (8+7+8+6+8+5 = 42 accounts)
- [ ] Run `./scripts/demo.sh` → ✓ (full demo)

---

## PHASE 2: Settlement & Verification (BLOCKED until Phase 1 gate passes)

### Objectives
- Implement settlement coordinator (netting, nostro account routing)
- Cross-node chain verification (hub-and-spoke model)
- FastAPI HTTP endpoints for all operations
- Demonstrate tamper detection: corrupt BANK_C, detect in <100ms

### Key Components
- `python/settlement.py` — net position calculation, inter-bank routing
- `python/verifier.py` — cross-node chain verification
- `python/api/main.py` — FastAPI server with HTTP endpoints
- Demo scenario: corrupt one bank's ledger, watch clearing house detect

### Gate
Corrupt BANK_C balance or add ghost transaction. Run verification on all 4 non-corrupt banks + CLEARING. All 5 detect the discrepancy in <100ms.

---

## PHASE 3: Console & Deployment (BLOCKED until Phase 2 gate passes)

### Objectives
- Static HTML/CSS/JavaScript console (no Node.js, no React)
- Live batch execution visualization
- Tamper-detection demo UI
- GitHub Pages deployment

### Key Components
- `console/index.html` — main entry point
- `console/css/style.css` — styling
- `console/js/app.js` — main logic
- `console/js/api-client.js` — HTTP client
- `.github/workflows/deploy.yml` — GitHub Actions deployment

### Gate
Full system runs end-to-end. Console displays all 6 nodes, chains, transactions. Demo shows tamper detection. Deployed to GitHub Pages.

---

## Critical Constraints

### COBOL
- **Copy v1 exactly.** No modifications, no bug fixes.
- **Document bugs** in KNOWN_ISSUES.md (these serve interview talking points).
- **4 programs:** ACCOUNTS, TRANSACT, VALIDATE, REPORTS.
- **3 copybooks:** ACCTREC (70 bytes), TRANSREC (103 bytes), COMCODE (common constants).

### Python
- **Bridge adapts v1 cobol_bridge.py** but removes AI-specific methods (translate_cobol, get_cobol_diff, apply_cobol_edit).
- **Integrity.py copied unchanged** from v1.
- **Auth.py copied, then strip AI permissions** (ai.officer, ai.explain, ai.audit, ai.edit).
- **No Node.js, ever.** Phase 3 is static HTML served by Python.

### Architecture
- **6 nodes, fixed.** 5 banks + 1 clearing house.
- **37 accounts, fixed.** 8+7+8+6+8+5.
- **Hub-and-spoke model.** Clearing house is authoritative witness.
- **Per-node databases.** Phase 1 uses separate SQLite per node; Phase 2 adds cross-node verification.

### Interview Narrative
The system tells a story:
1. **Problem:** COBOL batch settlement has no integrity verification.
2. **Solution:** Python observation layer wraps unmodified COBOL with cryptographic proof.
3. **Demo:** Five banks, one clearing house. Corrupt one bank's ledger. Clearing house independently detects it.
4. **Lesson:** Modern infrastructure around legacy systems without replacing them.

---

## Success Metrics

### Phase 1 ✓
- [ ] COBOL compiles (or gracefully skips)
- [ ] All 6 nodes seed with correct account counts
- [ ] Python bridge reads accounts from all nodes
- [ ] Transactions process and add to integrity chain
- [ ] Chain verification detects tampering
- [ ] Demo script runs end-to-end

### Phase 2 ✓
- [ ] Settlement coordinator calculates net positions correctly
- [ ] Corrupt one bank's ledger
- [ ] Other 4 banks + clearing house detect corruption in <100ms
- [ ] FastAPI endpoints respond to HTTP requests
- [ ] Cross-node verification hub-and-spoke model works

### Phase 3 ✓
- [ ] Static HTML console loads in browser
- [ ] Console displays all 6 nodes and their accounts
- [ ] Console shows integrity chains and verification results
- [ ] Tamper-demo button corrupts and detects in <100ms on UI
- [ ] Deployed to GitHub Pages

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| GnuCOBOL not installed | build.sh gracefully skips with clear message |
| COBOL bugs prevent compilation | Copy v1 exactly; if v1 compiles, ours will too |
| SQLite schema mismatch | Use init-db command to create schema idempotently |
| TRACE lines in COBOL output | Bridge parses and strips them |
| Phase 1 gate fails | Debug incrementally: build → seed → bridge read → demo |
| Inter-node communication | Phase 2 scope; Phase 1 is single-node SQLite per node |

---

## Dependencies & Ordering

### Phase 1 Task Sequence (Must be sequential)
1. **COBOL Layer** — must be done first (no dependencies)
2. **Data Seeding** — depends on COBOL copybooks
3. **Python Foundation** — independent, can start in parallel with 1+2
4. **Python Bridge** — depends on foundation, can start when foundation done
5. **CLI & Demo** — depends on bridge
6. **Tests & Docs** — can be done in parallel with 5
7. **Gate Verification** — done last, verifies everything

### Parallelization Opportunities
- COBOL Layer and Python Foundation can start simultaneously
- Individual COBOL program testing can be parallel
- Individual bridge methods can be tested as implemented

---

## Implementation Notes

### COBOL Source Files (v1)
These must be copied from the cobol-fintrust-engine v1 repo:
- `cobol/src/ACCOUNTS.cob` (381 lines)
- `cobol/src/TRANSACT.cob` (708 lines)
- `cobol/src/VALIDATE.cob` (stub or full, TBD)
- `cobol/src/REPORTS.cob` (stub or full, TBD)
- `cobol/copybooks/ACCTREC.cpy`
- `cobol/copybooks/TRANSREC.cpy`

### Python Source Files (v1)
These must be copied from the cobol-fintrust-engine v1 repo:
- `python/integrity.py` (copy unchanged)
- `python/auth.py` (copy, then strip AI permissions)
- `python/cobol_bridge.py` → rename to `bridge.py`, remove AI methods

### Seeding Strategy
Fixed-width binary format matching COBOL copybook specs:
- ACCTREC: 70 bytes per account
- TRANSREC: 103 bytes per transaction
- Use Python struct module to serialize, or bash printf with fixed-width fields

### Database Schema
Three-table approach:
1. `accounts` — account ledger (from COBOL ACCOUNTS.DAT)
2. `transactions` — transaction log (from COBOL TRANSACT.DAT)
3. `chain_entries` — integrity chain (generated by integrity.py)

Schema creation: idempotent SQL with `CREATE TABLE IF NOT EXISTS`.

---

## Next Steps

1. **Confirm Phase 1 scope** with stakeholders
2. **Obtain v1 source files** from cobol-fintrust-engine repo
3. **Start Phase 1.A (COBOL Layer)** — highest priority
4. **Gate verification at end of Phase 1** — must pass before Phase 2
5. **Review Phase 2 requirements** after Phase 1 gate passes

---

## Questions / Decisions Needed

1. **v1 Source Code:** Where is cobol-fintrust-engine repo? (needed for ACCOUNTS.cob, TRANSACT.cob, integrity.py, auth.py, cobol_bridge.py)
2. **GnuCOBOL:** Is cobc available on development machines? (Phase 1 build.sh handles both cases)
3. **Linux/Mac/Windows:** Which OS(s) for development and deployment? (impacts bash shebangs, path separators)
4. **Test Framework:** Pytest for Python tests? (specified in requirements.txt as implicit)
5. **CI/CD:** GitHub Actions for automated testing? (Phase 3 deployment uses it; Phase 1 scope TBD)

---

**Plan prepared by:** Claude (Haiku 4.5)
**Status:** Ready for Phase 1 start
**Last Updated:** 2026-02-17
