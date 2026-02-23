# COBOL Known Issues

**System**: cobol-legacy-ledger Phase 1+2
**Version**: 2.0.0
**Last Updated**: 2026-02-23

All bugs are documented as-is (not fixed). This reflects authentic legacy COBOL behavior.
Issues marked [RESOLVED] were fixed in the Phase 2 quality hardening milestone.

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

### [RESOLVED] T-R1: Hardcoded Dates

**What**: Transaction records used hardcoded `20260217` for date and `101530` for time.

**Fix**: Replaced with `ACCEPT WS-CURRENT-DATE FROM DATE YYYYMMDD` and `ACCEPT WS-CURRENT-TIME FROM TIME` in Phase 2 quality hardening.

---

### [RESOLVED] T-R2: Self-Assignment Dead Code

**What**: Line 284 had `MOVE WS-IN-ACCT-ID TO WS-IN-ACCT-ID` (noop).

**Fix**: Removed in Phase 2 quality hardening.

---

### [RESOLVED] T-R3: Hardcoded Node in Batch Header

**What**: Batch processing header displayed `NODE: BANK_A` regardless of which node was running.

**Fix**: Now derives node code from loaded account IDs, displaying correct bank identifier.

---

### T10: WS-DAILY-TOTAL Not Persisted

**What**: Daily withdrawal limit stored in `WS-DAILY-TOTAL PIC 9(10)V99` (WORKING-STORAGE). Resets to 0 every time TRANSACT runs.

**Why**: WORKING-STORAGE is temporary. No persistence between program runs. Tracking daily limits requires a separate file or database table.

**Risk**: $10,000 daily limit applies PER RUN, not PER DAY. Customer can withdraw $10k multiple times per day if TRANSACT is called multiple times.

**Production Fix**: Implement daily limit file (date-keyed) or move to database transaction table.

---

### [RESOLVED] T11: Negative Balance Floor

**What**: Fee deductions could drive account balance negative.

**Fix**: FEES.cob implements balance floor protection — fees are skipped if they would cause a negative balance.

---

### T12: Account ID Clobbered During TRANSFER

**What**: In `PROCESS-TRANSFER`, when looking up the target account, the code overwrites the source account ID:

```cobol
MOVE WS-IN-TARGET-ID TO WS-IN-ACCT-ID
PERFORM FIND-ACCOUNT
```

Then uses the source index saved earlier. This pattern is fragile.

**Why**: Memory constraints in 1970s-80s COBOL encouraged variable reuse.

**Risk**: If code is refactored and the index save is deleted, source account becomes corrupted.

**Production Fix**: Use separate variables (WS-SOURCE-ID, WS-TARGET-ID). Never reuse.

---

## REPORTS.cob Issues

### [RESOLVED] R-R1: Nested IF Chain for Status Codes

**What**: PRINT-EOD used 5-deep nested `IF/ELSE IF/END-IF` chain for transaction status counting.

**Fix**: Replaced with `EVALUATE TRANS-STATUS` block in Phase 2 quality hardening.

---

## INTEREST.cob Issues (Phase 2 — New)

### I1: Interest Not Compounded

**What**: Interest is calculated on the current balance, not on a compounding basis. If run multiple times in a month, interest is applied to the already-increased balance.

**Why**: Monthly batch assumption — designed to run exactly once per month.

**Risk**: Low. Simulation controls execution frequency.

**Production Fix**: Track last interest accrual date per account and prevent double-posting.

---

## RECONCILE.cob Issues (Phase 2 — New)

### R1: No Persisted Opening Balances

**What**: Reconciliation cannot fully verify balance changes because opening balances (at seed time) are not stored separately. Current implementation verifies transaction log internal consistency.

**Why**: Would require an additional file or database column for seed/opening balances.

**Risk**: Cannot detect silent balance corruption that occurred before the first transaction.

**Production Fix**: Store opening balance at account creation time and use for full reconciliation.

---

## Python Integration Issues

### P1: Bridge Parser Must Match COBOL Output Format Exactly

**What**: COBOL outputs `PIC S9(10)V99` balance as 12-digit signed number (no literal decimal point). Python parser must expect this exact format.

**Why**: Mismatch between COBOL display format and Python parsing expectations.

**Risk**: **HIGHEST RISK IN PHASE 1**. If parser expects "1542050.00" but COBOL outputs "000001542050", every balance is parsed wrong. Silent data corruption.

**Production Fix**: Run SMOKETEST.cob first. Observe actual output. Lock parser to match.

---

## Scope Limitations (Phase 1-2)

### C1: No Multi-User Concurrent Access

Demonstration context. Single operator, sequential batch.

### C2: No Daily Limit Persistence

Daily withdrawal limit resets per TRANSACT run. Would require additional infrastructure.

### C3: No Encrypted Data at Rest

.DAT files are plaintext. The integrity chain detects tampering but does not prevent reading.

---

## How to Use This Document

1. **For interviewers**: "Here's what I documented from v1+v2. These aren't secret — they're authentic COBOL patterns."
2. **For Phase 3 planning**: These become requirements for the Python coordinator.
3. **For auditors**: "We know about these. Here's why they exist and the production fix for each."
