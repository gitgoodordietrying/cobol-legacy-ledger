#!/bin/bash
# Run SMOKETEST.cob and capture output for balance format validation
# This script compiles and runs SMOKETEST.cob, then validates the parser

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "SMOKETEST.cob Execution & Validation"
echo "=========================================="
echo

# Check if GnuCOBOL is installed
if ! command -v cobc &> /dev/null; then
    echo "ERROR: GnuCOBOL (cobc) is not installed."
    echo ""
    echo "Quick installation (automated):"
    echo "  Linux/macOS/WSL:  ./scripts/install_gnucobol.sh"
    echo "  Windows (PowerShell):  .\scripts\install_gnucobol.ps1"
    echo ""
    echo "Manual installation:"
    echo "  Linux (Debian/Ubuntu): sudo apt-get install gnucobol"
    echo "  macOS:                 brew install gnu-cobol"
    echo "  Windows (WSL):         sudo apt-get install gnucobol"
    echo ""
    echo "See SMOKE_TEST_SETUP.md for detailed instructions."
    exit 1
fi

echo "✓ GnuCOBOL found: $(cobc --version)"
echo

# Navigate to COBOL source directory
cd "$PROJECT_ROOT/cobol/src"

# Compile SMOKETEST.cob
echo "Compiling SMOKETEST.cob..."
if cobc -x -free -I ../copybooks SMOKETEST.cob -o ../bin/SMOKETEST 2>&1; then
    echo "✓ Compilation successful"
else
    echo "✗ Compilation failed"
    exit 1
fi
echo

# Ensure BANK_A directory exists
mkdir -p "$PROJECT_ROOT/banks/BANK_A"
cd "$PROJECT_ROOT/banks/BANK_A"

# Run SMOKETEST
echo "Running SMOKETEST.cob..."
echo "----------------------------------------"
OUTPUT_FILE="$PROJECT_ROOT/smoketest_output.txt"
"$PROJECT_ROOT/cobol/bin/SMOKETEST" > "$OUTPUT_FILE" 2>&1
cat "$OUTPUT_FILE"
echo "----------------------------------------"
echo

# Extract balance field from output
BALANCE_LINE=$(grep "OK|READ" "$OUTPUT_FILE" || echo "")
if [ -z "$BALANCE_LINE" ]; then
    echo "✗ ERROR: Could not find READ line in output"
    exit 1
fi

echo "Extracted READ line:"
echo "$BALANCE_LINE"
echo

# Parse balance field (6th field total, 4th after "OK|READ|")
# Format: OK|READ|ACCT-ID|ACCT-NAME|ACCT-TYPE|ACCT-BALANCE|ACCT-STATUS|...
BALANCE_FIELD=$(echo "$BALANCE_LINE" | cut -d'|' -f6)
echo "Balance field extracted: '$BALANCE_FIELD'"
echo "Length: ${#BALANCE_FIELD} characters"
echo "Contains decimal point: $([ "$BALANCE_FIELD" = "${BALANCE_FIELD//./}" ] && echo "no" || echo "yes")"
echo

# Validate parser
echo "Validating parser against extracted balance format..."
cd "$PROJECT_ROOT"
python3 scripts/validate_balance_parser.py --format "$BALANCE_FIELD" --expected 12345.67

echo
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo "1. Review the balance format above"
echo "2. If parser validation passed, you're ready for Phase 2"
echo "3. If parser validation failed, update bridge.py _parse_balance() method"
echo "4. Document findings in SMOKE_TEST_OBSERVATION.md"
echo
