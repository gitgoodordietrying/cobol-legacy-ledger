# HANDOFF C — Cross-Node Integrity & Tamper Demo

**Project:** LegacyLedger: Closing the Multi-Bank Gap  
**Author:** Albert (AKD Solutions / Imperium)  
**Date:** February 19, 2026  
**Purpose:** Implement cross-node chain verification and the "two independent witnesses" tamper demo  
**Prerequisite:** HANDOFF_B gate PASSED (settlement coordinator working, nostro balanced)  
**Sequence:** HANDOFF_A (done) → HANDOFF_B (done) → **This document**

**READ THIS ENTIRE DOCUMENT BEFORE WRITING ANY CODE.**

---

## 0. THE DEMO PAYOFF

This document delivers the most powerful 30 seconds of the entire 15-minute presentation:

> "Every inter-bank transfer creates entries in three independent ledgers — the source bank, the clearing house, and the destination bank. Watch what happens when I tamper with BANK_A's record."
>
> *[runs tamper command]*
>
> "BANK_A says Alice still has $5,000. But the clearing house says she sent $500 to BANK_B. And BANK_B confirms Bob received $500. Two independent witnesses caught the lie in 3 milliseconds."

This is the thesis made tangible. Three COBOL flat files, three independent hash chains, one Python verifier that cross-references them. The architecture IS the demo.

---

## 1. CROSS-NODE VERIFICATION: THE ALGORITHM

### 1.1 What We're Comparing

After settlement (HANDOFF_B), a single inter-bank transfer creates entries across three chains:

| Chain | Entry | Description Contains |
|-------|-------|---------------------|
| BANK_A chain | WITHDRAW $500 | `XFER-TO-BANK_B-ACT-B-003` + settlement ref |
| CLEARING chain | DEPOSIT $500 to NST-BANK-A | `SETTLE:A→B` + settlement ref |
| CLEARING chain | WITHDRAW $500 from NST-BANK-B | `SETTLE:A→B` + settlement ref |
| BANK_B chain | DEPOSIT $500 | `XFER-FROM-BANK_A-ACT-A-001` + settlement ref |

The verifier's job: **for every settlement reference, confirm all expected entries exist across all involved chains, and that amounts match.**

### 1.2 Verification Algorithm

```
cross_verify(all_chains: dict[str, IntegrityChain]) → VerificationReport:

    1. Collect all settlement references from all chains
       (scan chain entries for STL-* patterns in metadata/description)
    
    2. For each settlement reference:
       a. Find the source bank entry (WITHDRAW with XFER-TO-*)
       b. Find the clearing entries (DEPOSIT + WITHDRAW with SETTLE:*)
       c. Find the destination bank entry (DEPOSIT with XFER-FROM-*)
       d. Verify: source amount == clearing amount == dest amount
       e. Verify: bank references are consistent (A→B in all entries)
       f. Record: MATCHED if all 4 entries found and consistent
                  PARTIAL if some entries missing
                  MISMATCH if amounts or references disagree
    
    3. Also verify each chain independently:
       (existing verify_chain() — hash continuity)
    
    4. Return VerificationReport with:
       - Per-chain hash integrity status
       - Per-settlement cross-reference status
       - List of anomalies (missing entries, amount mismatches)
       - Timing (must complete in single-digit milliseconds)
```

### 1.3 What Cross-Verification Catches

| Scenario | What Happened | What Verification Finds |
|----------|--------------|------------------------|
| Normal | All entries consistent | ✓ All settlements matched |
| Tampered balance | BANK_A balance edited | Chain hash broken at BANK_A |
| Deleted transaction | BANK_A entry removed | Settlement ref missing from BANK_A chain |
| Amount changed | BANK_A says $400 not $500 | Amount mismatch: BANK_A=$400, CLEARING=$500, BANK_B=$500 |
| Fake transaction | Entry added to BANK_A | Orphan entry — no matching settlement ref in CLEARING |

---

## 2. FILE: python/cross_verify.py (~150 lines)

**New file.** The cross-node verification engine.

### 2.1 Class: CrossNodeVerifier

```python
"""
cross_verify.py — Cross-node integrity verification for multi-bank settlement.

Compares hash chains across all 6 banking nodes to detect:
  - Hash chain breaks (single-node tamper detection)
  - Missing settlement entries (deleted transactions)
  - Amount mismatches (modified transactions)
  - Orphan entries (fabricated transactions)

The clearing house chain is the authoritative record. When bank chains
disagree with clearing, the clearing chain is treated as ground truth.

Dependencies: integrity.py (for per-chain verification)
"""
```

### 2.2 Data Types

```python
@dataclass
class SettlementMatch:
    """Result of cross-referencing one settlement across nodes."""
    settlement_ref: str
    status: str            # "MATCHED" | "PARTIAL" | "MISMATCH" | "ORPHAN"
    amount: float
    source_bank: str
    dest_bank: str
    source_entry_found: bool
    clearing_entries_found: int  # 0, 1, or 2
    dest_entry_found: bool
    discrepancies: list[str]   # Human-readable list of what's wrong

@dataclass  
class VerificationReport:
    """Complete cross-node verification results."""
    timestamp: str
    
    # Per-chain hash integrity
    chain_integrity: dict[str, bool]  # {"BANK_A": True, "CLEARING": False, ...}
    chain_lengths: dict[str, int]     # {"BANK_A": 24, ...}
    
    # Cross-node settlement matching
    settlements_checked: int
    settlements_matched: int
    settlements_partial: int
    settlements_mismatched: int
    settlements_orphaned: int
    settlement_details: list[SettlementMatch]
    
    # Summary
    all_chains_intact: bool
    all_settlements_matched: bool
    anomalies: list[str]
    
    # Performance
    verification_time_ms: float  # Must be < 10ms for demo
```

### 2.3 Core Methods

```python
class CrossNodeVerifier:
    def __init__(self, project_root: str):
        """Load all 6 chains."""
    
    def verify_all(self) -> VerificationReport:
        """
        Full cross-node verification:
        1. Verify each chain's hash integrity independently
        2. Extract all settlement references
        3. Cross-reference entries across chains
        4. Report anomalies
        """
    
    def find_settlement_entries(self, settlement_ref: str) -> dict:
        """
        For a given settlement reference, find all related entries
        across all chains. Returns:
        {
            'source': {'bank': 'BANK_A', 'entry': ..., 'amount': 500.0},
            'clearing_deposit': {'entry': ..., 'amount': 500.0},
            'clearing_withdraw': {'entry': ..., 'amount': 500.0},
            'dest': {'bank': 'BANK_B', 'entry': ..., 'amount': 500.0},
        }
        Missing entries have None values.
        """
    
    def detect_orphans(self) -> list[dict]:
        """
        Find chain entries that reference settlement but have no
        matching entries in other chains. These are either:
        - Fabricated transactions (if only in one bank)
        - Incomplete settlements (if only in clearing + one bank)
        """
```

---

## 3. TAMPER DEMO: THE DRAMATIC MOMENT

### 3.1 How Tamper Works

The tamper demo modifies a .DAT file directly (bypassing COBOL, bypassing the chain) and then runs verification to catch it.

**Two tamper scenarios for the demo:**

**Scenario A — Balance Tamper (chain break):**
Directly edit BANK_A/ACCOUNTS.DAT to change Alice's balance. The chain hash will break because the .DAT file no longer matches the hash at the time the chain entry was created.

**Scenario B — Transaction Delete (cross-node mismatch):**
Delete a TRANSACT.DAT entry from BANK_A that corresponds to an inter-bank transfer. The BANK_A chain may still be internally consistent (if we remove the chain entry too), but cross-node verification catches it because CLEARING and BANK_B still have records of the settlement that BANK_A now denies.

**Scenario B is the stronger demo** because it shows the multi-node value. Single-chain tamper detection (Scenario A) was already working. Cross-node detection is new.

### 3.2 CLI Commands

**Tamper command (creates the corruption):**
```
legacyledger tamper-demo --node BANK_A --type balance --account ACT-A-001 --amount 9999.99
legacyledger tamper-demo --node BANK_A --type delete-tx --settlement STL-20260219-000001
```

**Verify command (catches the corruption):**
```
legacyledger verify --cross-node
```

### 3.3 Verify Output Format (for demo)

**Clean verification (before tamper):**
```
╔══════════════════════════════════════════════════════════════╗
║  CROSS-NODE INTEGRITY VERIFICATION                           ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  CHAIN INTEGRITY                                             ║
║    BANK_A     24 entries   ✓ INTACT                          ║
║    BANK_B     18 entries   ✓ INTACT                          ║
║    BANK_C     21 entries   ✓ INTACT                          ║
║    BANK_D     15 entries   ✓ INTACT                          ║
║    BANK_E     19 entries   ✓ INTACT                          ║
║    CLEARING   42 entries   ✓ INTACT                          ║
║                                                              ║
║  SETTLEMENT CROSS-REFERENCES                                 ║
║    8 settlements verified                                    ║
║    8 matched  ·  0 partial  ·  0 mismatched  ·  0 orphaned  ║
║                                                              ║
║  ───────────────────────────────────────────────────────────  ║
║  ✓ ALL CHAINS INTACT  ·  ALL SETTLEMENTS MATCHED             ║
║  Verified in 2.8ms                                           ║
╚══════════════════════════════════════════════════════════════╝
```

**After tamper (balance modification):**
```
╔══════════════════════════════════════════════════════════════╗
║  CROSS-NODE INTEGRITY VERIFICATION                           ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  CHAIN INTEGRITY                                             ║
║    BANK_A     24 entries   ✗ BROKEN AT ENTRY #17             ║
║    BANK_B     18 entries   ✓ INTACT                          ║
║    BANK_C     21 entries   ✓ INTACT                          ║
║    BANK_D     15 entries   ✓ INTACT                          ║
║    BANK_E     19 entries   ✓ INTACT                          ║
║    CLEARING   42 entries   ✓ INTACT                          ║
║                                                              ║
║  ⚠ ANOMALY DETECTED                                          ║
║    BANK_A chain hash mismatch at entry #17                   ║
║    Expected hash: a3f7b2...                                  ║
║    Computed hash: 91c4e8...                                  ║
║                                                              ║
║    CLEARING record shows: ACT-A-001 WITHDRAW $500.00         ║
║    BANK_B record confirms: DEPOSIT $500.00 received          ║
║    → Two independent witnesses contradict BANK_A's ledger    ║
║                                                              ║
║  ───────────────────────────────────────────────────────────  ║
║  ✗ INTEGRITY VIOLATION  ·  1 chain broken  ·  1 anomaly      ║
║  Verified in 3.1ms                                           ║
╚══════════════════════════════════════════════════════════════╝
```

**The critical line for the demo:** "Two independent witnesses contradict BANK_A's ledger." That's the thesis in one sentence.

---

## 4. DEMO SCRIPT: THE 90-SECOND FLOW

This is the exact sequence for the interview demo. Practice it.

```
# 1. Show the clean network (5 seconds)
legacyledger network-status

# 2. Run settlement batch (20 seconds)
legacyledger settle --demo

# 3. Verify — everything clean (5 seconds)
legacyledger verify --cross-node
# "139 entries across 6 chains. All intact. All settlements matched. 2.8ms."

# 4. Now tamper with BANK_A (5 seconds)
legacyledger tamper-demo --node BANK_A --type balance --account ACT-A-001 --amount 9999.99
# "Modified BANK_A/ACCOUNTS.DAT: ACT-A-001 balance → $9,999.99"

# 5. Verify again — CAUGHT (10 seconds to read output)
legacyledger verify --cross-node
# "INTEGRITY VIOLATION at BANK_A entry #17"
# "Two independent witnesses contradict BANK_A's ledger"

# 6. Show clearing house has the truth (5 seconds)
legacyledger network-status
# CLEARING nostro accounts show what really happened
```

**Total: ~50 seconds for the integrity demo portion.**

**Talking points during the demo:**
- "BANK_A says Alice has $9,999. But the clearing house recorded that she sent $500 to BANK_B yesterday. And BANK_B confirms receipt. The lie takes 3 milliseconds to catch."
- "This is the same pattern banks use in real settlement — independent ledgers with a central reconciliation authority. Except now the reconciliation is cryptographic and instant."
- "The COBOL programs don't know about hash chains. They just write to flat files like they've done since 1959. Python wraps them with modern integrity guarantees."

---

## 5. IMPLEMENTATION SEQUENCE

### Step 1: Ensure HANDOFF_B state is clean (5 min)
```bash
# Re-seed, run demo settlement, verify network-status shows balanced nostro
./scripts/seed.sh
legacyledger settle --demo
legacyledger network-status
# Confirm: NOSTRO NET: $0.00
```

### Step 2: Write cross_verify.py (2 hours)
- CrossNodeVerifier class
- verify_all() with timing
- find_settlement_entries() for cross-referencing
- detect_orphans() for fabricated/missing entries
- VerificationReport dataclass

### Step 3: Write tamper logic (30 min)
Add to existing integrity.py or create a thin wrapper:
- `tamper_balance(node, account_id, new_amount)` — modifies .DAT file directly
- `tamper_delete_tx(node, settlement_ref)` — removes chain entry
Both methods MUST warn: "This is for DEMO PURPOSES ONLY. Modifying production data files would be a serious compliance violation."

### Step 4: Add CLI commands (1 hour)
- `legacyledger verify --cross-node` — runs CrossNodeVerifier.verify_all()
- `legacyledger tamper-demo --node X --type balance --account Y --amount Z`
- Update existing `legacyledger verify` (single-node) to also show cross-node option

### Step 5: Test the full demo flow (30 min)
Run the exact demo script from Section 4. Verify:
- Clean verification passes with correct counts
- Tamper produces the expected INTEGRITY VIOLATION output
- Timing is under 10ms
- The "two independent witnesses" message appears

### Step 6: Document in DEV_LOG.md (15 min)
Record: verification algorithm, tamper demo results, timing measurements, demo script.

---

## 6. GATE CRITERIA

**PASS if ALL of the following are true:**

1. `legacyledger verify --cross-node` on clean data shows all chains INTACT and all settlements MATCHED
2. Verification completes in < 10ms for all entries across all nodes
3. Balance tamper on BANK_A is detected with chain break at correct entry
4. The output explicitly states that other nodes contradict the tampered node
5. `legacyledger tamper-demo` works for both balance and delete-tx scenarios
6. The 90-second demo script (Section 4) runs without errors

---

## 7. WHAT THE COMPLETE SYSTEM NOW PROVES

When this gate passes, the full LegacyLedger system delivers on every promise:

| Master Overview Promise | Delivered | How |
|------------------------|-----------|-----|
| "5 banks, 1 clearing house" | ✅ | 6-node COBOL system verified standalone |
| "Three independent ledgers" | ✅ | Source, clearing, destination each record |
| "Hub-and-spoke settlement" | ✅ | Python coordinator calls COBOL at each node |
| "Tamper detection in milliseconds" | ✅ | Cross-node verification < 10ms |
| "Two independent witnesses" | ✅ | Clearing + destination contradict tampered source |
| "Zero cloud dependency" | ✅ | Docker + local COBOL + Python stdlib |
| "COBOL is the hero, Python wraps it" | ✅ | Zero COBOL modifications for settlement |
| "Blockchain-grade audit trail" | ✅ | HMAC-signed hash chains across 6 nodes |
| "Compliance flagging" | ✅ | CTR threshold detection in batch |
| "Balanced nostro accounts" | ✅ | $0.00 net after settlement |

**Every pitch point from the Master Overview is now demonstrable in the 15-minute window.**

---

## 8. POST-COMPLETION: WHAT COMES NEXT

After all three handoff gates pass, the remaining work is Layer 3 (frontend, API, AI integration) from the original Master Overview Phases 3-9. But the core architectural thesis — "wrap COBOL with modern infrastructure, don't rewrite it" — is now proven end-to-end.

The settlement coordinator + cross-node verifier is approximately 400 lines of Python that transforms a collection of isolated COBOL banking programs into a cryptographically auditable settlement network. The COBOL didn't change. That's the point.
