# Architecture

## Network Topology

```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│  BANK_A  │  │  BANK_B  │  │  BANK_C  │  │  BANK_D  │  │  BANK_E  │
│ 8 accts  │  │ 7 accts  │  │ 8 accts  │  │ 6 accts  │  │ 8 accts  │
│ retail   │  │ corporate│  │ mixed    │  │ trust    │  │community │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │             │             │
     └─────────────┴──────┬──────┴─────────────┴─────────────┘
                          │
                   ┌──────┴──────┐
                   │   CLEARING  │
                   │  5 nostro   │
                   │  accounts   │
                   └─────────────┘
```

6 independent nodes. Each node operates autonomously with its own data files and database. The clearing house holds one **nostro account** per bank (NST-BANK-A through NST-BANK-E) used for settlement balancing.

## Data Layer

Each node has three data stores:

```
banks/BANK_A/
  ACCOUNTS.DAT    ← COBOL fixed-width (70 bytes/record)
  TRANSACT.DAT    ← COBOL fixed-width (103 bytes/record)
  bank_a.db       ← SQLite (integrity chain + account snapshots)
```

### COBOL Record Formats

**ACCTREC** (70 bytes):
```
Bytes  0-9:   ACCT-ID         PIC X(10)      "ACT-A-001 "
Bytes 10-39:  ACCT-NAME       PIC X(30)      "Maria Santos              "
Byte  40:     ACCT-TYPE       PIC X(1)       "C" (checking) / "S" (savings)
Bytes 41-52:  ACCT-BALANCE    PIC S9(10)V99  "000000500000" ($5,000.00)
Byte  53:     ACCT-STATUS     PIC X(1)       "A" (active) / "F" (frozen) / "C" (closed)
Bytes 54-61:  ACCT-OPEN-DATE  PIC 9(8)       "20260217"
Bytes 62-69:  ACCT-LAST-ACTV  PIC 9(8)       "20260217"
```

**TRANSREC** (103 bytes):
```
Bytes  0-11:  TRANS-ID        PIC X(12)      "TRX-A-000001"
Bytes 12-21:  TRANS-ACCT-ID   PIC X(10)      "ACT-A-001 "
Byte  22:     TRANS-TYPE      PIC X(1)       D/W/T/I/F (deposit/withdraw/transfer/interest/fee)
Bytes 23-34:  TRANS-AMOUNT    PIC S9(10)V99  "000000250000" ($2,500.00)
Bytes 35-42:  TRANS-DATE      PIC 9(8)       "20260223"
Bytes 43-48:  TRANS-TIME      PIC 9(6)       "143022"
Bytes 49-88:  TRANS-DESC      PIC X(40)      "Wire transfer — proof of concept"
Bytes 89-90:  TRANS-STATUS    PIC XX         "00" (success) / "01" (NSF) / "03" (invalid)
Bytes 91-102: TRANS-BATCH-ID  PIC X(12)      "BATCH-00001 "
```

## Execution Model

### Dual-Mode Architecture

```
                  ┌──────────────────────────────────────┐
                  │           Python Bridge               │
                  │         (bridge.py)                   │
                  ├──────────────┬───────────────────────┤
                  │   Mode A     │       Mode B           │
                  │   COBOL      │       Python            │
                  │   subprocess │       file I/O          │
                  ├──────────────┼───────────────────────┤
                  │ cobol/bin/   │  load_accounts_from_dat│
                  │ ACCOUNTS     │  _mode_b_transaction   │
                  │ TRANSACT     │  _write_accounts_to_dat│
                  │ VALIDATE     │                         │
                  │ REPORTS      │  Same record formats    │
                  │ INTEREST     │  Same business rules    │
                  │ FEES         │  Same status codes      │
                  │ RECONCILE    │                         │
                  └──────┬───────┴───────────┬────────────┘
                         │                   │
                         ▼                   ▼
                  ┌──────────────────────────────────────┐
                  │       ACCOUNTS.DAT / TRANSACT.DAT     │
                  │       (70-byte / 103-byte records)    │
                  └──────────────────────────────────────┘
```

**Mode A** (COBOL available): Python calls compiled COBOL binaries as subprocesses, passing operations via stdin/command-line args. COBOL reads/writes the DAT files directly. Python parses stdout for results.

**Mode B** (Python fallback): Python reads/writes the same fixed-width DAT files directly, applying the same business rules. Used when `cobc` isn't installed.

Both modes produce identical data formats. The integrity chain doesn't care which mode executed the transaction.

## Inter-Bank Settlement Flow

```
    BANK_A                    CLEARING                   BANK_B
    ┌─────┐                   ┌─────┐                   ┌─────┐
    │     │  1. DEBIT $2,500  │     │                   │     │
    │ ACT │ ◄──────────────── │     │                   │     │
    │  A  │  Alice's account  │     │                   │     │
    │ 001 │                   │     │                   │     │
    └──┬──┘                   │     │                   │     │
       │                      │     │  2a. DEPOSIT      │     │
       │    chain entry ──►   │ NST │ ◄── from BANK_A   │     │
       │    (XFER-TO-BANK_B)  │BANK │                   │     │
       │                      │  A  │  2b. WITHDRAW     │     │
       │                      │ NST │ ──── to BANK_B ──►│     │
       │                      │BANK │                   │     │
       │                      │  B  │                   │ ACT │
       │                      └──┬──┘                   │  B  │
       │                         │                      │ 001 │
       │                         │   3. CREDIT $2,500   │     │
       │                         │ ────────────────────►│     │
       │                         │   Bob's account      │     │
       │                         │                      └──┬──┘
       │                         │                         │
       ▼                         ▼                         ▼
   chain_entries             chain_entries             chain_entries
   (BANK_A.db)              (clearing.db)             (BANK_B.db)
```

Each step generates a chain entry with the settlement reference (`STL-YYYYMMDD-NNNNNN`). Cross-node verification matches these references across all 3 chains to confirm the settlement is complete and amounts agree.

## Integrity Model

### Layer 1: Per-Node Hash Chains

Each node maintains a SHA-256 hash chain in SQLite:

```
Entry 0: hash = SHA256(tx_data + "GENESIS")
Entry 1: hash = SHA256(tx_data + entry_0.hash)
Entry 2: hash = SHA256(tx_data + entry_1.hash)
...
```

If any entry is modified or deleted, the chain breaks — the computed hash no longer matches the stored hash. Verification walks the full chain in O(n) time.

### Layer 2: Balance Reconciliation

After each COBOL operation, Python snapshots the account balance in SQLite. If someone tampers the DAT file directly (bypassing COBOL and the chain):

```
ACCOUNTS.DAT:  ACT-C-001  balance = $999,999.99  ← tampered
bank_c.db:     ACT-C-001  balance = $150,000.00  ← last known good
```

The verifier compares DAT vs DB and flags the mismatch. This catches tampering that doesn't touch the chain at all.

### Layer 3: Cross-Node Settlement Matching

For every settlement reference found in any chain, the verifier checks:
- Source bank has a debit entry (XFER-TO)
- Clearing house has deposit + withdraw entries (SETTLE)
- Destination bank has a credit entry (XFER-FROM)
- All amounts match

Missing or mismatched entries indicate deleted transactions, fabricated entries, or modified amounts.

## COBOL Programs

| Program | Lines | Purpose |
|---------|-------|---------|
| `ACCOUNTS.cob` | 251 | Account lifecycle: CREATE, READ, UPDATE, CLOSE, LIST |
| `TRANSACT.cob` | 545 | Transaction engine: DEPOSIT, WITHDRAW, TRANSFER, BATCH |
| `VALIDATE.cob` | 175 | Business rules: status, balance, and limit checks |
| `REPORTS.cob` | 243 | Reporting: STATEMENT, LEDGER, EOD, AUDIT |
| `INTEREST.cob` | 276 | Monthly interest accrual for savings accounts |
| `FEES.cob` | 305 | Monthly maintenance fee processing |
| `RECONCILE.cob` | 276 | Transaction-to-balance reconciliation |
| `SMOKETEST.cob` | 95 | Compilation verification |
| **Total** | **2,166** | |

All programs share copybooks: `ACCTREC.cpy` (account record), `TRANSREC.cpy` (transaction record), `COMCODE.cpy` (status codes and constants).

## Python Observation Layer

| Module | Lines | Purpose |
|--------|-------|---------|
| `bridge.py` | 1,021 | COBOL subprocess execution, DAT file I/O, SQLite sync |
| `integrity.py` | 180 | SHA-256 hash chain + HMAC verification |
| `settlement.py` | 330 | 3-step inter-bank settlement coordinator |
| `cross_verify.py` | 382 | Cross-node integrity verification + tamper detection |
| `simulator.py` | 704 | Multi-day banking simulation engine |
| `cli.py` | 630 | Command-line interface |
| **Total** | **3,376** | |

## Verification Performance

Cross-node verification of all 6 chains completes in <5ms (typical). This includes:
- Walking all hash chains
- Comparing DAT vs DB balances for 42 accounts
- Cross-referencing all settlement entries

The entire `prove.sh` demonstration runs in ~10 seconds, dominated by COBOL compilation and node seeding — verification itself is near-instantaneous.
