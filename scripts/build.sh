#!/bin/bash
#================================================================*
# build.sh — COBOL compiler wrapper with Docker fallback
# Tries local cobc first, falls back to Docker if missing
#================================================================*

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Determine COBC command (local or Docker)
if command -v cobc &> /dev/null; then
  COBC="cobc"
  echo "Using local cobc: $(which cobc)"
elif [ -f /.dockerenv ]; then
  # Already inside a Docker container — cobc must be here (cobol-dev image)
  echo "Running inside Docker. cobc expected at: $(which cobc 2>/dev/null || echo NOT FOUND)"
  COBC="cobc"
else
  COBC="$SCRIPT_DIR/cobol-run.sh cobc"
  echo "cobc not found locally. Using Docker fallback."
fi

# Create bin directory
mkdir -p "$PROJECT_ROOT/COBOL-BANKING/bin"

# Array of programs to compile
PROGRAMS=(SMOKETEST ACCOUNTS TRANSACT VALIDATE REPORTS INTEREST FEES RECONCILE SIMULATE SETTLE)
FAILED_PROGRAMS=()

# Compile each program independently
for PROG in "${PROGRAMS[@]}"; do
  PROG_PATH="$PROJECT_ROOT/COBOL-BANKING/src/${PROG}.cob"
  BIN_PATH="$PROJECT_ROOT/COBOL-BANKING/bin/${PROG}"

  if [ ! -f "$PROG_PATH" ]; then
    echo "SKIP $PROG (file not found: $PROG_PATH)"
    continue
  fi

  echo -n "BUILD $PROG ... "
  # Use relative paths for Docker compatibility (Docker workdir is /app)
  if [ "$COBC" = "cobc" ]; then
    # Local cobc — use absolute paths
    if $COBC -x -free -I "$PROJECT_ROOT/COBOL-BANKING/copybooks" "$PROG_PATH" -o "$BIN_PATH" 2>&1; then
      echo "OK"
    else
      echo "FAIL"
      FAILED_PROGRAMS+=("$PROG")
    fi
  else
    # Docker cobc (via cobol-run.sh) — use relative paths from /app
    if $COBC -x -free -I COBOL-BANKING/copybooks "COBOL-BANKING/src/${PROG}.cob" -o "COBOL-BANKING/bin/${PROG}" 2>&1; then
      echo "OK"
    else
      echo "FAIL"
      FAILED_PROGRAMS+=("$PROG")
    fi
  fi
done

# ── Payroll sidecar programs ──────────────────────────────────
# Legacy payroll system with intentional anti-patterns (Layer 5).
# Uses its own copybook directory in addition to the banking copybooks.
echo ""
echo "=== PAYROLL SIDECAR ==="
PAYROLL_PROGRAMS=(PAYROLL TAXCALC DEDUCTN PAYBATCH)

for PROG in "${PAYROLL_PROGRAMS[@]}"; do
  PROG_PATH="$PROJECT_ROOT/COBOL-BANKING/payroll/src/${PROG}.cob"
  BIN_PATH="$PROJECT_ROOT/COBOL-BANKING/bin/${PROG}"

  if [ ! -f "$PROG_PATH" ]; then
    echo "SKIP $PROG (file not found: $PROG_PATH)"
    continue
  fi

  echo -n "BUILD $PROG ... "
  if [ "$COBC" = "cobc" ]; then
    if $COBC -x -free -I "$PROJECT_ROOT/COBOL-BANKING/payroll/copybooks" "$PROG_PATH" -o "$BIN_PATH" 2>&1; then
      echo "OK"
    else
      echo "FAIL"
      FAILED_PROGRAMS+=("$PROG")
    fi
  else
    if $COBC -x -free -I COBOL-BANKING/payroll/copybooks "COBOL-BANKING/payroll/src/${PROG}.cob" -o "COBOL-BANKING/bin/${PROG}" 2>&1; then
      echo "OK"
    else
      echo "FAIL"
      FAILED_PROGRAMS+=("$PROG")
    fi
  fi
done

# Fix permissions (Docker creates files as root)
chmod +x "$PROJECT_ROOT/COBOL-BANKING/bin"/* 2>/dev/null || true

# Report results
if [ ${#FAILED_PROGRAMS[@]} -eq 0 ]; then
  echo ""
  echo "All programs compiled successfully → COBOL-BANKING/bin/"
  exit 0
else
  echo ""
  echo "ERROR: ${#FAILED_PROGRAMS[@]} program(s) failed: ${FAILED_PROGRAMS[*]}"
  exit 1
fi
