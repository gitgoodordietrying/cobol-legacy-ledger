# Marcus Chen — Live LLM Session Report

**Senior COBOL Systems Programmer, IBM Z**

*Focus: Does the chatbot actually understand COBOL and the banking system?*

---

## Summary

| Metric | Value |
|--------|-------|
| Model | `qwen3:8b` |
| Total interactions | 5 |
| PASS | 5 |
| PARTIAL | 0 |
| FAIL | 0 |
| Tool invocations | 4 |
| Average latency | 10.7s |
| Total session time | 53.4s |
| Date | 2026-03-06 08:20 |

---

## Interaction 1 — [PASS]

**User** (admin, direct mode): List all accounts in BANK_A

**Latency**: 16.36s

### Tool Calls

- **list_accounts** [PERMITTED]
  - Result keys: `['accounts', 'count']`

### LLM Response

> Here are the accounts in BANK_A:

1. **ACT-A-001** - Maria Santos (C) $3,833,804.67 (Active, opened 2026-02-17, last active 2026-02-17)
2. **ACT-A-002** - James Wilson (S) $1,790,426.46 (Active, opened 2026-02-17, last active 2026-02-28)
3. **ACT-A-003** - Chen Liu (C) $571,459.24 (Active, opened 2026-02-17, last active 2026-02-17)
4. **ACT-A-004** - Patricia Kumar (S) $2,392,075.11 (Active, opened 2026-02-17, last active 2026-02-28)
5. **ACT-A-005** - Robert Brown (C) $386,618.44 (Active, opened 2026-02-17, last active 2026-02-17)
6. **ACT-A-006** - Sophie Martin (S) $1,849,043.17 (Active, opened 2026-02-17, last active 2026-02-28)
7. **ACT-A-007** - David Garcia (C) $1,590,557.81 (Closed, opened 2026-02-17, last active 2026-03-04)
8. **ACT-A-008** - Emma Johnson (S) $2,364,987.39 (Active, opened 2026-02-17, last active 2026-02-28)

Total accounts: 8  
Note: 'C' = Checking, 'S' = Savings; 'Active' status indicated by 'A', 'Closed' by 'C'

---

## Interaction 2 — [PASS]

**User** (admin, direct mode): Verify the integrity chain for BANK_A. Use the verify_chain tool.

**Latency**: 6.14s

### Tool Calls

- **verify_chain** [PERMITTED]
  - Result keys: `['valid', 'entries_checked', 'time_ms', 'first_break', 'break_type', 'details']`

### LLM Response

> The integrity chain for **BANK_A** is valid ✅  
- **Entries verified**: 45,557  
- **Verification time**: 528.6 ms  
- **Chain status**: Intact (no breaks detected)  

No issues found in the SHA-256 chain. Would you like to check another node or view recent chain entries?

---

## Interaction 3 — [PASS]

**User** (admin, direct mode): What is a nostro account in banking? Answer in 2-3 sentences.

**Latency**: 3.82s

### Tool Calls

_No tools invoked_

### LLM Response

> A **nostro account** is a bank account held by one financial institution in another bank, used to facilitate inter-bank transactions and settlements. In the 6-node network, the CLEARING house maintains nostro accounts (NST-BANK-X) for each participating bank to enable 3-leg settlement of cross-border or inter-bank transfers. These accounts act as a liquidity buffer for settlement, ensuring funds are available for transfers while maintaining balance across the network.

---

## Interaction 4 — [PASS]

**User** (admin, direct mode): Compare the complexity of PAYROLL.cob vs TRANSACT.cob using the compare_complexity tool.

**Latency**: 13.74s

### Tool Calls

- **compare_complexity** [PERMITTED]
  - Result keys: `['file_a', 'file_b', 'delta']`

### LLM Response

> The **compare_complexity** tool reveals stark differences between the legacy `PAYROLL.cob` (spaghetti code) and the cleaner `TRANSACT.cob` (moderate complexity):

---

### **Complexity Metrics**
- **PAYROLL.cob**  
  - **Total Score**: 134 (rated "spaghetti")  
  - **Paragraphs**: 17  
  - **Hotspots**:  
    - **P-000**: 23 points (GO TO x2 + ALTER x1 + nested IF depth 2)  
    - **P-040**: 21 points (GO TO x2 + ALTER x1)  
    - **P-045**: 17 points (GO TO x1 + ALTER x1 + nested IF depth 2)  
    - **P-010**: 16 points (GO TO x3)  
    - **P-050**: 14 points (GO TO x2 + PERFORM THRU x1)  

- **TRANSACT.cob**  
  - **Total Score**: 33 (rated "moderate")  
  - **Paragraphs**: 14  
  - **Hotspots**:  
    - **PROCESS-ONE-TRANSACTION**: 11 points (nested IF depth 10)  
    - **PROCESS-WITHDRAW**: 4 points (nested IF depth 4)  
    - **PROCESS-TRANSFER**: 4 points (nested IF depth 4)  
    - **GENERATE-TX-ID**: 2 points (nested IF depth 2)  

---

### **Key Observations**
1. **PAYROLL.cob** suffers from:  
   - **Spaghetti code**: Frequent `GO TO` and `ALTER` statements (e.g., P-000 has 2 `GO TO`s and 1 `ALTER`).  
   - **Deep nesting**: Some paragraphs have nested IFs up to depth 2 (P-045) or 10 (PROCESS-ONE-TRANSACTION).  
   - **Unstructured flow**: The reliance on `GO TO` and `ALTER` creates unpredictable control paths.  

2. **TRANSACT.cob** is more structured:  
   - **Nested IFs** are used but limited to depth 10 (still a concern) compared to PAYROLL's deeper nesting.  
   - **No `GO TO`/`ALTER`**: Uses structured control flow (e.g., `PERFORM`/`RETURN`).  

3. **Delta**:  
   - **Score Difference**: 101 points (PAYROLL is 3x more complex).  
   - **Dead Code**: Both have 0 dead paragraphs, but PAYROLL’s complexity stems from unstructured logic.  

---

### **Recommendations**
- **Refactor PAYROLL.cob**: Replace `GO TO`/`ALTER` with structured `PERFORM` and `RETURN` for maintainability.  
- **Audit nested IFs**: Deep nesting (e.g., depth 10) in TRANSACT.cob could
> ... (truncated, 2239 chars total)

---

## Interaction 5 — [PASS]

**User** (admin, direct mode): What is the ALTER statement in COBOL and why is it considered harmful?

**Latency**: 13.34s

### Tool Calls

- **explain_cobol_pattern** [PERMITTED]
  - Result keys: `['name', 'category', 'era', 'purpose', 'mainframe_context', 'modern_equivalent', 'example', 'risk']`

### LLM Response

> The **ALTER** statement in COBOL is a control-flow mechanism that dynamically changes the target of a `GO TO` statement at runtime. For example:  
```cobol
ALTER P-030 TO PROCEED TO P-040
```
This instructs the program to redirect the `GO TO P-040` in paragraph `P-030` to a different location. While it was historically used for computed dispatch (before `EVALUATE` in COBOL-85), it is **considered harmful** for several reasons:

### Why ALTER is Harmful:
1. **Unreadable Control Flow**:  
   - The `GO TO` target is modified *dynamically*, making it impossible to statically trace execution paths. This creates "spaghetti code" with hidden, runtime-dependent logic.

2. **Debugging Challenges**:  
   - Breakpoints and static analysis tools cannot predict altered paths. Debugging becomes error-prone, as the code's behavior depends on runtime state.

3. **Maintenance Risks**:  
   - Alterations are often undocumented or tied to legacy logic. Modern developers may unknowingly break behavior if they restructure code without understanding these hidden dependencies.

4. **Deprecation**:  
   - `ALTER` was deprecated in COBOL-85 and removed in COBOL-2002. Modern practices use `EVALUATE` or flag-based `IF/ELSE` structures for clarity and maintainability.

### Modern Alternatives:
- **EVALUATE**: Replaces `ALTER` for conditional branching.  
- **Flag Variables**: Use flags to simulate dynamic routing with `IF/ELSE`.  
- **Structured Programming**: Avoid `GO TO` entirely in favor of modular, hierarchical control flow.

In summary, **ALTER** is a relic of early COBOL's goto-heavy design. While it enabled advanced logic in its time, its opacity and maintenance risks make it a prime example of why structured programming practices evolved. 🚫

---
