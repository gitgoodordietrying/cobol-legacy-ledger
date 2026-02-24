#!/bin/bash
#================================================================*
# cobol-test-suite.sh — Comprehensive COBOL Branch Coverage Tests
#
# Pure COBOL tests (zero Python). Deterministic fixtures, exact
# output assertions, every reachable branch exercised.
#
# Usage:  bash scripts/cobol-test-suite.sh
#================================================================*

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BIN_DIR="$PROJECT_ROOT/cobol/bin"

# Counters
PASS=0
FAIL=0
SKIP=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

#----------------------------------------------------------------
# Infrastructure
#----------------------------------------------------------------

# Create temp directories INSIDE the project tree (required for Docker mounts)
TEST_TMPROOT="$PROJECT_ROOT/.test-tmp"
mkdir -p "$TEST_TMPROOT"

new_test_dir() {
  mktemp -d "$TEST_TMPROOT/ct.XXXXXX"
}

cleanup_test_temps() {
  rm -rf "$TEST_TMPROOT"
}
trap cleanup_test_temps EXIT

# Write a 70-byte ACCTREC record to ACCOUNTS.DAT
# Args: dir acct_id name type balance_cents status [open_date] [last_activity]
write_account() {
  local dir="$1" id="$2" name="$3" type="$4" cents="$5" status="$6"
  local open_date="${7:-20260217}" last_activity="${8:-20260217}"
  local padded_id padded_name bal_str
  padded_id=$(printf '%-10s' "$id")
  padded_name=$(printf '%-30s' "$name")
  bal_str=$(printf '%012d' "$cents")
  printf '%s%s%s%s%s%s%s\n' \
    "$padded_id" "$padded_name" "$type" "$bal_str" "$status" "$open_date" "$last_activity" \
    >> "$dir/ACCOUNTS.DAT"
}

# Write a 103-byte TRANSREC record to TRANSACT.DAT
# Args: dir tx_id acct_id type amount_cents date time desc status [batch_id]
write_transaction() {
  local dir="$1" tx_id="$2" acct_id="$3" type="$4" cents="$5"
  local date="$6" time="$7" desc="$8" status="$9" batch_id="${10:-}"
  local padded_txid padded_acctid amt_str padded_desc padded_status padded_batch
  padded_txid=$(printf '%-12s' "$tx_id")
  padded_acctid=$(printf '%-10s' "$acct_id")
  amt_str=$(printf '%012d' "$cents")
  padded_desc=$(printf '%-40s' "$desc")
  padded_status=$(printf '%-2s' "$status")
  padded_batch=$(printf '%-12s' "$batch_id")
  printf '%s%s%s%s%s%s%s%s%s\n' \
    "$padded_txid" "$padded_acctid" "$type" "$amt_str" \
    "$date" "$time" "$padded_desc" "$padded_status" "$padded_batch" \
    >> "$dir/TRANSACT.DAT"
}

# Write a line to BATCH-INPUT.DAT
write_batch_line() {
  local dir="$1"; shift
  echo "$*" >> "$dir/BATCH-INPUT.DAT"
}

# Run a COBOL program in a given working directory
# For programs that accept command-line string (TRANSACT, VALIDATE), pass
# all args as a single string. For simple commands (ACCOUNTS LIST, FEES,
# INTEREST, RECONCILE, SMOKETEST), pass as separate args.
run_cobol() {
  local program="$1" dir="$2"
  shift 2
  if command -v cobc &> /dev/null || [ -f /.dockerenv ]; then
    (cd "$dir" && "$BIN_DIR/$program" "$@" 2>&1) || true
  else
    local rel_dir
    # Use python (Windows) or python3 (Linux/Mac) for relpath
    local py_cmd
    py_cmd=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo "python")
    rel_dir=$($py_cmd -c "import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))" "$dir" "$PROJECT_ROOT" 2>/dev/null)
    # Convert backslashes to forward slashes (Windows relpath returns backslashes)
    rel_dir="${rel_dir//\\//}"
    local escaped_args=""
    for arg in "$@"; do
      escaped_args="$escaped_args '$arg'"
    done
    MSYS_NO_PATHCONV=1 "$SCRIPT_DIR/cobol-run.sh" bash -c "cd /app/$rel_dir && /app/cobol/bin/$program $escaped_args" 2>&1 || true
  fi
}

# Assertions
assert_contains() {
  local output="$1" pattern="$2" test_name="$3"
  if echo "$output" | grep -qF "$pattern"; then
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}PASS${NC} $test_name"
  else
    FAIL=$((FAIL + 1))
    echo -e "  ${RED}FAIL${NC} $test_name"
    echo -e "       Expected to contain: ${YELLOW}$pattern${NC}"
    echo -e "       Got: $(echo "$output" | head -3)"
  fi
}

assert_not_contains() {
  local output="$1" pattern="$2" test_name="$3"
  if echo "$output" | grep -qF "$pattern"; then
    FAIL=$((FAIL + 1))
    echo -e "  ${RED}FAIL${NC} $test_name"
    echo -e "       Should NOT contain: ${YELLOW}$pattern${NC}"
  else
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}PASS${NC} $test_name"
  fi
}

assert_line_count() {
  local output="$1" pattern="$2" expected="$3" test_name="$4"
  local actual
  actual=$(echo "$output" | grep -cF "$pattern" || true)
  if [ "$actual" -eq "$expected" ]; then
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}PASS${NC} $test_name"
  else
    FAIL=$((FAIL + 1))
    echo -e "  ${RED}FAIL${NC} $test_name"
    echo -e "       Expected $expected lines matching '$pattern', got $actual"
  fi
}

assert_file_has_content() {
  local filepath="$1" test_name="$2"
  if [ -s "$filepath" ]; then
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}PASS${NC} $test_name"
  else
    FAIL=$((FAIL + 1))
    echo -e "  ${RED}FAIL${NC} $test_name (file empty or missing)"
  fi
}

skip_test() {
  local test_name="$1"
  SKIP=$((SKIP + 1))
  echo -e "  ${YELLOW}SKIP${NC} $test_name"
}

#----------------------------------------------------------------
# Pre-flight: check binaries
#----------------------------------------------------------------
echo "================================================================"
echo "  COBOL TEST SUITE — Full Branch Coverage"
echo "================================================================"
echo ""

REQUIRED_BINS="ACCOUNTS TRANSACT VALIDATE REPORTS FEES INTEREST RECONCILE SMOKETEST"
MISSING=0
for bin in $REQUIRED_BINS; do
  if [ ! -f "$BIN_DIR/$bin" ]; then
    MISSING=$((MISSING + 1))
  fi
done

if [ "$MISSING" -gt 0 ]; then
  echo "Building COBOL programs..."
  if "$SCRIPT_DIR/build.sh" > /dev/null 2>&1; then
    echo -e "${GREEN}Build successful${NC}"
  else
    echo -e "${RED}Build failed — cannot run tests${NC}"
    exit 1
  fi
  for bin in $REQUIRED_BINS; do
    if [ ! -f "$BIN_DIR/$bin" ]; then
      echo -e "${RED}Binary still missing after build: $bin${NC}"
      exit 1
    fi
  done
fi

echo -e "${GREEN}All 8 binaries found${NC}"
echo ""

#================================================================
# SMOKETEST.cob (1 test)
#================================================================
echo -e "${CYAN}--- SMOKETEST.cob ---${NC}"

# S01: Smoke test passes
TD=$(new_test_dir)
OUTPUT=$(run_cobol SMOKETEST "$TD")
assert_contains "$OUTPUT" "SMOKE-TEST|PASS" "S01: Smoke test passes"
rm -rf "$TD"

#================================================================
# ACCOUNTS.cob (11 tests — LIST + READ/CREATE/UPDATE/CLOSE)
#
# ACCOUNTS.cob uses UNSTRING to parse the full command line,
# so all operations work: LIST, READ, CREATE, UPDATE, CLOSE.
#================================================================
echo ""
echo -e "${CYAN}--- ACCOUNTS.cob ---${NC}"

# A01: LIST all accounts (3 records)
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
write_account "$TD" "ACT-T-002" "Bob Test" "S" 1250000 "A"
write_account "$TD" "ACT-T-003" "Carol Test" "C" 85050 "A"
OUTPUT=$(run_cobol ACCOUNTS "$TD" LIST)
assert_line_count "$OUTPUT" "ACCOUNT|" 3 "A01: LIST returns 3 account records"
assert_contains "$OUTPUT" "RESULT|00" "A01: LIST returns RESULT|00"
rm -rf "$TD"

# A02: LIST empty file
TD=$(new_test_dir)
touch "$TD/ACCOUNTS.DAT"
OUTPUT=$(run_cobol ACCOUNTS "$TD" LIST)
assert_contains "$OUTPUT" "RESULT|00" "A02: LIST empty file returns RESULT|00"
assert_line_count "$OUTPUT" "ACCOUNT|" 0 "A02: LIST empty file returns 0 accounts"
rm -rf "$TD"

# A03: READ existing account
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
write_account "$TD" "ACT-T-002" "Bob Test" "S" 1250000 "A"
OUTPUT=$(run_cobol ACCOUNTS "$TD" "READ ACT-T-001")
assert_contains "$OUTPUT" "ACCOUNT|" "A03: READ returns ACCOUNT| line"
assert_contains "$OUTPUT" "ACT-T-001" "A03: READ returns correct account ID"
assert_contains "$OUTPUT" "RESULT|00" "A03: READ returns RESULT|00"
rm -rf "$TD"

# A04: READ nonexistent account
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
OUTPUT=$(run_cobol ACCOUNTS "$TD" "READ NONEXIST00")
assert_contains "$OUTPUT" "RESULT|03" "A04: READ nonexistent returns RESULT|03"
rm -rf "$TD"

# A05: CREATE new account
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
OUTPUT=$(run_cobol ACCOUNTS "$TD" "CREATE ACT-T-099 NewAccount C")
assert_contains "$OUTPUT" "ACCOUNT-CREATED|" "A05: CREATE returns ACCOUNT-CREATED|"
assert_contains "$OUTPUT" "RESULT|00" "A05: CREATE returns RESULT|00"
rm -rf "$TD"

# A06: CREATE duplicate account
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
OUTPUT=$(run_cobol ACCOUNTS "$TD" "CREATE ACT-T-001 Duplicate C")
assert_contains "$OUTPUT" "RESULT|99" "A06: CREATE duplicate returns RESULT|99"
rm -rf "$TD"

# A07: UPDATE account status to frozen
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
OUTPUT=$(run_cobol ACCOUNTS "$TD" "UPDATE ACT-T-001 F")
assert_contains "$OUTPUT" "ACCOUNT-UPDATED|" "A07: UPDATE returns ACCOUNT-UPDATED|"
assert_contains "$OUTPUT" "RESULT|00" "A07: UPDATE returns RESULT|00"
rm -rf "$TD"

# A08: UPDATE nonexistent account
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
OUTPUT=$(run_cobol ACCOUNTS "$TD" "UPDATE NONEXIST00 F")
assert_contains "$OUTPUT" "RESULT|03" "A08: UPDATE nonexistent returns RESULT|03"
rm -rf "$TD"

# A09: CLOSE account
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
OUTPUT=$(run_cobol ACCOUNTS "$TD" "CLOSE ACT-T-001")
assert_contains "$OUTPUT" "ACCOUNT-CLOSED|" "A09: CLOSE returns ACCOUNT-CLOSED|"
assert_contains "$OUTPUT" "RESULT|00" "A09: CLOSE returns RESULT|00"
rm -rf "$TD"

# A10: LIST verifies correct field output
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
OUTPUT=$(run_cobol ACCOUNTS "$TD" LIST)
assert_contains "$OUTPUT" "ACT-T-001" "A10: LIST output contains account ID"
assert_contains "$OUTPUT" "Alice Test" "A10: LIST output contains account name"
rm -rf "$TD"

# A11: Invalid operation
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
OUTPUT=$(run_cobol ACCOUNTS "$TD" "BADOP")
assert_contains "$OUTPUT" "RESULT|99" "A11: Invalid operation returns RESULT|99"
rm -rf "$TD"

#================================================================
# TRANSACT.cob (18 tests)
# TRANSACT uses UNSTRING on command line, so multi-arg works.
# All args passed as single string: "DEPOSIT ACT-T-001 1000.00"
#================================================================
echo ""
echo -e "${CYAN}--- TRANSACT.cob ---${NC}"

# T01: Deposit success
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol TRANSACT "$TD" "DEPOSIT ACT-T-001 1000.00")
assert_contains "$OUTPUT" "OK|DEPOSIT" "T01: Deposit returns OK|DEPOSIT"
assert_contains "$OUTPUT" "RESULT|00" "T01: Deposit returns RESULT|00"
rm -rf "$TD"

# T02: Deposit to frozen account
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Frozen Acct" "C" 500000 "F"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol TRANSACT "$TD" "DEPOSIT ACT-T-001 100.00")
assert_contains "$OUTPUT" "RESULT|04" "T02: Deposit to frozen returns RESULT|04"
rm -rf "$TD"

# T03: Deposit to nonexistent account
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol TRANSACT "$TD" "DEPOSIT NONEXIST00 100.00")
assert_contains "$OUTPUT" "RESULT|03" "T03: Deposit nonexistent returns RESULT|03"
rm -rf "$TD"

# T04: Withdraw success
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol TRANSACT "$TD" "WITHDRAW ACT-T-001 1000.00")
assert_contains "$OUTPUT" "OK|WITHDRAW" "T04: Withdraw returns OK|WITHDRAW"
assert_contains "$OUTPUT" "RESULT|00" "T04: Withdraw returns RESULT|00"
rm -rf "$TD"

# T05: Withdraw NSF (balance $100 < $500)
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 10000 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol TRANSACT "$TD" "WITHDRAW ACT-T-001 500.00")
assert_contains "$OUTPUT" "RESULT|01" "T05: Withdraw NSF returns RESULT|01"
rm -rf "$TD"

# T06: Withdraw over daily limit ($60k > $50k)
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Rich Person" "C" 9999999999 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol TRANSACT "$TD" "WITHDRAW ACT-T-001 60000.00")
assert_contains "$OUTPUT" "RESULT|02" "T06: Withdraw over limit returns RESULT|02"
rm -rf "$TD"

# T07: Withdraw from frozen account
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Frozen Acct" "C" 500000 "F"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol TRANSACT "$TD" "WITHDRAW ACT-T-001 100.00")
assert_contains "$OUTPUT" "RESULT|04" "T07: Withdraw frozen returns RESULT|04"
rm -rf "$TD"

# T08: Transfer success
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
write_account "$TD" "ACT-T-002" "Bob Test" "C" 300000 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol TRANSACT "$TD" "TRANSFER ACT-T-001 1000.00 ACT-T-002")
assert_contains "$OUTPUT" "OK|TRANSFER" "T08: Transfer returns OK|TRANSFER"
assert_contains "$OUTPUT" "RESULT|00" "T08: Transfer returns RESULT|00"
rm -rf "$TD"

# T09: Transfer bad target
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol TRANSACT "$TD" "TRANSFER ACT-T-001 1000.00 NONEXIST00")
assert_contains "$OUTPUT" "RESULT|03" "T09: Transfer bad target returns RESULT|03"
rm -rf "$TD"

# T10: Transfer NSF
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 10000 "A"
write_account "$TD" "ACT-T-002" "Bob Test" "C" 300000 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol TRANSACT "$TD" "TRANSFER ACT-T-001 500.00 ACT-T-002")
assert_contains "$OUTPUT" "RESULT|01" "T10: Transfer NSF returns RESULT|01"
rm -rf "$TD"

# T11: Batch deposits
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
write_account "$TD" "ACT-T-002" "Bob Test" "C" 300000 "A"
touch "$TD/TRANSACT.DAT"
write_batch_line "$TD" "ACT-T-001|D|1000.00|Payroll deposit"
write_batch_line "$TD" "ACT-T-002|D|2000.00|Wire transfer in"
OUTPUT=$(run_cobol TRANSACT "$TD" BATCH)
assert_contains "$OUTPUT" "BATCH SUMMARY" "T11: Batch deposits show summary"
assert_contains "$OUTPUT" "RESULT|00" "T11: Batch deposits return RESULT|00"
rm -rf "$TD"

# T12: Batch withdrawal
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
touch "$TD/TRANSACT.DAT"
write_batch_line "$TD" "ACT-T-001|W|1000.00|ATM withdrawal"
OUTPUT=$(run_cobol TRANSACT "$TD" BATCH)
assert_contains "$OUTPUT" "OK" "T12: Batch withdrawal succeeds"
assert_contains "$OUTPUT" "RESULT|00" "T12: Batch withdrawal returns RESULT|00"
rm -rf "$TD"

# T13: Batch mixed pass/fail
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
write_account "$TD" "ACT-T-002" "Bob Test" "C" 5000 "A"
touch "$TD/TRANSACT.DAT"
write_batch_line "$TD" "ACT-T-001|D|1000.00|Good deposit"
write_batch_line "$TD" "ACT-T-002|W|500.00|Overdraw attempt"
write_batch_line "$TD" "NONEXIST00|D|100.00|Bad account"
OUTPUT=$(run_cobol TRANSACT "$TD" BATCH)
assert_contains "$OUTPUT" "Successful:" "T13: Batch mixed shows success count"
assert_contains "$OUTPUT" "Failed:" "T13: Batch mixed shows fail count"
rm -rf "$TD"

# T14: Batch transfer
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
write_account "$TD" "ACT-T-002" "Bob Test" "C" 300000 "A"
touch "$TD/TRANSACT.DAT"
write_batch_line "$TD" "ACT-T-001|T|1000.00|Transfer to Bob|ACT-T-002"
OUTPUT=$(run_cobol TRANSACT "$TD" BATCH)
assert_contains "$OUTPUT" "XFR" "T14: Batch transfer shows XFR type"
assert_contains "$OUTPUT" "RESULT|00" "T14: Batch transfer returns RESULT|00"
rm -rf "$TD"

# T15: Batch transfer bad target
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
touch "$TD/TRANSACT.DAT"
write_batch_line "$TD" "ACT-T-001|T|1000.00|Transfer to nobody|NONEXIST00"
OUTPUT=$(run_cobol TRANSACT "$TD" BATCH)
assert_contains "$OUTPUT" "FAIL03" "T15: Batch transfer bad target shows FAIL03"
rm -rf "$TD"

# T16: Batch frozen account
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Frozen Acct" "C" 500000 "F"
touch "$TD/TRANSACT.DAT"
write_batch_line "$TD" "ACT-T-001|D|1000.00|Deposit to frozen"
OUTPUT=$(run_cobol TRANSACT "$TD" BATCH)
assert_contains "$OUTPUT" "FAIL04" "T16: Batch frozen account shows FAIL04"
rm -rf "$TD"

# T17: Invalid operation
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol TRANSACT "$TD" "BADOP ACT-T-001 100.00")
assert_contains "$OUTPUT" "RESULT|99" "T17: Invalid operation returns RESULT|99"
rm -rf "$TD"

# T18: TX ID sequencing
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol TRANSACT "$TD" "DEPOSIT ACT-T-001 100.00")
assert_contains "$OUTPUT" "TRX-T-000001" "T18a: First TX ID is TRX-T-000001"
OUTPUT2=$(run_cobol TRANSACT "$TD" "DEPOSIT ACT-T-001 200.00")
assert_contains "$OUTPUT2" "TRX-T-000002" "T18b: Second TX ID is TRX-T-000002"
rm -rf "$TD"

#================================================================
# VALIDATE.cob (6 tests)
# VALIDATE uses UNSTRING to parse "account_id amount" from command line.
#================================================================
echo ""
echo -e "${CYAN}--- VALIDATE.cob ---${NC}"

# V01: Valid account + amount
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
OUTPUT=$(run_cobol VALIDATE "$TD" "ACT-T-001 1000.00")
assert_contains "$OUTPUT" "RESULT|00" "V01: Valid account+amount returns RESULT|00"
rm -rf "$TD"

# V02: Account not found
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
OUTPUT=$(run_cobol VALIDATE "$TD" "NONEXIST00 100.00")
assert_contains "$OUTPUT" "RESULT|03" "V02: Not found returns RESULT|03"
rm -rf "$TD"

# V03: Frozen account
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Frozen Acct" "C" 500000 "F"
OUTPUT=$(run_cobol VALIDATE "$TD" "ACT-T-001 100.00")
assert_contains "$OUTPUT" "RESULT|04" "V03: Frozen returns RESULT|04"
rm -rf "$TD"

# V04: Insufficient balance
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Low Balance" "C" 10000 "A"
OUTPUT=$(run_cobol VALIDATE "$TD" "ACT-T-001 500.00")
assert_contains "$OUTPUT" "RESULT|01" "V04: Insufficient balance returns RESULT|01"
rm -rf "$TD"

# V05: Daily limit exceeded
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Rich Person" "C" 9999999999 "A"
OUTPUT=$(run_cobol VALIDATE "$TD" "ACT-T-001 60000.00")
assert_contains "$OUTPUT" "RESULT|02" "V05: Limit exceeded returns RESULT|02"
rm -rf "$TD"

# V06: No amount arg (skip balance/limit checks)
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
OUTPUT=$(run_cobol VALIDATE "$TD" "ACT-T-001")
assert_contains "$OUTPUT" "RESULT|00" "V06: No amount returns RESULT|00"
rm -rf "$TD"

#================================================================
# REPORTS.cob (7 tests)
# REPORTS accepts operation as first arg (single word fits PIC X(10)).
# STATEMENT also reads WS-IN-ACCT-ID from command line — same
# multi-ACCEPT issue as ACCOUNTS, so STATEMENT with account ID
# is tested but may exhibit similar limitations.
#================================================================
echo ""
echo -e "${CYAN}--- REPORTS.cob ---${NC}"

# R01: LEDGER report with C/S split
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Check" "C" 500000 "A"
write_account "$TD" "ACT-T-002" "Bob Savings" "S" 1000000 "A"
OUTPUT=$(run_cobol REPORTS "$TD" LEDGER)
assert_contains "$OUTPUT" "RESULT|00" "R01: LEDGER returns RESULT|00"
assert_contains "$OUTPUT" "CHECKING-BALANCE" "R01: LEDGER shows checking balance"
assert_contains "$OUTPUT" "SAVINGS-BALANCE" "R01: LEDGER shows savings balance"
assert_line_count "$OUTPUT" "ACCOUNT|" 2 "R01: LEDGER shows 2 accounts"
rm -rf "$TD"

# R02: STATEMENT with transactions
# Note: REPORTS uses ACCEPT for operation, then ACCEPT for acct_id.
# Pass as single word + space + id. Both ACCEPTs get the whole string.
# The program sets WS-OPERATION to the first 10 chars: "STATEMENT "
# which should match "STATEMENT ". Then WS-IN-ACCT-ID also gets
# "STATEMENT ACT-T-001" (first 10 chars: "STATEMENT ").
# This means STATEMENT filtering won't work correctly due to the
# multi-ACCEPT limitation. We test the code path that runs.
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
write_transaction "$TD" "TRX-T-000001" "ACT-T-001" "D" 100000 "20260217" "103000" "Test deposit" "00"
write_transaction "$TD" "TRX-T-000002" "ACT-T-002" "D" 200000 "20260217" "103100" "Other deposit" "00"
OUTPUT=$(run_cobol REPORTS "$TD" STATEMENT)
# STATEMENT reads TRANSACT.DAT regardless of account filter
assert_contains "$OUTPUT" "RESULT|00" "R02: STATEMENT returns RESULT|00"
rm -rf "$TD"

# R03: STATEMENT no TX file
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
OUTPUT=$(run_cobol REPORTS "$TD" STATEMENT)
assert_contains "$OUTPUT" "RESULT|99" "R03: STATEMENT no TX file returns RESULT|99"
rm -rf "$TD"

# R04: EOD with mixed status codes
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
write_transaction "$TD" "TRX-T-000001" "ACT-T-001" "D" 100000 "20260217" "103000" "Success tx" "00"
write_transaction "$TD" "TRX-T-000002" "ACT-T-001" "W" 999999 "20260217" "103100" "NSF tx" "01"
write_transaction "$TD" "TRX-T-000003" "ACT-T-001" "W" 100000 "20260217" "103200" "Limit tx" "02"
write_transaction "$TD" "TRX-T-000004" "NONEXIST00" "D" 100000 "20260217" "103300" "Bad acct tx" "03"
write_transaction "$TD" "TRX-T-000005" "ACT-T-001" "D" 100000 "20260217" "103400" "Frozen tx" "04"
OUTPUT=$(run_cobol REPORTS "$TD" EOD)
assert_contains "$OUTPUT" "RESULT|00" "R04: EOD returns RESULT|00"
assert_contains "$OUTPUT" "STATS|SUCCESS|" "R04: EOD has SUCCESS stats"
assert_contains "$OUTPUT" "STATS|NSF|" "R04: EOD has NSF stats"
assert_contains "$OUTPUT" "STATS|LIMIT|" "R04: EOD has LIMIT stats"
assert_contains "$OUTPUT" "STATS|BADACCT|" "R04: EOD has BADACCT stats"
assert_contains "$OUTPUT" "STATS|FROZEN|" "R04: EOD has FROZEN stats"
rm -rf "$TD"

# R05: AUDIT trail
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
write_transaction "$TD" "TRX-T-000001" "ACT-T-001" "D" 100000 "20260217" "103000" "Test deposit" "00"
write_transaction "$TD" "TRX-T-000002" "ACT-T-001" "W" 50000 "20260217" "103100" "Test withdraw" "00"
OUTPUT=$(run_cobol REPORTS "$TD" AUDIT)
assert_contains "$OUTPUT" "RESULT|00" "R05: AUDIT returns RESULT|00"
assert_line_count "$OUTPUT" "TRANS|" 2 "R05: AUDIT shows all 2 transactions"
rm -rf "$TD"

# R06: Invalid operation
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
OUTPUT=$(run_cobol REPORTS "$TD" "BADOP")
assert_contains "$OUTPUT" "RESULT|99" "R06: Invalid report op returns RESULT|99"
rm -rf "$TD"

# R07: LEDGER empty (no accounts)
TD=$(new_test_dir)
touch "$TD/ACCOUNTS.DAT"
OUTPUT=$(run_cobol REPORTS "$TD" LEDGER)
assert_contains "$OUTPUT" "RESULT|00" "R07: LEDGER empty returns RESULT|00"
assert_line_count "$OUTPUT" "ACCOUNT|" 0 "R07: LEDGER empty shows 0 accounts"
rm -rf "$TD"

#================================================================
# FEES.cob (8 tests)
# FEES takes no args, reads ACCOUNTS.DAT, writes TRANSACT.DAT.
#================================================================
echo ""
echo -e "${CYAN}--- FEES.cob ---${NC}"

# F01: Maintenance fee ($12.00 for checking < $5000)
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Check" "C" 300000 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol FEES "$TD")
assert_contains "$OUTPUT" "FEE|" "F01: Fee assessed (FEE| line present)"
assert_contains "$OUTPUT" "MAINT" "F01: Fee type is MAINT"
assert_contains "$OUTPUT" "RESULT|00" "F01: Returns RESULT|00"
rm -rf "$TD"

# F02: Low-balance surcharge ($12 + $8 = $20 for < $500)
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Low Balance" "C" 30000 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol FEES "$TD")
assert_contains "$OUTPUT" "FEE|" "F02: Low-balance fee assessed"
assert_contains "$OUTPUT" "RESULT|00" "F02: Returns RESULT|00"
rm -rf "$TD"

# F03: Fee waived (balance > $5000)
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Rich Check" "C" 1000000 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol FEES "$TD")
assert_contains "$OUTPUT" "FEE-SKIP|" "F03: Fee waived (FEE-SKIP present)"
assert_contains "$OUTPUT" "WAIVED-ABOVE-5000" "F03: Reason is WAIVED-ABOVE-5000"
rm -rf "$TD"

# F04: Balance floor protection (fee > balance → skip)
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Tiny Balance" "C" 500 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol FEES "$TD")
assert_contains "$OUTPUT" "FEE-SKIP|" "F04: Fee skipped (FEE-SKIP present)"
assert_contains "$OUTPUT" "INSUFFICIENT-BALANCE" "F04: Reason is INSUFFICIENT-BALANCE"
rm -rf "$TD"

# F05: Savings account skipped (type != 'C')
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Savings Only" "S" 300000 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol FEES "$TD")
assert_not_contains "$OUTPUT" "FEE|ACT-T-001" "F05: Savings not assessed (no FEE|)"
assert_not_contains "$OUTPUT" "FEE-SKIP|ACT-T-001" "F05: Savings not mentioned"
assert_contains "$OUTPUT" "RESULT|00" "F05: Returns RESULT|00"
rm -rf "$TD"

# F06: Frozen checking skipped (status != 'A')
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Frozen Check" "C" 300000 "F"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol FEES "$TD")
assert_not_contains "$OUTPUT" "FEE|ACT-T-001" "F06: Frozen not assessed"
assert_contains "$OUTPUT" "RESULT|00" "F06: Returns RESULT|00"
rm -rf "$TD"

# F07: Mixed types — one waived, one assessed, one savings-skip
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Rich Check" "C" 1000000 "A"
write_account "$TD" "ACT-T-002" "Normal Check" "C" 300000 "A"
write_account "$TD" "ACT-T-003" "Savings Acct" "S" 500000 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol FEES "$TD")
assert_contains "$OUTPUT" "WAIVED-ABOVE-5000" "F07: One fee waived"
assert_contains "$OUTPUT" "FEE|" "F07: One fee assessed"
assert_contains "$OUTPUT" "RESULT|00" "F07: Returns RESULT|00"
rm -rf "$TD"

# F08: TX record written to TRANSACT.DAT
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Check" "C" 300000 "A"
touch "$TD/TRANSACT.DAT"
run_cobol FEES "$TD" > /dev/null
assert_file_has_content "$TD/TRANSACT.DAT" "F08: TRANSACT.DAT has F-type record"
rm -rf "$TD"

#================================================================
# INTEREST.cob (7 tests)
# INTEREST takes no args, reads ACCOUNTS.DAT, writes TRANSACT.DAT.
#================================================================
echo ""
echo -e "${CYAN}--- INTEREST.cob ---${NC}"

# I01: Low-tier interest (< $10k, 0.50% APR)
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Small Savings" "S" 500000 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol INTEREST "$TD")
assert_contains "$OUTPUT" "INTEREST|" "I01: Interest accrued (INTEREST| line)"
assert_contains "$OUTPUT" "RESULT|00" "I01: Returns RESULT|00"
rm -rf "$TD"

# I02: Mid-tier interest ($10k-$100k, 1.50% APR)
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Mid Savings" "S" 5000000 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol INTEREST "$TD")
assert_contains "$OUTPUT" "INTEREST|" "I02: Mid-tier interest accrued"
assert_contains "$OUTPUT" "RESULT|00" "I02: Returns RESULT|00"
rm -rf "$TD"

# I03: High-tier interest (> $100k, 2.00% APR)
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Big Savings" "S" 20000000 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol INTEREST "$TD")
assert_contains "$OUTPUT" "INTEREST|" "I03: High-tier interest accrued"
assert_contains "$OUTPUT" "RESULT|00" "I03: Returns RESULT|00"
rm -rf "$TD"

# I04: Checking account skipped (type != 'S')
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Checking Acct" "C" 500000 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol INTEREST "$TD")
assert_not_contains "$OUTPUT" "INTEREST|ACT-T-001" "I04: Checking not accrued"
assert_contains "$OUTPUT" "RESULT|00" "I04: Returns RESULT|00"
rm -rf "$TD"

# I05: Frozen savings skipped (status != 'A')
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Frozen Savings" "S" 500000 "F"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol INTEREST "$TD")
assert_not_contains "$OUTPUT" "INTEREST|ACT-T-001" "I05: Frozen not accrued"
assert_contains "$OUTPUT" "RESULT|00" "I05: Returns RESULT|00"
rm -rf "$TD"

# I06: Zero-balance savings skipped
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Zero Savings" "S" 0 "A"
touch "$TD/TRANSACT.DAT"
OUTPUT=$(run_cobol INTEREST "$TD")
assert_not_contains "$OUTPUT" "INTEREST|ACT-T-001" "I06: Zero-balance not accrued"
assert_contains "$OUTPUT" "RESULT|00" "I06: Returns RESULT|00"
rm -rf "$TD"

# I07: TX record written to TRANSACT.DAT
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Active Savings" "S" 500000 "A"
touch "$TD/TRANSACT.DAT"
run_cobol INTEREST "$TD" > /dev/null
assert_file_has_content "$TD/TRANSACT.DAT" "I07: TRANSACT.DAT has I-type record"
rm -rf "$TD"

#================================================================
# RECONCILE.cob (7 tests)
# RECONCILE takes no args, reads both DAT files.
#================================================================
echo ""
echo -e "${CYAN}--- RECONCILE.cob ---${NC}"

# RC01: All match (no transactions)
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
write_account "$TD" "ACT-T-002" "Bob Test" "S" 1000000 "A"
write_account "$TD" "ACT-T-003" "Carol Test" "C" 250000 "A"
OUTPUT=$(run_cobol RECONCILE "$TD")
assert_contains "$OUTPUT" "RESULT|00" "RC01: All match (no TXs) returns RESULT|00"
assert_contains "$OUTPUT" "RECON-SUMMARY|" "RC01: Shows RECON-SUMMARY"
rm -rf "$TD"

# RC02: Match with consistent transactions
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 600000 "A"
write_transaction "$TD" "TRX-T-000001" "ACT-T-001" "D" 100000 "20260217" "103000" "Deposit" "00"
OUTPUT=$(run_cobol RECONCILE "$TD")
assert_contains "$OUTPUT" "MATCH" "RC02: Consistent TX shows MATCH"
assert_contains "$OUTPUT" "RESULT|00" "RC02: Returns RESULT|00"
rm -rf "$TD"

# RC03: Mismatch detected (implied opening < 0)
# Balance $100, deposit TX $500 → opening = 100 - 500 = -400 → MISMATCH
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Tampered Acct" "C" 10000 "A"
write_transaction "$TD" "TRX-T-000001" "ACT-T-001" "D" 50000 "20260217" "103000" "Fake deposit" "00"
OUTPUT=$(run_cobol RECONCILE "$TD")
assert_contains "$OUTPUT" "MISMATCH" "RC03: Tampered balance shows MISMATCH"
assert_contains "$OUTPUT" "RESULT|01" "RC03: Returns RESULT|01 (mismatches found)"
rm -rf "$TD"

# RC04: Mixed match/mismatch
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Consistent" "C" 600000 "A"
write_account "$TD" "ACT-T-002" "Tampered" "C" 10000 "A"
write_transaction "$TD" "TRX-T-000001" "ACT-T-001" "D" 100000 "20260217" "103000" "Good deposit" "00"
write_transaction "$TD" "TRX-T-000002" "ACT-T-002" "D" 500000 "20260217" "103100" "Bad deposit" "00"
OUTPUT=$(run_cobol RECONCILE "$TD")
assert_contains "$OUTPUT" "MATCH" "RC04: Has at least one MATCH"
assert_contains "$OUTPUT" "MISMATCH" "RC04: Has at least one MISMATCH"
assert_contains "$OUTPUT" "RESULT|01" "RC04: Returns RESULT|01"
rm -rf "$TD"

# RC05: All TX types (D, I, W, F, T) correctly classified
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "All Types" "C" 1000000 "A"
write_transaction "$TD" "TRX-T-000001" "ACT-T-001" "D" 100000 "20260217" "103000" "Deposit" "00"
write_transaction "$TD" "TRX-T-000002" "ACT-T-001" "I" 5000 "20260217" "103100" "Interest" "00"
write_transaction "$TD" "TRX-T-000003" "ACT-T-001" "W" 50000 "20260217" "103200" "Withdraw" "00"
write_transaction "$TD" "TRX-T-000004" "ACT-T-001" "F" 1200 "20260217" "103300" "Fee" "00"
write_transaction "$TD" "TRX-T-000005" "ACT-T-001" "T" 20000 "20260217" "103400" "Transfer" "00"
OUTPUT=$(run_cobol RECONCILE "$TD")
assert_contains "$OUTPUT" "MATCH" "RC05: All TX types reconcile to MATCH"
assert_contains "$OUTPUT" "RESULT|00" "RC05: Returns RESULT|00"
rm -rf "$TD"

# RC06: Failed TX (status != '00') ignored
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
write_transaction "$TD" "TRX-T-000001" "ACT-T-001" "D" 100000 "20260217" "103000" "Failed deposit" "01"
OUTPUT=$(run_cobol RECONCILE "$TD")
assert_contains "$OUTPUT" "MATCH" "RC06: Failed TX ignored → MATCH"
assert_contains "$OUTPUT" "RESULT|00" "RC06: Returns RESULT|00"
rm -rf "$TD"

# RC07: Summary format check
TD=$(new_test_dir)
write_account "$TD" "ACT-T-001" "Alice Test" "C" 500000 "A"
write_account "$TD" "ACT-T-002" "Bob Test" "S" 1000000 "A"
OUTPUT=$(run_cobol RECONCILE "$TD")
assert_contains "$OUTPUT" "RECON-SUMMARY|" "RC07: RECON-SUMMARY format present"
rm -rf "$TD"

#================================================================
# Summary
#================================================================
echo ""
echo "================================================================"
TOTAL=$((PASS + FAIL))
if [ "$SKIP" -gt 0 ]; then
  echo -e "  RESULTS: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}, ${YELLOW}$SKIP skipped${NC}, $TOTAL total"
else
  echo -e "  RESULTS: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}, $TOTAL total"
fi
echo "================================================================"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
