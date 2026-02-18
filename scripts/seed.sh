#!/bin/bash
#================================================================*
# seed.sh — Populate all 6 nodes with seeded account data
# Phase 1: Initializes ACCOUNTS.DAT and SQLite for all banks
# Usage: ./scripts/seed.sh
#================================================================*

set -e

echo "Seeding Phase 1: Building COBOL and initializing all nodes..."

# Step 1: Try to compile COBOL (graceful skip if cobc unavailable)
echo ""
echo "Step 1: Build COBOL (if available)..."
./scripts/build.sh

# Step 2: Create Python venv if needed
if [ ! -d "python/venv" ]; then
    echo ""
    echo "Step 2: Setting up Python environment..."
    python3 -m venv python/venv
    source python/venv/bin/activate
    pip install --quiet -r python/requirements.txt
else
    source python/venv/bin/activate
fi

# Step 3: Generate fixed-width ACCOUNTS.DAT for each node
echo ""
echo "Step 3: Generating fixed-width ACCOUNTS.DAT for all nodes..."

python3 - <<'EOF'
import os
from pathlib import Path
from struct import pack

def write_fixed_width_record(f, acct_id, name, acct_type, balance, status, open_date, last_activity):
    """Write a 70-byte ACCTREC record (fixed-width, LINE SEQUENTIAL)."""
    # ACCTREC layout: 70 bytes
    #   0-9:   ACCT-ID (PIC X(10))
    #  10-39:  ACCT-NAME (PIC X(30))
    #  40:     ACCT-TYPE (PIC X(1))
    #  41-52:  ACCT-BALANCE (PIC S9(10)V99 — 12 bytes, stored as ASCII digits)
    #  53:     ACCT-STATUS (PIC X(1))
    #  54-61:  ACCT-OPEN-DATE (PIC 9(8))
    #  62-69:  ACCT-LAST-ACTIVITY (PIC 9(8))

    # Format balance: PIC S9(10)V99 = 12 ASCII digits (no literal decimal, implied decimal position)
    # E.g., 1234.56 → "000001234567" (10 digits + 2 fractional)
    balance_int = int(abs(balance) * 100)  # Convert to cents
    balance_str = f"{balance_int:012d}"    # 12-digit ASCII string
    if balance < 0:
        balance_str = "-" + balance_str[1:]  # Add minus sign
    balance_bytes = balance_str.encode('ascii')[:12]

    record = (
        acct_id.ljust(10)[:10].encode('ascii') +           # 10 bytes
        name.ljust(30)[:30].encode('ascii') +               # 30 bytes
        acct_type.encode('ascii')[0:1] +                   # 1 byte
        balance_bytes +                                     # 12 bytes
        status.encode('ascii')[0:1] +                       # 1 byte
        str(open_date).ljust(8)[:8].encode('ascii') +       # 8 bytes
        str(last_activity).ljust(8)[:8].encode('ascii')     # 8 bytes
    )

    # Verify 70 bytes
    assert len(record) == 70, f"Record length {len(record)} != 70: {record!r}"
    f.write(record + b'\n')  # LINE SEQUENTIAL = text file with newlines

# Bank data: list of (node, [(acct_id, name, type, balance, status), ...])
bank_data = {
    "BANK_A": [
        ("ACT-A-001", "Maria Santos", "C", 5000.00, "A"),
        ("ACT-A-002", "James Wilson", "S", 12500.00, "A"),
        ("ACT-A-003", "Chen Liu", "C", 850.50, "A"),
        ("ACT-A-004", "Patricia Kumar", "S", 25000.00, "A"),
        ("ACT-A-005", "Robert Brown", "C", 3200.00, "A"),
        ("ACT-A-006", "Sophie Martin", "S", 75000.00, "A"),
        ("ACT-A-007", "David Garcia", "C", 1500.00, "A"),
        ("ACT-A-008", "Emma Johnson", "S", 45000.00, "A"),
    ],
    "BANK_B": [
        ("ACT-B-001", "Acme Manufacturing", "C", 350000.00, "A"),
        ("ACT-B-002", "Global Logistics", "C", 125000.00, "A"),
        ("ACT-B-003", "TechStart Ventures", "S", 500000.00, "A"),
        ("ACT-B-004", "Peninsula Holdings", "C", 75000.00, "A"),
        ("ACT-B-005", "NorthSide Insurance", "C", 250000.00, "A"),
        ("ACT-B-006", "Pacific Shipping", "C", 180000.00, "A"),
        ("ACT-B-007", "Greenfield Properties", "S", 1000000.00, "A"),
    ],
    "BANK_C": [
        ("ACT-C-001", "Lisa Wong", "S", 150000.00, "A"),
        ("ACT-C-002", "Michael O'Brien", "C", 45000.00, "A"),
        ("ACT-C-003", "Alicia Patel", "S", 200000.00, "A"),
        ("ACT-C-004", "Nina Kumar", "S", 320000.00, "A"),
        ("ACT-C-005", "Thomas Anderson", "C", 25000.00, "A"),
        ("ACT-C-006", "Rachel Green", "S", 550000.00, "A"),
        ("ACT-C-007", "Christopher Lee", "C", 80000.00, "A"),
        ("ACT-C-008", "Sophia Rivera", "S", 400000.00, "A"),
    ],
    "BANK_D": [
        ("ACT-D-001", "Westchester Trust Corp", "C", 5000000.00, "A"),
        ("ACT-D-002", "Birch Estate Partners", "S", 12000000.00, "A"),
        ("ACT-D-003", "Alpine Investment Club", "C", 750000.00, "A"),
        ("ACT-D-004", "Laurel Foundation", "S", 2500000.00, "A"),
        ("ACT-D-005", "Strategic Capital Fund", "C", 8000000.00, "A"),
        ("ACT-D-006", "Legacy Trust Settlement", "S", 15000000.00, "A"),
    ],
    "BANK_E": [
        ("ACT-E-001", "Metro Community Fund", "C", 1200000.00, "A"),
        ("ACT-E-002", "Angela Rodriguez", "C", 45000.00, "A"),
        ("ACT-E-003", "SBA Loan Pool", "S", 2500000.00, "A"),
        ("ACT-E-004", "Marcus Thompson", "S", 125000.00, "A"),
        ("ACT-E-005", "Metro Food Bank", "C", 500000.00, "A"),
        ("ACT-E-006", "Urban Development Proj", "S", 3000000.00, "A"),
        ("ACT-E-007", "Women Entrepreneurs Fund", "C", 750000.00, "A"),
        ("ACT-E-008", "Youth Skills Initiative", "S", 850000.00, "A"),
    ],
    "CLEARING": [
        ("NST-BANK-A", "Nostro Account - BANK_A", "C", 0.00, "A"),
        ("NST-BANK-B", "Nostro Account - BANK_B", "C", 0.00, "A"),
        ("NST-BANK-C", "Nostro Account - BANK_C", "C", 0.00, "A"),
        ("NST-BANK-D", "Nostro Account - BANK_D", "C", 0.00, "A"),
        ("NST-BANK-E", "Nostro Account - BANK_E", "C", 0.00, "A"),
    ],
}

# Create all node directories and ACCOUNTS.DAT files
for node, accounts in bank_data.items():
    node_dir = Path(f"banks/{node.lower().replace('_', '-')}")
    node_dir.mkdir(parents=True, exist_ok=True)

    accounts_file = node_dir / "ACCOUNTS.DAT"
    with open(accounts_file, 'wb') as f:
        for acct_id, name, acct_type, balance, status in accounts:
            write_fixed_width_record(f, acct_id, name, acct_type, balance, status, 20260217, 20260217)

    print(f"  ✓ {node}: {len(accounts)} accounts → {accounts_file}")

print(f"✓ All {sum(len(a) for a in bank_data.values())} accounts written")
EOF

# Step 4: Initialize SQLite databases and sync accounts
echo ""
echo "Step 4: Initializing SQLite and syncing accounts..."

python3 - <<'EOF'
from pathlib import Path
from python.bridge import COBOLBridge

nodes = ["BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E", "CLEARING"]

for node in nodes:
    bridge = COBOLBridge(node=node, data_dir="banks", bin_dir="cobol/bin")
    bridge.seed_demo_data()
    account_count = len(bridge.list_accounts())
    bridge.close()
    print(f"  ✓ {node}: {account_count} accounts synced to SQLite")

print(f"✓ All {len(nodes)} nodes initialized")
EOF

echo ""
echo "✓ Phase 1 seeding complete!"
echo ""
echo "Verification: python3 -c \\"
echo "  from python.bridge import COBOLBridge; "
echo "  for n in ['BANK_A','BANK_B','BANK_C','BANK_D','BANK_E','CLEARING']: "
echo "    b = COBOLBridge(node=n); print(f'{n}: {len(b.list_accounts())} accts'); b.close()\""
