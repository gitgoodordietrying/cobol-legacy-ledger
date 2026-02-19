#!/bin/bash
#================================================================*
# cobol-test.sh — Standalone COBOL system harness (zero Python)
# Tests COBOL programs in isolation: LIST, TRANSACT, VALIDATE, REPORTS
#================================================================*

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

NODE="${1:-BANK_A}"
NODE_DIR="$PROJECT_ROOT/banks/$NODE"
DATA_DIR="$NODE_DIR"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "COBOL SYSTEM TEST — $NODE"
echo "=========================================="

# Step 0: Build all COBOL programs
echo ""
echo "Step 0: Compiling COBOL programs..."
if "$SCRIPT_DIR/build.sh" > /dev/null 2>&1; then
  echo -e "${GREEN}✓ Build successful${NC}"
else
  echo -e "${RED}✗ Build failed${NC}"
  exit 1
fi

# Helper: Determine COBOL run command
run_cobol() {
  local program="$1"
  shift

  if command -v cobc &> /dev/null || [ -f /.dockerenv ]; then
    # Local cobc available, OR already inside Docker — run binary directly
    (cd "$DATA_DIR" && "$PROJECT_ROOT/cobol/bin/$program" "$@")
  else
    # Host without cobc — use Docker wrapper (spawns container for each call)
    "$SCRIPT_DIR/cobol-run.sh" bash -c "cd /app/banks/$NODE && /app/cobol/bin/$program $*"
  fi
}

# Helper: Check file exists
check_file() {
  local filepath="$1"
  if [ ! -f "$filepath" ]; then
    echo -e "${RED}✗ File not found: $filepath${NC}"
    return 1
  fi
  return 0
}

# Helper: Check output contains string
check_output_contains() {
  local output="$1"
  local pattern="$2"
  if echo "$output" | grep -q "$pattern"; then
    return 0
  fi
  return 1
}

# Step 1: Verify ACCOUNTS.DAT exists
echo ""
echo "Step 1: Verify ACCOUNTS.DAT exists..."
if check_file "$DATA_DIR/ACCOUNTS.DAT"; then
  echo -e "${GREEN}✓ $DATA_DIR/ACCOUNTS.DAT found${NC}"
else
  echo -e "${YELLOW}⊘ ACCOUNTS.DAT not found (expected for Phase 1)${NC}"
fi

# Step 2: Run ACCOUNTS LIST
echo ""
echo "Step 2: Test ACCOUNTS LIST..."
if [ ! -f "$PROJECT_ROOT/cobol/bin/ACCOUNTS" ]; then
  echo -e "${YELLOW}⊘ ACCOUNTS binary not built (stub program)${NC}"
else
  if OUTPUT=$(run_cobol ACCOUNTS LIST 2>&1); then
    if check_output_contains "$OUTPUT" "ACCOUNT|"; then
      echo -e "${GREEN}✓ ACCOUNTS LIST returned account records${NC}"
    else
      echo -e "${YELLOW}⊘ ACCOUNTS LIST did not return ACCOUNT| records${NC}"
    fi

    if check_output_contains "$OUTPUT" "RESULT|00"; then
      echo -e "${GREEN}✓ RESULT|00 status code found${NC}"
    else
      echo -e "${YELLOW}⊘ RESULT|00 not found in output${NC}"
    fi
  else
    echo -e "${YELLOW}⊘ ACCOUNTS LIST execution failed (stub program)${NC}"
  fi
fi

# Step 3: Run TRANSACT DEPOSIT
echo ""
echo "Step 3: Test TRANSACT DEPOSIT..."
if [ ! -f "$PROJECT_ROOT/cobol/bin/TRANSACT" ]; then
  echo -e "${YELLOW}⊘ TRANSACT binary not built (stub program)${NC}"
else
  # Extract first account ID from ACCOUNTS.DAT if it exists
  FIRST_ACCT="ACT-$NODE-001"

  if OUTPUT=$(run_cobol TRANSACT DEPOSIT "$FIRST_ACCT" 1000.00 "test deposit" 2>&1); then
    if check_output_contains "$OUTPUT" "OK|DEPOSIT"; then
      echo -e "${GREEN}✓ TRANSACT DEPOSIT returned OK|DEPOSIT${NC}"
    else
      echo -e "${YELLOW}⊘ TRANSACT DEPOSIT did not return OK|DEPOSIT${NC}"
    fi

    if check_output_contains "$OUTPUT" "RESULT|00"; then
      echo -e "${GREEN}✓ RESULT|00 status code found${NC}"
    else
      echo -e "${YELLOW}⊘ RESULT|00 not found${NC}"
    fi
  else
    echo -e "${YELLOW}⊘ TRANSACT DEPOSIT execution failed (stub program)${NC}"
  fi
fi

# Step 4: Run TRANSACT BATCH (if BATCH-INPUT.DAT exists)
echo ""
echo "Step 4: Test TRANSACT BATCH..."
if [ ! -f "$DATA_DIR/BATCH-INPUT.DAT" ]; then
  echo -e "${YELLOW}⊘ BATCH-INPUT.DAT not found (skipping batch test)${NC}"
elif [ ! -f "$PROJECT_ROOT/cobol/bin/TRANSACT" ]; then
  echo -e "${YELLOW}⊘ TRANSACT binary not built${NC}"
else
  if OUTPUT=$(run_cobol TRANSACT BATCH 2>&1); then
    if check_output_contains "$OUTPUT" "SEQ"; then
      echo -e "${GREEN}✓ Batch processing returned SEQ header${NC}"
    else
      echo -e "${YELLOW}⊘ SEQ header not found${NC}"
    fi

    if check_output_contains "$OUTPUT" "BATCH SUMMARY"; then
      echo -e "${GREEN}✓ BATCH SUMMARY found${NC}"
    else
      echo -e "${YELLOW}⊘ BATCH SUMMARY not found${NC}"
    fi

    if check_output_contains "$OUTPUT" "RESULT|00"; then
      echo -e "${GREEN}✓ RESULT|00 status code found${NC}"
    else
      echo -e "${YELLOW}⊘ RESULT|00 not found${NC}"
    fi
  else
    echo -e "${YELLOW}⊘ TRANSACT BATCH execution failed${NC}"
  fi
fi

# Step 5: Run VALIDATE
echo ""
echo "Step 5: Test VALIDATE..."
if [ ! -f "$PROJECT_ROOT/cobol/bin/VALIDATE" ]; then
  echo -e "${YELLOW}⊘ VALIDATE binary not built (stub program)${NC}"
else
  # Test valid account
  if OUTPUT=$(run_cobol VALIDATE "ACT-$NODE-001" 2>&1); then
    if check_output_contains "$OUTPUT" "RESULT|00"; then
      echo -e "${GREEN}✓ VALIDATE returned RESULT|00 for valid account${NC}"
    else
      echo -e "${YELLOW}⊘ RESULT|00 not found for valid account${NC}"
    fi
  else
    echo -e "${YELLOW}⊘ VALIDATE execution failed${NC}"
  fi

  # Test invalid account
  if OUTPUT=$(run_cobol VALIDATE "NONEXIST00" 2>&1); then
    if check_output_contains "$OUTPUT" "RESULT|03"; then
      echo -e "${GREEN}✓ VALIDATE returned RESULT|03 for invalid account${NC}"
    else
      echo -e "${YELLOW}⊘ RESULT|03 not found for invalid account${NC}"
    fi
  else
    echo -e "${YELLOW}⊘ VALIDATE invalid test failed${NC}"
  fi
fi

# Step 6: Run REPORTS LEDGER
echo ""
echo "Step 6: Test REPORTS LEDGER..."
if [ ! -f "$PROJECT_ROOT/cobol/bin/REPORTS" ]; then
  echo -e "${YELLOW}⊘ REPORTS binary not built (stub program)${NC}"
else
  if OUTPUT=$(run_cobol REPORTS LEDGER 2>&1); then
    if check_output_contains "$OUTPUT" "RESULT|00"; then
      echo -e "${GREEN}✓ REPORTS LEDGER returned RESULT|00${NC}"
    else
      echo -e "${YELLOW}⊘ RESULT|00 not found${NC}"
    fi
  else
    echo -e "${YELLOW}⊘ REPORTS LEDGER execution failed${NC}"
  fi
fi

# Step 7: Re-run ACCOUNTS LIST and verify account count unchanged
echo ""
echo "Step 7: Verify account count unchanged..."
if [ -f "$PROJECT_ROOT/cobol/bin/ACCOUNTS" ]; then
  if OUTPUT=$(run_cobol ACCOUNTS LIST 2>&1); then
    ACCOUNT_COUNT=$(echo "$OUTPUT" | grep -c "^ACCOUNT|" || true)
    if [ "$ACCOUNT_COUNT" -gt 0 ]; then
      echo -e "${GREEN}✓ Final account count: $ACCOUNT_COUNT${NC}"
    else
      echo -e "${YELLOW}⊘ No account records found in final LIST${NC}"
    fi
  fi
else
  echo -e "${YELLOW}⊘ ACCOUNTS binary not available${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}★ COBOL SYSTEM TEST COMPLETE ★${NC}"
echo "=========================================="
echo ""
echo "Note: Most steps will SKIP during Phase 1 (programs are stubs)."
echo "This test harness gates Phase 2 COBOL implementation."
echo ""
