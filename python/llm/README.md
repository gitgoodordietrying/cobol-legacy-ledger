# LLM Tool-Use Layer

LLM-as-client architecture: an AI chatbot that can query accounts, process transactions, verify chains, and work with COBOL source — all gated by the same RBAC permissions as the CLI and REST API.

## Architecture

```
User Message
    │
    ▼
ConversationManager
    │
    ├── Sends messages + tool definitions to Provider
    │       │
    │       ├── OllamaProvider (LOCAL — zero data exfiltration)
    │       └── AnthropicProvider (CLOUD — opt-in, requires API key)
    │
    ├── If tool calls in response:
    │       │
    │       ▼
    │   ToolExecutor (4-layer pipeline)
    │       ├── Layer 1: RBAC Gate (check role permissions)
    │       ├── Layer 2: Input Validation (node, account_id, amount)
    │       ├── Layer 3: Dispatch (→ bridge / settlement / codegen)
    │       └── Layer 4: Audit (→ SQLite audit log)
    │
    └── Loop until final text response or MAX_TOOL_ITERATIONS
```

## Tool Catalog

| Tool | Permission | Description |
|------|-----------|-------------|
| `list_accounts` | accounts.read | List accounts for a banking node |
| `get_account` | accounts.read | Get account details by ID |
| `process_transaction` | transactions.process | Deposit, withdraw, transfer, interest, fee |
| `verify_chain` | chain.verify | Verify SHA-256 integrity chain |
| `view_chain` | chain.view | View recent chain entries |
| `transfer` | transactions.process | Inter-bank 3-leg settlement |
| `verify_all_nodes` | chain.verify | Cross-node verification (all 6 nodes) |
| `run_reconciliation` | transactions.read | Transaction-to-balance reconciliation |
| `parse_cobol` | cobol.read | Parse COBOL source → AST summary |
| `generate_cobol` | cobol.read | Generate COBOL from template |
| `edit_cobol` | cobol.read | Edit COBOL via AST operations |
| `validate_cobol` | cobol.read | Validate against project conventions |

## Provider Comparison

| Feature | Ollama (LOCAL) | Anthropic (CLOUD) |
|---------|---------------|-------------------|
| Security | Zero data exfiltration | Data sent via HTTPS |
| Default | Yes (always available) | Opt-in (requires API key) |
| Models | llama3.1, mistral, etc. | claude-sonnet-4-20250514 |
| Tool-use | Function calling API | Native tool_use blocks |
| Cost | Free (local compute) | Pay per token |

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `llama3.1` | Default Ollama model |
| `ANTHROPIC_API_KEY` | (none) | Anthropic API key (enables cloud provider) |

## Audit Log Schema

Every tool invocation is recorded in `llm_audit.db`:

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Auto-increment primary key |
| timestamp | TEXT | UTC ISO 8601 timestamp |
| user_id | TEXT | User who made the request |
| role | TEXT | User's RBAC role |
| provider | TEXT | LLM provider that requested the tool |
| tool_name | TEXT | Tool that was called |
| params | TEXT | JSON-serialized parameters |
| result | TEXT | JSON-serialized result (nullable) |
| permitted | INTEGER | 1=allowed, 0=RBAC denied |
| error | TEXT | Error message (empty on success) |

## Module Reference

| Module | Purpose |
|--------|---------|
| `tools.py` | 12 tool definitions (Anthropic-compatible JSON Schema) |
| `tool_executor.py` | 4-layer RBAC-gated dispatch pipeline |
| `providers.py` | Ollama + Anthropic provider adapters |
| `conversation.py` | Session management + tool-use resolution loop |
| `audit.py` | SQLite audit log for all tool invocations |
