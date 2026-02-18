#!/bin/bash
#================================================================*
# demo.sh — Run Phase 1 demo: transactions and tamper detection
# Shows end-to-end integrity chain verification
# Usage: ./scripts/demo.sh
#================================================================*

set -e

echo "Running Phase 1 Demo: Inter-bank Settlement with Integrity Verification"
echo "================================================================"
echo ""

# Activate venv
if [ ! -d "python/venv" ]; then
    echo "Error: Python venv not found. Run ./scripts/setup.sh first"
    exit 1
fi
source python/venv/bin/activate

# Demo sequence
echo "Step 1: Check account balances (Alice in BANK_A, Bob in BANK_B)"
echo "-----------------------------------------------------------------"
python3 - <<'EOF'
from python.bridge import COBOLBridge

alice_bank = COBOLBridge(node="BANK_A")
bob_bank = COBOLBridge(node="BANK_B")

alice = alice_bank.get_account("ACT-A-001")
bob = bob_bank.get_account("ACT-B-001")

print(f"Alice (BANK_A, ACT-A-001): ${alice['balance']:,.2f}")
print(f"Bob (BANK_B, ACT-B-001):   ${bob['balance']:,.2f}")

alice_bank.close()
bob_bank.close()
EOF

echo ""
echo "Step 2: Alice deposits $5,000 in BANK_A"
echo "-----------------------------------------"
python3 - <<'EOF'
from python.bridge import COBOLBridge

bridge = COBOLBridge(node="BANK_A")
result = bridge.process_transaction("ACT-A-001", "D", 5000.00, "Salary deposit")
print(f"Transaction: {result['tx_id']}")
print(f"Status:      {result['status']} (success)")
print(f"New balance: ${result['new_balance']:,.2f}")
bridge.close()
EOF

echo ""
echo "Step 3: Bob withdraws $10,000 from BANK_B"
echo "------------------------------------------"
python3 - <<'EOF'
from python.bridge import COBOLBridge

bridge = COBOLBridge(node="BANK_B")
result = bridge.process_transaction("ACT-B-001", "W", 10000.00, "Payroll distribution")
print(f"Transaction: {result['tx_id']}")
print(f"Status:      {result['status']} (success)")
print(f"New balance: ${result['new_balance']:,.2f}")
bridge.close()
EOF

echo ""
echo "Step 4: Verify integrity chains are valid"
echo "------------------------------------------"
python3 - <<'EOF'
from python.bridge import COBOLBridge

for node in ["BANK_A", "BANK_B"]:
    bridge = COBOLBridge(node=node)
    result = bridge.chain.verify_chain()
    print(f"{node}: {result['entries_checked']} entries, {result['time_ms']:.1f}ms, valid={result['valid']}")
    bridge.close()
EOF

echo ""
echo "Step 5: Simulate tampering - corrupt BANK_A chain"
echo "--------------------------------------------------"
python3 - <<'EOF'
import sqlite3

# Tamper with BANK_A chain entry
db_path = "banks/bank_a/bank_a.db"
db = sqlite3.connect(db_path)
db.execute("UPDATE chain_entries SET prev_hash = 'TAMPERED' WHERE chain_index = 0")
db.commit()
db.close()

print("Corrupted: BANK_A chain entry 0 prev_hash set to 'TAMPERED'")
EOF

echo ""
echo "Step 6: Verify detection of tampering"
echo "--------------------------------------"
python3 - <<'EOF'
from python.bridge import COBOLBridge

bridge = COBOLBridge(node="BANK_A")
result = bridge.chain.verify_chain()

if not result['valid']:
    print(f"✓ TAMPER DETECTED!")
    print(f"  First break at entry {result['first_break']} ({result['break_type']})")
    print(f"  Details: {result['details']}")
    print(f"  Detection time: {result['time_ms']:.1f}ms")
else:
    print("✗ ERROR: Chain should have been detected as invalid!")

bridge.close()
EOF

echo ""
echo "Demo complete!"
echo "================================================================"
