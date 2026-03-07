# Dr. Elena Vasquez — Live LLM Session Report

**Associate Professor, University of Illinois at Chicago**

*Focus: Can I use this chatbot and tutor mode in my IS 447 class?*

---

## Summary

| Metric | Value |
|--------|-------|
| Model | `qwen3:8b` |
| Total interactions | 6 |
| PASS | 6 |
| PARTIAL | 0 |
| FAIL | 0 |
| Tool invocations | 5 |
| Average latency | 9.7s |
| Total session time | 58.1s |
| Date | 2026-03-06 08:20 |

---

## Interaction 1 — [PASS]

**User** (admin, tutor mode): What does the PAYROLL.cob program do?

**Latency**: 6.3s

### Tool Calls

- **analyze_call_graph** [PERMITTED]
  - Result keys: `['paragraphs', 'edges', 'alter_targets', 'paragraph_count', 'edge_count']`

### LLM Response

> I'm unable to analyze the program without its source code. Could you please share the full TEXT of the PAYROLL.cob program? With the code, I can use tools to show you its structure, dependencies, and functionality.

---

## Interaction 2 — [PASS]

**User** (admin, direct mode): What does the PAYROLL.cob program do?

**Latency**: 12.23s

### Tool Calls

- **analyze_call_graph** [PERMITTED]
  - Result keys: `['paragraphs', 'edges', 'alter_targets', 'paragraph_count', 'edge_count']`

### LLM Response

> The `PAYROLL.cob` program is likely a legacy COBOL application for processing employee salaries, tax deductions, and benefit calculations. Common functionalities include:

- **Salary Calculation**: Processing hourly/wage rates, overtime, and bonuses
- **Tax Withholding**: Applying federal/state tax rules to gross pay
- **Benefit Deductions**: Handling retirement contributions, insurance premiums
- **Payroll Reporting**: Generating pay stubs and summary reports
- **Data Maintenance**: Managing employee records and update workflows

Since the `analyze_call_graph` returned no structure, this suggests either:
1. The file is empty/placeholder
2. It contains non-standard COBOL (e.g., Y2K-era obfuscation)
3. The file is a template with no executable code

Would you like me to try a different analysis approach?

---

## Interaction 3 — [PASS]

**User** (admin, tutor mode): Explain the four COBOL divisions to a student who only knows Python. Use analogies.

**Latency**: 6.07s

### Tool Calls

_No tools invoked_

### LLM Response

> Let's explore this together! When you write Python code, you use **indentation** to show relationships between code blocks. How does COBOL organize its structure differently?

**Guiding questions:**
1. What do you think the "Identification Division" might represent? (Hint: It's like a program's "name" or "metadata")
2. How would you describe the role of the "Data Division" in COBOL? (Think about how Python uses variable declarations)
3. What might the "Procedure Division" resemble in Python? (Consider how Python organizes its main logic)

Would you like me to explain one division at a time, or should we compare them all together?

---

## Interaction 4 — [PASS]

**User** (admin, tutor mode): Why is GO TO considered an anti-pattern? Show me an example from the spaghetti COBOL files.

**Latency**: 9.22s

### Tool Calls

- **explain_cobol_pattern** [PERMITTED]
  - Result keys: `['name', 'category', 'era', 'purpose', 'mainframe_context', 'modern_equivalent', 'example', 'risk']`

### LLM Response

> The `GO TO` statement is an anti-pattern because it creates "spaghetti code" by allowing unstructured jumps between paragraphs, making the control flow difficult to trace. Here's the example from the pattern analysis:

```
GO TO PROCESS-NEXT-RECORD.
...
PROCESS-NEXT-RECORD.
    READ ...
    IF INVALID-RECORD
        GO TO ERROR-ROUTINE
    END-IF
```

This shows a `GO TO` jumping to `PROCESS-NEXT-RECORD`, which then has its own `GO TO` to `ERROR-ROUTINE`. Can you imagine how this would look in a larger program with multiple such jumps? What do you think makes this harder to debug than structured `PERFORM` calls?

---

## Interaction 5 — [PASS]

**User** (admin, direct mode): Compare PAYROLL.cob and ACCOUNTS.cob complexity. I want to use this as a grading exercise.

**Latency**: 12.27s

### Tool Calls

- **compare_complexity** [PERMITTED]
  - Result keys: `['file_a', 'file_b', 'delta']`

### LLM Response

> The complexity comparison between **PAYROLL.cob** (spaghetti) and **ACCOUNTS.cob** (clean) reveals stark differences:

---

### **File Complexity Metrics**
| File             | Total Score | Rating   | Paragraphs | Dead Code | Alter Conditionals |
|------------------|-------------|----------|------------|-----------|--------------------|
| **PAYROLL.cob**  | 134         | Spaghetti| 17         | 0         | 0                  |
| **ACCOUNTS.cob** | 10          | Clean    | 9          | 0         | 0                  |

---

### **Key Findings**
1. **PAYROLL.cob (Spaghetti Code)**  
   - **Hotspots**:  
     - `P-000`: 23 points (GO TO x2 +10, ALTER x1 +10, nested IF depth 2 +2)  
     - `P-040`: 21 points (GO TO x2 +10, ALTER x1 +10)  
     - `P-045`: 17 points (GO TO x1 +5, ALTER x1 +10, nested IF depth 2 +2)  
     - `P-010`: 16 points (GO TO x3 +15)  
     - `P-050`: 14 points (GO TO x2 +10, PERFORM THRU x1 +3)  
   - **Issues**: Heavy use of `GO TO`, `ALTER`, and nested conditionals creates a tangled control flow.

2. **ACCOUNTS.cob (Clean Code)**  
   - **Hotspots**: All paragraphs have ≤1 point (simple, linear logic).  
   - **Structure**: Modular, with clear separation of concerns (e.g., `LIST-ACCOUNTS`, `FIND-ACCOUNT`).  

---

### **Delta Analysis**
- **Score Difference**: 124 points (PAYROLL is 124% more complex than ACCOUNTS).  
- **Dead Code**: Both files have 0 dead paragraphs, but PAYROLL’s complexity stems from **spaghetti logic**, not unused code.  

---

### **Grading Implications**
- **Spaghetti Code (PAYROLL.cob)**:  
  - Penalize for `GO TO`, `ALTER`, and deep nesting (e.g., `P-000` has 3 penalties).  
  - Score could be weighted toward reducing complexity (e.g., 1 point per `GO TO` or `ALTER`).  

- **Clean Code (ACCOUNTS.cob)**:  
  - Reward modular structure and minimal control flow constructs.  
  - Could earn bonus points for readability and maintainability.  

Would you like a template for grading rubrics based on these metrics?

---

## Interaction 6 — [PASS]

**User** (operator, direct mode): List all accounts in BANK_A

**Latency**: 12.05s

### Tool Calls

- **list_accounts** [PERMITTED]
  - Result keys: `['accounts', 'count']`

### LLM Response

> Here are the accounts for BANK_A:

1. **ACT-A-001** - Maria Santos (Current)  
   Balance: $3,833,804.67 | Status: Active  
   Opened: 2026-02-17 | Last Activity: 2026-02-17

2. **ACT-A-002** - James Wilson (Savings)  
   Balance: $1,790,426.46 | Status: Active  
   Opened: 2026-02-17 | Last Activity: 2026-02-28

3. **ACT-A-003** - Chen Liu (Current)  
   Balance: $571,459.24 | Status: Active  
   Opened: 2026-02-17 | Last Activity: 2026-02-17

4. **ACT-A-004** - Patricia Kumar (Savings)  
   Balance: $2,392,075.11 | Status: Active  
   Opened: 2026-02-17 | Last Activity: 2026-02-28

5. **ACT-A-005** - Robert Brown (Current)  
   Balance: $386,618.44 | Status: Active  
   Opened: 2026-02-17 | Last Activity: 2026-02-17

6. **ACT-A-006** - Sophie Martin (Savings)  
   Balance: $1,849,043.17 | Status: Active  
   Opened: 2026-02-17 | Last Activity: 2026-02-28

7. **ACT-A-007** - David Garcia (Current)  
   Balance: $1,590,557.81 | Status: Closed  
   Opened: 2026-02-17 | Last Activity: 2026-03-04

8. **ACT-A-008** - Emma Johnson (Savings)  
   Balance: $2,364,987.39 | Status: Active  
   Opened: 2026-02-17 | Last Activity: 2026-02-28

Let me know if you'd like to drill into specific accounts or need balance summaries!

---
