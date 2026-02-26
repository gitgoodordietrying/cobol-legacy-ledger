# REST API Layer

FastAPI REST layer wrapping the existing bridge, settlement, codegen, and LLM modules as HTTP endpoints.

## Quick Start

```bash
pip install -e ".[dev]"
uvicorn python.api.app:app --reload
# Open http://localhost:8000/docs for interactive Swagger UI
```

## Endpoint Reference

### Banking (`/api`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/nodes` | accounts.read | List all 6 nodes with status |
| GET | `/api/nodes/{node}/accounts` | accounts.read | List accounts for a node |
| GET | `/api/nodes/{node}/accounts/{id}` | accounts.read | Get single account |
| POST | `/api/nodes/{node}/transactions` | transactions.process | Process deposit/withdraw/transfer |
| GET | `/api/nodes/{node}/chain` | chain.view | View integrity chain entries |
| POST | `/api/nodes/{node}/chain/verify` | chain.verify | Verify chain integrity |
| POST | `/api/settlement/transfer` | transactions.process | Inter-bank 3-leg settlement |
| POST | `/api/settlement/verify` | chain.verify | Cross-node verification |

### Codegen (`/api/codegen`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/codegen/parse` | None | Parse COBOL source → AST summary |
| POST | `/api/codegen/generate` | None | Template → COBOL source |
| POST | `/api/codegen/edit` | None | AST operation → modified source |
| POST | `/api/codegen/validate` | None | Validate against conventions |

### Chat (`/api`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/chat` | Any role | Send message, get response + tool calls |
| GET | `/api/chat/history/{id}` | Any role | Get conversation history |
| POST | `/api/provider/switch` | None | Switch LLM provider |
| GET | `/api/provider/status` | None | Current provider info |

### Health (`/api`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/health` | None | System health check |

## Authentication

Demo-grade header-based auth (not for production):

```bash
# Admin — full access
curl -H "X-User: admin" -H "X-Role: admin" http://localhost:8000/api/nodes

# Viewer — read-only
curl -H "X-User: viewer" -H "X-Role: viewer" http://localhost:8000/api/nodes/BANK_A/accounts

# Operator — can transact
curl -H "X-User: operator" -H "X-Role: operator" \
  -X POST http://localhost:8000/api/nodes/BANK_A/transactions \
  -H "Content-Type: application/json" \
  -d '{"account_id": "ACT-A-001", "tx_type": "D", "amount": 100, "description": "Deposit"}'
```

### Roles

| Role | Permissions |
|------|------------|
| admin | Full access (all operations) |
| auditor | Read + chain verification |
| operator | Read + transactions (no chain verify) |
| viewer | Read-only |

## Request/Response Examples

### List Accounts

```bash
curl -H "X-User: admin" -H "X-Role: admin" \
  http://localhost:8000/api/nodes/BANK_A/accounts | jq
```

```json
[
  {
    "account_id": "ACT-A-001",
    "name": "Alice Johnson",
    "account_type": "C",
    "balance": 15000.00,
    "status": "A",
    "open_date": "20260101",
    "last_activity": "20260217"
  }
]
```

### Process Transaction

```bash
curl -X POST -H "X-User: admin" -H "X-Role: admin" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/nodes/BANK_A/transactions \
  -d '{"account_id": "ACT-A-001", "tx_type": "D", "amount": 500, "description": "Payroll"}' | jq
```

```json
{
  "status": "00",
  "tx_id": "TRX-A-000001",
  "new_balance": 15500.00,
  "message": "Transaction successful"
}
```

### Verify Chain

```bash
curl -X POST -H "X-User: admin" -H "X-Role: admin" \
  http://localhost:8000/api/nodes/BANK_A/chain/verify | jq
```

```json
{
  "valid": true,
  "entries_checked": 42,
  "time_ms": 3.2,
  "first_break": null,
  "break_type": null
}
```
