# COBOL Known Issues

**System**: cobol-legacy-ledger Phase 1
**Version**: 1.0.0
**Last Updated**: 2026-02-17

All bugs are documented as-is (not fixed). This reflects authentic legacy COBOL behavior.

---

## ACCOUNTS.cob Issues

### A1: Silent Overflow on Account Count

**What**: `LOAD-ALL-ACCOUNTS` uses `OCCURS 100 TIMES` for the temp account array. If a bank has >100 accounts, the 101st account is silently lost.

**Why**: Array bounds in COBOL are design-time fixed. Dynamic arrays require complex workarounds.

**Risk**: In production, opening the 101st account would disappear from the ledger. No error, no warning — just gone.

**Production Fix**: Use indexed file (VSAM) or database instead of sequential file + array cache.

---

### A2: O(n) Sequential Scan

**What**: Every READ or UPDATE operation scans the entire ACCOUNTS.DAT file sequentially. With 8 accounts per bank, this is negligible. With 10,000 accounts, this becomes a bottleneck.

**Why**: No indexing capability in line-sequential files. Modern systems use B-trees or hash indexes.

**Risk**: Performance degradation as account counts grow.

**Production Fix**: Implement indexed file (VSAM) or migrate to database with proper indexes.

---

## TRANSACT.cob Issues

### T1–T9: Debug TRACE Lines

**What**: Multiple `DISPLAY 'TRACE|...'` lines remain in the PROCEDURE DIVISION, outputting during normal operations.

**Example**:
```
TRACE|PERFORM PROCESS-DEPOSIT
TRACE|MOVE 3200.00 TO TRANS-AMOUNT
TRACE|ADD TRANS-AMOUNT TO ACCT-BALANCE
```

**Why**: Left in from development. Removing would require recompilation in production.

**Risk**: Makes stdout noisy. Python bridge must parse TRACE lines out of output stream.

**Production Fix**: Remove TRACE lines before production deployment. Implement proper logging instead.

---

### T10: WS-DAILY-TOTAL Not Persisted

**What**: Daily withdrawal limit stored in `WS-DAILY-TOTAL PIC 9(10)V99` (WORKING-STORAGE). Resets to 0 every time TRANSACT runs.

**Why**: WORKING-STORAGE is temporary. No persistence between program runs. Tracking daily limits requires a separate file or database table.

**Risk**: $10,000 daily limit applies PER RUN, not PER DAY. Customer can withdraw $10k multiple times per day if TRANSACT is called multiple times.

**Production Fix**: Implement daily limit file (date-keyed) or move to database transaction table.

---

### T11: Negative Balance Floor

**What**: `BATCH-FEE` subtracts a fee from an account balance without checking if it goes negative.

```cobol
SUBTRACT WS-IN-AMOUNT FROM WS-A-BAL(WS-FOUND-IDX)
```

**Why**: Original design allowed overdraft fees to drive balance negative (intentional or oversight — unclear).

**Risk**: Account balance can go negative. Customer sees "-$50.00" after fee.

**Production Fix**: Check balance >= fee amount before deducting. Return error code '01' (NSF) if insufficient.

---

### T12: Account ID Clobbered During TRANSFER

**What**: In `BATCH-TRANSFER`, when looking up the target account, the code overwrites the source account ID:

```cobol
MOVE WS-IN-TARGET-ID TO WS-IN-ACCT-ID
PERFORM FIND-ACCOUNT
```

Then later restores it. This pattern is fragile.

**Why**: Memory constraints in 1970s-80s COBOL encouraged variable reuse.

**Risk**: If code is refactored and the restore line is deleted, source account becomes corrupted. Subtle bugs.

**Production Fix**: Use separate variables (WS-SOURCE-ID, WS-TARGET-ID). Never reuse.

---

## Python Integration Issues

### P1: Bridge Parser Must Match COBOL Output Format Exactly

**What**: COBOL outputs `PIC S9(10)V99` balance as 12-digit signed number (no literal decimal point). Python parser must expect this exact format.

**Why**: Mismatch between COBOL display format and Python parsing expectations.

**Risk**: **HIGHEST RISK IN PHASE 1**. If parser expects "1542050.00" but COBOL outputs "000001542050", every balance is parsed wrong. Silent data corruption.

**Production Fix**: Run SMOKETEST.cob first. Observe actual output. Lock parser to match.

---

### P2: TRACE Line Parsing

**What**: Bridge must filter out `TRACE|...` lines from COBOL stdout. If TRACE output is parsed as a transaction record, bad data enters SQLite.

**Why**: TRACE lines left in production COBOL.

**Risk**: Noise in output stream if parser doesn't filter.

**Production Fix**: Bridge includes line filter (ignore lines starting with TRACE|).

---

## Scope Limitations (Phase 1)

### C1: No Cross-Node Settlement (Phase 2)

**What**: Phase 1 runs each node independently. No inter-bank settlement coordinator.

**Why**: Phase 2 feature.

**Risk**: None for Phase 1. By design.

---

### C2: No Daily Limit Persistence (Phase 2)

**What**: Daily withdrawal limit resets per TRANSACT run.

**Why**: Would require additional infrastructure (daily limit file or DB table).

**Risk**: Customers can exceed intended daily limits if TRANSACT is called multiple times.

---

### C3: No Netting or Position Reports (Phase 2)

**What**: Phase 1 records transactions. Phase 2 calculates settlement positions.

**Why**: Requires cross-node verification.

**Risk**: None for Phase 1. Demo is single-node transfers.

---

## How to Use This Document

1. **For interviewers**: "Here's what I documented from v1. These aren't secret — they're authentic COBOL patterns."
2. **For Phase 2 planning**: These become requirements for the Python coordinator.
3. **For auditors**: "We know about these. Here's why they exist and the production fix for each."
