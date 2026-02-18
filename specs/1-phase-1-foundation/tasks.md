# Phase 1 Task Breakdown

**Feature**: 1-phase-1-foundation
**Total Tasks**: 48 (organized in 7 phases)
**Parallel Opportunities**: 4 COBOL programs can compile in parallel; 3 Python modules can develop in parallel
**MVP Scope**: All 7 phases (no tasks can be skipped — each blocks others)
**Date**: 2026-02-17

---

## Overview

```
Phase 1 (Setup)              — 4 tasks: dirs, scripts, config
    ↓
Phase 2 (Foundation)        — 5 tasks: COBOL copybooks, headers
    ↓
Phase 3 (COBOL Programs)    — 6 tasks: ACCOUNTS, TRANSACT, VALIDATE, REPORTS + smoke test
    ↓ (parallel)
Phase 4 (Seeding)           — 2 tasks: seed.sh + demo batches
Phase 5 (Python Bridge)     — 6 tasks: bridge, integrity, auth, cli, requirements, __init__
Phase 6 (Testing)           — 3 tasks: test_bridge, test_integrity, tests/__init__
    ↓
Phase 7 (Verification)      — 22 tasks: verification tests for Phase 1 gate
```

**Critical Path**: Setup → Foundation → COBOL → Seeding → Python → Testing → Verification
**Blocking Dependencies**: Foundation blocks COBOL; COBOL blocks build.sh; build.sh blocks seed.sh

---

## Phase 1: Setup

Project scaffolding, directories, git config.

- [ ] T001 Create directory structure: `cobol/src`, `cobol/copybooks`, `cobol/bin`, `banks/{6 nodes}`, `python/tests`, `scripts`, `data` in `B:\Projects\portfolio\cobol-legacy-ledger\`
- [ ] T002 [P] Create `.gitignore` with patterns: `cobol/bin/`, `data/`, `python/venv/`, `__pycache__/`, `*.pyc`, `*.db`, `.server_key`, `.api_keys`, `*.egg-info/`, `.DS_Store` in `B:\Projects\portfolio\cobol-legacy-ledger\.gitignore`
- [ ] T003 [P] Create `python/requirements.txt` with: `fastapi==0.109.0`, `uvicorn==0.27.0`, `click==8.1.7`, `pydantic==2.5.0` in `B:\Projects\portfolio\cobol-legacy-ledger\python\requirements.txt`
- [ ] T004 [P] Create `python/__init__.py` (empty, marks python/ as package) in `B:\Projects\portfolio\cobol-legacy-ledger\python\__init__.py`

---

## Phase 2: Foundation (COBOL Copybooks)

Shared data layouts that all COBOL programs depend on.

- [ ] T005 Create `cobol/copybooks/ACCTREC.cpy` (account record: 70 bytes) with fields: ACCT-ID (10), ACCT-NAME (30), ACCT-TYPE (1), ACCT-BALANCE (12 signed, V99), ACCT-STATUS (1), ACCT-OPEN-DATE (8), ACCT-LAST-ACTIVITY (8) in `B:\Projects\portfolio\cobol-legacy-ledger\cobol\copybooks\ACCTREC.cpy`

- [ ] T006 Create `cobol/copybooks/TRANSREC.cpy` (transaction record: 103 bytes) with fields: TRANS-ID (12), TRANS-ACCT-ID (10), TRANS-TYPE (1), TRANS-AMOUNT (12 signed, V99), TRANS-DATE (8), TRANS-TIME (6), TRANS-DESC (40), TRANS-STATUS (2), TRANS-BATCH-ID (12) in `B:\Projects\portfolio\cobol-legacy-ledger\cobol\copybooks\TRANSREC.cpy`

- [ ] T007 Create `cobol/copybooks/COMCODE.cpy` (constants: status codes, bank IDs, types) with groups: RESULT-CODES (RC-SUCCESS='00', RC-NSF='01', RC-LIMIT-EXCEEDED='02', RC-INVALID-ACCT='03', RC-ACCOUNT-FROZEN='04', RC-FILE-ERROR='99'), BANK-IDS (BANK-FIRST-NATL='BANK_A', etc.), ACCOUNT-TYPES (ACCT-CHECKING='C', ACCT-SAVINGS='S'), TX-TYPES (TX-DEPOSIT='D', etc.), DAILY-LIMIT=10000.00, MAX-ACCOUNTS=100 in `B:\Projects\portfolio\cobol-legacy-ledger\cobol\copybooks\COMCODE.cpy`

- [ ] T008 Read COBOL_STYLE_REFERENCE.md Section 0.2 (annotated reference program REFERENCE.cob) and COBOL_SUPPLEMENTS.md Supplement C (program header template) to understand production-grade COBOL structure in `docs/handoff/COBOL_STYLE_REFERENCE.md` and `docs/handoff/COBOL_SUPPLEMENTS.md`

- [ ] T009 Create `cobol/KNOWN_ISSUES.md` using template from COBOL_SUPPLEMENTS.md Supplement B with sections: ACCOUNTS.cob (A1-A2), TRANSACT.cob (T1-T12), VALIDATE.cob (V1-V2), and scope limitations in `B:\Projects\portfolio\cobol-legacy-ledger\cobol\KNOWN_ISSUES.md`

---

## Phase 3: COBOL Programs

Core business logic. All 4 programs implement from specification in 02_COBOL_AND_DATA.md, not from external source.

- [ ] T010 Read COBOL_STYLE_REFERENCE.md Section 0.1 (SMOKETEST.cob) and run smoke test to verify compiler output format (balance representation with PIC S9(10)V99) before implementing ACCOUNTS.cob. Document result in notes. Reference: `docs/handoff/COBOL_STYLE_REFERENCE.md`

- [ ] T011 [P] Create `cobol/src/ACCOUNTS.cob` implementing: program header (System=BANK_{node}, Purpose=Account lifecycle), SELECT ACCOUNTS-FILE with FILE STATUS, WORKING-STORAGE including WS-FILE-STATUS and OCCURS table, PROCEDURE DIVISION with paragraphs: CREATE-ACCOUNT, READ-ACCOUNT, UPDATE-ACCOUNT, CLOSE-ACCOUNT, LIST-ACCOUNTS, CHECK-DUPLICATE, LOAD-ALL-ACCOUNTS, WRITE-ALL-ACCOUNTS. Output: pipe-delimited to stdout. Copy header template from COBOL_SUPPLEMENTS.md. Use production-grade structure throughout in `B:\Projects\portfolio\cobol-legacy-ledger\cobol\src\ACCOUNTS.cob`

- [ ] T012 [P] Create `cobol/src/TRANSACT.cob` implementing: program header (Purpose=Transaction processing engine), SELECT ACCOUNTS-FILE and TRANSACT-FILE with FILE STATUS, WORKING-STORAGE with transaction fields and tables, PROCEDURE DIVISION with paragraphs: PROCESS-DEPOSIT, PROCESS-WITHDRAW, PROCESS-TRANSFER, PROCESS-BATCH, BATCH-DEPOSIT, BATCH-WITHDRAW, BATCH-TRANSFER, BATCH-FEE, LOAD-ACCOUNTS, SAVE-ACCOUNTS, WRITE-TRANSACTION-RECORD. Include compliance check (>$9500 → COMPLIANCE|CTR-FLAG output). Output: pipe-delimited to stdout. Batch trace format per COBOL_SUPPLEMENTS.md Supplement A. Transaction IDs: TRX-{node}-{6-digit seq} in `B:\Projects\portfolio\cobol-legacy-ledger\cobol\src\TRANSACT.cob`

- [ ] T013 [P] Create `cobol/src/VALIDATE.cob` implementing: program header (Purpose=Business rules & validation), SELECT ACCOUNTS-FILE with FILE STATUS, WORKING-STORAGE with input/output fields, PROCEDURE DIVISION with paragraphs: CHECK-ACCOUNT-STATUS (frozen → '04', not found → '03'), CHECK-BALANCE (NSF → '01'), CHECK-DAILY-LIMIT (limit exceeded → '02'), VALIDATE-RECORD (calls checks in order, returns first failure or '00'). Output: RESULT|{RC} to stdout in `B:\Projects\portfolio\cobol-legacy-ledger\cobol\src\VALIDATE.cob`

- [ ] T014 [P] Create `cobol/src/REPORTS.cob` implementing: program header (Purpose=Reporting and reconciliation), SELECT ACCOUNTS-FILE and TRANSACT-FILE with FILE STATUS, PROCEDURE DIVISION with paragraphs: PRINT-STATEMENT (filter TRANSACT.DAT by account), PRINT-LEDGER (display all accounts with balances), PRINT-EOD (sum balances by type, count transactions by status), PRINT-AUDIT (full TRANSACT.DAT dump). Accept command-line operation: STATEMENT, LEDGER, EOD, AUDIT. Output: pipe-delimited to stdout in `B:\Projects\portfolio\cobol-legacy-ledger\cobol\src\REPORTS.cob`

- [ ] T015 [P] Create `scripts/build.sh`: Set bash options (set -e), check if cobc exists, create `cobol/bin/` dir, cd to `cobol/src`, compile all 4 programs with flags `-x -free -I ../copybooks` (copybook include path is critical), output success message. If cobc unavailable, exit gracefully with message in `B:\Projects\portfolio\cobol-legacy-ledger\scripts\build.sh`

---

## Phase 4: Seeding

Populate all 6 nodes with demo data.

- [ ] T016 [P] Create `scripts/seed.sh`: Bash script that for each node in (BANK_A, BANK_B, BANK_C, BANK_D, BANK_E, CLEARING), creates `banks/{NODE}/` dir, writes ACCOUNTS.DAT in fixed-width ACCTREC format (70 bytes per line, using exact data from 02_COBOL_AND_DATA.md account roster), writes empty TRANSACT.DAT, writes BATCH-INPUT.DAT with pipe-delimited sample transactions (from 02_COBOL_AND_DATA.md), generates .server_key using Python `secrets.token_hex(32)` (stored as 64-char hex string) in `B:\Projects\portfolio\cobol-legacy-ledger\scripts\seed.sh`

- [ ] T017 [P] Create `scripts/setup.sh`: Bash script that creates Python venv with `python3 -m venv python/venv`, activates it, runs `pip install -q -r python/requirements.txt`, outputs success message in `B:\Projects\portfolio\cobol-legacy-ledger\scripts\setup.sh`

---

## Phase 5: Python Bridge & Integrity

Core Python infrastructure.

- [ ] T018 Create `python/integrity.py` implementing IntegrityChain class: `__init__(db_connection, secret_key)` loads/creates chain_entries table; `get_latest_hash()` returns prev hash (GENESIS_HASH if empty); `append(tx_id, account_id, tx_type, amount, timestamp, description, status)` creates entry with `tx_hash = SHA-256(contents + prev_hash)` and `signature = HMAC-SHA256(tx_hash, secret_key)`, returns ChainedTransaction dict; `verify_chain()` checks all entries: linkage (prev_hash match), hash mismatch (recompute & compare), signature validity, returns {valid, entries_checked, time_ms, first_break, break_type, details}; `simulate_tamper(chain_index)` modifies entry, verifies detection, restores, returns tamper report; `get_chain_for_display(limit, offset)` returns list for UI in `B:\Projects\portfolio\cobol-legacy-ledger\python\integrity.py`

- [ ] T019 Create `python/auth.py` implementing AuthManager class: `__init__(db_connection, data_dir)` initializes auth, creates api_keys table; `initialize_default_keys()` generates default keys for TELLER, AUDITOR, ADMIN roles (returns dict mapping); `authenticate(api_key)` verifies key, returns AuthContext or None; `check_permission(auth, permission)` checks role-based permissions; `get_role_permissions(role)` returns permission set; `list_keys()` returns all keys; PERMISSIONS dict with 3 roles, each with specific permission strings (cobol.translate removed per clarification), all keys with HASH not plaintext in database in `B:\Projects\portfolio\cobol-legacy-ledger\python\auth.py`

- [ ] T020 Create `python/bridge.py` implementing COBOLBridge class: `__init__(node, bin_dir, data_dir, cobol_src_dir, db_path)` where bin_dir and db_path resolved to absolute paths, db_path defaults to `{data_dir}/{node.lower()}.db` (per-node database); `list_accounts()` returns list of account dicts from SQLite; `get_account(account_id)` returns single account dict or None; `create_account(account_id, name, account_type, initial_balance)` writes to SQLite + COBOL execution if available; `process_transaction(account_id, tx_type, amount, description, target_id, batch_id)` executes TRANSACT.cob as subprocess with `cwd=banks/{node}/` (resolved to absolute), parses pipe-delimited output, updates SQLite, appends to integrity chain, returns {tx_id, status, balance_before, balance_after, chain}; `run_cobol(program, operation, args)` executes binary as subprocess with absolute binary path and resolved CWD, captures stdout/stderr, parses output; `get_status()` returns system health dict; `chain` property exposes IntegrityChain instance; fallback to Mode B (Python file I/O) if COBOL unavailable in `B:\Projects\portfolio\cobol-legacy-ledger\python\bridge.py`

- [ ] T021 Create `python/cli.py` implementing CLI commands with click: `init-db [NODE]` initializes SQLite schema (accounts, transactions, chain_entries, api_keys tables); `seed-demo [NODE]` calls generate_demo_data() for seeding; `list-nodes` shows all 6 nodes with account counts; `verify-chain [NODE]` runs bridge.chain.verify_chain() and displays results; `run-batch [NODE]` executes BATCH-INPUT.DAT on node; `status` shows system health in `B:\Projects\portfolio\cobol-legacy-ledger\python\cli.py`

- [ ] T022 [P] Create `python/tests/__init__.py` (empty) in `B:\Projects\portfolio\cobol-legacy-ledger\python\tests\__init__.py`

- [ ] T023 [P] Create `python/tests/test_integrity.py` with tests: `test_chain_append_and_retrieve()` (append entry, verify retrieval), `test_chain_verification_passes_when_valid()` (verify clean chain), `test_chain_verification_detects_hash_mismatch()` (corrupt balance, detect), `test_chain_verification_detects_signature_fraud()` (corrupt signature, detect), `test_chain_verification_detects_linkage_break()` (break link, detect), `test_tamper_simulation()` (inject tamper, detect, restore) in `B:\Projects\portfolio\cobol-legacy-ledger\python\tests\test_integrity.py`

- [ ] T024 [P] Create `python/tests/test_bridge.py` with tests: `test_bridge_initialization()` (create bridge), `test_create_account()` (add account), `test_list_accounts()` (retrieve demo accounts), `test_get_account()` (fetch by ID), `test_process_deposit()` (deposit transaction), `test_process_withdraw_nsf()` (withdraw with insufficient funds), `test_process_transfer()` (transfer between accounts), `test_run_batch()` (batch processing), `test_chain_integrated_with_transactions()` (each tx in chain), `test_get_status()` (health summary) in `B:\Projects\portfolio\cobol-legacy-ledger\python\tests\test_bridge.py`

---

## Phase 6: Demo & Gate Verification

End-to-end demonstration and verification.

- [ ] T025 Create `scripts/demo.sh` implementing Phase 1 scenario: Alice (BANK_A) sends $5,000 to Bob (BANK_B), CLEARING settles the transfer, all chains updated and verified. Steps: (1) output header with scenario description, (2) call build.sh, (3) call setup.sh, (4) call seed.sh, (5) initialize Python bridge for all nodes, (6) execute transfer (Alice debit → CLEARING credit/debit → Bob credit), (7) verify chains on BANK_A, BANK_B, CLEARING with detailed output showing tx_id, status, balance changes, chain verification result in `B:\Projects\portfolio\cobol-legacy-ledger\scripts\demo.sh`

- [ ] T026 [US6] Verify Phase 1 Gate Check 1: `scripts/build.sh` runs and produces `cobol/bin/ACCOUNTS`, `cobol/bin/TRANSACT`, `cobol/bin/VALIDATE`, `cobol/bin/REPORTS` (or gracefully skips if cobc unavailable). Expected: files exist or message printed in `B:\Projects\portfolio\cobol-legacy-ledger\cobol\bin\`

- [ ] T027 [US6] Verify Phase 1 Gate Check 2: `scripts/seed.sh` runs successfully. Expected: `banks/BANK_A/ACCOUNTS.DAT` contains 8 accounts (fixed-width, 70 bytes each), `banks/CLEARING/ACCOUNTS.DAT` contains 5 nostro accounts (NST-BANK-A through NST-BANK-E), all batch files present, all .server_key files generated in `banks/{NODE}/`

- [ ] T028 [US6] Verify Phase 1 Gate Check 3: Python bridge lists correct account counts. Run: `python -c "from python.bridge import COBOLBridge; b = COBOLBridge(node='BANK_A'); assert len(b.list_accounts()) == 8"` for all 6 nodes. Expected: BANK_A(8), BANK_B(7), BANK_C(8), BANK_D(6), BANK_E(8), CLEARING(5) in `python/bridge.py`

- [ ] T029 [US6] Verify Phase 1 Gate Check 4: Transaction processing returns status 00. Run: `b.process_transaction('ACT-A-001', 'D', 1000.00, 'test')`. Expected: status='00', tx_id starts with 'TRX-A-', balance_after > balance_before in `python/bridge.py`

- [ ] T030 [US6] Verify Phase 1 Gate Check 5: Integrity chain records and verifies. Run: `b.chain.verify_chain()`. Expected: valid=True, entries_checked > 0, time_ms < 100 in `python/bridge.py`

- [ ] T031 [US3] Test Mode A (with COBOL): seed.sh creates ACCOUNTS.DAT, bridge loads via COBOL subprocess, parses output, syncs to SQLite. Verify account counts match. Expected: BANK_A has 8 accounts in SQLite in `python/bridge.py`

- [ ] T032 [US5] Test Mode B (without COBOL): Simulate COBOL unavailable, seed.sh creates ACCOUNTS.DAT, bridge reads directly via Python file I/O, parses fixed-width records, syncs to SQLite. Verify account counts match Mode A. Expected: same results as Mode A in `python/bridge.py`

- [ ] T033 [US1] Verify SMOKETEST.cob ran before ACCOUNTS.cob implementation. Document in notes: exact balance format output (PIC S9(10)V99 representation). Expected: no literal decimal point in balance field in `docs/handoff/COBOL_STYLE_REFERENCE.md` section 0.1

- [ ] T034 [US4] Verify integrity chain for tampering: Run bridge.chain.simulate_tamper(chain_index=1), change balance from 15420.50 to 51420.50. Expected: verify_chain() detects hash_mismatch, shows first_break=1, returns valid=False in `python/integrity.py`

- [ ] T035 [US2] Verify NOSTRO IDs are exactly 10 characters: NST-BANK-A, NST-BANK-B, NST-BANK-C, NST-BANK-D, NST-BANK-E. Expected: each fits PIC X(10) in ACCTREC, no truncation in `banks/CLEARING/ACCOUNTS.DAT`

- [ ] T036 [US2] Verify transaction ID format TRX-{node}-{seq}: TRX-A-000001, TRX-B-000015, TRX-X-000003. Expected: exactly 12 characters, node code correct, sequence increments in `python/bridge.py`

- [ ] T037 [US4] Verify per-node key isolation: Read `banks/BANK_A/.server_key`, `banks/BANK_B/.server_key`, etc. Expected: 6 different 64-char hex strings, each node has unique key in `banks/{NODE}/.server_key`

- [ ] T038 [US1] Verify COBOL FILE STATUS on all files: Check ACCOUNTS.cob, TRANSACT.cob, VALIDATE.cob, REPORTS.cob for `FILE STATUS IS WS-FILE-STATUS` clause in all SELECT statements. Expected: present in all 4 programs in `cobol/src/*.cob`

- [ ] T039 [US1] Verify COBOL production headers: Check all 4 programs for comment block with: System, Node, Author, Purpose, Operations, Files, Copybooks, Output Format, Exit Codes, Dependencies, Change Log. Expected: all sections present, following COBOL_SUPPLEMENTS.md Supplement C template in `cobol/src/*.cob`

- [ ] T040 [US2] Verify seed.sh creates .server_key per node: Confirm `banks/BANK_A/.server_key` through `banks/CLEARING/.server_key` exist and contain 64-char hex strings. Expected: all 6 files exist with valid format in `banks/{NODE}/.server_key`

- [ ] T041 [US3] Verify bridge resolves paths to absolute: Check COBOLBridge.__init__ resolves bin_dir and db_path. Expected: Path.resolve() used on both, no relative paths in subprocess calls in `python/bridge.py`

- [ ] T042 [US3] Verify bridge subprocess uses correct CWD: Check run_cobol() sets cwd=banks/{NODE}/ (resolved to absolute). Expected: COBOL subprocess finds ACCOUNTS.DAT relative to node directory in `python/bridge.py`

- [ ] T043 [US2] Verify BATCH-INPUT.DAT format: Check `banks/BANK_A/BATCH-INPUT.DAT` for pipe-delimited format with 4 fields (D/W/I/F) and 5 fields (T transfers). Expected: format matches spec, all transfers have TARGET_ID in `banks/{NODE}/BATCH-INPUT.DAT`

- [ ] T044 [US4] Verify CTR compliance detection: Check TRANSACT.cob detects deposits/transfers > $9,500 and outputs `COMPLIANCE|CTR-FLAG|{TRANS-ID}|{AMOUNT}`. Expected: Elena Petrov's $9,500 deposit triggers flag (not >10000) in `cobol/src/TRANSACT.cob`

- [ ] T045 [US4] Verify compliance output is parsed by bridge: Run transaction that exceeds $9,500, check bridge output includes compliance warning. Expected: bridge relays warning, doesn't validate (COBOL is source of truth) in `python/bridge.py`

- [ ] T046 [US6] Run full Phase 1 gate (all 5 checks): Execute demo.sh or manual gate verification. Expected: all 5 checks pass in `scripts/demo.sh`

- [ ] T047 [US6] Verify Phase 1 gate is repeatable: Run gate verification twice. Expected: same results both times (idempotent) in `scripts/demo.sh` and `python/bridge.py`

---

## Task Status

**Ready for `/speckit.build`**

All 47 tasks defined with explicit file paths and dependencies clearly documented. No tasks without file locations. Parallel opportunities identified (COBOL programs, Python modules, tests).

---

## Execution Notes

### Sequential Execution Order (Critical Path)

1. Phase 1 (T001-T004) — Setup
2. Phase 2 (T005-T009) — Foundation (copybooks + headers)
3. Phase 3 (T010-T015) — COBOL programs (with T010 smoke test first)
4. Then parallel:
   - Phase 4 (T016-T017) — Seeding scripts
   - Phase 5 (T018-T024) — Python modules
5. Phase 6 (T025-T047) — Verification

### Parallelizable Tasks

- T011, T012, T013, T014 — Four COBOL programs can compile in parallel (after T015 build.sh created)
- T018, T019, T020, T021 — Python modules can develop in parallel (after requirements.txt)
- T023, T024 — Tests can run in parallel

### Blockers

- T005-T007 copybooks block T011-T014 COBOL programs
- T011-T014 COBOL programs block T015 build.sh
- T015 build.sh blocks T016 seed.sh
- T016 seed.sh blocks T018-T047 Python and verification

---

## Gate Status

**Gate**: All tasks must have explicit file paths and be independently executable.

**Result**: ✅ **PASS** — All 47 tasks have file locations and no dependencies on vague instructions.

**Ready for `/speckit.build`**
