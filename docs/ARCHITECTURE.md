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
COBOL-BANKING/data/BANK_A/
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
                  │ COBOL-BANKING│  load_accounts_from_dat│
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

## Layer 3: REST API + LLM Tool-Use

### API Layer (FastAPI)

```
HTTP Request → FastAPI Router → RBAC Check → Bridge/Settlement/Codegen → JSON Response
                                    │
                              X-User / X-Role
                              request headers
```

The REST API wraps all existing bridge/settlement/integrity/codegen modules as HTTP endpoints. No new business logic — pure HTTP translation. Endpoints at `/api/nodes`, `/api/codegen`, `/api/settlement`, `/api/chat`, `/api/health`.

### LLM Architecture

```
User Message → ConversationManager → LLM Provider → Tool Calls?
                     │                                    │
                     │                              ┌─────┴──────┐
                     │                              │  Yes        │ No
                     │                              ▼             ▼
                     │                        ToolExecutor    Final Response
                     │                         │  │  │  │
                     │                     RBAC Validate Dispatch Audit
                     │                              │
                     │                        Bridge/Codegen
                     │                              │
                     └──── Tool Result ◄────────────┘
```

**Key design**: The LLM is a *client*, not a controller. It calls the same bridge/codegen methods the CLI calls, gated by RBAC. Every tool call is visible and auditable.

### Provider Security Model

| Provider | Security Level | Data Location | Configuration |
|----------|---------------|---------------|---------------|
| Ollama | LOCAL | Machine-local | Default, zero-trust |
| Anthropic | CLOUD | API servers | Opt-in via ANTHROPIC_API_KEY |

Providers are swappable at runtime via `POST /api/provider/switch`.

### Tool Definitions (17 tools, 6 categories)

| Category | Tools | Required Permission |
|----------|-------|-------------------|
| Banking | list_accounts, get_account | accounts.read |
| Banking | process_transaction, transfer | transactions.process |
| Banking | verify_chain, verify_all_nodes | chain.verify |
| Banking | view_chain | chain.view |
| Banking | run_reconciliation | transactions.read |
| Codegen | parse_cobol, generate_cobol, edit_cobol, validate_cobol | cobol.read |
| Analysis | analyze_call_graph, trace_execution | cobol.read |
| Analysis | analyze_data_flow, detect_dead_code | cobol.read |
| Analysis | explain_cobol_pattern | cobol.read |

## Layer 4: Web Console

### Dashboard + Chatbot SPA

```
Browser → /console/index.html → Static HTML/CSS/JS (no Node.js)
                                        │
                ┌───────────────────────┼───────────────────────┐
                │                       │                       │
          Dashboard View           Chat View              SSE Stream
          ┌──────────┐          ┌──────────┐          ┌──────────┐
          │ Network   │          │ Messages │          │ EventSource│
          │ Graph     │          │ Tool     │          │ /api/sim  │
          │ (SVG)     │          │ Cards    │          │ /events   │
          │ Controls  │          │ Provider │          └──────────┘
          │ Feed      │          │ Sessions │
          │ COBOL     │          └──────────┘
          │ Viewer    │
          └──────────┘
```

**Architecture**: Static HTML/CSS/JS served via FastAPI `StaticFiles`. No build step, no npm. All API calls use `fetch()` with `X-User`/`X-Role` headers. SSE uses native `EventSource` with query-param auth.

**Glass morphism design**: Dark void background (#0a0e1a), `backdrop-filter: blur(16px) saturate(180%)`, rgba borders, per-bank color palette.

| Component | File | Purpose |
|-----------|------|---------|
| Network Graph | `network-graph.js` | SVG hub-and-spoke, 6 nodes, edge flash animations |
| Dashboard | `dashboard.js` | Sim controls, event feed (SSE), stats, tamper/verify |
| COBOL Viewer | `cobol-viewer.js` | Syntax highlighting, auto-navigation by tx type |
| Chat | `chat.js` | LLM messages, tool call cards, provider switching |
| API Client | `api-client.js` | Fetch wrapper with RBAC headers, SSE factory |

---

## COBOL Programs

| Program | Lines | Purpose |
|---------|-------|---------|
| `TRANSACT.cob` | 677 | Transaction engine: DEPOSIT, WITHDRAW, TRANSFER, BATCH |
| `SIMULATE.cob` | 497 | Deterministic daily transaction generator |
| `SETTLE.cob` | 392 | 3-leg inter-bank clearing house settlement |
| `ACCOUNTS.cob` | 383 | Account lifecycle: CREATE, READ, UPDATE, CLOSE, LIST |
| `FEES.cob` | 344 | Monthly maintenance fee processing |
| `RECONCILE.cob` | 334 | Transaction-to-balance reconciliation |
| `INTEREST.cob` | 321 | Monthly interest accrual for savings accounts |
| `REPORTS.cob` | 294 | Reporting: STATEMENT, LEDGER, EOD, AUDIT |
| `SMOKETEST.cob` | 239 | Compilation verification — START HERE for learning |
| `VALIDATE.cob` | 218 | Business rules: status, balance, and limit checks |
| **Total** | **3,699** | |

All programs share copybooks: `ACCTREC.cpy` (account record), `TRANSREC.cpy` (transaction record), `COMCODE.cpy` (status codes and constants).

### Payroll Sidecar Programs (Layer 5 — Intentional Spaghetti)

| Program | Lines | Era | Anti-Patterns |
|---------|-------|-----|---------------|
| `PAYROLL.cob` | ~400 | 1974 | GO TO network, ALTER, magic numbers, dead P-085 |
| `TAXCALC.cob` | ~300 | 1983 | 6-level nested IF, PERFORM THRU, misleading comments |
| `DEDUCTN.cob` | ~280 | 1991 | Structured/spaghetti hybrid, mixed COMP types, dead code |
| `PAYBATCH.cob` | ~400 | 2002 | Y2K dead code, excessive DISPLAY tracing, half-finished refactor |
| **Total** | **~1,380** | | See `COBOL-BANKING/payroll/KNOWN_ISSUES.md` |

These programs are **intentionally** written with anti-patterns for educational contrast with the clean banking COBOL above. All issues are documented in the anti-pattern catalog.

## Python Observation Layer

| Module | Lines | Purpose |
|--------|-------|---------|
| `bridge.py` | 1,438 | COBOL subprocess execution, DAT file I/O, SQLite sync |
| `simulator.py` | 1,284 | Multi-day banking simulation engine |
| `cli.py` | 1,087 | Command-line interface |
| `cross_verify.py` | 469 | Cross-node integrity verification + tamper detection |
| `settlement.py` | 398 | 3-step inter-bank settlement coordinator |
| `integrity.py` | 305 | SHA-256 hash chain + HMAC verification |
| `auth.py` | 192 | RBAC — 4 roles, 18 permissions (incl. payroll) |
| `payroll_bridge.py` | ~350 | Payroll COBOL bridge (Mode A/B) + settlement integration |
| `cobol_analyzer/` | ~600 | Static analysis: call graph, data flow, dead code, complexity, knowledge base |
| **Total** | **~6,100** | |

## Layer 5: Legacy Payroll Sidecar

The payroll sidecar exists to teach the **contrast** between clean COBOL (Layers 1-4) and real-world legacy spaghetti. While banking COBOL follows modern structured practices, the payroll programs reproduce patterns from 1974-2002 mainframe development.

```
COBOL-BANKING/payroll/data/PAYROLL/
  EMPLOYEES.DAT    ← 25 employees (95-byte fixed-width, LINE SEQUENTIAL)

                    ┌─────────────────────────────┐
                    │      PayrollBridge           │
                    │   (payroll_bridge.py)        │
                    ├──────────┬──────────────────┤
                    │ Mode A   │    Mode B         │
                    │ COBOL    │    Python          │
                    │ subprocess│   file I/O        │
                    └─────┬────┴────────┬─────────┘
                          │             │
                          ▼             ▼
                    EMPLOYEES.DAT + payroll.db
                          │
                          ▼
              Settlement transfers → existing 6-node settlement
```

**Anti-pattern catalog**: GO TO networks, ALTER (runtime branch modification), PERFORM THRU, 6-level nested IF without END-IF, mixed COMP types, misleading comments, dead code, Y2K artifacts, magic numbers. All documented in `COBOL-BANKING/payroll/KNOWN_ISSUES.md`.

**Integration**: Payroll salary deposits generate settlement transfers that flow through the existing 6-node clearing house. Per-node isolation is preserved — payroll data stays in `payroll/data/PAYROLL/` with its own SQLite database.

## Layer 5: COBOL Analysis Pipeline

The analysis pipeline provides **structured context** that makes an LLM better at understanding spaghetti COBOL. An LLM cannot reliably trace GO TO chains across 500 lines, but deterministic tools can — then the LLM interprets the structured results.

| Module | Purpose |
|--------|---------|
| `call_graph.py` | Paragraph dependency graph: PERFORM, GO TO, ALTER, PERFORM THRU, fall-through edges |
| `data_flow.py` | Field read/write tracking per paragraph, single-field tracing |
| `dead_code.py` | Unreachable paragraph detection (REACHABLE, DEAD, ALTER_CONDITIONAL) |
| `complexity.py` | Per-paragraph complexity scoring: GO TO (+5), ALTER (+15), nested IF (+3/level) |
| `knowledge_base.py` | COBOL pattern encyclopedia (~20 entries: ALTER, COMP-3, PERFORM THRU, etc.) |

**LLM integration**: 5 analysis tools (17 total), enhanced system prompt with call-graph-first strategy. The prompt instructs the LLM to always run `analyze_call_graph` before attempting to explain unfamiliar COBOL.

**Web console**: Analysis tab with interactive call graph SVG, execution trace visualization, and side-by-side compare viewer (spaghetti vs clean).

## Verification Performance

Cross-node verification of all 6 chains completes in <5ms (typical). This includes:
- Walking all hash chains
- Comparing DAT vs DB balances for 42 accounts
- Cross-referencing all settlement entries

The entire `prove.sh` demonstration runs in ~10 seconds, dominated by COBOL compilation and node seeding — verification itself is near-instantaneous.
