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
else
  COBC="$SCRIPT_DIR/cobol-run.sh cobc"
  echo "cobc not found locally. Using Docker fallback."
fi

# Create bin directory
mkdir -p "$PROJECT_ROOT/cobol/bin"

# Array of programs to compile
PROGRAMS=(SMOKETEST ACCOUNTS TRANSACT VALIDATE REPORTS)
FAILED_PROGRAMS=()

# Compile each program independently
for PROG in "${PROGRAMS[@]}"; do
  PROG_PATH="$PROJECT_ROOT/cobol/src/${PROG}.cob"
  BIN_PATH="$PROJECT_ROOT/cobol/bin/${PROG}"

  if [ ! -f "$PROG_PATH" ]; then
    echo "SKIP $PROG (file not found: $PROG_PATH)"
    continue
  fi

  echo -n "BUILD $PROG ... "
  if $COBC -x -free -I "$PROJECT_ROOT/cobol/copybooks" "$PROG_PATH" -o "$BIN_PATH" 2>&1; then
    echo "OK"
  else
    echo "FAIL"
    FAILED_PROGRAMS+=("$PROG")
  fi
done

# Fix permissions (Docker creates files as root)
chmod +x "$PROJECT_ROOT/cobol/bin"/* 2>/dev/null || true

# Report results
if [ ${#FAILED_PROGRAMS[@]} -eq 0 ]; then
  echo ""
  echo "All programs compiled successfully → cobol/bin/"
  exit 0
else
  echo ""
  echo "ERROR: ${#FAILED_PROGRAMS[@]} program(s) failed: ${FAILED_PROGRAMS[*]}"
  exit 1
fi
