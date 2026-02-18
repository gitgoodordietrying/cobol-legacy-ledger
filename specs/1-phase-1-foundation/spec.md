# Feature Specification: Phase 1 Foundation

**Feature ID**: 1-phase-1-foundation
**Priority**: P1 (MVP — without this, nothing runs)
**Date**: 2026-02-17

---

## Overview

Phase 1 delivers the foundational COBOL programs, Python bridge, and integrity verification system. This is the minimal viable system: all 6 nodes seeded, COBOL compilation working (or gracefully skipped), Python bridge can read accounts and process transactions, and integrity chains record and verify.

**MVP Success Criteria**: Phase 1 gate passes (5 checks: build, seed, accounts, transaction, chain)

---

## User Stories

### User Story 1 - COBOL Foundation (Priority: P1)

**As a** financial auditor, **I want to** compile and run unmodified COBOL programs that manage bank accounts and transactions, **so that** I can verify the legacy system works as documented.

**Acceptance Scenarios**:
1. Given `cobc` is installed, when `scripts/build.sh` runs, then 4 COBOL binaries are created in `cobol/bin/` (ACCOUNTS, TRANSACT, VALIDATE, REPORTS)
2. Given `cobc` is unavailable, when `scripts/build.sh` runs, then the script exits gracefully with a message and continues in Python-only mode
3. Given ACCOUNTS.cob is compiled, when it runs with LIST operation, then it outputs pipe-delimited account records to stdout
4. Given TRANSACT.cob is compiled, when it processes a deposit, then it updates the account balance and writes a transaction record to TRANSACT.DAT

**Notes**:
- COBOL source must implement the specification in `02_COBOL_AND_DATA.md` exactly
- Production-style headers required on all 4 programs (see COBOL_SUPPLEMENTS.md)
- All known bugs documented in `cobol/KNOWN_ISSUES.md` (use template from COBOL_SUPPLEMENTS.md)
- Smoke test (SMOKETEST.cob) must be run and verified before implementing ACCOUNTS.cob

---

### User Story 2 - Data Seeding (Priority: P1)

**As a** system tester, **I want to** populate all 6 nodes with realistic account data, **so that** I can run end-to-end scenarios without manual data entry.

**Acceptance Scenarios**:
1. Given `scripts/seed.sh` runs, when it completes, then `banks/BANK_A/ACCOUNTS.DAT` contains 8 customer accounts in ACCTREC fixed-width format
2. Given seeding is complete, when `scripts/seed.sh` runs again, then all 6 nodes are populated with correct account counts (8+7+8+6+8 customers, 5 nostro)
3. Given CLEARING/ACCOUNTS.DAT is populated, when account IDs are listed, then all 5 nostro IDs are exactly `NST-BANK-A` through `NST-BANK-E` (10 chars, fits PIC X(10))
4. Given each node has BATCH-INPUT.DAT, when the file is read, then transaction format is correct (pipe-delimited, D/W/T/I/F types, AMOUNT as decimal)

**Notes**:
- Seed script must write fixed-width records matching ACCTREC.cpy layout (70 bytes per record)
- NOSTRO IDs: `NST-BANK-A`, `NST-BANK-B`, `NST-BANK-C`, `NST-BANK-D`, `NST-BANK-E` (not `NOSTRO-BANK-*`)
- Account total: 42 (37 customer + 5 nostro)
- Batch samples provided for all 6 nodes in `02_COBOL_AND_DATA.md`

---

### User Story 3 - Python Bridge (Priority: P1)

**As a** Python developer, **I want to** execute COBOL programs as subprocesses and parse their output into SQLite, **so that** I can query accounts and transactions from Python without maintaining separate flat files.

**Acceptance Scenarios**:
1. Given `COBOLBridge(node="BANK_A")` is instantiated, when `list_accounts()` is called, then it returns a list of 8 account dicts with keys: id, name, account_type, balance, status, opened_at, last_activity
2. Given accounts are listed, when `get_account("ACT-A-001")` is called, then it returns the account dict for Maria Santos
3. Given `process_transaction(account_id, type, amount, description)` is called with valid deposit, then it returns a dict with tx_id, status='00', balance_after, and chain index
4. Given COBOL binaries don't exist, when the bridge initializes, then it falls back to Python-only mode (reads ACCOUNTS.DAT directly, no subprocess)

**Notes**:
- One database file per node: `bank_a.db`, `bank_b.db`, clearing.db, etc.
- Binary path resolution must be absolute (use `.resolve()`)
- Working directory for COBOL subprocess: `banks/{node}/` (relative path resolution)
- Parse TRACE lines from stdout; don't fail on them
- Bridge must detect if COBOL binaries exist and fall back to Mode B (Python file I/O) if not

---

### User Story 4 - Integrity Chain (Priority: P1)

**As a** compliance officer, **I want to** verify that all transactions in a node's chain are tamper-evident and linked, **so that** I can detect unauthorized modifications.

**Acceptance Scenarios**:
1. Given a transaction is processed, when `bridge.chain.append()` is called, then a chain entry is created with tx_hash = SHA-256(contents + prev_hash) and signature = HMAC-SHA256(tx_hash, secret_key)
2. Given the chain has 5+ entries, when `bridge.chain.verify_chain()` is called, then it returns {valid: true, entries_checked: 5, time_ms: <10}
3. Given entry #3 is corrupted (balance changed), when chain verification runs, then it detects the hash mismatch and returns {valid: false, first_break: 3, break_type: 'hash_mismatch'}
4. Given the chain is valid, when `bridge.chain.simulate_tamper(chain_index=2)` is called, then the entry is modified, verification detects it, and the entry is restored

**Notes**:
- SHA-256 hash chain is the core verification mechanism
- HMAC signatures provide authoritative proof (requires secret_key in env var `.server_key`)
- Verification must complete in <100ms for demo purposes
- Each node has its own chain (per-node database isolation)

---

### User Story 5 - Seeding With and Without COBOL (Priority: P1)

**As a** system architect, **I want to** support both COBOL-based and Python-only seeding modes, **so that** the system works on machines without GnuCOBOL installed.

**Acceptance Scenarios**:
1. Given `cobc` is installed, when `bridge.load_accounts_from_cobol(node)` is called, then ACCOUNTS binary runs as subprocess and returns parsed accounts
2. Given `cobc` is unavailable, when `generate_demo_data(bridge)` is called, then it reads ACCOUNTS.DAT directly and parses fixed-width records into dicts
3. Given both modes complete seeding, when the SQLite database is queried, then account counts and balances match exactly
4. Given ACCOUNTS.DAT is written in fixed-width format (70 bytes per record), when Python parser reads it, then fields are parsed correctly (account_id, name, type, balance, status, dates)

**Notes**:
- Mode A: COBOL subprocess → stdout parsing
- Mode B: Python file I/O → fixed-width parsing
- Both modes write identical SQLite state
- Bridge must detect which mode is available and choose automatically

---

### User Story 6 - Phase 1 Verification Gate (Priority: P1)

**As a** QA engineer, **I want to** run a 5-step verification gate that proves the system works, **so that** I can sign off on Phase 1 before Phase 2 begins.

**Acceptance Scenarios**:
1. Given all Phase 1 components are implemented, when `scripts/build.sh` runs, then COBOL binaries are created (or gracefully skipped)
2. When `scripts/seed.sh` runs, then all 6 nodes are seeded with correct account counts
3. When Python bridge lists accounts, then expected counts match: BANK_A(8), BANK_B(7), BANK_C(8), BANK_D(6), BANK_E(8), CLEARING(5)
4. When `process_transaction('ACT-A-001', 'D', 1000.00, 'test')` is called, then status is '00' and balance increases
5. When `bridge.chain.verify_chain()` is called, then it returns {valid: true} for all 3 nodes (BANK_A, BANK_B, CLEARING)

**Notes**:
- Gate is blocking: Phase 1 not complete until all 5 steps pass
- Gate can be run repeatedly during development
- Each check uses consistent account IDs: ACT-A-001 (Maria Santos), NST-BANK-A, etc.

---

## Functional Requirements

### COBOL Programs

**FR-001**: ACCOUNTS.cob MUST implement CREATE, READ, UPDATE, CLOSE, LIST operations
**FR-002**: TRANSACT.cob MUST implement DEPOSIT, WITHDRAW, TRANSFER, BATCH, and fee processing
**FR-003**: VALIDATE.cob MUST check account status (frozen), balance (NSF), and daily limits
**FR-004**: REPORTS.cob MUST generate STATEMENT, LEDGER, EOD, and AUDIT reports
**FR-005**: All programs MUST include production-style headers per COBOL_SUPPLEMENTS.md Supplement C
**FR-006**: All programs MUST output pipe-delimited records to stdout; errors to STDERR

### Data Format

**FR-007**: Account records MUST be 70 bytes fixed-width (ACCTREC.cpy format)
**FR-008**: Transaction records MUST be 103 bytes fixed-width (TRANSREC.cpy format)
**FR-009**: NOSTRO account IDs MUST be exactly 10 characters: NST-BANK-A through NST-BANK-E
**FR-010**: BATCH-INPUT.DAT MUST use pipe-delimited format with 4 fields (D/W/I/F) or 5 fields (T transfers)
**FR-011**: Balance values MUST use PIC S9(10)V99 (implied decimal, no literal point in storage)

### Python Bridge

**FR-012**: COBOLBridge MUST accept node parameter (BANK_A, BANK_B, ... CLEARING)
**FR-013**: Database path MUST default to {data_dir}/{node.lower()}.db (per-node isolation)
**FR-014**: list_accounts() MUST return list of dicts with keys: id, name, account_type, balance, status, opened_at, last_activity
**FR-015**: get_account(account_id) MUST return single account dict or None if not found
**FR-016**: process_transaction() MUST return dict with: tx_id, status, balance_before, balance_after, chain index
**FR-017**: Binary paths MUST be resolved to absolute paths to prevent CWD-relative issues
**FR-018**: Working directory for COBOL subprocess MUST be set to banks/{node}/ (relative path resolution for data files)

### Integrity Chain

**FR-019**: Each transaction MUST be recorded with SHA-256(contents + prev_hash) as tx_hash
**FR-020**: Each entry MUST be signed with HMAC-SHA256(tx_hash, secret_key)
**FR-021**: verify_chain() MUST check three things: chain linkage, hash mismatch, signature validity
**FR-022**: Verification MUST complete in <100ms for 50+ entries
**FR-023**: Chain table MUST track: chain_index, tx_id, tx_hash, prev_hash, signature, status
**FR-024**: Secret key MUST be loaded from .server_key file (generated if missing, perms 0o600)

### Scripts

**FR-025**: build.sh MUST compile 4 COBOL programs with `-x -free -I ../copybooks` flags
**FR-026**: build.sh MUST gracefully skip if cobc is unavailable
**FR-027**: seed.sh MUST create ACCOUNTS.DAT files for all 6 nodes in fixed-width ACCTREC format
**FR-028**: seed.sh MUST create empty TRANSACT.DAT files for all 6 nodes
**FR-029**: seed.sh MUST create BATCH-INPUT.DAT files with sample transactions for all 6 nodes
**FR-030**: setup.sh MUST create Python venv and install requirements from requirements.txt

---

## Success Criteria

**SC-001**: All 4 COBOL programs compile without errors (or gracefully skip if cobc unavailable)
**SC-002**: All 6 nodes seed with correct account counts (42 total: 37 customer + 5 nostro)
**SC-003**: Bridge can list accounts from any node and count them correctly
**SC-004**: Transaction processing returns status '00' for valid operations
**SC-005**: Integrity chain records all transactions and verifies without tampering
**SC-006**: Phase 1 gate (5 checks) passes completely
**SC-007**: COBOL_STYLE_REFERENCE.md smoke test has been run and verified before implementing ACCOUNTS.cob
**SC-008**: All COBOL programs include production-style headers per template
**SC-009**: All known issues documented in cobol/KNOWN_ISSUES.md with production fix recommendations
**SC-010**: Seeding works both with COBOL (Mode A) and without COBOL (Mode B)

---

## Out of Scope (Phase 2+)

- HTTP API endpoints (Phase 2)
- Cross-node settlement coordination (Phase 2)
- HTML console dashboard (Phase 3)
- GitHub Pages deployment (Phase 3)
- Netting calculations (Phase 2)
- Live tamper-detection demo UI (Phase 3)

---

## Edge Cases

**EC-001**: Account balance goes negative due to fee (BATCH-FEE bug) — documented, not fixed
**EC-002**: Daily limit tracking resets per COBOL run (WS-DAILY-TOTAL in WORKING-STORAGE) — documented, Python bridge tracks in Phase 2
**EC-003**: Account ID clobbered during TRANSFER lookup (WS-IN-ACCT-ID reuse) — documented, fragile pattern
**EC-004**: OCCURS 100 TIMES overflow (101st account lost) — documented, Python bridge warns if >= 100
**EC-005**: No bridge with COBOL unavailable — falls back to Python file I/O, same results
**EC-006**: Empty TRANSACT.DAT (no transactions yet) — chain verification still works, just 0 entries

---

## Dependencies & Integration

**External**:
- GnuCOBOL (cobc) — optional but recommended
- Python 3.8+ (fastapi, uvicorn, click, pydantic)

**Internal**:
- COBOL_STYLE_REFERENCE.md (mandatory read before implementing COBOL)
- COBOL_SUPPLEMENTS.md (mandatory read for templates and specs)
- 02_COBOL_AND_DATA.md (complete COBOL specification)
- 03_PYTHON_BACKEND.md (complete Python bridge specification)

**Files to Create**:
- cobol/src/ACCOUNTS.cob, TRANSACT.cob, VALIDATE.cob, REPORTS.cob
- cobol/copybooks/ACCTREC.cpy, TRANSREC.cpy, COMCODE.cpy
- cobol/KNOWN_ISSUES.md
- scripts/build.sh, setup.sh, seed.sh, demo.sh
- python/bridge.py, integrity.py, auth.py, cli.py
- python/requirements.txt
- python/tests/test_bridge.py, test_integrity.py
- .gitignore

---

## Clarifications (To Be Updated)

*None yet — awaiting clarify phase.*

---

## Constitution Check

- [x] **COBOL Immutability**: COBOL code is unmodified, Python layer observes
- [x] **Cryptographic Integrity**: SHA-256 chain + HMAC signatures for all transactions
- [x] **Per-Node Database Isolation**: Each node has its own bank_*.db file
- [x] **Specification-Driven**: All implementation follows 02_COBOL_AND_DATA.md exactly
- [x] **6-Node Fixed Architecture**: Exactly 6 nodes (5 banks + clearing house)
- [x] **Production-Grade COBOL**: Headers and bug documentation required
- [x] **Phase Gates**: Phase 1 gate blocks Phase 2 start
- [x] **Testability**: All requirements are testable (gate checks them)
- [x] **No Node.js**: Frontend is static HTML/CSS/JS (Phase 3)
- [x] **Clear Error Paths**: Status codes (00, 01, 02, 03, 04, 99) in all COBOL output
