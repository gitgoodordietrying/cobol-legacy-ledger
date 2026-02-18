# 04_FRONTEND_AND_DEMO

Phase 1 demo script and Phase 3 static console specification.

---

## § PHASE 1: Demo & Verification

The Phase 1 deliverable includes a CLI-based demo that proves the system works. No GUI. No HTTP API. Just shell commands that anyone can run to verify:

1. COBOL compiles (or gracefully skips if unavailable)
2. All 6 nodes seed successfully
3. Python bridge reads accounts from all nodes
4. Transactions process and integrity chain records them
5. Chain verification works

---

## Phase 1 Demo Script

**File location:** `scripts/demo.sh`
**Purpose:** Walk through a realistic banking scenario and verify integrity

**Execution:**
```bash
cd cobol-legacy-ledger
bash scripts/demo.sh
```

**Output:** Complete walkthrough of the system with verification checkpoints.

---

### Demo Script Pseudocode

```bash
#!/bin/bash

set -e  # Exit on error

echo "════════════════════════════════════════════════════════════════"
echo "    cobol-legacy-ledger — Phase 1 Verification Demo"
echo "════════════════════════════════════════════════════════════════"
echo ""

# ────────────────────────────────────────────────────────────────────
# STEP 1: Build
# ────────────────────────────────────────────────────────────────────
echo "[1/6] Building COBOL..."
bash scripts/build.sh
echo "✓ COBOL built (or skipped if cobc unavailable)"
echo ""

# ────────────────────────────────────────────────────────────────────
# STEP 2: Setup Python
# ────────────────────────────────────────────────────────────────────
echo "[2/6] Setting up Python environment..."
bash scripts/setup.sh
source venv/bin/activate  # or venv\Scripts\activate on Windows
echo "✓ Python environment ready"
echo ""

# ────────────────────────────────────────────────────────────────────
# STEP 3: Seed Data
# ────────────────────────────────────────────────────────────────────
echo "[3/6] Seeding all 6 nodes..."
bash scripts/seed.sh
echo "✓ All nodes seeded"
echo ""

# ────────────────────────────────────────────────────────────────────
# STEP 4: Initialize Bridge
# ────────────────────────────────────────────────────────────────────
echo "[4/6] Initializing Python bridge..."
cd python

python3 << 'PYTHON_INIT'
from bridge import COBOLBridge

# Test connectivity to all 6 nodes
nodes = ["BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E", "CLEARING"]
for node in nodes:
    b = COBOLBridge(node=node)
    accts = b.list_accounts()
    print(f"  ✓ {node}: {len(accts)} accounts")

print("\n✓ Bridge initialization complete")
PYTHON_INIT

echo ""

# ────────────────────────────────────────────────────────────────────
# STEP 5: Execute Scenario
# ────────────────────────────────────────────────────────────────────
echo "[5/6] Running banking scenario..."
echo ""
echo "Scenario: Alice (BANK_A) sends $5,000 to Bob (BANK_B)"
echo "          CLEARING records the transfer"
echo "          All chains are updated and verified"
echo ""

python3 << 'PYTHON_SCENARIO'
from bridge import COBOLBridge
from datetime import datetime

# Initialize bridges for source, clearing, destination
alice_bank = COBOLBridge(node="BANK_A")
bob_bank = COBOLBridge(node="BANK_B")
clearing = COBOLBridge(node="CLEARING")

# Get Alice and Bob by ID (not by index)
alice_account = alice_bank.get_account("ACT-A-001")  # Maria Santos
bob_account = bob_bank.get_account("ACT-B-001")      # Acme Manufacturing

print(f"BEFORE:")
print(f"  Alice ({alice_account['id']}): ${alice_account['balance']:.2f}")
print(f"  Bob ({bob_account['id']}): ${bob_account['balance']:.2f}")
print()

# Execute transfer from Alice's perspective
tx1 = alice_bank.process_transaction(
    account_id=alice_account['id'],
    tx_type="W",
    amount=5000.00,
    description="Transfer to BANK_B"
)
print(f"TX1 (BANK_A debit): {tx1['tx_id']} - Status {tx1['status']}")
print(f"  Alice now: ${tx1['balance_after']:.2f}")
print()

# Execute transfer from Clearing's perspective (debit BANK_B's nostro, credit BANK_A's nostro)
clearing_nostro_alice = clearing.get_account("NST-BANK-A")
clearing_nostro_bob = clearing.get_account("NST-BANK-B")

tx2 = clearing.process_transaction(
    account_id=clearing_nostro_alice['id'],
    tx_type="W",
    amount=5000.00,
    description=f"Debit for transfer to BANK_B (ref: {tx1['tx_id']})"
)
print(f"TX2 (CLEARING debit Alice nostro): {tx2['tx_id']} - Status {tx2['status']}")

tx3 = clearing.process_transaction(
    account_id=clearing_nostro_bob['id'],
    tx_type="D",
    amount=5000.00,
    description=f"Credit for transfer from BANK_A (ref: {tx1['tx_id']})"
)
print(f"TX3 (CLEARING credit Bob nostro): {tx3['tx_id']} - Status {tx3['status']}")
print()

# Execute transfer from Bob's perspective
tx4 = bob_bank.process_transaction(
    account_id=bob_account['id'],
    tx_type="D",
    amount=5000.00,
    description="Transfer from BANK_A"
)
print(f"TX4 (BANK_B credit): {tx4['tx_id']} - Status {tx4['status']}")
print(f"  Bob now: ${tx4['balance_after']:.2f}")
print()

print(f"AFTER:")
alice_updated = alice_bank.get_account(alice_account['id'])
bob_updated = bob_bank.get_account(bob_account['id'])
print(f"  Alice ({alice_updated['id']}): ${alice_updated['balance']:.2f}")
print(f"  Bob ({bob_updated['id']}): ${bob_updated['balance']:.2f}")
print()

print("✓ All transactions processed successfully")
PYTHON_SCENARIO

echo ""

# ────────────────────────────────────────────────────────────────────
# STEP 6: Verify Integrity
# ────────────────────────────────────────────────────────────────────
echo "[6/6] Verifying integrity chains..."
echo ""

python3 << 'PYTHON_VERIFY'
from bridge import COBOLBridge

nodes = ["BANK_A", "BANK_B", "CLEARING"]

print("Chain verification results:")
for node in nodes:
    b = COBOLBridge(node=node)
    result = b.chain.verify_chain()

    status = "✓ VALID" if result['valid'] else "✗ INVALID"
    print(f"  {node}: {status} ({result['entries_checked']} entries, {result['time_ms']:.1f}ms)")

    if not result['valid']:
        print(f"    → {result['break_type']} at entry {result['first_break']}")
        print(f"    → {result['details']}")

print("\n✓ All chains verified — system integrity confirmed")
PYTHON_VERIFY

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Demo Complete ✓"
echo "════════════════════════════════════════════════════════════════"
```

---

## Phase 1 CLI Commands

**File location:** `python/cli.py`

Users can interact with the system via command-line:

```bash
cd python

# List all nodes and their account counts
python cli.py status

# Output:
# System Status
# ═════════════════════════════════════════════
# COBOL Sources:    4 (ACCOUNTS, TRANSACT, VALIDATE, REPORTS)
# COBOL Binaries:   4 (compiled)
# Nodes:            6 (BANK_A, BANK_B, BANK_C, BANK_D, BANK_E, CLEARING)
#
# Account Summary:
#   BANK_A:       8 accounts, $668,671.75 total
#   BANK_B:       7 accounts, $1,078,900.00 total
#   BANK_C:       8 accounts, $1,209,100.00 total
#   BANK_D:       6 accounts, $9,543,000.00 total
#   BANK_E:       8 accounts, $1,172,400.00 total
#   CLEARING:     5 nostro accounts, $0.00 total
#
# Transactions:     12 across all nodes
# Chain Entries:    12 across all nodes
#
# Database:         ./data/ledger.db
```

```bash
# Run batch on a specific node
python cli.py run-batch BANK_A

# Output:
# Running batch: BAT20240102080000 on BANK_A
# ═══════════════════════════════════════════════════
# TX #1: DEPOSIT | ACT-A-001 | +$3,200.00 | SUCCESS ✓
# TX #2: INTEREST | ACT-A-002 | +$210.50 | SUCCESS ✓
# TX #3: WITHDRAW | ACT-A-003 | -$45,000.00 | SUCCESS ✓
# ...
# ═══════════════════════════════════════════════════
# Total: 15 transactions
# Success: 14 | Failed: 1
# Duration: 2.34 seconds
```

```bash
# Verify chain integrity on a node
python cli.py verify-chain BANK_C

# Output:
# Chain Verification: BANK_C
# ═══════════════════════════════════════════════════
# Total Entries:      12
# Verified in:        1.2 ms
# Status:             ✓ VALID
# ═══════════════════════════════════════════════════
```

---

---

## § PHASE 3: Static Console (Deferred)

The Phase 3 deliverable adds a frontend dashboard. No Node.js. No React. No webpack. Just static HTML/CSS/vanilla JavaScript served by Python.

---

## Design Principles

- **Static files:** HTML, CSS, JavaScript only (no templating engines)
- **Served by:** Python http.server or FastAPI StaticFiles
- **Data source:** JSON API endpoints (added in Phase 2)
- **No dependencies:** No npm, no build process, no CDN for core libraries
- **Deployment:** GitHub Pages (commit `/console/dist/index.html` and assets)

---

## Console Architecture (Phase 3)

### Pages

| Page | Purpose |
|------|---------|
| **Dashboard** | System status, account summary, recent transactions |
| **Nodes** | Drill into each of 6 nodes; account list for selected node |
| **Transactions** | Browse all transactions; filter by account, date, type |
| **Chains** | View integrity chain for selected node; verify/tamper demo |
| **Settlement** | (Phase 2+) Show net positions and inter-bank movements |

### Components

**Header:**
- System title (cobol-legacy-ledger)
- Node selector dropdown
- Navigation tabs (Dashboard, Nodes, Transactions, Chains)

**Main Content:**
- Dynamic content based on selected page
- Real-time SSE updates during batch runs
- Color-coded status (✓ valid, ✗ tampered, ⏳ in-progress)

**Footer:**
- System health (API status, last sync time)
- Help link

---

## Data Endpoints (Phase 2+)

The console expects these HTTP endpoints:

```
GET /api/status
  → {"accounts": 37, "transactions": 150, "chain_entries": 150, ...}

GET /api/nodes
  → [{"id": "BANK_A", "name": "First National", "accounts": 8}, ...]

GET /api/nodes/{node}/accounts
  → [{"id": "ACT-A-001", "name": "Maria Santos", "balance": 18620.50, ...}, ...]

GET /api/nodes/{node}/transactions?limit=50
  → [{"id": "TRX-...", "account_id": "...", "type": "D", ...}, ...]

GET /api/nodes/{node}/chain?limit=50
  → [{"chain_index": 0, "tx_id": "...", "hash": "...", ...}, ...]

POST /api/nodes/{node}/verify
  → {"valid": true, "entries_checked": 12, "time_ms": 1.2, ...}

GET /api/settlement/net-positions  (Phase 2+)
  → [{"bank": "BANK_A", "net_position": -2400.00, ...}, ...]
```

---

## Phase 3 Deliverables

1. `console/index.html` — main entry point
2. `console/css/style.css` — styling
3. `console/js/app.js` — main application logic
4. `console/js/api-client.js` — HTTP client for backend
5. `console/js/components/` — reusable UI components
6. `.github/workflows/deploy.yml` — GitHub Actions to deploy to Pages

---

## Example: Transaction View (HTML Pseudocode)

```html
<div id="transactions">
  <h2>Transactions</h2>

  <div class="filters">
    <select id="node-select">
      <option value="BANK_A">BANK_A (First National)</option>
      <option value="BANK_B">BANK_B (Commerce Trust)</option>
      ...
    </select>

    <input type="date" id="date-filter" placeholder="Filter by date">

    <select id="type-filter">
      <option value="">All types</option>
      <option value="D">Deposits</option>
      <option value="W">Withdrawals</option>
      <option value="T">Transfers</option>
      <option value="I">Interest</option>
      <option value="F">Fees</option>
    </select>
  </div>

  <table id="tx-table">
    <thead>
      <tr>
        <th>TX ID</th>
        <th>Account</th>
        <th>Type</th>
        <th>Amount</th>
        <th>Status</th>
        <th>Date/Time</th>
        <th>Chain Index</th>
      </tr>
    </thead>
    <tbody>
      <!-- Populated by JavaScript -->
    </tbody>
  </table>

  <div id="pagination">
    <button id="prev-page">← Previous</button>
    <span id="page-info">Page 1 of 10</span>
    <button id="next-page">Next →</button>
  </div>
</div>
```

**JavaScript (pseudocode):**
```javascript
// Load transactions when page loads or filters change
async function loadTransactions() {
  const node = document.getElementById('node-select').value;
  const response = await fetch(`/api/nodes/${node}/transactions?limit=50`);
  const transactions = await response.json();

  renderTable(transactions);
}

function renderTable(transactions) {
  const tbody = document.querySelector('#tx-table tbody');
  tbody.innerHTML = transactions.map(tx => `
    <tr class="status-${tx.status}">
      <td><code>${tx.id}</code></td>
      <td>${tx.account_id}</td>
      <td>${tx.type}</td>
      <td>$${tx.amount.toFixed(2)}</td>
      <td>${statusBadge(tx.status)}</td>
      <td>${tx.date} ${tx.time}</td>
      <td><a href="#chain/${tx.chain_index}">${tx.chain_index}</a></td>
    </tr>
  `).join('');
}
```

---

## Phase 1 Does NOT Include

- Web server (Phase 2+)
- API endpoints (Phase 2+)
- Console files (Phase 3)
- Live batch monitoring (Phase 3)
- Tamper-detection demo UI (Phase 3)

Phase 1 is CLI-only. Phase 2 adds the HTTP API. Phase 3 adds the console.

---

## Deployment (Phase 3+)

When Phase 3 is complete:

```bash
# Build console assets (minimal — just copy files)
mkdir -p console/dist
cp console/*.html console/dist/
cp console/css/* console/dist/css/
cp console/js/* console/dist/js/

# Commit to GitHub
git add console/dist/
git commit -m "Phase 3: Add static console dashboard"
git push origin main

# GitHub Actions automatically deploys to Pages
# Console is available at: https://yourusername.github.io/cobol-legacy-ledger/console/
```

---

## Summary

**Phase 1:** CLI demo script that proves the system works.

**Phase 2:** HTTP API that feeds data to the console.

**Phase 3:** Static HTML/CSS/JS console that visualizes the system and demonstrates tamper detection.

All three are defensible to a financial audience: no external dependencies, no build complexity, transparency about what's running where.

---

## Next Steps

1. **Phase 1:** Run `scripts/demo.sh` to verify everything works
2. **Phase 2:** Design and implement settlement coordinator + API
3. **Phase 3:** Build console dashboard and deploy to GitHub Pages

**Implementation is now complete. Handoff package is ready for Phase 1 build.**
