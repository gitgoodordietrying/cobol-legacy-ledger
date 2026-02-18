# 01_MASTER_OVERVIEW

**cobol-legacy-ledger** — Cryptographic integrity monitoring for inter-bank COBOL batch settlement.

---

## The Problem

Inter-bank COBOL batch settlement systems have no native integrity verification. Transactions flow through batch processing pipelines — nightly settlement runs, sequential flat-file processing — that introduce data distortion at every step: reference IDs change or disappear, individual transactions are collapsed into net settlements, timing gaps span time zones. When a transaction leaves one bank's COBOL ledger and arrives at another's, there is no cryptographic proof it wasn't altered in transit. Detection depends on manual reconciliation by humans who increasingly don't exist.

The result: banks spend enormous effort manually reconciling inter-bank discrepancies. The real question isn't *what* went wrong — it's *where* in the pipeline and *when*.

---

## The Solution

A non-invasive Python observation layer that wraps around unmodified COBOL batch programs and provides cryptographic proof that every transaction in a multi-bank settlement cycle is intact, consistent, and reconcilable.

**Core mechanism:**
- Every transaction is SHA-256 hash-chained (linked to its predecessor)
- Every transaction is HMAC-signed (authorizes its contents)
- Three independent ledgers (source bank, clearing house, destination bank) record the same transfer
- End-of-day netting shows settlement positions and proves double-entry integrity (sum of all nets = $0.00)
- When a ledger is corrupted, the clearing house's authoritative record proves what *should* have happened

**The message:** The COBOL never changes. The .DAT files never change. We just wrapped them in cryptographic verification that the COBOL never even knows exists.

---

## Architecture

### Six-Node Design

| Node | Purpose | Accounts | COBOL Program |
|------|---------|----------|---------------|
| BANK_A (First National) | Customer deposits/withdrawals | 8 customer | ACCOUNTS, TRANSACT |
| BANK_B (Commerce Trust) | Customer + payroll | 7 customer | ACCOUNTS, TRANSACT |
| BANK_C (Pacific Savings) | Customer (TAMPER TARGET) | 8 customer | ACCOUNTS, TRANSACT |
| BANK_D (Heritage Federal) | Wealth management | 6 customer | ACCOUNTS, TRANSACT |
| BANK_E (Metro Credit Union) | Community banking | 8 customer | ACCOUNTS, TRANSACT |
| CLEARING (Central House) | Inter-bank settlement | 5 nostro | ACCOUNTS, TRANSACT |

**All 6 nodes run the same compiled COBOL binaries.** Each node has its own directory with ACCOUNTS.DAT and TRANSACT.DAT. The COBOL programs open these files relative to their working directory — one program, six data sets. This is how COBOL works in production.

### Data Flow

```
Customer Transaction: Alice (BANK_A) pays Bob (BANK_B) $500

1. BANK_A debits Alice's account
   → TRANSACT.cob (cwd=banks/BANK_A/)
   → Writes to BANK_A/TRANSACT.DAT
   → Entry in BANK_A integrity chain

2. CLEARING settles the transfer
   → Credits BANK_A's nostro account
   → Debits BANK_B's nostro account
   → TRANSACT.cob (cwd=banks/CLEARING/)
   → Writes to CLEARING/TRANSACT.DAT
   → Entry in CLEARING integrity chain (authoritative record)

3. BANK_B credits Bob's account
   → TRANSACT.cob (cwd=banks/BANK_B/)
   → Writes to BANK_B/TRANSACT.DAT
   → Entry in BANK_B integrity chain

Three independent records of the same transfer:
   BANK_A chain:   TX#247: DEBIT Alice $500 → CLEARING
   CLEARING chain: TX#891: BANK_A→BANK_B $500 ref:TX247
   BANK_B chain:   TX#103: CREDIT Bob $500 ← CLEARING
```

### Integrity Layer

Each transaction gets two cryptographic artifacts:
- **tx_hash**: SHA-256(transaction contents + previous transaction's hash)
- **signature**: HMAC-SHA256(tx_hash, secret_key)

**Three-check verification:**
1. Chain linkage — each entry's prev_hash matches the previous entry's tx_hash
2. Hash mismatch — recompute the hash from contents and compare to stored hash
3. Signature invalid — verify HMAC using the node's secret key

If any check fails, the system has detected unauthorized modification.

### Settlement Coordinator (Phase 2)

At end-of-day, compute net settlement positions:
```
For each bank:
  credits_in = sum(all deposits from other banks)
  debits_out = sum(all withdrawals to other banks)
  net_position = credits_in - debits_out

Verify: sum(all nets) = $0.00  (double-entry proof)
```

Output:
```
BANK_A: -$2,400.00  (net payer)
BANK_B: +$8,247.50  (net receiver)
BANK_C: -$1,200.00  (net payer)
BANK_D: -$6,100.00  (net payer)
BANK_E: +$1,452.50  (net receiver)
───────────────────
NET:     $0.00       ✓  (balanced)
```

---

## Three-Phase Phasing

| Phase | Scope | Gate | Deliverable |
|-------|-------|------|-------------|
| **1** | COBOL foundation, Python bridge, integrity chain, seeding | build.sh + seed.sh + accounts + transaction + chain all pass | Handoff docs (this package) |
| **2** | Settlement coordinator, cross-node verification (5×5 → hub-and-spoke), netting, demo script | Corrupt BANK_C; other 4 banks + CLEARING detect in <100ms | Phase 2 handoff docs |
| **3** | Static HTML console (no Node.js), live demo visualization, GitHub Pages | Full demo end-to-end; console shows all 6 nodes, chains, tamper detection | Live system |

### Phase 1 Detail

**COBOL layer:**
- 4 programs: ACCOUNTS, TRANSACT, VALIDATE, REPORTS (implement from specification in `02_COBOL_AND_DATA.md`)
- 3 copybooks: ACCTREC, TRANSREC, COMCODE (specs provided)
- Document all known issues in `cobol/KNOWN_ISSUES.md` (template in COBOL_SUPPLEMENTS.md)

**Python layer:**
- `bridge.py` (adapt from v1 cobol_bridge.py, strip AI methods, adapt for 6 nodes)
- `integrity.py` (implement from interface specification in `03_PYTHON_BACKEND.md`)
- `auth.py` (implement from specification, stripped of `ai.*` permissions)
- `cli.py` (implement from specification in `03_PYTHON_BACKEND.md`)
- `requirements.txt` (fastapi, uvicorn, click, pydantic only)

**Data & scripts:**
- 6 node directories with seeded account files
- `scripts/build.sh` (compile COBOL with cobc)
- `scripts/setup.sh` (Python venv + pip)
- `scripts/seed.sh` (populate all 6 nodes)

**Deliverables:**
- Compiled COBOL binaries (or skip if cobc unavailable)
- Seeded ACCOUNTS.DAT, TRANSACT.DAT, BATCH-INPUT.DAT in all 6 nodes
- Python bridge that reads 8 customer accounts from any bank, 5 nostro from CLEARING
- Passing verification gate

### What Phase 1 is NOT

- No settlement coordinator (Phase 2)
- No netting calculations (Phase 2)
- No cross-node chain verification (Phase 2)
- No FastAPI HTTP endpoints (Phase 2)
- No frontend, no console, no visualization (Phase 3)
- No tamper-detection demo (Phase 3)

**Phase 1 = proof the system *can* run. Phase 2 = proof it can *verify*. Phase 3 = proof it can *demonstrate*.**

---

## Critical Design Decisions (Locked)

| Decision | Value | Rationale |
|----------|-------|-----------|
| COBOL source | Implement from specification in `02_COBOL_AND_DATA.md` | All program behaviors, I/O contracts, and output formats are fully specified. No external v1 repo needed. |
| COBOL bugs | DO NOT FIX | Bugs are authentic and serve as interview talking points. Copy v1 exactly. |
| Node count | 6 (5 banks + clearing) | Clearing house makes verification hub-and-spoke instead of peer-to-peer. Matches real ACH architecture. |
| Account types | Customer + nostro | Banks have customer accounts; clearing house has nostro (settlement) accounts. Same COBOL processes both. |
| Node.js | Dropped, forever | No npm, no React, no Node dependencies. Phase 3 is static HTML served by Python. |
| Verification model | Hub-and-spoke | Each bank's chain vs. clearing house's authoritative record. Not peer-to-peer voting. |
| Database | SQLite | Phase 1 proof-of-concept. Production would sync to mainframe DB via bridge. |
| Integrity layer | SHA-256 + HMAC | Standard cryptographic primitives. Not blockchain, not exotic. |

---

## Interview Narrative

This system tells a story:

1. **The Problem:** "Banks connect through batch settlement systems written in COBOL in the 1970s. Money goes in, money comes out, but if something goes wrong in the middle, detection depends on manual reconciliation by people who increasingly don't exist."

2. **The Solution:** "Instead of rewriting COBOL or forcing legacy systems into a blockchain, I built a Python observation layer that proves every transaction is intact and consistent. No changes to the COBOL. No changes to the data files. Just cryptographic verification wrapped around them."

3. **The Demo:** "Five banks, one clearing house. Money flows between them. We corrupt one bank's ledger — change a balance, falsify a hash. The clearing house independently detects it because the transaction it records doesn't match the bank's ledger. One witness would be suspicious; two independent witnesses prove tampering."

4. **The Lesson:** "COBOL isn't the problem. Lack of observability is. You can build modern infrastructure around legacy systems without replacing them."

---

## File Structure (Final)

```
cobol-legacy-ledger/
├── cobol/
│   ├── src/                    ← COBOL programs (4 files)
│   │   ├── ACCOUNTS.cob
│   │   ├── TRANSACT.cob
│   │   ├── VALIDATE.cob
│   │   └── REPORTS.cob
│   ├── copybooks/              ← Shared layouts (3 files)
│   │   ├── ACCTREC.cpy
│   │   ├── TRANSREC.cpy
│   │   └── COMCODE.cpy
│   ├── bin/                    ← Compiled binaries (gitignored)
│   └── KNOWN_ISSUES.md         ← All identified bugs documented
├── banks/                      ← Six node directories
│   ├── BANK_A/
│   │   ├── ACCOUNTS.DAT        ← 8 customer accounts (seeded)
│   │   ├── TRANSACT.DAT        ← (empty on first run)
│   │   └── BATCH-INPUT.DAT     ← Pre-authored batch scenario
│   ├── BANK_B/ through BANK_E/
│   └── CLEARING/
│       ├── ACCOUNTS.DAT        ← 5 nostro accounts (seeded)
│       ├── TRANSACT.DAT        ← (empty on first run)
│       └── BATCH-INPUT.DAT
├── python/
│   ├── bridge.py               ← COBOL → SQLite bridge
│   ├── integrity.py            ← Hash chain + HMAC verification
│   ├── auth.py                 ← Role-based auth (stripped of ai.*)
│   ├── requirements.txt        ← Dependencies (4 packages)
│   └── tests/
│       ├── test_integrity.py
│       └── test_bridge.py
├── scripts/
│   ├── build.sh                ← Compile COBOL (cobc)
│   ├── setup.sh                ← Python venv + pip
│   └── seed.sh                 ← Populate all 6 nodes
├── docs/
│   ├── README.md               ← Project overview
│   ├── ARCHITECTURE.md         ← 90-second architecture for senior dev
│   └── handoff/
│       ├── 00_README.md        ← This package guide
│       ├── 01_MASTER_OVERVIEW.md ← You are here
│       ├── 02_COBOL_AND_DATA.md
│       ├── 03_PYTHON_BACKEND.md
│       └── 04_FRONTEND_AND_DEMO.md
├── console/                    ← Reserved for Phase 3
│   └── .gitkeep
├── arcade/                     ← Reserved for Phase 4
│   └── .gitkeep
├── data/                       ← SQLite databases (gitignored)
├── .gitignore
└── .git/
```

---

## Phase 1 Verification Gate

All five must pass:

```bash
# 1. COBOL compiles (or gracefully skips if cobc unavailable)
./scripts/build.sh

# 2. All 6 nodes seed
./scripts/seed.sh

# 3. Bridge reads correct account counts from all nodes
python -c "
from bridge import COBOLBridge
expected = {'BANK_A':8,'BANK_B':7,'BANK_C':8,'BANK_D':6,'BANK_E':8,'CLEARING':5}
for node, count in expected.items():
    b = COBOLBridge(node=node)
    assert len(b.list_accounts()) == count, f'{node} count wrong'
    print(f'{node}: {count} accounts ✓')
print('Account check passed')
"

# 4. Transaction processes and returns status 00
python -c "
from bridge import COBOLBridge
b = COBOLBridge(node='BANK_A')
result = b.process_transaction('ACT-A-001','D',1000.00,'Gate test deposit')
assert result['status'] == '00', f'Unexpected status: {result[\"status\"]}'
print(f'Transaction {result[\"tx_id\"]}: status 00 ✓')
"

# 5. Integrity chain records and verifies
python -c "
from bridge import COBOLBridge
b = COBOLBridge(node='BANK_A')
verify = b.chain.verify_chain()
assert verify['valid'], f'Chain invalid: {verify[\"details\"]}'
print(f'Chain: {verify[\"entries_checked\"]} entries verified in {verify[\"time_ms\"]:.1f}ms ✓')
"
```

---

## Next Steps

1. **Read** `02_COBOL_AND_DATA.md` for the complete COBOL specification and account roster
2. **Read** `03_PYTHON_BACKEND.md` for Python bridge + integrity engine details
3. **Implement** Phase 1 in order: COBOL → Data seeding → Python bridge
4. **Verify** using the gate above
5. **Deliver** a working system that passes all three checks

---

## Questions?

If you're blocked on something not covered in the Phase 1 gate, it's likely Phase 2. Refer to the phase boundaries above.

If you're unsure whether to fix a bug, ask yourself: "Does this bug represent authentic legacy COBOL behavior?" If yes, document it and move on. If no, and it's in the v1 code, copy it anyway.

**Start with `02_COBOL_AND_DATA.md` next.**
