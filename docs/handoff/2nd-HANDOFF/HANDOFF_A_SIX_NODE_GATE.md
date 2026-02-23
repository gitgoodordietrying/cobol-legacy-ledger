# HANDOFF A — Six-Node Verification Gate

**Project:** LegacyLedger: Closing the Multi-Bank Gap  
**Author:** Albert (AKD Solutions / Imperium)  
**Date:** February 19, 2026  
**Purpose:** Verify existing COBOL works across ALL 6 nodes before adding settlement logic  
**Sequence:** This document → HANDOFF_B (Settlement Coordinator) → HANDOFF_C (Cross-Node Integrity)

**READ THIS ENTIRE DOCUMENT BEFORE EXECUTING ANY COMMANDS.**

---

## 0. WHY THIS DOCUMENT EXISTS

The gap analysis revealed that only BANK_A has been tested. The COBOL programs compile and run correctly for a single node, but 5 of the 6 nodes (BANK_B, BANK_C, BANK_D, BANK_E, CLEARING) have never been exercised. Before writing any new code, we need ground truth: does the existing COBOL system work across all nodes?

**This is a verification-only task. Do NOT write new COBOL. Do NOT modify Python. Do NOT create new features.** The only acceptable modifications are:

- Fixing bugs discovered during testing (COBOL programs that fail on non-BANK_A nodes)
- Fixing seed data issues (missing or malformed .DAT files)
- Updating `cobol-test.sh` if tests make incorrect assumptions about node data

**Time estimate:** 30-60 minutes if everything works. 2-3 hours if bugs surface.

---

## 1. PRE-FLIGHT CHECKS

Before running anything, confirm the project state:

```bash
# 1. Docker image exists
docker image inspect cobol-dev &>/dev/null && echo "OK: cobol-dev image exists" || echo "FAIL: run docker build -t cobol-dev -f Dockerfile.cobol ."

# 2. COBOL binaries exist
ls -la cobol/bin/
# Expected: ACCOUNTS, TRANSACT, VALIDATE, REPORTS (all executable)
# If missing: run ./scripts/build.sh

# 3. All 6 node directories exist with seed data
for NODE in BANK_A BANK_B BANK_C BANK_D BANK_E CLEARING; do
    DIR="banks/$NODE"
    if [ -d "$DIR" ] && [ -f "$DIR/ACCOUNTS.DAT" ]; then
        BYTES=$(wc -c < "$DIR/ACCOUNTS.DAT")
        echo "OK: $DIR/ACCOUNTS.DAT ($BYTES bytes)"
    else
        echo "FAIL: $DIR missing or no ACCOUNTS.DAT"
    fi
done

# 4. Each node should also have BATCH-INPUT.DAT for batch testing
for NODE in BANK_A BANK_B BANK_C BANK_D BANK_E; do
    if [ -f "banks/$NODE/BATCH-INPUT.DAT" ]; then
        echo "OK: banks/$NODE/BATCH-INPUT.DAT exists"
    else
        echo "WARN: banks/$NODE/BATCH-INPUT.DAT missing (batch test will skip)"
    fi
done
```

**If any node directory is missing or has no ACCOUNTS.DAT:** Run `./scripts/seed.sh` first. If `seed.sh` doesn't populate all 6 nodes, that's a bug to fix before proceeding.

**Document the pre-flight results** by pasting the full output into DEV_LOG.md under a heading `## Six-Node Verification Gate — Pre-Flight`.

---

## 2. THE GATE: RUN cobol-test.sh FOR ALL 6 NODES

```bash
echo "========================================"
echo "  SIX-NODE VERIFICATION GATE"
echo "========================================"
echo ""

TOTAL_PASS=0
TOTAL_FAIL=0

for NODE in BANK_A BANK_B BANK_C BANK_D BANK_E CLEARING; do
    echo ""
    echo "════════════════════════════════════════"
    echo "  TESTING: $NODE"
    echo "════════════════════════════════════════"
    ./scripts/cobol-test.sh $NODE
    RESULT=$?
    if [ $RESULT -eq 0 ]; then
        TOTAL_PASS=$((TOTAL_PASS + 1))
    else
        TOTAL_FAIL=$((TOTAL_FAIL + 1))
    fi
done

echo ""
echo "========================================"
echo "  GATE RESULTS: $TOTAL_PASS nodes passed, $TOTAL_FAIL nodes failed"
echo "========================================"

if [ $TOTAL_FAIL -eq 0 ]; then
    echo "  ★ ALL 6 NODES OPERATIONAL ★"
    echo "  Proceed to HANDOFF_B (Settlement Coordinator)"
else
    echo "  ✗ FIX FAILURES BEFORE PROCEEDING"
fi
```

**Expected outcome:** All 6 nodes pass. The COBOL programs are designed to be node-agnostic — they operate on whatever .DAT files are in the current working directory. If the seed data is correct, the same binaries should work on every node.

---

## 3. KNOWN DIFFERENCES: CLEARING vs BANK NODES

The CLEARING node is architecturally different from the 5 bank nodes:

| Aspect | BANK_A through BANK_E | CLEARING |
|--------|----------------------|----------|
| Account IDs | `ACT-{letter}-{seq}` | `NST-BANK-{letter}` (nostro accounts) |
| Account purpose | Customer accounts | Inter-bank settlement accounts |
| BATCH-INPUT.DAT | Customer transactions | Settlement entries (may not exist yet) |
| Transaction types | DEPOSIT, WITHDRAW, TRANSFER | DEPOSIT, WITHDRAW only (settlement legs) |

**CLEARING may need special handling in cobol-test.sh.** If the test assumes customer-style account IDs (`ACT-A-001`) and CLEARING has nostro-style IDs (`NST-BANK-A`), the test will fail. This is NOT a COBOL bug — it's a test script assumption. Fix the test, not the COBOL.

**Acceptable test modification for CLEARING:**

```bash
# In cobol-test.sh, when NODE=CLEARING:
# - FIRST_ACCT should be extracted from actual LIST output (already dynamic)
# - BATCH test may skip if no BATCH-INPUT.DAT exists
# - VALIDATE test should use a real CLEARING account ID
```

The existing `cobol-test.sh` already extracts `FIRST_ACCT` dynamically from LIST output, so it *should* work. But verify.

---

## 4. WHAT TO DO IF A NODE FAILS

### Symptom: "ACCOUNTS.DAT not found"
**Fix:** Run `./scripts/seed.sh`. If seed.sh only creates BANK_A, that's the bug — it needs to create all 6 nodes.

### Symptom: ACCOUNTS LIST returns wrong number of accounts
**Check:** Is the .DAT file correct? Each node should have a defined number of accounts per the seed data spec. Verify with:
```bash
wc -c < banks/BANK_B/ACCOUNTS.DAT
# Compare byte count to BANK_A — if record length is N bytes, file should be N * num_accounts
```

### Symptom: TRANSACT DEPOSIT fails
**Check:** Is the account ID format correct for this node? BANK_B accounts should be `ACT-B-001`, not `ACT-A-001`. The test extracts the ID from LIST output, so this should be automatic.

### Symptom: BATCH fails with "no BATCH-INPUT.DAT"
**Check:** This is a seed data gap, not a COBOL bug. Either create BATCH-INPUT.DAT for this node (following the same format as BANK_A's) or accept the skip.

### Symptom: VALIDATE fails on CLEARING node
**Check:** CLEARING nostro accounts may have different validation rules. If VALIDATE.cob hardcodes assumptions about account ID formats, fix the COBOL to handle both `ACT-` and `NST-` prefixes.

---

## 5. DOCUMENTING RESULTS

After the gate run, paste the COMPLETE output into DEV_LOG.md under:

```markdown
## Six-Node Verification Gate — Results

**Date:** [date]
**Nodes tested:** BANK_A, BANK_B, BANK_C, BANK_D, BANK_E, CLEARING

### Per-node results:
[paste full output]

### Issues found and fixed:
- [list any bugs fixed, with what changed]

### Gate status: PASSED / FAILED
```

---

## 6. GATE CRITERIA

**PASS:** All 6 nodes complete cobol-test.sh with zero failures. The output for each node shows:
```
  ★ COBOL SYSTEM WORKS STANDALONE ★
```

**CONDITIONAL PASS:** 5 bank nodes pass. CLEARING has documented differences (e.g., no BATCH-INPUT.DAT, different account format) that are understood and noted. The CLEARING node's core operations (LIST, DEPOSIT, WITHDRAW) still work.

**FAIL:** Any bank node (A-E) fails, or CLEARING can't perform basic LIST/DEPOSIT operations.

**On PASS or CONDITIONAL PASS:** Proceed to HANDOFF_B (Settlement Coordinator).  
**On FAIL:** Fix the failures. Do not proceed until the gate clears.

---

## 7. WHAT THIS PROVES

When this gate passes, we have confirmed:

- ✅ 42 customer accounts across 5 banks are readable and operable
- ✅ 5 nostro accounts in CLEARING are readable and operable
- ✅ Single-node deposits, withdrawals work on every node
- ✅ Batch processing works on every node that has batch data
- ✅ Validation works on every node
- ✅ Reporting works on every node
- ✅ Data integrity survives the full round-trip on every node

**What this does NOT prove (and why we need HANDOFF_B):**
- ❌ Inter-bank transfers work
- ❌ CLEARING settlement logic exists
- ❌ Cross-node chain verification works
- ❌ The "5 banks, 1 clearing house" demo is possible

Those are HANDOFF_B and HANDOFF_C. This document is only about confirming the foundation is solid.
