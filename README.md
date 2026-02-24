# COBOL Legacy Ledger

**Non-invasive cryptographic integrity for inter-bank COBOL settlement.**

> "COBOL isn't the problem. Lack of observability is."

6 independent banking nodes running real COBOL programs, wrapped with Python observation and SHA-256 hash chain verification. No COBOL was modified — Python observes, records, and detects tampering in milliseconds.

## See It Work

```bash
./scripts/prove.sh
```

One command. 30 seconds. The full thesis demonstrated:

1. **Compiles** 8 COBOL programs (2,166 lines of production-style banking code)
2. **Seeds** 6 independent banking nodes (42 accounts, $100M+ in balances)
3. **Settles** an inter-bank transfer: Alice@BANK_A pays Bob@BANK_B $2,500 through the clearing house (3-step flow)
4. **Verifies** all SHA-256 hash chains intact across the network
5. **Tampers** one bank's ledger directly (bypassing COBOL and the integrity chain)
6. **Detects** the tamper in <5ms via balance reconciliation

No Docker required. Just GnuCOBOL + Python 3.8+. Falls back to Python-only mode if COBOL isn't installed.

## Architecture

```
BANK_A ─────┐                    ┌───── BANK_D
BANK_B ─────┤◄── Settlement ──►├───── BANK_E
BANK_C ─────┘    Coordinator     └───── CLEARING
                      │
                 SHA-256 chain
                 per node (SQLite)
```

**6 nodes** (5 banks + 1 clearing house), each with:
- `ACCOUNTS.DAT` — COBOL fixed-width account records (70 bytes each)
- `TRANSACT.DAT` — COBOL transaction log (103 bytes each)
- `{node}.db` — SQLite with integrity chain, transaction history, account snapshots

**Inter-bank settlement** flows through 3 steps:
1. Source bank debits sender's account
2. Clearing house records both sides (deposit from source, withdraw to dest)
3. Destination bank credits receiver's account

Every step is recorded in the node's SHA-256 hash chain. Cross-node verification matches settlement references across all 6 chains.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full topology, data flow, and integrity model.

## What's Here

```
cobol/src/           8 COBOL programs (2,166 lines)
  ACCOUNTS.cob       Account lifecycle: CREATE, READ, UPDATE, CLOSE, LIST
  TRANSACT.cob       Transaction engine: DEPOSIT, WITHDRAW, TRANSFER, BATCH
  VALIDATE.cob       Business rules: status checks, balance limits
  REPORTS.cob        Reporting: STATEMENT, LEDGER, EOD, AUDIT
  INTEREST.cob       Monthly interest accrual for savings accounts
  FEES.cob           Monthly maintenance fee processing
  RECONCILE.cob      Transaction-to-balance reconciliation
  SMOKETEST.cob      Compilation verification

python/              Python observation layer (3,376 lines)
  bridge.py          COBOL subprocess execution + DAT file I/O + SQLite sync
  integrity.py       SHA-256 hash chain + HMAC verification
  settlement.py      3-step inter-bank settlement coordinator
  cross_verify.py    Cross-node integrity verification + tamper detection
  simulator.py       Multi-day banking simulation engine
  cli.py             Command-line interface (seed, transact, verify, simulate)

banks/               6 independent node directories
  BANK_A/ .. BANK_E/ Customer accounts (37 total)
  CLEARING/          5 nostro accounts (one per bank)

scripts/
  prove.sh           Executable proof — run this first
  build.sh           Compile COBOL programs
  seed.sh            Seed all 6 nodes with demo data
```

## Key Design Decisions

**Dual-mode execution** — Every operation works two ways: Mode A calls compiled COBOL binaries as subprocesses (production path), Mode B uses Python file I/O as fallback (when `cobc` isn't available). Same business logic, same data formats.

**COBOL immutability** — The COBOL programs are never modified. Python wraps them non-invasively, reading their output and maintaining integrity chains alongside the legacy data.

**Per-node isolation** — Each node has its own SQLite database and hash chain. No shared ledger. This mirrors how real banking systems operate — distributed, independent, reconciled through settlement.

**Tamper detection** — Two layers: (1) SHA-256 hash chains detect if chain entries are modified or deleted, (2) balance reconciliation compares DAT file balances against SQLite snapshots to detect direct file tampering.

## Prerequisites

- **Python 3.8+** (required)
- **GnuCOBOL 3.x** (optional — falls back to Python-only mode)

```bash
# Ubuntu/Debian
sudo apt install gnucobol

# macOS
brew install gnucobol

# Windows (MSYS2)
pacman -S mingw-w64-x86_64-gnucobol
```

## Status Codes

COBOL programs return standard status codes in all responses:

| Code | Meaning |
|------|---------|
| `00` | Success |
| `01` | Insufficient funds |
| `02` | Limit exceeded |
| `03` | Invalid account/operation |
| `04` | Account frozen |
| `99` | System error |

## License

MIT
