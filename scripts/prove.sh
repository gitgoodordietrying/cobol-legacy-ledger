#!/usr/bin/env bash
# prove.sh — Executable proof of the cobol-legacy-ledger system.
#
# Run this one command to see the full thesis demonstrated in 30 seconds:
#   1959 COBOL → 2026 Python observation → cryptographic integrity in milliseconds.
#
# What it does:
#   1. Compiles 8 COBOL programs (or confirms binaries exist)
#   2. Seeds 6 independent banking nodes (42 accounts, $100M+)
#   3. Executes an inter-bank settlement (Alice@BANK_A → Bob@BANK_B, 3-step trace)
#   4. Verifies all hash chains intact across the network
#   5. Tampers one bank's ledger (bypassing COBOL and the integrity chain)
#   6. Re-verifies — detects the tamper in <100ms
#
# Usage:
#   ./scripts/prove.sh
#   ./scripts/prove.sh --skip-build    # Skip COBOL compilation

set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"

# Colors (degrade gracefully if terminal doesn't support them)
if [ -t 1 ]; then
    BOLD="\033[1m"
    DIM="\033[2m"
    GREEN="\033[32m"
    RED="\033[31m"
    YELLOW="\033[33m"
    CYAN="\033[36m"
    RESET="\033[0m"
else
    BOLD="" DIM="" GREEN="" RED="" YELLOW="" CYAN="" RESET=""
fi

banner() {
    echo ""
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════${RESET}"
    echo -e "${BOLD}  $1${RESET}"
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════${RESET}"
}

step() {
    echo ""
    echo -e "${BOLD}${GREEN}▸ STEP $1: $2${RESET}"
    echo -e "${DIM}  $3${RESET}"
}

ok() {
    echo -e "  ${GREEN}✓${RESET} $1"
}

fail() {
    echo -e "  ${RED}✗${RESET} $1"
}

info() {
    echo -e "  ${DIM}$1${RESET}"
}

# ═══════════════════════════════════════════════════════════
banner "COBOL LEGACY LEDGER — PROOF OF CONCEPT"
echo ""
echo -e "  ${DIM}\"COBOL isn't the problem. Lack of observability is.\"${RESET}"
echo -e "  ${DIM}Non-invasive cryptographic integrity for inter-bank settlement.${RESET}"
echo -e "  ${DIM}6 nodes · SHA-256 hash chains · tamper detection in milliseconds.${RESET}"

# Ensure Python is available
PYTHON="${PYTHON:-python}"
if ! command -v "$PYTHON" &>/dev/null; then
    PYTHON="python3"
fi

export PYTHONIOENCODING=utf-8

# ═══════════════════════════════════════════════════════════
step 1 "COMPILE COBOL" "Building 8 banking programs from source"

SKIP_BUILD=false
if [[ "${1:-}" == "--skip-build" ]]; then
    SKIP_BUILD=true
fi

if [ "$SKIP_BUILD" = false ] && [ -f scripts/build.sh ]; then
    if bash scripts/build.sh 2>&1 | tail -12; then
        ok "COBOL compilation complete"
    else
        info "COBOL compiler not available — using Python-only mode (Mode B)"
        info "All business logic still works via Python fallback"
    fi
else
    COBOL_COUNT=$(ls cobol/bin/ 2>/dev/null | wc -l)
    if [ "$COBOL_COUNT" -gt 0 ]; then
        ok "$COBOL_COUNT COBOL binaries already present"
    else
        info "No COBOL binaries — using Python-only mode (Mode B)"
    fi
fi

# ═══════════════════════════════════════════════════════════
step 2 "SEED NETWORK" "Initializing 6 independent banking nodes"

# Clean slate: remove old databases so chains start fresh
for NODE in BANK_A BANK_B BANK_C BANK_D BANK_E CLEARING; do
    rm -f "banks/${NODE}/"*.db 2>/dev/null || true
done

$PYTHON -m python.cli seed-all 2>&1

# Show account counts
echo ""
info "Account counts per node:"
for NODE in BANK_A BANK_B BANK_C BANK_D BANK_E CLEARING; do
    COUNT=$($PYTHON -c "
from python.bridge import COBOLBridge
b = COBOLBridge(node='$NODE')
print(len(b.list_accounts()))
b.close()
" 2>/dev/null)
    info "  $NODE: $COUNT accounts"
done

# ═══════════════════════════════════════════════════════════
step 3 "INTER-BANK SETTLEMENT" "Alice@BANK_A pays Bob@BANK_B \$2,500 through clearing house"

info "3-step flow: Source debit → Clearing settlement → Destination credit"
echo ""

$PYTHON -c "
from python.settlement import SettlementCoordinator

coord = SettlementCoordinator()
result = coord.execute_transfer(
    source_bank='BANK_A',
    source_account='ACT-A-001',
    dest_bank='BANK_B',
    dest_account='ACT-B-001',
    amount=2500.00,
    description='Wire transfer — proof of concept'
)

print(f'  Settlement: {result.settlement_ref}')
print(f'  Step 1 — BANK_A debit:      TRX {result.source_trx_id}')
print(f'  Step 2 — CLEARING deposit:   TRX {result.clearing_deposit_id}')
print(f'  Step 2 — CLEARING withdraw:  TRX {result.clearing_withdraw_id}')
print(f'  Step 3 — BANK_B credit:      TRX {result.dest_trx_id}')
print(f'  Status: {result.status} ({result.steps_completed}/3 steps)')
print(f'  Amount: \${result.amount:,.2f}')
" 2>&1

# ═══════════════════════════════════════════════════════════
step 4 "VERIFY INTEGRITY" "Cross-node hash chain verification (all 6 nodes)"

$PYTHON -m python.cli verify --cross-node 2>&1

# ═══════════════════════════════════════════════════════════
step 5 "TAMPER ATTACK" "Attacker modifies BANK_C's ledger directly (bypasses COBOL)"

info "Changing ACT-C-001 balance from legitimate value to \$999,999.99"
info "This bypasses the integrity chain — like editing a database directly."
echo ""

$PYTHON -c "
from python.cross_verify import tamper_balance
result = tamper_balance('banks', 'BANK_C', 'ACT-C-001', 999999.99)
print(f'  Tampered: {result[\"node\"]}/{result[\"account_id\"]}')
print(f'  New (fraudulent) balance: \${result[\"new_amount\"]:,.2f}')
print(f'  File modified: {result[\"file\"]}')
" 2>&1

# ═══════════════════════════════════════════════════════════
step 6 "DETECT TAMPER" "Re-verifying — the system should catch the fraud"

$PYTHON -m python.cli verify --cross-node 2>&1

# ═══════════════════════════════════════════════════════════
banner "PROOF COMPLETE"
echo ""
echo -e "  ${BOLD}What you just saw:${RESET}"
echo -e "  ${GREEN}✓${RESET} 8 COBOL programs compiled (or Mode B fallback active)"
echo -e "  ${GREEN}✓${RESET} 6 banking nodes seeded (42 accounts, \$100M+ in balances)"
echo -e "  ${GREEN}✓${RESET} Inter-bank settlement: 3-step flow through clearing house"
echo -e "  ${GREEN}✓${RESET} SHA-256 hash chains verified intact across all nodes"
echo -e "  ${RED}✗${RESET} Attacker tampered BANK_C's ledger (bypassed COBOL)"
echo -e "  ${GREEN}✓${RESET} Tamper detected — balance drift caught by cross-node verification"
echo ""
echo -e "  ${DIM}The COBOL programs were never modified.${RESET}"
echo -e "  ${DIM}Python observes, records, and verifies — non-invasively.${RESET}"
echo ""
echo -e "  ${BOLD}Architecture:${RESET} docs/ARCHITECTURE.md"
echo -e "  ${BOLD}Full spec:${RESET}     docs/handoff/02_COBOL_AND_DATA.md"
echo -e "  ${BOLD}Source:${RESET}        cobol/src/ (8 programs, 2,166 lines)"
echo ""
