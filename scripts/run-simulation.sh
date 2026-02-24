#!/bin/bash
#================================================================*
# run-simulation.sh — 25-Day Hub-and-Spoke Banking Simulation
#
# Orchestrates the pure COBOL inter-bank settlement simulation.
# Each day: 5 banks generate transactions (SIMULATE), then the
# clearing house settles outbound transfers (SETTLE).
#
# Usage:
#   ./scripts/run-simulation.sh          # Full 25-day run
#   ./scripts/run-simulation.sh 10       # Run only 10 days
#
# Prerequisites:
#   ./scripts/build.sh   — Compile SIMULATE and SETTLE
#   ./scripts/seed.sh    — Fresh starting data
#================================================================*

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Number of days (default 25, or from argument)
DAYS=${1:-25}

# Determine execution mode: local cobc or Docker
if command -v cobc &> /dev/null || [ -f /.dockerenv ]; then
  # Running locally or inside Docker — use binaries directly
  RUN_CMD=""
  SIMULATE="$PROJECT_ROOT/cobol/bin/SIMULATE"
  SETTLE="$PROJECT_ROOT/cobol/bin/SETTLE"
  RUN_MODE="local"
else
  # Need Docker to run Linux binaries
  DOCKER_PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd -W 2>/dev/null || cygpath -w "$PROJECT_ROOT" 2>/dev/null || echo "$PROJECT_ROOT")"
  IMAGE_NAME="cobol-dev"
  RUN_MODE="docker"
fi

# Verify binaries exist
if [ ! -f "$PROJECT_ROOT/cobol/bin/SIMULATE" ]; then
  echo "ERROR: SIMULATE binary not found. Run ./scripts/build.sh first."
  exit 1
fi
if [ ! -f "$PROJECT_ROOT/cobol/bin/SETTLE" ]; then
  echo "ERROR: SETTLE binary not found. Run ./scripts/build.sh first."
  exit 1
fi

run_cobol() {
  local WORKDIR="$1"
  local BINARY="$2"
  local ARGS="$3"

  if [ "$RUN_MODE" = "local" ]; then
    cd "$PROJECT_ROOT/$WORKDIR"
    "$PROJECT_ROOT/cobol/bin/$BINARY" "$ARGS"
  else
    MSYS_NO_PATHCONV=1 docker run --rm \
      -v "$DOCKER_PROJECT_ROOT":/app \
      -w "/app/$WORKDIR" \
      "$IMAGE_NAME" \
      "/app/cobol/bin/$BINARY" "$ARGS"
  fi
}

BANKS="BANK_A BANK_B BANK_C BANK_D BANK_E"

echo "========================================"
echo "  LEGACY LEDGER — BANKING SIMULATION"
echo "  Days: $DAYS  |  Mode: $RUN_MODE"
echo "  Banks: $BANKS"
echo "========================================"
echo ""

for DAY in $(seq 1 $DAYS); do
  echo "--- DAY $DAY ---"

  # Phase 1: Each bank generates daily transactions
  for BANK in $BANKS; do
    run_cobol "banks/$BANK" "SIMULATE" "$BANK $DAY"
  done

  # Phase 2: Clearing house settles outbound transfers
  run_cobol "banks/clearing" "SETTLE" "$DAY"

  echo ""
done

echo "========================================"
echo "  SIMULATION COMPLETE — $DAYS days"
echo "========================================"
echo ""
echo "Output files:"
for BANK in $BANKS; do
  TX_FILE="$PROJECT_ROOT/banks/$BANK/TRANSACT.DAT"
  TX_COUNT=0
  if [ -f "$TX_FILE" ]; then
    TX_COUNT=$(wc -l < "$TX_FILE")
  fi
  echo "  $BANK: $TX_COUNT transactions"
done

CLEARING_TX="$PROJECT_ROOT/banks/clearing/TRANSACT.DAT"
STL_COUNT=0
if [ -f "$CLEARING_TX" ]; then
  STL_COUNT=$(wc -l < "$CLEARING_TX")
fi
echo "  CLEARING: $STL_COUNT settlement records"
echo ""
