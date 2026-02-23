# Phase 2 Prerequisites & Critical Issues

**Updated**: 2026-02-17 (Post-Phase-1 review)

---

## 🚨 Critical Bug Fixes (Phase 1 → Phase 1.1)

### Transaction ID Format — FIXED ✓

**Issue**: Transaction IDs were being generated as `TRX-BANK_A-000001` (17 chars), which silently truncates to 12 chars in the TRANSREC `PIC X(12)` TRANS-ID field, losing the sequence number.

**Root Cause**: Used full node name `self.node` instead of single-letter node code.

**Fix Applied**:
- Added NODE_CODES mapping: `{"BANK_A": "A", "BANK_B": "B", ..., "CLEARING": "Z"}`
- Updated generation: `TRX-{node_code}-{seq}` format (exactly 12 chars: TRX-A-000001)
- Fixed substr offset: Changed from `substr(tx_id, 9)` to `substr(tx_id, 7)` (correct for new format)
- Updated tests to verify 12-char format

**Impact**: Critical. Every transaction record written to DAT file would have been corrupted. Same class of bug as the NOSTRO-BANK-A overflow we caught in handoff proofread.

**Status**: ✓ FIXED in bridge.py and test_bridge.py

---

## ⚠️ Known Limitations (Phase 1)

### COBOL Programs Are Stubs

**Status**: ACCOUNTS.cob, TRANSACT.cob, VALIDATE.cob, REPORTS.cob are empty shells.

**What They Don't Do Yet**:
- File I/O choreography (OPEN, READ, WRITE, CLOSE)
- Batch transaction processing with compliance CTR warnings
- Pipe-delimited output formatting
- Status code logic and error handling
- BATCH-INPUT.DAT parsing and validation

**Why This Is OK for Phase 1**: The bridge operates in Mode B (Python-only), reading DAT files directly without COBOL subprocess. Phase 1 gate doesn't require real COBOL programs.

**Why This Matters for Phase 2**: COBOL programs ARE the main deliverable. Phase 1 built scaffolding; Phase 2 needs to build the house. When COBOL programs are implemented, the bridge will switch to Mode A (subprocess execution).

---

### Smoke Test Never Ran

**Issue**: SMOKETEST.cob exists but was never compiled or executed (GnuCOBOL not available on dev system).

**What Should Have Happened**:
```bash
cobc -x -free -I ../copybooks SMOKETEST.cob -o cobol/bin/SMOKETEST
cd banks/BANK_A
../../cobol/bin/SMOKETEST
# Observe output showing actual PIC S9(10)V99 balance format
```

**Expected Output** (from COBOL_STYLE_REFERENCE.md):
```
OK|READ|ACT-T-001 |Smoke Test User               |C|00000012345.67|A|20260217|20260217
```

**What This Means**: The balance format `00000012345.67` is ASSUMED, not OBSERVED. When real COBOL is implemented, it might display balance differently.

**Risk**: Parser mismatch. If COBOL's actual DISPLAY format differs from assumption, the bridge parser will silently produce wrong numbers for all transactions.

---

### Tests Are Mode B Only

**Status**: 21 unit tests validate the Python-only fallback path.

**What's Not Tested**:
- Mode A (COBOL subprocess execution)
- Pipe-delimited stdout parsing from COBOL ACCOUNTS LIST
- Integration with real COBOL file I/O

**Why This Matters**: When Phase 2 implements real COBOL, tests should verify both modes:
- Mode B tests: Direct DAT file parsing (existing ✓)
- Mode A tests: COBOL subprocess + stdout parsing (TBD)

---

## 📋 Phase 2 Prerequisites & Sequence

### Must Do First (Before Any COBOL Implementation)

#### 1. Run Smoke Test & Observe Balance Format
**Prerequisite**: GnuCOBOL available on developer system

**Steps**:
```bash
cd /path/to/project
cobc -x -free -I cobol/copybooks cobol/src/SMOKETEST.cob -o cobol/bin/SMOKETEST
mkdir -p banks/BANK_TEST
cd banks/BANK_TEST
../../cobol/bin/SMOKETEST
```

**Output to Document**:
```
OK|WRITE|ACT-T-001|Smoke Test User
OK|READ|ACT-T-001 |Smoke Test User               |C|??????|A|20260217|20260217
SMOKE-TEST|PASS|All checks succeeded
```

**What to Extract**: The actual balance rendering in the READ line (marked with `??????` above). Count characters, note format:
- Does it show "00000012345.67" (13 chars with dot)?
- Does it show "000001234567" (12 chars, no dot)?
- Does it show something else?

**Document In**: Create `SMOKE_TEST_OBSERVATION.md` with actual output

**Purpose**: Validate that bridge.py's `_parse_balance()` method correctly interprets COBOL's display format

---

#### 2. Update bridge.py's `_parse_balance()` Method
**If needed**: Adjust balance parser to match observed COBOL format

**Current Implementation** (in bridge.py):
```python
def _parse_balance(self, balance_bytes: bytes) -> float:
    # Assumes: 12 ASCII digits with implied decimal
    # Example: b'000001234567' → 12345.67
    balance_str = balance_bytes.decode('ascii').strip()
    # [parsing logic here]
    return balance
```

**Validation**: After observing smoke test output, write a test case:
```python
def test_balance_parsing_vs_cobol_output():
    # Use actual smoke test output values
    assert bridge._parse_balance(b'000001234567') == 12345.67
    # (values taken from actual COBOL output)
```

---

#### 3. Document Batch Trace Format
**From**: COBOL_SUPPLEMENTS.md Supplement A

**What to Implement in Phase 2**:
- DISPLAY output format during BATCH processing
- Columnar layout with `PIC $$$,$$$,$$9.99` for dollar formatting
- Batch status codes (e.g., FAIL01, FAIL04)
- Compliance CTR warning flag
- Python-only hash footer

**Example** (from spec):
```
BATCH|BEGIN|BAT20260217080000|TOTAL=0|SUCCESS=0|FAILED=0
BATCH|TRX|TRX-A-000001|ACT-A-001|D|$1,000.00|OK|00
BATCH|CTR|COMPLIANCE WARNING: Wire transfer >$100k|CHECK REQUIRED
BATCH|END|BAT20260217080000|TOTAL=1|SUCCESS=1|FAILED=0
HASH|ABC123DEF456...
```

---

### Phase 2a: Cross-Node Verifier (Lower Risk, No COBOL Required)

**Goal**: Implement multi-node tamper detection

**Files to Create**:
- `python/verifier.py` — Instantiate bridges for all 6 nodes, compare chains
- `python/tests/test_verifier.py` — Test tamper detection scenarios

**Key Methods**:
- `compare_chains(node1, node2)` → {matching: bool, differences: []}
- `detect_tampering_in_node(node)` → {tampered: bool, first_break: int, ...}
- `verify_all_nodes()` → {all_valid: bool, node_status: {...}, ...}

**Demo Flow**:
1. Seed all 6 nodes with transactions
2. Corrupt BANK_A's chain_entries table
3. verifier.verify_all_nodes() returns:
   ```
   {
     "all_valid": false,
     "node_status": {
       "BANK_A": {"valid": false, "first_break": 1, ...},
       "BANK_B": {"valid": true},
       "BANK_C": {"valid": true},
       ...
     },
     "tampered_nodes": ["BANK_A"]
   }
   ```

**Why This First**: Doesn't require real COBOL. Validates integrity chain across all nodes. Can be done immediately.

---

### Phase 2b: Real COBOL Implementation (Higher Risk, COBOL Required)

**Prerequisite**: SMOKE_TEST_OBSERVATION.md complete, balance parser validated

**Files to Implement**:
- `cobol/src/ACCOUNTS.cob` — Full implementation
  - LIST operation: Read ACCOUNTS.DAT, output pipe-delimited
  - CREATE operation: Validate, write new account

- `cobol/src/TRANSACT.cob` — Full implementation
  - DEPOSIT: Read account, validate, write transaction, update balance
  - WITHDRAW: Read account, validate balance/limits, write transaction
  - BATCH: Process BATCH-INPUT.DAT with compliance checks

- `cobol/src/VALIDATE.cob` — Full implementation
  - CHECK-ACCOUNT-STATUS: Verify not frozen
  - CHECK-BALANCE: Verify sufficient funds
  - CHECK-DAILY-LIMIT: Verify amount ≤ $10,000

- `cobol/src/REPORTS.cob` — Full implementation
  - LEDGER: List all accounts
  - STATEMENT: Single account history
  - EOD: End-of-day summary
  - AUDIT: Full transaction audit

**Testing Strategy**:
1. Compile each program
2. Test individually with data files
3. Test with bridge in Mode A (subprocess)
4. Add Mode A test cases to bridge test suite
5. Compare Mode A vs Mode B results (should be identical)

**Key Deliverables**:
- Batch trace format implementation (COBOL_SUPPLEMENTS.md Supplement A)
- Compliance CTR warnings for large transactions
- Proper error codes and status reporting
- FILE STATUS error handling on all I/O operations

---

## 🗂️ Files Affected in Phase 2

### Smoke Test Observation
- **Create**: `SMOKE_TEST_OBSERVATION.md` (after running SMOKETEST.cob)
- **Update**: `bridge.py` _parse_balance() if needed (after observation)
- **Update**: `test_bridge.py` test_parse_balance() (add COBOL output cases)

### Cross-Node Verifier
- **Create**: `python/verifier.py` (new)
- **Create**: `python/tests/test_verifier.py` (new)
- **Update**: `cli.py` (add verify-all-nodes command)

### Real COBOL Implementation
- **Implement**: `cobol/src/ACCOUNTS.cob`
- **Implement**: `cobol/src/TRANSACT.cob`
- **Implement**: `cobol/src/VALIDATE.cob`
- **Implement**: `cobol/src/REPORTS.cob`
- **Create**: `BATCH_TRACE_OUTPUT.md` (document expected output format)
- **Update**: `bridge.py` test suite with Mode A tests
- **Update**: `test_bridge.py` (add subprocess execution tests)

### Documentation
- **Create**: `SMOKE_TEST_OBSERVATION.md`
- **Create**: `BATCH_TRACE_OUTPUT.md`
- **Update**: `KNOWN_ISSUES.md` (document bugs found + fixed)

---

## Decision: What Order?

### Recommended Sequence

**For Interview Demo Readiness**:
1. **Phase 2a: Cross-Node Verifier** (Week 1)
   - Completes "show which bank was tampered with" capability
   - Doesn't require COBOL
   - Adds cross-node tamper detection UI requirement for Phase 3

2. **Phase 2b: Real COBOL** (Week 2-3)
   - Run smoke test, observe balance format
   - Implement all 4 programs
   - Validate against Mode A tests

3. **Phase 3: Dashboard** (Week 4)
   - Interactive tamper demo with cross-node reporting
   - Show "BANK_A tampered" with visual detection time

**Advantage**: Demo works after Phase 2a (single-node detection), then adds multi-node intelligence in Phase 2b.

### Alternative: COBOL-First

If you want Phase 1 + COBOL to feel "complete":
1. **SMOKE_TEST_OBSERVATION** (immediately)
2. **Implement all COBOL** (Phase 2b)
3. **Cross-Node Verifier** (Phase 2a)
4. **Dashboard** (Phase 3)

**Advantage**: Full COBOL implementation before cross-node logic. Better for "COBOL-first" narrative.

---

## Testing Checklist for Phase 2

### Smoke Test Observation
- [ ] SMOKETEST.cob compiles without warnings
- [ ] TEST-ACCOUNTS.DAT created in banks/BANK_A/
- [ ] Read output shows exact balance format
- [ ] Balance parser validated against output
- [ ] SMOKE_TEST_OBSERVATION.md documented

### Cross-Node Verifier
- [ ] verifier.py instantiates all 6 bridges
- [ ] compare_chains() correctly identifies differences
- [ ] detect_tampering_in_node() finds first break
- [ ] verify_all_nodes() returns complete status
- [ ] test_verifier.py: 10+ tests covering all scenarios
- [ ] CLI command verify-all-nodes works

### Real COBOL
- [ ] ACCOUNTS.cob LIST operation reads and outputs correctly
- [ ] TRANSACT.cob DEPOSIT/WITHDRAW processes transactions
- [ ] VALIDATE.cob returns correct status codes
- [ ] REPORTS.cob generates all 4 report types
- [ ] bridge.py Mode A subprocess execution works
- [ ] Mode A and Mode B produce identical results
- [ ] test_bridge.py Mode A tests pass
- [ ] Batch trace format matches specification
- [ ] FILE STATUS error handling works

---

## Summary

**Phase 1 delivered**: Working Python infrastructure, correct data formats, integrity chain, all 6 nodes seeded.

**Phase 1 bug fixed**: Transaction ID format (was 17 chars, truncated to 12; now correct 12-char format).

**Phase 2 critical path**:
1. Observe smoke test balance format (or assume current parser is correct)
2. Cross-node verifier (no COBOL needed)
3. Real COBOL implementation (COBOL needed, smoke test observation critical)
4. Dashboard with multi-node tamper detection

**Key risk**: Balance parser hasn't been validated against real COBOL output. Run smoke test first.

