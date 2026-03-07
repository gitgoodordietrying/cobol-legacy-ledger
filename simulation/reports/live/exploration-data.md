# System Exploration Data

```

============================================================
  1. HEALTH & OVERVIEW
============================================================
  [GET] /api/health -> 200 (3.0s)
  Version: 6.1.0, Nodes: 6
  Ollama: True, Anthropic: False
  [GET] /api/nodes -> 200 (4.37s)
  Node: None - 8 accounts, chain=0
  Node: None - 7 accounts, chain=0
  Node: None - 8 accounts, chain=0
  Node: None - 6 accounts, chain=0
  Node: None - 8 accounts, chain=0
  Node: None - 5 accounts, chain=0

============================================================
  2. BANKING DATA
============================================================
  [GET] /api/nodes/BANK_A/accounts -> 200 (2.36s)
  BANK_A: 8 accounts
  [GET] /api/nodes/BANK_B/accounts -> 200 (2.36s)
  BANK_B: 7 accounts
  [GET] /api/nodes/BANK_C/accounts -> 200 (2.37s)
  BANK_C: 8 accounts
  [GET] /api/nodes/BANK_D/accounts -> 200 (2.37s)
  BANK_D: 6 accounts
  [GET] /api/nodes/BANK_E/accounts -> 200 (2.36s)
  BANK_E: 8 accounts
  [GET] /api/nodes/CLEARING/accounts -> 200 (2.35s)
  CLEARING: 5 accounts

--- Sample accounts BANK_A ---
  [GET] /api/nodes/BANK_A/accounts -> 200 (2.35s)

--- Deposit + Withdraw ---
  [POST] /api/nodes/BANK_A/transactions -> 422 (2.35s)
  Deposit result: {"detail": [{"type": "missing", "loc": ["body", "tx_type"], "msg": "Field required", "input": {"account_id": "ACT-A-001", "type": "D", "amount": 100.0, "description": "Test deposit"}}]}
  [POST] /api/nodes/BANK_A/transactions -> 422 (2.35s)
  Withdraw result: {"detail": [{"type": "missing", "loc": ["body", "tx_type"], "msg": "Field required", "input": {"account_id": "ACT-A-001", "type": "W", "amount": 50.0, "description": "Test withdraw"}}]}

============================================================
  3. SETTLEMENT
============================================================
  [POST] /api/settlement -> 404 (2.38s)
  Settlement: status=None
  Latency: 2.38s

============================================================
  4. INTEGRITY
============================================================
  [POST] /api/verify/BANK_A -> 404 (2.43s)
  BANK_A chain: valid=None, entries=None, time=Nonems
  [POST] /api/verify/all -> 404 (2.38s)

--- Tamper Demo ---
  [POST] /api/tamper -> 404 (2.37s)
  Tamper result: {"detail": "Not Found"}
  [POST] /api/verify/BANK_C -> 404 (2.36s)
  BANK_C after tamper: valid=None, first_break=None
  [POST] /api/nodes/BANK_C/seed -> 404 (2.36s)

============================================================
  5. SIMULATION
============================================================
  [POST] /api/simulation/start -> 200 (2.37s)
  Sim start: {"status": "started", "days": 3, "seed": null}
  Sim latency: 2.37s
  [GET] /api/simulation/status -> 200 (2.41s)
  Sim status: {"running": true, "paused": false, "day": 0, "completed": 0, "failed": 0, "volume": 0.0}
  [GET] /api/transactions -> 404 (2.4s)
  Transactions response: ['detail']

============================================================
  6. ANALYSIS — CRITICAL (was broken before)
============================================================

--- Available files ---
  [GET] /api/analysis/files -> 404 (2.39s)
  Files: {"detail": "Not Found"}

--- Call Graph - PAYROLL.cob (spaghetti) ---
  [POST] /api/analysis/call-graph -> 422 (2.41s)
  Paragraphs: 0
  Edges: 0
  Edge types: set()

--- Call Graph - TRANSACT.cob (clean) ---
  [POST] /api/analysis/call-graph -> 422 (2.37s)
  Paragraphs: 0
  Edges: 0

--- Complexity - PAYROLL.cob ---
  [POST] /api/analysis/complexity -> 422 (2.54s)
  Total score: None, Rating: None

--- Complexity - TRANSACT.cob ---
  [POST] /api/analysis/complexity -> 422 (2.38s)
  Total score: None, Rating: None

--- Dead Code - PAYROLL.cob ---
  [POST] /api/analysis/dead-code -> 422 (2.39s)
  Dead code: {"detail": [{"type": "missing", "loc": ["body", "source_text"], "msg": "Field required", "input": {"filename": "PAYROLL.cob"}}]}

--- Execution Trace - PAYROLL.cob ---
  [POST] /api/analysis/trace -> 422 (2.4s)
  Steps: 0

--- Compare - PAYROLL vs TRANSACT ---
  [POST] /api/analysis/compare -> 422 (2.39s)
  A (PAYROLL): complexity=None, rating=None
  B (TRANSACT): complexity=None, rating=None
  Full response keys: ['detail']

--- Cross-file analysis ---
  [POST] /api/analysis/cross-file -> 422 (2.42s)
  Cross-file: {"detail": [{"type": "missing", "loc": ["body", "sources"], "msg": "Field required", "input": {"filenames": ["PAYROLL.cob", "TAXCALC.cob", "DEDUCTN.cob"]}}]}

--- Data Flow - PAYROLL.cob ---
  [POST] /api/analysis/data-flow -> 422 (2.4s)
  Data flow: {"detail": [{"type": "missing", "loc": ["body", "source_text"], "msg": "Field required", "input": {"filename": "PAYROLL.cob"}}]}

--- All spaghetti files analysis check ---
  [POST] /api/analysis/complexity -> 422 (2.37s)
  PAYROLL.cob: FAIL (422)
  [POST] /api/analysis/complexity -> 422 (2.36s)
  TAXCALC.cob: FAIL (422)
  [POST] /api/analysis/complexity -> 422 (2.38s)
  DEDUCTN.cob: FAIL (422)
  [POST] /api/analysis/complexity -> 422 (2.4s)
  PAYBATCH.cob: FAIL (422)
  [POST] /api/analysis/complexity -> 422 (2.37s)
  MERCHANT.cob: FAIL (422)
  [POST] /api/analysis/complexity -> 422 (2.39s)
  FEEENGN.cob: FAIL (422)
  [POST] /api/analysis/complexity -> 422 (2.37s)
  DISPUTE.cob: FAIL (422)
  [POST] /api/analysis/complexity -> 422 (2.37s)
  RISKCHK.cob: FAIL (422)

============================================================
  7. CODEGEN
============================================================
  [GET] /api/codegen/templates -> 404 (2.37s)
  Templates: {"detail": "Not Found"}
  [POST] /api/codegen/parse -> 200 (2.4s)
  Parse result: {"program_id": "TEST", "author": "", "paragraphs": [], "files": [], "copybooks": [], "working_storage_fields": 0}

============================================================
  8. LLM / CHAT
============================================================

--- Provider status ---
  [GET] /api/provider/status -> 200 (2.71s)
  Provider: {"provider": "ollama", "model": "qwen3:8b", "security_level": "LOCAL", "available": true, "error": null}

--- Switch to Ollama qwen3:8b ---
  [POST] /api/provider/switch -> 200 (2.71s)
  Switch result: {"provider": "ollama", "model": "qwen3:8b", "security_level": "LOCAL", "available": true, "error": null}

--- Chat: Hello (should explain capabilities) ---
  [POST] /api/chat -> 200 (8.82s)
  Response length: 990 chars
  Session: cdc4601b-40af-4cf4-b
  Provider: ollama, Model: qwen3:8b
  Tool calls: 0
  Response preview: I'm the banking assistant for the COBOL Legacy Ledger system. Here's what I can help with:

**Banking Operations**
- Check account balances (ACT-X-NNN format)
- Process transactions: deposits, withdrawals, transfers, fees
- Verify SHA-256 integrity chains
- Run cross-node settlement verification
- E
  Latency: 8.82s

--- Chat: List accounts (MUST use list_accounts tool) ---
  [POST] /api/chat -> 200 (15.92s)
  Tool calls: ['list_accounts']
  Response preview: Here are the accounts for BANK_A (8 accounts total):

1. **ACT-A-001** - Maria Santos (Checking)  
   Balance: $3,894,238.12 | Status: Active  
   Opened: 2026-02-17 | Last Activity: 2026-02-17

2. **ACT-A-002** - James Wilson (Savings)  
   Balance: $1,807,805.95 | Status: Active  
   Opened: 2026-
  Latency: 15.92s

--- Chat: Compare complexity (MUST use compare_complexity tool) ---
  [POST] /api/chat -> 200 (14.7s)
  Tool calls: ['compare_complexity']
  Response preview: The **compare_complexity** tool reveals stark differences between the two COBOL programs:

### 📊 **Complexity Summary**
- **PAYROLL.cob**:  
  - **Total Score**: 134 (Spaghetti)  
  - **Paragraphs**: 17  
  - **Key Hotspots**:  
    - `P-000` (23 points): Heavy use of `GO TO` (×2), `ALTER` (×1), and
  Latency: 14.7s

--- Chat: Tutor mode (should ask guiding questions) ---
  [POST] /api/chat -> 200 (6.46s)
  Tool calls: []
  Contains question mark (Socratic): True
  Response preview: The ALTER statement is a powerful but often misunderstood control flow tool in COBOL. Let me guide you to discover its purpose:

1. How do you think COBOL handles changing the execution path between paragraphs (e.g., when a condition is met)?  
2. Have you seen any code where a paragraph might be skipped or redirected based on a condition?  
3. What do you think the word "ALTER" might imply about 
  Latency: 6.46s

--- Chat: Verify chain (MUST use verify_chain tool) ---
  [POST] /api/chat -> 200 (8.75s)
  Tool calls: ['verify_chain']
  Response preview: The integrity chain for **BANK_B** has been verified successfully:

- **Status:** ✅ Valid  
- **Entries Checked:** 44,627  
- **Verification Time:** 294.0 ms  
- **Breaks Detected:** None  

The chain is fully intact with no discrepancies. No further action required.
  Latency: 8.75s

============================================================
  9. RBAC
============================================================

--- Viewer tries simulation start ---
  [POST] /api/simulation/start -> 403 (2.34s)
  Viewer sim start: code=403, response={"detail": "User viewer (role: viewer) lacks permission: transactions.process"}

--- Operator tries verify ---
  [POST] /api/verify/BANK_A -> 404 (2.37s)
  Operator verify: code=404, response={"detail": "Not Found"}

--- Viewer tries chat ---
  [POST] /api/chat -> 200 (4.27s)
  Viewer chat: code=200
  Viewer sees 0 tool calls

============================================================
  10. PAYROLL
============================================================
  [GET] /api/payroll/employees -> 200 (2.37s)
  Employees: 25
    ? | Alice Johnson | ?
    ? | Bob Martinez | ?
    ? | Carol Williams | ?
  [POST] /api/payroll/run -> 200 (2.44s)
  Payroll run: {"summary": {"total_employees": 25, "processed": 23, "skipped": 2, "batch_gross": 56738.76, "batch_net": 31053.8, "run_date": "20260306", "period": 5}, "stubs_count": 23, "transfers_count": 23, "stubs": [{"emp_id": "EMP-001", "emp_name": "Alice Johnson", "period": 5, "run_date": "20260306", "gross": 2884.62, "fed_tax": 634.62, "state_tax": 209.13, "fica": 220.67, "deductions": 196.0, "net": 1624.2

============================================================
  11. WEB CONSOLE CHECK
============================================================
  Console HTML: 200, 19533 bytes
  Dashboard tab: True
  Analysis tab: True
  Chat tab: True
  ARIA accessibility: True
  Health indicator: True
  CSS variables.css: 200, 2702 bytes
  CSS layout.css: 200, 4432 bytes
  CSS dashboard.css: 200, 11426 bytes
  CSS chat.css: 200, 8534 bytes
  CSS analysis.css: 200, 8965 bytes

============================================================
  SUMMARY STATS
============================================================
  Server version: 6.1.0
  Total nodes: 6
  Ollama available: True
  Spaghetti files analyzed: 8/8
```
