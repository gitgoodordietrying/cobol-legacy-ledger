# Phase 2 Ready — Smoke Test is the Gate

**Date**: 2026-02-18
**Status**: Phase 1 complete, Phase 2 blocked by smoke test observation
**Blocker**: GnuCOBOL not available on current dev environment

---

## What's Complete

✓ **Phase 1 Foundation**:
- Python bridge (Mode A + Mode B)
- Integrity chain with <100ms verification
- Per-node SQLite, per-node HMAC keys
- 42 seeded accounts across all 6 nodes
- CLI interface
- 21 unit tests (Mode B path)
- Transaction ID format fixed (TRX-A-000001, exactly 12 chars)

✓ **Specifications Locked**:
- Batch trace format (COBOL_SUPPLEMENTS.md Supplement A — columnar, mainframe-style)
- VALIDATE logic (inline in TRANSACT.cob + standalone utility)
- All 4 COBOL programs specified and ready for implementation
- Balance parser logic implemented (pending validation against real COBOL output)

✓ **Documentation Complete**:
- PHASE2_PREREQUISITES.md — Full implementation plan
- SMOKE_TEST_SETUP.md — Step-by-step guide with troubleshooting
- COBOL_STYLE_REFERENCE.md — Patterns and annotations
- COBOL_SUPPLEMENTS.md — Batch format, known issues, headers

---

## What's Blocked

🚫 **Smoke Test**: Cannot run on current system (no sudo, no GnuCOBOL)

**Why it matters**:
- Bridge parser assumes PIC S9(10)V99 displays as `00000012345.67` (13 chars with dot)
- If actual COBOL output differs, parser will silently produce wrong numbers
- Every transaction in Phase 2 depends on this being correct
- This is the de-risk gate — must observe real output before writing COBOL

---

## Your Next Action (Only Step Needed)

Run this on a system where you have GnuCOBOL installed (or can install it):

```bash
# 1. Install cobc if not already present
sudo apt install gnucobol  # or brew install gnu-cobol, or Windows installer
cobc --version

# 2. Navigate to project
cd /path/to/cobol-legacy-ledger

# 3. Compile SMOKETEST
cd cobol/src
cobc -x -free -I ../copybooks SMOKETEST.cob -o ../bin/SMOKETEST

# 4. Run it and capture output
cd ../../banks/BANK_A
../../cobol/bin/SMOKETEST > smoketest_output.txt
cat smoketest_output.txt

# 5. Create SMOKE_TEST_OBSERVATION.md with:
# - The actual output (paste here)
# - Analysis of balance field format
# - Validation that parser matches
```

**That's it.** Once you do this and we have the actual output, Phase 2 implementation is completely unblocked.

---

## After Smoke Test: Straight Path to Phase 2

```
Smoke Test (observe balance format)
    ↓
Validate bridge parser (or fix if needed)
    ↓
ACCOUNTS.cob (file I/O, LIST operation)
    ↓
TRANSACT.cob (batch processing, columnar output, compliance flags)
    ↓
VALIDATE.cob (inline in TRANSACT + standalone utility)
    ↓
REPORTS.cob (ledger, statement, EOD, audit)
    ↓
Integration tests (Mode A vs Mode B identical)
    ↓
Cross-node verifier (Python, detects which bank tampered)
    ↓
Dashboard (interactive demo, columnar batch output, tamper detection UI)
```

---

## Files Ready for Phase 2 Implementation

### COBOL Programs (Stubs, Ready to Implement)
- `cobol/src/ACCOUNTS.cob` — Spec locked, patterns in COBOL_STYLE_REFERENCE.md
- `cobol/src/TRANSACT.cob` — Spec locked, batch format from COBOL_SUPPLEMENTS.md Supplement A
- `cobol/src/VALIDATE.cob` — Spec locked, inline logic in TRANSACT + utility in VALIDATE
- `cobol/src/REPORTS.cob` — Spec locked, 4 operations (LEDGER, STATEMENT, EOD, AUDIT)

### Data & Configuration
- `cobol/copybooks/ACCTREC.cpy` — 70-byte record (locked ✓)
- `cobol/copybooks/TRANSREC.cpy` — 103-byte record (locked ✓)
- `cobol/copybooks/COMCODE.cpy` — Constants (locked ✓)
- `banks/*/ACCOUNTS.DAT` — Seeded with all 42 accounts (locked ✓)

### Bridge Ready for Mode A
- `python/bridge.py` — Mode A (subprocess execution) ready to test
- `python/tests/test_bridge_mode_a.py` — Ready to add Mode A tests

### Documentation
- `COBOL_STYLE_REFERENCE.md` — Section 0.2: Annotated reference program with all patterns
- `COBOL_STYLE_REFERENCE.md` — Section 0.3: GnuCOBOL cheat sheet (18 critical points)
- `COBOL_SUPPLEMENTS.md` — Supplement A: Batch trace format (columnar, mainframe-style)
- `COBOL_SUPPLEMENTS.md` — Supplement B: KNOWN_ISSUES.md template
- `COBOL_SUPPLEMENTS.md` — Supplement C: Program header template

---

## Critical Notes for Implementation

### Batch Trace Format (NON-NEGOTIABLE)
When writing TRANSACT.cob BATCH mode, follow COBOL_SUPPLEMENTS.md Supplement A EXACTLY:
- Columnar layout with aligned columns
- Dollar formatting: PIC $$$,$$9.99 with leading spaces
- Status column: "OK" or "FAIL##" with specific codes
- CTR! flag in status for compliance warnings (large transactions)
- This is not pipe-delimited. This is real mainframe-style COBOL output.

Example (from spec):
```
001  OK      DEP   $  5,000.00   ACT-A-001   $ 20,420.50   Payroll deposit — Santos
002  FAIL02  WIT   $ 50,000.00   ACT-B-001   $175,000.00   LIMIT EXCEEDED — Rejected
```

### VALIDATE.cob Architecture (LOCKED)
- Primary validation: Inline paragraphs in TRANSACT.cob (CHECK-ACCOUNT-STATUS, CHECK-BALANCE, CHECK-DAILY-LIMIT)
- Utility validation: Standalone VALIDATE.cob program for pre-flight checks from Python bridge
- NOT a subprocess per transaction (would be inefficient, not authentic to real COBOL)

### Balance Parser (PENDING VALIDATION)
- Current assumption: `00000012345.67` (13 chars, 10 + dot + 2)
- Will be validated against SMOKETEST.cob output
- If mismatch found, update `bridge.py` `_parse_balance()` method
- This MUST be correct before ACCOUNTS.cob produces real output

### Transaction ID Format (FIXED ✓)
- Format: `TRX-{node_code}-{6-digit seq}` (exactly 12 chars for PIC X(12))
- Node codes: A (BANK_A), B (BANK_B), C (BANK_C), D (BANK_D), E (BANK_E), Z (CLEARING)
- Examples: TRX-A-000001, TRX-B-000042, TRX-Z-000005
- Fixed in bridge.py, tests updated

---

## Timeline After Smoke Test

Assuming smoke test takes 30 minutes (install + compile + run + document):

| Phase | Program | Est. Time | Blocker |
|-------|---------|-----------|---------|
| 2.0 | Smoke Test | 0.5 hrs | GnuCOBOL install |
| 2.1 | ACCOUNTS.cob | 2 hrs | Smoke test complete |
| 2.2 | TRANSACT.cob | 4 hrs | ACCOUNTS working |
| 2.3 | VALIDATE.cob | 1 hr | TRANSACT done |
| 2.4 | REPORTS.cob | 2 hrs | Core done |
| 2.5 | Integration + Mode A tests | 2 hrs | All programs done |
| 3.0 | Cross-node verifier | 3 hrs | Core done |
| 4.0 | Dashboard | 4 hrs | Verifier done |
| **Total** | **Full Phase 2-4** | **~18-20 hrs** | **Smoke test** |

---

## Success Criteria for Smoke Test

All of these must be true:
- [ ] GnuCOBOL installed and `cobc --version` works
- [ ] SMOKETEST.cob compiles without errors
- [ ] SMOKETEST.cob runs and produces output
- [ ] Output shows three lines (WRITE, READ, PASS)
- [ ] Balance field in READ line is analyzed (format, character count)
- [ ] Bridge parser validation test shows Match: True (or fix documented)
- [ ] SMOKE_TEST_OBSERVATION.md created with all details
- [ ] TEST-ACCOUNTS.DAT created in banks/BANK_A/ (70 bytes + newline)

---

## How to Proceed

**Option A: Run on your development machine now**
1. Install GnuCOBOL on a system where you have sudo/admin privileges
2. Clone/sync the project
3. Follow SMOKE_TEST_SETUP.md steps 1-7
4. Share SMOKE_TEST_OBSERVATION.md output
5. Validation complete, Phase 2 unblocked

**Option B: Run via Docker (if preferred)**
```bash
docker run -it --rm -v $(pwd):/work -w /work ubuntu:22.04 bash
apt-get update && apt-get install -y gnucobol
cd /work
# Now follow SMOKE_TEST_SETUP.md steps 2-7
```

**Option C: Run on WSL (Windows Subsystem for Linux)**
1. Open WSL Ubuntu terminal
2. Install GnuCOBOL in WSL
3. Navigate to project in WSL
4. Follow SMOKE_TEST_SETUP.md steps 2-7

---

## Current Project Structure

```
cobol-legacy-ledger/
├── cobol/
│   ├── bin/                        # Compiled binaries (empty until SMOKETEST)
│   ├── src/
│   │   ├── SMOKETEST.cob          # Smoke test (ready to compile)
│   │   ├── ACCOUNTS.cob           # Stub (ready to implement)
│   │   ├── TRANSACT.cob           # Stub (ready to implement)
│   │   ├── VALIDATE.cob           # Stub (ready to implement)
│   │   └── REPORTS.cob            # Stub (ready to implement)
│   └── copybooks/
│       ├── ACCTREC.cpy            # 70-byte account record (locked ✓)
│       ├── TRANSREC.cpy           # 103-byte transaction record (locked ✓)
│       └── COMCODE.cpy            # Constants (locked ✓)
├── python/
│   ├── bridge.py                  # Mode A + B ready
│   ├── integrity.py               # Verified ✓
│   ├── auth.py                    # Verified ✓
│   ├── cli.py                     # Verified ✓
│   └── tests/
│       ├── test_integrity.py      # 21 tests passing ✓
│       └── test_bridge.py         # Mode B tests passing ✓
├── banks/
│   ├── bank_a/
│   │   ├── ACCOUNTS.DAT           # Seeded ✓
│   │   ├── bank_a.db              # SQLite (empty until transactions)
│   │   └── .server_key            # HMAC key (created) ✓
│   └── [similarly for b through e, plus clearing]
├── scripts/
│   ├── build.sh                   # Ready (waiting for cobc) ✓
│   ├── seed.sh                    # Executed ✓
│   ├── setup.sh                   # Ready ✓
│   └── demo.sh                    # Ready (waiting for COBOL) ✓
├── docs/handoff/
│   ├── COBOL_STYLE_REFERENCE.md   # Annotations + cheat sheet ✓
│   ├── COBOL_SUPPLEMENTS.md       # Batch format + known issues + header template ✓
│   └── [other handoff docs]       # Complete ✓
└── SMOKE_TEST_SETUP.md            # Step-by-step guide (created) ✓
```

---

## The Gate is Clear

Phase 1 is complete. All specifications are locked. All infrastructure works. The only thing blocking Phase 2 is the smoke test observation — a 30-minute task on a system with GnuCOBOL installed.

**Next: Run SMOKE_TEST.cob and paste the output.**

