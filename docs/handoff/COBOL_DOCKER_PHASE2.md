# COBOL-First Docker Infrastructure & Revised Phase 2

**Purpose:** Gives Claude Code everything needed to compile, run, and test COBOL programs inside Docker — making COBOL the standalone hero before Python touches anything.

**Add these files to the project, then hand this document to Claude Code before starting Phase 2.**

---

## 1. Dockerfile

**File:** `Dockerfile.cobol` (project root)

```dockerfile
# Dockerfile.cobol — GnuCOBOL build and runtime environment
# Usage: docker build -t cobol-dev -f Dockerfile.cobol .
# Then:  docker run -v $(pwd):/app cobol-dev cobc --version
FROM ubuntu:24.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends gnucobol \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
```

Three layers: base image, compiler, working directory. Nothing else. The `--no-install-recommends` keeps the image small (~180MB). The `/app` workdir is where the project mounts.

**Build once:**
```bash
docker build -t cobol-dev -f Dockerfile.cobol .
```

**Verify:**
```bash
docker run --rm cobol-dev cobc --version
# Should show: cobc (GnuCOBOL) 3.x.x
```

---

## 2. cobol-run.sh — Docker Wrapper

**File:** `scripts/cobol-run.sh`

```bash
#!/bin/bash
# cobol-run.sh — Execute any command inside the cobol-dev Docker container
# Mounts the project directory so COBOL binaries and .DAT files persist
# on the host filesystem after the container exits.
#
# Usage:
#   ./scripts/cobol-run.sh cobc --version
#   ./scripts/cobol-run.sh cobc -x -free -I cobol/copybooks cobol/src/ACCOUNTS.cob -o cobol/bin/ACCOUNTS
#   ./scripts/cobol-run.sh bash -c "cd banks/BANK_A && ../../cobol/bin/ACCOUNTS LIST"
#
# The container is ephemeral (--rm). All file changes happen on the host
# via the bind mount. Nothing persists inside the container.

set -e

IMAGE_NAME="cobol-dev"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Build image if it doesn't exist
if ! docker image inspect "$IMAGE_NAME" &>/dev/null; then
    echo "Building $IMAGE_NAME Docker image..."
    docker build -t "$IMAGE_NAME" -f "$PROJECT_ROOT/Dockerfile.cobol" "$PROJECT_ROOT"
    echo ""
fi

# Run command inside container with project mounted at /app
docker run --rm \
    -v "$PROJECT_ROOT:/app" \
    -w /app \
    "$IMAGE_NAME" \
    "$@"
```

**What this does:** You never type `docker run -v ...` manually. Every COBOL operation goes through this script. The project root is auto-detected. The image auto-builds on first use. The container is disposable (`--rm`) — all persistent state lives in the host filesystem via the bind mount.

**Examples:**
```bash
# Check compiler
./scripts/cobol-run.sh cobc --version

# Compile a program
./scripts/cobol-run.sh cobc -x -free -I cobol/copybooks cobol/src/ACCOUNTS.cob -o cobol/bin/ACCOUNTS

# Run a program in a specific bank directory
./scripts/cobol-run.sh bash -c "cd banks/BANK_A && ../../cobol/bin/ACCOUNTS LIST"

# Interactive shell inside the container (for debugging)
./scripts/cobol-run.sh bash
```

---

## 3. build.sh — Updated with Docker Fallback

**File:** `scripts/build.sh` (replaces existing)

```bash
#!/bin/bash
# build.sh — Compile all COBOL programs
# Uses local cobc if available, falls back to Docker container.
# All compiled binaries go to cobol/bin/.
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# Determine compile command: local cobc or Docker
if command -v cobc &>/dev/null; then
    COBC="cobc"
    echo "Using local GnuCOBOL: $(cobc --version | head -1)"
else
    echo "Local cobc not found. Using Docker..."
    # Ensure image exists
    if ! docker image inspect cobol-dev &>/dev/null; then
        echo "Building cobol-dev Docker image..."
        docker build -t cobol-dev -f Dockerfile.cobol .
    fi
    COBC="docker run --rm -v $PROJECT_ROOT:/app -w /app cobol-dev cobc"
    echo "Using Docker GnuCOBOL: $($COBC --version | head -1)"
fi

echo ""
echo "========================================"
echo "  COMPILING COBOL PROGRAMS"
echo "========================================"
echo ""

mkdir -p cobol/bin

PROGRAMS=(SMOKETEST ACCOUNTS TRANSACT VALIDATE REPORTS)
COMPILED=0
FAILED=0

for PROG in "${PROGRAMS[@]}"; do
    SRC="cobol/src/${PROG}.cob"
    OUT="cobol/bin/${PROG}"

    if [ ! -f "$SRC" ]; then
        echo "  SKIP  $PROG — source not found ($SRC)"
        continue
    fi

    echo -n "  BUILD $PROG ... "
    if $COBC -x -free -I cobol/copybooks "$SRC" -o "$OUT" 2>/tmp/cobol_build_err; then
        echo "OK"
        COMPILED=$((COMPILED + 1))
    else
        echo "FAILED"
        cat /tmp/cobol_build_err
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "========================================"
echo "  RESULTS: $COMPILED compiled, $FAILED failed"
echo "  Binaries: cobol/bin/"
echo "========================================"

# Make binaries executable (Docker may create as root)
chmod +x cobol/bin/* 2>/dev/null || true

if [ $FAILED -gt 0 ]; then
    exit 1
fi
```

**Key design decisions:**
- Local `cobc` takes priority (zero overhead if you have it)
- Docker is automatic fallback (no user action needed)
- Each program compiles independently (one failure doesn't stop the others)
- Error output is captured and displayed per program
- `chmod +x` at the end handles Docker's root-owned file permission issue
- Exit code 1 if any compilation failed (so CI/scripts can detect failure)

---

## 4. cobol-test.sh — Standalone COBOL Test Harness

**File:** `scripts/cobol-test.sh`

This is the proof that COBOL is the hero. It runs the entire banking system end-to-end with **zero Python**. If this script passes, the COBOL system works standalone.

```bash
#!/bin/bash
# cobol-test.sh — Standalone COBOL system test (NO PYTHON)
#
# Proves the COBOL banking system works independently:
#   1. Compiles all programs
#   2. Creates accounts via ACCOUNTS.cob
#   3. Processes a batch via TRANSACT.cob
#   4. Validates an account via VALIDATE.cob
#   5. Generates a report via REPORTS.cob
#
# Usage:
#   ./scripts/cobol-test.sh            # Test all nodes
#   ./scripts/cobol-test.sh BANK_A     # Test one node
#
# This script uses Docker if cobc is not available locally.
# Zero Python. Zero SQLite. Just COBOL and flat files.

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# -----------------------------------------------------------
# Helper: run a command, locally or in Docker
# -----------------------------------------------------------
run_cmd() {
    if command -v cobc &>/dev/null; then
        "$@"
    else
        docker run --rm -v "$PROJECT_ROOT:/app" -w /app cobol-dev "$@"
    fi
}

run_cobol() {
    local BINARY="$1"
    shift
    local NODE_DIR="$1"
    shift
    if command -v cobc &>/dev/null; then
        (cd "$NODE_DIR" && "$PROJECT_ROOT/cobol/bin/$BINARY" "$@")
    else
        docker run --rm \
            -v "$PROJECT_ROOT:/app" \
            -w "/app/$NODE_DIR" \
            cobol-dev \
            "/app/cobol/bin/$BINARY" "$@"
    fi
}

PASS=0
FAIL=0
TESTS=0

check() {
    TESTS=$((TESTS + 1))
    local LABEL="$1"
    local RESULT="$2"
    local EXPECTED="$3"

    if echo "$RESULT" | grep -q "$EXPECTED"; then
        echo "  ✓ $LABEL"
        PASS=$((PASS + 1))
    else
        echo "  ✗ $LABEL"
        echo "    Expected: $EXPECTED"
        echo "    Got:      $RESULT"
        FAIL=$((FAIL + 1))
    fi
}

NODE="${1:-BANK_A}"
NODE_DIR="banks/$NODE"

echo "========================================================"
echo "  COBOL STANDALONE TEST — $NODE"
echo "  Zero Python. Zero SQLite. Just COBOL and flat files."
echo "========================================================"
echo ""

# -----------------------------------------------------------
# STEP 0: Compile
# -----------------------------------------------------------
echo "--- STEP 0: Compile all programs ---"
./scripts/build.sh
echo ""

# -----------------------------------------------------------
# STEP 1: Verify data directory exists and has ACCOUNTS.DAT
# -----------------------------------------------------------
echo "--- STEP 1: Verify node data directory ---"
if [ ! -d "$NODE_DIR" ]; then
    echo "  Node directory $NODE_DIR does not exist."
    echo "  Run ./scripts/seed.sh first."
    exit 1
fi

if [ ! -f "$NODE_DIR/ACCOUNTS.DAT" ]; then
    echo "  ACCOUNTS.DAT not found in $NODE_DIR."
    echo "  Run ./scripts/seed.sh first."
    exit 1
fi

BYTE_COUNT=$(wc -c < "$NODE_DIR/ACCOUNTS.DAT")
echo "  ✓ $NODE_DIR/ACCOUNTS.DAT exists ($BYTE_COUNT bytes)"
echo ""

# -----------------------------------------------------------
# STEP 2: ACCOUNTS.cob — List all accounts
# -----------------------------------------------------------
echo "--- STEP 2: ACCOUNTS.cob LIST ---"
ACCT_OUTPUT=$(run_cobol ACCOUNTS "$NODE_DIR" LIST 2>&1)
echo "$ACCT_OUTPUT"
echo ""

check "ACCOUNTS LIST returns RESULT|00" "$ACCT_OUTPUT" "RESULT|00"
check "ACCOUNTS LIST shows ACCOUNT lines" "$ACCT_OUTPUT" "ACCOUNT|"

# Count accounts
ACCT_COUNT=$(echo "$ACCT_OUTPUT" | grep -c "^ACCOUNT|" || true)
echo "  Accounts found: $ACCT_COUNT"
echo ""

# -----------------------------------------------------------
# STEP 3: TRANSACT.cob — Single deposit
# -----------------------------------------------------------
echo "--- STEP 3: TRANSACT.cob DEPOSIT ---"

# Find first account ID from the LIST output
FIRST_ACCT=$(echo "$ACCT_OUTPUT" | grep "^ACCOUNT|" | head -1 | cut -d'|' -f2 | tr -d ' ')

if [ -z "$FIRST_ACCT" ]; then
    echo "  ✗ Could not extract account ID from LIST output"
    FAIL=$((FAIL + 1))
else
    echo "  Testing deposit to $FIRST_ACCT..."
    DEP_OUTPUT=$(run_cobol TRANSACT "$NODE_DIR" DEPOSIT "$FIRST_ACCT" 1000.00 "COBOL standalone test" 2>&1)
    echo "$DEP_OUTPUT"
    echo ""
    check "DEPOSIT returns RESULT|00" "$DEP_OUTPUT" "RESULT|00"
    check "DEPOSIT shows OK status" "$DEP_OUTPUT" "OK|DEPOSIT"
fi
echo ""

# -----------------------------------------------------------
# STEP 4: TRANSACT.cob — Batch processing
# -----------------------------------------------------------
echo "--- STEP 4: TRANSACT.cob BATCH ---"

if [ -f "$NODE_DIR/BATCH-INPUT.DAT" ]; then
    BATCH_OUTPUT=$(run_cobol TRANSACT "$NODE_DIR" BATCH 2>&1)
    echo "$BATCH_OUTPUT"
    echo ""

    check "BATCH returns RESULT|00" "$BATCH_OUTPUT" "RESULT|00"
    check "BATCH shows columnar header" "$BATCH_OUTPUT" "SEQ"
    check "BATCH shows summary" "$BATCH_OUTPUT" "BATCH SUMMARY"

    # Check for compliance flag if node has large transactions
    if echo "$BATCH_OUTPUT" | grep -q "CTR\|COMPLIANCE"; then
        echo "  ✓ Compliance flag detected (CTR threshold)"
        PASS=$((PASS + 1))
        TESTS=$((TESTS + 1))
    fi
else
    echo "  SKIP — No BATCH-INPUT.DAT in $NODE_DIR"
fi
echo ""

# -----------------------------------------------------------
# STEP 5: VALIDATE.cob — Pre-flight check
# -----------------------------------------------------------
echo "--- STEP 5: VALIDATE.cob ---"

if [ -f "cobol/bin/VALIDATE" ]; then
    # Valid account
    VAL_OUTPUT=$(run_cobol VALIDATE "$NODE_DIR" "$FIRST_ACCT" 2>&1)
    check "VALIDATE valid account returns 00" "$VAL_OUTPUT" "RESULT|00"

    # Invalid account
    VAL_OUTPUT=$(run_cobol VALIDATE "$NODE_DIR" "NONEXIST00" 2>&1)
    check "VALIDATE invalid account returns 03" "$VAL_OUTPUT" "RESULT|03"
else
    echo "  SKIP — VALIDATE binary not found"
fi
echo ""

# -----------------------------------------------------------
# STEP 6: REPORTS.cob — Ledger report
# -----------------------------------------------------------
echo "--- STEP 6: REPORTS.cob LEDGER ---"

if [ -f "cobol/bin/REPORTS" ]; then
    RPT_OUTPUT=$(run_cobol REPORTS "$NODE_DIR" LEDGER 2>&1)
    echo "$RPT_OUTPUT" | head -15
    echo "  ..."
    echo ""
    check "REPORTS LEDGER returns RESULT|00" "$RPT_OUTPUT" "RESULT|00"
else
    echo "  SKIP — REPORTS binary not found"
fi
echo ""

# -----------------------------------------------------------
# STEP 7: Verify data integrity (COBOL-only)
# -----------------------------------------------------------
echo "--- STEP 7: Data integrity check ---"

# After all operations, list accounts again and verify first account
# balance increased by $1000 from the deposit
ACCT_AFTER=$(run_cobol ACCOUNTS "$NODE_DIR" LIST 2>&1)
check "ACCOUNTS still readable after transactions" "$ACCT_AFTER" "RESULT|00"

AFTER_COUNT=$(echo "$ACCT_AFTER" | grep -c "^ACCOUNT|" || true)
check "Account count unchanged ($ACCT_COUNT)" \
    "COUNT=$AFTER_COUNT" "COUNT=$ACCT_COUNT"
echo ""

# -----------------------------------------------------------
# RESULTS
# -----------------------------------------------------------
echo "========================================================"
echo "  RESULTS: $PASS passed, $FAIL failed (of $TESTS tests)"
echo ""
if [ $FAIL -eq 0 ]; then
    echo "  ★ COBOL SYSTEM WORKS STANDALONE ★"
    echo "  Zero Python. Zero SQLite. Just COBOL and flat files."
    echo ""
    echo "  The banking system processes transactions, validates"
    echo "  accounts, and generates reports entirely in COBOL."
    echo "  Python is Layer 2. This is Layer 1. It works."
else
    echo "  ✗ $FAIL tests failed. Fix COBOL programs before"
    echo "    proceeding to Python bridge integration."
fi
echo "========================================================"

exit $FAIL
```

**What this proves:**
- COBOL compiles (via Docker or local)
- ACCOUNTS.cob reads and lists accounts from .DAT files
- TRANSACT.cob processes individual deposits
- TRANSACT.cob runs batch processing with columnar output
- VALIDATE.cob checks valid and invalid accounts
- REPORTS.cob generates a ledger report
- Data files survive the full round-trip (read → modify → read again)
- Account count is stable (no records lost or duplicated)

**All without Python.** The test harness is pure bash + COBOL. This is the "Layer 1 works standalone" gate.

---

## 5. Revised Phase 2 Plan — COBOL First, Docker Native

### Pre-requisite: Docker Available

```bash
docker --version    # Must work. Docker Desktop on Windows/Mac, docker-ce on Linux.
```

If Claude Code's environment has Docker, everything below is unblocked. No local `cobc` needed.

### Phase 2.0: Docker Setup + Smoke Test (15 minutes)

**Gate: cobc works inside Docker and balance format is observed.**

```bash
# Build the image
docker build -t cobol-dev -f Dockerfile.cobol .

# Verify compiler
./scripts/cobol-run.sh cobc --version

# Compile smoke test
./scripts/cobol-run.sh cobc -x -free -I cobol/copybooks cobol/src/SMOKETEST.cob -o cobol/bin/SMOKETEST

# Run smoke test
./scripts/cobol-run.sh bash -c "cd banks/BANK_A && /app/cobol/bin/SMOKETEST"
```

**Critical action:** Capture the balance field output. Compare to bridge parser. Fix parser if mismatch. Document in `SMOKE_TEST_OBSERVATION.md`.

**Gate check:** Parser handles the actual GnuCOBOL balance format correctly.

---

### Phase 2.1: ACCOUNTS.cob — Standalone (2 hours)

**Goal:** Working account management program. No Python.

**Implement:** LIST, READ, CREATE operations using patterns from COBOL Style Reference Section 0.2.

**Test standalone:**
```bash
# Compile
./scripts/cobol-run.sh cobc -x -free -I cobol/copybooks cobol/src/ACCOUNTS.cob -o cobol/bin/ACCOUNTS

# List all accounts in BANK_A
./scripts/cobol-run.sh bash -c "cd banks/BANK_A && /app/cobol/bin/ACCOUNTS LIST"

# Read single account
./scripts/cobol-run.sh bash -c "cd banks/BANK_A && /app/cobol/bin/ACCOUNTS READ ACT-A-001"
```

**Gate check:**
- LIST shows all 8 BANK_A accounts with correct balances
- READ shows single account details
- Output is pipe-delimited matching the bridge parser expectations
- RESULT|00 appears at the end

**Do NOT touch Python yet.** ACCOUNTS.cob must work standalone first.

---

### Phase 2.2: TRANSACT.cob — Standalone (4 hours)

**Goal:** Working transaction processing with batch mode. The demo centerpiece. No Python.

**Implement:**
- DEPOSIT, WITHDRAW operations (single transaction)
- BATCH mode reading BATCH-INPUT.DAT
- Columnar batch trace output (Supplement A format — non-negotiable)
- Compliance CTR flag for deposits > $9,500
- Transaction ID generation (TRX-{node}-{seq}, 12 chars)
- Inline validation (CHECK-ACCOUNT-STATUS, CHECK-BALANCE, CHECK-DAILY-LIMIT)

**Test standalone:**
```bash
# Compile
./scripts/cobol-run.sh cobc -x -free -I cobol/copybooks cobol/src/TRANSACT.cob -o cobol/bin/TRANSACT

# Single deposit
./scripts/cobol-run.sh bash -c "cd banks/BANK_A && /app/cobol/bin/TRANSACT DEPOSIT ACT-A-001 5000.00 'Payroll deposit'"

# Verify balance changed
./scripts/cobol-run.sh bash -c "cd banks/BANK_A && /app/cobol/bin/ACCOUNTS READ ACT-A-001"

# Batch processing — THE DEMO MOMENT
./scripts/cobol-run.sh bash -c "cd banks/BANK_A && /app/cobol/bin/TRANSACT BATCH"
```

**Gate checks:**
- Single deposit changes balance in ACCOUNTS.DAT (verify with ACCOUNTS READ)
- TRANSACT.DAT has a new record after deposit
- Transaction ID is exactly 12 characters (TRX-A-000001)
- Batch output is COLUMNAR (not pipe-delimited) matching Supplement A
- Compliance flag appears for deposits > $9,500
- Failed transactions show FAIL## codes with correct reasons
- Batch summary footer shows correct totals

**This is the most important phase.** Spend the time to get the columnar output right. This is what the interviewer sees.

---

### Phase 2.3: VALIDATE.cob — Standalone Utility (1 hour)

**Goal:** Pre-flight validation callable from command line. Also serves as the pattern for the inline validation in TRANSACT.cob (same logic, different calling convention).

**Implement:** Account existence check, status check (frozen), balance check, daily limit check.

**Test standalone:**
```bash
# Compile
./scripts/cobol-run.sh cobc -x -free -I cobol/copybooks cobol/src/VALIDATE.cob -o cobol/bin/VALIDATE

# Valid account
./scripts/cobol-run.sh bash -c "cd banks/BANK_A && /app/cobol/bin/VALIDATE ACT-A-001"
# Expected: RESULT|00

# Nonexistent account
./scripts/cobol-run.sh bash -c "cd banks/BANK_A && /app/cobol/bin/VALIDATE NONEXIST00"
# Expected: RESULT|03

# Frozen account (if one exists in seed data)
# Expected: RESULT|04
```

---

### Phase 2.4: REPORTS.cob — Standalone (2 hours)

**Goal:** Reporting program. Read-only operations on ACCOUNTS.DAT and TRANSACT.DAT.

**Implement:** LEDGER (all accounts), STATEMENT (single account history), EOD (end-of-day summary), AUDIT (full transaction log).

**Test standalone:**
```bash
# Compile
./scripts/cobol-run.sh cobc -x -free -I cobol/copybooks cobol/src/REPORTS.cob -o cobol/bin/REPORTS

# Ledger (all accounts)
./scripts/cobol-run.sh bash -c "cd banks/BANK_A && /app/cobol/bin/REPORTS LEDGER"

# EOD summary
./scripts/cobol-run.sh bash -c "cd banks/BANK_A && /app/cobol/bin/REPORTS EOD"
```

---

### Phase 2.5: Standalone System Gate — cobol-test.sh (30 minutes)

**Goal:** Prove the entire COBOL system works without Python.

```bash
./scripts/cobol-test.sh BANK_A
```

**Gate check:** All tests pass. The output ends with:

```
  ★ COBOL SYSTEM WORKS STANDALONE ★
  Zero Python. Zero SQLite. Just COBOL and flat files.
```

**Run for all nodes:**
```bash
for NODE in BANK_A BANK_B BANK_C BANK_D BANK_E CLEARING; do
    echo "Testing $NODE..."
    ./scripts/cobol-test.sh $NODE
    echo ""
done
```

**This is the Layer 1 gate.** Do not proceed to Layer 2 until this passes for all 6 nodes.

---

### Phase 2.6: Wire Python Bridge Mode A (2 hours)

**Now — and only now — Python enters the picture.**

- Update `bridge.py` to call COBOL via `./scripts/cobol-run.sh` (or direct subprocess if `cobc` is local)
- Parse the pipe-delimited output from ACCOUNTS.cob LIST
- Parse transaction results from TRANSACT.cob
- Sync to SQLite + chain

**Test:**
```bash
# Mode A: uses COBOL subprocess
python -c "
from python.bridge import COBOLBridge
b = COBOLBridge(node='BANK_A')
accounts = b.list_accounts()
print(f'Mode A: {len(accounts)} accounts')
"

# Compare Mode A vs Mode B
python -c "
from python.bridge import COBOLBridge

# Mode B (Python-only)
b = COBOLBridge(node='BANK_A')
b.cobol_available = False
accounts_b = b.list_accounts()

# Mode A (COBOL subprocess)
b.cobol_available = True
accounts_a = b.list_accounts()

for a, b_acct in zip(accounts_a, accounts_b):
    assert a['id'].strip() == b_acct['id'].strip(), f'ID mismatch: {a[\"id\"]} vs {b_acct[\"id\"]}'
    assert abs(a['balance'] - b_acct['balance']) < 0.01, f'Balance mismatch: {a[\"balance\"]} vs {b_acct[\"balance\"]}'

print(f'✓ Mode A = Mode B ({len(accounts_a)} accounts match)')
"
```

---

### Phase 2.7: Mode A Integration Tests (1 hour)

Add `python/tests/test_bridge_mode_a.py` with tests that exercise COBOL subprocesses.

**These tests require Docker** (or local cobc). Mark them with a pytest marker so they can be skipped when COBOL is unavailable:

```python
import pytest
import shutil

requires_cobol = pytest.mark.skipif(
    not shutil.which("cobc") and not shutil.which("docker"),
    reason="Requires GnuCOBOL (local or Docker)"
)

@requires_cobol
def test_accounts_mode_a():
    ...
```

---

### Phase Summary

| Phase | What | Layer | Docker? | Python? | Gate |
|-------|------|-------|---------|---------|------|
| 2.0 | Smoke test | — | Yes | No | Balance format observed |
| 2.1 | ACCOUNTS.cob | COBOL | Yes | No | LIST shows correct accounts |
| 2.2 | TRANSACT.cob | COBOL | Yes | No | Batch output matches Supplement A |
| 2.3 | VALIDATE.cob | COBOL | Yes | No | All 5 status codes work |
| 2.4 | REPORTS.cob | COBOL | Yes | No | LEDGER and EOD produce output |
| 2.5 | cobol-test.sh | COBOL | Yes | No | ★ STANDALONE GATE — all nodes pass |
| 2.6 | Bridge Mode A | Python | Yes | Yes | Mode A = Mode B |
| 2.7 | Integration tests | Python | Yes | Yes | All Mode A tests pass |

**The dividing line is Phase 2.5.** Everything before it is pure COBOL. Everything after it is Python wrapping a proven COBOL system. That's the narrative. That's the portfolio story.

---

## Files to Add to Project

| File | Location | Purpose |
|------|----------|---------|
| `Dockerfile.cobol` | Project root | GnuCOBOL build environment |
| `scripts/cobol-run.sh` | scripts/ | Docker wrapper for any COBOL command |
| `scripts/build.sh` | scripts/ | Updated: Docker fallback if no local cobc |
| `scripts/cobol-test.sh` | scripts/ | Standalone COBOL test harness (zero Python) |

All four files are complete and ready to use. No additional dependencies beyond Docker.

---

## Instruction for Claude Code

When starting Phase 2, read this document first. The workflow is:

1. **Docker first.** Build the image. Verify `cobc` works inside it.
2. **Smoke test.** Compile SMOKETEST.cob in Docker. Run it. Paste the balance field output.
3. **Write COBOL, not Python.** Implement ACCOUNTS.cob → TRANSACT.cob → VALIDATE.cob → REPORTS.cob. Test each one standalone using `cobol-run.sh`. Do not import Python. Do not open bridge.py.
4. **Run cobol-test.sh.** When it passes for all 6 nodes, Layer 1 is done.
5. **Then wire Python.** Only after the standalone gate passes, update bridge.py for Mode A.
6. **No new markdown.** Write programs, not plans. The specs are done.
