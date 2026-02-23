# HANDOFF B — Settlement Coordinator

**Project:** LegacyLedger: Closing the Multi-Bank Gap  
**Author:** Albert (AKD Solutions / Imperium)  
**Date:** February 19, 2026  
**Purpose:** Implement the Python orchestration layer that turns 6 isolated COBOL nodes into a settlement network  
**Prerequisite:** HANDOFF_A gate PASSED (all 6 nodes verified operational)  
**Sequence:** HANDOFF_A (done) → **This document** → HANDOFF_C (Cross-Node Integrity)

**READ THIS ENTIRE DOCUMENT BEFORE WRITING ANY CODE.**

---

## 0. THE ARCHITECTURAL INSIGHT

The COBOL programs are single-node by design. Each program operates on whatever .DAT files exist in its working directory. No COBOL program should ever reach into another bank's directory — that's not how settlement works in reality either.

In real banking, an intermediary **orchestrates** the flow: debit source → record in clearing → credit destination. That orchestrator is Python. That's the entire thesis: "COBOL handles banking. Python provides the modern infrastructure COBOL can't."

**What exists:** 6 independent COBOL banking nodes, each fully functional standalone.  
**What's missing:** The ~200-line Python coordinator that calls COBOL across nodes to execute inter-bank transfers.  
**What does NOT change:** Zero COBOL modifications. The existing programs already support every operation we need.

---

## 1. THE INTER-BANK TRANSFER FLOW

This is the core algorithm. Everything in this document serves this flow.

```
SETTLEMENT COORDINATOR receives: "Alice@BANK_A → Bob@BANK_B, $500.00"

STEP 1 — SOURCE DEBIT:
    Call: banks/BANK_A/  →  TRANSACT WITHDRAW ACT-A-001 500.00 "XFER→BANK_B:ACT-B-003"
    Result: BANK_A/ACCOUNTS.DAT balance decreased
    Result: BANK_A/TRANSACT.DAT has new WITHDRAW record
    Chain:  BANK_A integrity chain records the debit
    On FAIL: STOP. Return error. Nothing else touched.

STEP 2 — CLEARING HOUSE SETTLEMENT (two-sided):
    Call: banks/CLEARING/  →  TRANSACT DEPOSIT NST-BANK-A 500.00 "SETTLE:A→B:TRX-A-000042"
    Call: banks/CLEARING/  →  TRANSACT WITHDRAW NST-BANK-B 500.00 "SETTLE:A→B:TRX-A-000042"
    Result: CLEARING/ACCOUNTS.DAT updated (A's nostro +500, B's nostro -500)
    Result: CLEARING/TRANSACT.DAT has TWO records (deposit + withdrawal)
    Chain:  CLEARING integrity chain records both legs
    On FAIL: CRITICAL — partial settlement. Log error. Flag for manual review.

STEP 3 — DESTINATION CREDIT:
    Call: banks/BANK_B/  →  TRANSACT DEPOSIT ACT-B-003 500.00 "XFER←BANK_A:ACT-A-001"
    Result: BANK_B/ACCOUNTS.DAT balance increased
    Result: BANK_B/TRANSACT.DAT has new DEPOSIT record
    Chain:  BANK_B integrity chain records the credit
    On FAIL: CRITICAL — money debited but not credited. Log error. Flag for manual review.

RESULT: Three independent .DAT file updates. Three chain entries. One coordinator.
```

**Key design decisions:**

1. **Fail-forward with flags, not rollbacks.** Real COBOL batch systems don't have transactions in the RDBMS sense. If Step 1 succeeds but Step 3 fails, we log it and flag it — just like real settlement exception handling. We do NOT attempt to reverse Step 1.

2. **Description fields carry cross-references.** Every TRANSACT call includes the counterparty info in the description string. This creates a paper trail that the cross-node verifier (HANDOFF_C) can follow.

3. **CLEARING always has two entries per transfer.** One DEPOSIT (receiving bank's nostro increases — "they owe us") and one WITHDRAW (sending bank's nostro decreases — "we owe them"). This double-entry bookkeeping is the authoritative record.

4. **Transaction ID cross-reference format:** `XFER→{dest_bank}:{dest_acct}` for debits, `XFER←{src_bank}:{src_acct}` for credits, `SETTLE:{src}→{dest}:{trx_id}` for clearing legs. These strings MUST fit within whatever description field length TRANSACT.cob supports — verify this.

---

## 2. FILE: python/settlement.py (~200 lines)

**New file.** This is the settlement coordinator.

### 2.1 Class: SettlementCoordinator

```python
"""
settlement.py — Inter-bank transfer orchestration via COBOL subprocess calls.

The settlement coordinator turns 6 independent COBOL banking nodes into a
network by orchestrating multi-step transfers through the CLEARING node.
No COBOL programs are modified. Python calls the existing binaries at each
node in sequence, creating a settlement flow with three independent records.

Dependencies: bridge.py (for COBOL subprocess execution and output parsing)
"""
```

**Constructor:**
```python
def __init__(self, project_root: str):
    """
    Initialize with path to project root (parent of banks/ directory).
    Creates a COBOLBridge instance for each of the 6 nodes.
    """
    self.project_root = project_root
    self.nodes = {}
    for node in ['BANK_A', 'BANK_B', 'BANK_C', 'BANK_D', 'BANK_E', 'CLEARING']:
        self.nodes[node] = COBOLBridge(node=node, project_root=project_root)
```

**Core method:**
```python
def execute_transfer(
    self,
    source_bank: str,       # "BANK_A"
    source_account: str,    # "ACT-A-001"
    dest_bank: str,         # "BANK_B"  
    dest_account: str,      # "ACT-B-003"
    amount: float,          # 500.00
    description: str = ""   # Optional human description
) -> SettlementResult:
    """
    Execute a three-step inter-bank transfer:
      1. Debit source account at source bank
      2. Record settlement at CLEARING (two-sided)
      3. Credit destination account at destination bank
    
    Returns SettlementResult with status, all transaction IDs, and any errors.
    On partial failure, returns partial results with error flags — does NOT
    attempt rollback (matches real settlement exception handling).
    """
```

**Return type:**
```python
@dataclass
class SettlementResult:
    status: str              # "COMPLETED" | "PARTIAL_FAILURE" | "FAILED"
    source_trx_id: str       # Transaction ID from Step 1 (or "" if failed)
    clearing_deposit_id: str  # Transaction ID from Step 2a (or "")
    clearing_withdraw_id: str # Transaction ID from Step 2b (or "")
    dest_trx_id: str         # Transaction ID from Step 3 (or "")
    amount: float
    source_bank: str
    dest_bank: str
    error: str               # Empty string on success, error message on failure
    steps_completed: int     # 0, 1, 2, or 3
    settlement_ref: str      # Unique settlement reference tying all legs together
```

### 2.2 Nostro Account Mapping

The coordinator needs to know which CLEARING account corresponds to which bank:

```python
NOSTRO_MAP = {
    'BANK_A': 'NST-BANK-A',
    'BANK_B': 'NST-BANK-B',
    'BANK_C': 'NST-BANK-C',
    'BANK_D': 'NST-BANK-D',
    'BANK_E': 'NST-BANK-E',
}
```

This mapping is static and defined in ONE place. If the seed data uses different nostro IDs, update this map — do not change the COBOL or the seed data.

### 2.3 Settlement Reference Generation

Each settlement gets a unique reference that ties all 3-4 transaction legs together:

```python
def _generate_settlement_ref(self) -> str:
    """Generate unique settlement reference: STL-YYYYMMDD-NNNNNN"""
    # Use date + sequence counter or timestamp
    # This ref appears in all description fields for cross-referencing
```

### 2.4 Batch Settlement

For the demo, we need to process multiple inter-bank transfers in sequence:

```python
def execute_batch_settlement(
    self, 
    transfers: list[dict]
) -> list[SettlementResult]:
    """
    Process a list of inter-bank transfers sequentially.
    Each transfer is: {source_bank, source_account, dest_bank, dest_account, amount, description}
    Returns list of SettlementResult in same order.
    
    Does NOT stop on individual transfer failure — processes all and reports.
    This matches real batch settlement behavior.
    """
```

### 2.5 Settlement Summary

After a batch, generate a summary showing net positions:

```python
def get_settlement_summary(self, results: list[SettlementResult]) -> dict:
    """
    Compute net settlement positions across all banks.
    Returns: {
        'total_transfers': int,
        'completed': int,
        'failed': int,
        'net_positions': {
            'BANK_A': -1500.00,  # net sender
            'BANK_B': +2000.00,  # net receiver
            ...
        },
        'clearing_balance_check': True  # sum of all nostro changes == 0
    }
    """
```

**The clearing balance check is a demo moment:** After all settlement, the sum of all nostro account changes MUST be zero. This is double-entry bookkeeping. If it's not zero, something went wrong. Display this prominently.

---

## 3. BRIDGE.PY MODIFICATIONS

The existing `bridge.py` needs minor additions to support the settlement coordinator. **Do not rewrite bridge.py.** Add only what's needed.

### 3.1 Node-Aware Construction

If the bridge currently assumes a single node, make it configurable:

```python
class COBOLBridge:
    def __init__(self, node: str = 'BANK_A', project_root: str = None):
        self.node = node
        self.node_dir = f"banks/{node}"
        # ... existing init
```

### 3.2 Transaction Description Handling

Verify that the bridge correctly passes description strings to TRANSACT.cob. The description may contain colons and arrows (`XFER→BANK_B:ACT-B-003`). Ensure these don't break:

- Shell escaping in subprocess calls
- COBOL's ACCEPT or command-line argument parsing
- The pipe-delimited output parser

**Test this explicitly:**
```bash
./scripts/cobol-run.sh bash -c "cd banks/BANK_A && /app/cobol/bin/TRANSACT DEPOSIT ACT-A-001 100.00 'XFER→BANK_B:ACT-B-003'"
```

If special characters cause issues, simplify the description format:
- Fallback: `XFER-TO-BANK_B-ACT-B-003` (ASCII only, hyphens instead of arrows/colons)

### 3.3 Transaction ID Extraction

The bridge must extract the transaction ID from TRANSACT.cob's output so the coordinator can include it in cross-references. Verify the output includes the transaction ID and the parser captures it.

---

## 4. CLI ADDITIONS: python/cli.py

Add settlement commands to the existing CLI. **Do not restructure the CLI.** Add subcommands.

### 4.1 Single Transfer

```
legacyledger transfer --from BANK_A:ACT-A-001 --to BANK_B:ACT-B-003 --amount 500.00 --desc "Wire transfer"
```

**Output format (for demo):**
```
╔══════════════════════════════════════════════════════════════╗
║  INTER-BANK SETTLEMENT                                      ║
║  REF: STL-20260219-000001                                    ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  STEP 1: DEBIT SOURCE                                        ║
║    BANK_A / ACT-A-001  -$500.00                              ║
║    TRX: TRX-A-000042   STATUS: OK                            ║
║                                                              ║
║  STEP 2: CLEARING SETTLEMENT                                 ║
║    CLEARING / NST-BANK-A  +$500.00  (deposit)                ║
║    CLEARING / NST-BANK-B  -$500.00  (withdrawal)             ║
║    TRX: TRX-C-000015, TRX-C-000016   STATUS: OK             ║
║                                                              ║
║  STEP 3: CREDIT DESTINATION                                  ║
║    BANK_B / ACT-B-003  +$500.00                              ║
║    TRX: TRX-B-000008   STATUS: OK                            ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║  RESULT: COMPLETED   CHAIN ENTRIES: 4   TIME: 1.2s          ║
╚══════════════════════════════════════════════════════════════╝
```

### 4.2 Batch Settlement (Demo Mode)

```
legacyledger settle --demo
```

Runs a pre-defined set of 8-12 inter-bank transfers designed to exercise:
- All 5 banks as both sender and receiver
- At least one transfer per bank pair direction
- One large transfer near CTR threshold ($9,500+)
- One transfer to a frozen account (should fail at Step 1)
- One transfer with insufficient funds (should fail at Step 1)

**Demo batch (hardcoded in settlement.py):**

```python
DEMO_SETTLEMENT_BATCH = [
    # Normal transfers across different bank pairs
    {"source_bank": "BANK_A", "source_account": "ACT-A-001", "dest_bank": "BANK_B", "dest_account": "ACT-B-003", "amount": 500.00, "description": "Wire transfer"},
    {"source_bank": "BANK_B", "source_account": "ACT-B-001", "dest_bank": "BANK_C", "dest_account": "ACT-C-002", "amount": 1200.00, "description": "Invoice payment"},
    {"source_bank": "BANK_C", "source_account": "ACT-C-001", "dest_bank": "BANK_D", "dest_account": "ACT-D-001", "amount": 3500.00, "description": "Quarterly dividend"},
    {"source_bank": "BANK_D", "source_account": "ACT-D-002", "dest_bank": "BANK_E", "dest_account": "ACT-E-001", "amount": 750.00, "description": "Consulting fee"},
    {"source_bank": "BANK_E", "source_account": "ACT-E-001", "dest_bank": "BANK_A", "dest_account": "ACT-A-003", "amount": 2000.00, "description": "Loan repayment"},
    
    # Near-CTR threshold (compliance flag expected)
    {"source_bank": "BANK_A", "source_account": "ACT-A-002", "dest_bank": "BANK_C", "dest_account": "ACT-C-001", "amount": 9500.00, "description": "Large wire transfer"},
    
    # Should fail: insufficient funds (use an account with low balance)
    {"source_bank": "BANK_D", "source_account": "ACT-D-004", "dest_bank": "BANK_A", "dest_account": "ACT-A-001", "amount": 50000.00, "description": "Oversized transfer"},
    
    # Reverse direction to create circular flow
    {"source_bank": "BANK_B", "source_account": "ACT-B-002", "dest_bank": "BANK_A", "dest_account": "ACT-A-001", "amount": 800.00, "description": "Refund"},
]
```

**IMPORTANT:** The account IDs in this batch MUST match actual accounts in the seed data. Before finalizing this list, verify account IDs exist by running `ACCOUNTS LIST` for each node. Adjust IDs as needed.

### 4.3 Network Status

```
legacyledger network-status
```

Shows all 6 nodes, their account counts, and total balances:

```
╔══════════════════════════════════════════════════════════════╗
║  CLEARING NETWORK STATUS                                     ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  BANK_A    8 accounts   Total: $45,230.00   Chain: 24 entries║
║  BANK_B    8 accounts   Total: $38,100.00   Chain: 18 entries║
║  BANK_C    8 accounts   Total: $52,400.00   Chain: 21 entries║
║  BANK_D    8 accounts   Total: $29,800.00   Chain: 15 entries║
║  BANK_E    8 accounts   Total: $41,600.00   Chain: 19 entries║
║  ────────────────────────────────────────────────────────────║
║  CLEARING  5 accounts   Net:   $0.00        Chain: 42 entries║
║                                                              ║
║  NST-BANK-A: +$1,200.00                                     ║
║  NST-BANK-B: -$400.00                                       ║
║  NST-BANK-C: +$800.00                                       ║
║  NST-BANK-D: -$750.00                                       ║
║  NST-BANK-E: -$850.00                                       ║
║  ────────────────────────────────────────────────────────────║
║  NOSTRO NET: $0.00  ✓ BALANCED                               ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

**The $0.00 net is a demo moment.** After all settlement, the sum of all nostro positions must be zero. If it's not, something is wrong with the settlement logic.

---

## 5. INTEGRATION WITH EXISTING INTEGRITY CHAIN

Every COBOL subprocess call that goes through the bridge MUST be chained and signed, just like single-node transactions. The settlement coordinator should use the bridge's existing chain integration, not bypass it.

**Flow:**
```
settlement.py → bridge.deposit(node='BANK_A', ...) → subprocess(TRANSACT DEPOSIT) → parse output → chain_append + HMAC_sign → SQLite sync
```

After a complete inter-bank transfer, there should be:
- 1 chain entry in source bank's chain (debit)
- 2 chain entries in CLEARING's chain (deposit + withdrawal)
- 1 chain entry in destination bank's chain (credit)
- **Total: 4 chain entries per transfer**

The settlement reference (`STL-...`) should appear in the chain metadata so the cross-node verifier (HANDOFF_C) can correlate entries across chains.

---

## 6. IMPLEMENTATION SEQUENCE

### Step 1: Verify COBOL Description Handling (15 min)
Test that special characters in description fields don't break COBOL subprocess calls:
```bash
./scripts/cobol-run.sh bash -c "cd banks/BANK_A && /app/cobol/bin/TRANSACT DEPOSIT ACT-A-001 100.00 'XFER-TO-BANK_B-ACT-B-003'"
```
If this works, proceed. If not, choose a safe description format.

### Step 2: Write settlement.py (2 hours)
- SettlementCoordinator class
- execute_transfer() with 3-step flow
- execute_batch_settlement()
- get_settlement_summary()
- DEMO_SETTLEMENT_BATCH constant
- SettlementResult dataclass

### Step 3: Update bridge.py (30 min)
- Make node configurable in constructor
- Verify transaction ID extraction from TRANSACT output
- Verify chain integration works for non-BANK_A nodes

### Step 4: Add CLI commands (1 hour)
- `legacyledger transfer` — single inter-bank transfer
- `legacyledger settle --demo` — demo batch with formatted output
- `legacyledger network-status` — all-node summary

### Step 5: Test the demo flow (1 hour)
```bash
# Start clean: re-seed all nodes
./scripts/seed.sh

# Verify starting state
legacyledger network-status

# Run demo settlement batch
legacyledger settle --demo

# Verify ending state
legacyledger network-status

# Check clearing balance
# NST net should be $0.00
```

### Step 6: Document in DEV_LOG.md (15 min)
Record: what was implemented, the demo batch results, the net position check, any issues.

---

## 7. GATE CRITERIA

**PASS if ALL of the following are true:**

1. `legacyledger transfer --from BANK_A:ACT-A-001 --to BANK_B:ACT-B-003 --amount 500` completes with COMPLETED status
2. After the transfer, BANK_A's chain has a debit entry, CLEARING has two entries, BANK_B has a credit entry
3. `legacyledger settle --demo` processes 8+ transfers with mix of successes and expected failures
4. `legacyledger network-status` shows NOSTRO NET: $0.00 after demo batch
5. Insufficient-funds transfer fails at Step 1 without touching CLEARING or destination
6. All chain entries include settlement reference for cross-node correlation

**On PASS:** Proceed to HANDOFF_C (Cross-Node Integrity & Tamper Demo).

---

## 8. WHAT THIS PROVES (AND WHAT'S LEFT)

When this gate passes:
- ✅ Python orchestrates COBOL across 6 independent nodes
- ✅ The "5 banks, 1 clearing house" architecture is real and functional
- ✅ Double-entry settlement produces balanced nostro accounts
- ✅ The integrity chain records every leg of every transfer
- ✅ Failure handling is realistic (fail-forward, not rollback)

What HANDOFF_C adds:
- Cross-node verification (compare chains across nodes)
- Tamper demo (corrupt one chain → clearing house proves what happened)
- The "two independent witnesses" demo moment
