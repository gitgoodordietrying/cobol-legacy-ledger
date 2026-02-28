"""
knowledge_base -- COBOL pattern/idiom/anti-pattern encyclopedia.

Provides structured explanations for ~30 COBOL patterns that an LLM might
encounter in legacy code. Each entry includes:
    - pattern name
    - era (when it was common)
    - purpose (what it does)
    - mainframe_context (why it existed on mainframes)
    - modern_equivalent (what you'd use today)
    - example (short code snippet)
    - risk (what can go wrong)

The LLM tool `explain_cobol_pattern` queries this knowledge base. When the
LLM encounters an unfamiliar pattern in spaghetti code, it can look it up
here for authoritative context rather than guessing.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class PatternEntry:
    """A single knowledge base entry."""
    name: str
    category: str      # "control_flow", "data", "file_io", "mainframe", "anti_pattern"
    era: str           # e.g., "COBOL-68", "COBOL-85", "1990s", "Y2K"
    purpose: str
    mainframe_context: str
    modern_equivalent: str
    example: str
    risk: str


# ── Knowledge Base Entries ────────────────────────────────────────

ENTRIES: Dict[str, PatternEntry] = {}


def _add(name, **kwargs):
    ENTRIES[name.lower()] = PatternEntry(name=name, **kwargs)


# ── Control Flow Patterns ─────────────────────────────────────────

_add("ALTER",
     category="control_flow", era="COBOL-68",
     purpose="Modify a GO TO target at runtime. ALTER P-030 TO PROCEED TO P-040 changes where GO TO in P-030 jumps.",
     mainframe_context="Before EVALUATE (COBOL-85), ALTER was the standard way to implement computed dispatch. IBM training courses taught it as an 'advanced technique'.",
     modern_equivalent="EVALUATE TRUE / WHEN condition / PERFORM paragraph. Or simply use a flag variable and IF/ELSE.",
     example="ALTER P-030 TO PROCEED TO P-040.\n...\nP-030.\n    GO TO P-040.  *> Target changed by ALTER above",
     risk="Extremely difficult to trace statically. The GO TO target is invisible in the source — you must simulate ALTER execution to know where it goes. Deprecated in COBOL-85, removed in COBOL-2002.")

_add("GO TO",
     category="control_flow", era="COBOL-68",
     purpose="Unconditional jump to a named paragraph. Transfers control without returning.",
     mainframe_context="COBOL-68 had limited structured programming. GO TO was the primary flow control mechanism alongside PERFORM.",
     modern_equivalent="PERFORM (structured call with return), inline PERFORM blocks, or EVALUATE/WHEN.",
     example="GO TO PROCESS-NEXT-RECORD.\n...\nPROCESS-NEXT-RECORD.\n    READ ...",
     risk="Creates 'spaghetti code' — tangled control flow that's hard to follow. GO TO chains across multiple paragraphs are nearly impossible to trace mentally.")

_add("PERFORM THRU",
     category="control_flow", era="COBOL-85",
     purpose="Execute a range of paragraphs as a single unit. PERFORM A THRU B executes A, then all paragraphs between A and B, then B.",
     mainframe_context="Before inline PERFORM, THRU was the way to group related paragraphs. Common in tax calculations, report formatting, and batch processing.",
     modern_equivalent="Inline PERFORM blocks, or simply PERFORM each paragraph individually.",
     example="PERFORM COMPUTE-FED THRU COMPUTE-EXIT.\n...\nCOMPUTE-FED.\n    ...\nCOMPUTE-STATE.\n    ...\nCOMPUTE-EXIT.\n    EXIT.",
     risk="Inserting a new paragraph between the start and end of the range SILENTLY adds it to execution. No compiler warning. This is one of the most dangerous COBOL patterns.")

_add("Nested IF without END-IF",
     category="control_flow", era="COBOL-68",
     purpose="Multiple IF statements terminated by a single period. Each ELSE matches the nearest unmatched IF.",
     mainframe_context="COBOL-68 had no END-IF. A period (.) terminated ALL open IF scopes simultaneously. Indentation was cosmetic only.",
     modern_equivalent="IF/ELSE/END-IF blocks, or EVALUATE/WHEN for multi-way branching.",
     example="IF A > 10\n    IF B > 20\n        MOVE 1 TO C\n    ELSE\n        MOVE 2 TO C.  *> Period ends BOTH IFs",
     risk="Adding a line in the wrong place changes which IF each ELSE matches. A misplaced period terminates all open scopes. These bugs are nearly invisible in code review.")

_add("Paragraph fall-through",
     category="control_flow", era="COBOL-68",
     purpose="When a paragraph ends without GO TO or STOP RUN, execution continues into the next paragraph sequentially.",
     mainframe_context="COBOL paragraphs are not functions — they're labeled sections of sequential code. Fall-through is the default behavior.",
     modern_equivalent="Explicit PERFORM calls. Each paragraph should end with a GO TO, STOP RUN, or EXIT (or be called via PERFORM which returns automatically).",
     example="PARA-A.\n    MOVE 1 TO X.\n*> Falls through to PARA-B\nPARA-B.\n    MOVE 2 TO Y.",
     risk="Unintentional fall-through can cause paragraphs to execute when they shouldn't. Adding a new paragraph between two existing ones changes the fall-through chain.")

# ── Data Patterns ─────────────────────────────────────────────────

_add("COMP-3",
     category="data", era="COBOL-68",
     purpose="Packed decimal storage. Each byte holds 2 decimal digits. The last nibble is the sign (C=positive, D=negative, F=unsigned).",
     mainframe_context="IBM System/360+ has hardware instructions (AP, SP, MP, DP) that operate directly on packed decimal. No conversion needed — the CPU arithmetic unit works natively with this format. 50% denser than DISPLAY for numeric data.",
     modern_equivalent="No direct equivalent. Modern CPUs use IEEE 754 floating-point. Java's BigDecimal and Python's decimal.Decimal are the closest in terms of exact decimal arithmetic.",
     example="05  SALARY  PIC S9(7)V99 COMP-3.\n*> 9 digits → ceil((9+1)/2) = 5 bytes\n*> Value 75000.00 stored as: 07 50 00 00 0C",
     risk="COMP-3 fields contain binary data that can't be displayed or printed directly. Hex dumps are needed to read them. LINE SEQUENTIAL files cannot contain COMP-3 data.")

_add("COMP",
     category="data", era="COBOL-68",
     purpose="Binary integer storage. PIC S9(4) COMP = 2-byte halfword. PIC S9(9) COMP = 4-byte fullword.",
     mainframe_context="IBM mainframes have fast binary arithmetic (AR, SR, MR, DR). COMP fields are used for counters, indexes, and integer operations where speed matters more than decimal precision.",
     modern_equivalent="int / long in any modern language.",
     example="05  HOURS-WORKED  PIC S9(4) COMP.\n*> 2 bytes, range -32768 to +32767",
     risk="Mixing COMP and COMP-3 in arithmetic causes implicit conversions that add CPU overhead. On batch runs processing millions of records, this matters.")

_add("COPY REPLACING",
     category="data", era="COBOL-85",
     purpose="Include a copybook but substitute specific text. COPY 'RECORD.cpy' REPLACING ==OLD-PREFIX== BY ==NEW-PREFIX==.",
     mainframe_context="Allows reusing record layouts across programs that name fields differently. A single copybook can serve multiple programs.",
     modern_equivalent="Generics, templates, or simply renaming after import.",
     example="COPY 'EMPREC.cpy' REPLACING\n    ==EMP-== BY ==WS-EMP-==.",
     risk="REPLACING operates on text, not identifiers. It can match inside comments, strings, or partial names, causing unexpected substitutions.")

_add("88-level condition",
     category="data", era="COBOL-68",
     purpose="Named boolean test on a field's value. 88 ACCT-ACTIVE VALUE 'A'. Makes IF ACCT-ACTIVE equivalent to IF ACCT-STATUS = 'A'.",
     mainframe_context="Self-documenting code pattern. Instead of IF ACCT-STATUS = 'A', you write IF ACCT-ACTIVE. The 88-level both documents valid values and makes code more readable.",
     modern_equivalent="Enum values with named constants, or boolean properties.",
     example="05  STATUS  PIC X(1).\n    88  IS-ACTIVE    VALUE 'A'.\n    88  IS-CLOSED    VALUE 'C'.\n...\nIF IS-ACTIVE\n    PERFORM PROCESS-ACCOUNT.",
     risk="None — this is one of COBOL's best features. Universally recommended.")

_add("REDEFINES",
     category="data", era="COBOL-68",
     purpose="Overlay one data item on top of another, sharing the same memory. Different 'views' of the same bytes.",
     mainframe_context="Memory was expensive. REDEFINES allowed multiple interpretations of the same storage area — e.g., a date field viewed as 8 individual digits or as 4 two-digit groups.",
     modern_equivalent="Union types in C, or struct reinterpretation. Python's struct.unpack with different format strings.",
     example="05  DATE-FULL   PIC 9(8).\n05  DATE-PARTS REDEFINES DATE-FULL.\n    10  DATE-YYYY  PIC 9(4).\n    10  DATE-MM    PIC 9(2).\n    10  DATE-DD    PIC 9(2).",
     risk="Changing one view changes all views. If DATE-FULL is 20260227, DATE-YYYY is 2026. But writing 99 to DATE-MM makes DATE-FULL contain 20269927 — corrupting the year.")

_add("Implied decimal (V)",
     category="data", era="COBOL-68",
     purpose="V marks where the decimal point is, but no actual '.' is stored. PIC 9(5)V99 stores 7 digits; the V tells COBOL that the last 2 are cents.",
     mainframe_context="Fixed-point arithmetic avoids floating-point rounding errors. Financial systems require exact decimal math — $10.00 + $10.00 must equal $20.00, never $19.999999.",
     modern_equivalent="decimal.Decimal in Python, BigDecimal in Java, or integer-cents representation (store $10.00 as 1000).",
     example="05  BALANCE  PIC S9(10)V99.\n*> 12 bytes. Value 12345.67 stored as '000001234567'",
     risk="If you MOVE a V99 field to a field without V, the decimal position is lost. COBOL doesn't warn — it just truncates or pads.")

# ── Mainframe Patterns ────────────────────────────────────────────

_add("JCL job card",
     category="mainframe", era="1960s-present",
     purpose="Job Control Language (JCL) tells the mainframe operating system (z/OS) what program to run, what files to use, and what resources to allocate.",
     mainframe_context="On mainframes, you don't 'run a program' — you submit a JOB. The JOB card specifies accounting info, job name, priority class, and output routing. EXEC runs the program. DD statements define file assignments.",
     modern_equivalent="Docker Compose, Kubernetes manifests, or shell scripts that configure environment before running a program.",
     example="//PAYRL100 JOB (ACCT),'PAYROLL',CLASS=A\n//STEP01   EXEC PGM=PAYROLL\n//EMPFILE  DD DSN=PAYRL.EMPLOYEE.MASTER,DISP=SHR",
     risk="JCL syntax errors prevent the job from running. A missing comma or wrong DSN can take down a batch run.")

_add("VSAM",
     category="mainframe", era="1970s-present",
     purpose="Virtual Storage Access Method — IBM's high-performance file system for mainframes. Supports keyed (KSDS), sequential (ESDS), and relative (RRDS) datasets.",
     mainframe_context="VSAM replaced older access methods (ISAM, BSAM). It provides indexed access, buffering, and concurrent access control. Most COBOL batch programs read/write VSAM files.",
     modern_equivalent="Database tables with indexes. SQLite, PostgreSQL, etc.",
     example="SELECT ACCOUNT-FILE ASSIGN TO ACCTFILE\n    ORGANIZATION IS INDEXED\n    ACCESS MODE IS DYNAMIC\n    RECORD KEY IS ACCT-ID.",
     risk="VSAM files can become fragmented, requiring periodic reorganization (IDCAMS REPRO). CI/CA splits degrade performance.")

_add("CICS",
     category="mainframe", era="1970s-present",
     purpose="Customer Information Control System — IBM's online transaction processing (OLTP) monitor. Runs COBOL programs interactively (not batch).",
     mainframe_context="CICS handles terminal I/O, transaction management, and concurrency for online COBOL programs (e.g., bank teller screens, airline reservation systems).",
     modern_equivalent="Application server (Tomcat, Express.js) + REST API framework.",
     example="EXEC CICS SEND MAP('ACCTMAP')\n    FROM(ACCT-DISPLAY-AREA)\n    MAPSET('ACCTSET')\nEND-EXEC.",
     risk="CICS programs share memory — a bug in one program can crash others. ABEND codes (like ASRA) indicate specific failure types.")

_add("ABEND codes",
     category="mainframe", era="1960s-present",
     purpose="Abnormal End codes identify why a mainframe program crashed. System ABENDs start with S (e.g., S0C7 = data exception). User ABENDs start with U.",
     mainframe_context="When a COBOL program ABENDs, the system produces a dump with the ABEND code. S0C7 (data exception) is the most common — it means a non-numeric character was found in a numeric field during arithmetic.",
     modern_equivalent="Exception types (NullPointerException, ValueError) with stack traces.",
     example="*> S0C7: Tried to add 'ABC' to a COMP-3 field\n*> S0C4: Tried to access memory outside program area\n*> U4038: Application-defined error (custom ABEND)",
     risk="ABENDs in batch runs can leave files in inconsistent states if COMMIT/ROLLBACK isn't properly handled.")

# ── Anti-Patterns ─────────────────────────────────────────────────

_add("Dead code",
     category="anti_pattern", era="All eras",
     purpose="Code that can never execute because no PERFORM, GO TO, or fall-through reaches it.",
     mainframe_context="Removing code from production COBOL requires a change request, regression testing, and sign-off. It's universally considered 'safer' to leave dead code in place. Over decades, dead paragraphs accumulate.",
     modern_equivalent="Delete the code. Version control preserves the history.",
     example="*> This paragraph is never called:\nDEAD-PARA.\n    COMPUTE X = Y * Z.\n    DISPLAY 'THIS NEVER RUNS'.",
     risk="Dead code misleads readers into thinking it executes. It makes the program longer and harder to understand.")

_add("Misleading comments",
     category="anti_pattern", era="All eras",
     purpose="Comments that describe what the code USED to do, not what it currently does.",
     mainframe_context="Comments are not verified by the compiler. When code changes but comments don't, the comments become lies. This is the #1 documentation bug in legacy COBOL.",
     modern_equivalent="Self-documenting code with meaningful variable names. Comments should explain WHY, not WHAT.",
     example="*> PMR: 'Apply standard 5% state tax'\nCOMPUTE TAX = GROSS * 0.0725.  *> Actually 7.25%!",
     risk="New developers trust comments over code. 'Fixing' the code to match the comments introduces bugs.")

_add("Magic numbers",
     category="anti_pattern", era="All eras",
     purpose="Unnamed numeric literals scattered throughout code. COMPUTE PAY = HOURS * 40 — what does 40 mean?",
     mainframe_context="Early COBOL had limited naming conventions. Numeric literals were used for 'obvious' values like 40 hours/week or 1.5x overtime. But they're only obvious to the original developer.",
     modern_equivalent="Named constants: STANDARD-HOURS = 40, OT-MULTIPLIER = 1.50.",
     example="IF HOURS > 40\n    COMPUTE OT = (HOURS - 40) * RATE * 1.50.",
     risk="When the value changes, you must find every occurrence. Searching for '40' returns hundreds of false positives.")

_add("Mixed COMP types",
     category="anti_pattern", era="1970s-1990s",
     purpose="Using COMP-3, COMP, and DISPLAY in the same arithmetic expression. Each requires implicit type conversion.",
     mainframe_context="Different developers preferred different USAGE types. The compiler handles conversions silently, so there's no immediate error. But each conversion adds CPU instructions.",
     modern_equivalent="Consistent typing. In Python, don't mix int and Decimal in the same expression without explicit conversion.",
     example="ADD MED-COST (COMP-3) TO DENTAL-COST (COMP)\n    GIVING TOTAL (DISPLAY).\n*> Two implicit conversions per ADD",
     risk="Performance degradation in batch runs. On millions of records, implicit conversions add measurable CPU time.")

_add("Y2K artifacts",
     category="anti_pattern", era="1999-2002",
     purpose="Code added during Y2K remediation that was never cleaned up: parallel 2-digit and 4-digit date fields, windowing techniques, validation routines.",
     mainframe_context="Y2K was done under extreme time pressure with massive budgets. The strategy was 'add new fields, keep old fields, ship it.' Nobody went back to clean up.",
     modern_equivalent="N/A — just use 4-digit years from the start.",
     example="05  DATE-FULL  PIC 9(8).  *> Y2K: new\n05  DATE-SHORT PIC 9(6).  *> Pre-Y2K: old\n*> Both are populated. Both are written. Neither is removed.",
     risk="Y2K windowing (YY >= 50 → 19XX) will break again in 2050. Dead Y2K validation code wastes cycles.")


class KnowledgeBase:
    """Query interface for the COBOL knowledge base."""

    def lookup(self, pattern_name: str) -> Optional[Dict]:
        """Look up a pattern by name (case-insensitive)."""
        entry = ENTRIES.get(pattern_name.lower())
        if entry is None:
            # Try partial match
            for key, e in ENTRIES.items():
                if pattern_name.lower() in key:
                    entry = e
                    break
        if entry is None:
            return None
        return {
            "name": entry.name,
            "category": entry.category,
            "era": entry.era,
            "purpose": entry.purpose,
            "mainframe_context": entry.mainframe_context,
            "modern_equivalent": entry.modern_equivalent,
            "example": entry.example,
            "risk": entry.risk,
        }

    def list_patterns(self, category: str = None) -> List[Dict]:
        """List all patterns, optionally filtered by category."""
        results = []
        for entry in ENTRIES.values():
            if category and entry.category != category:
                continue
            results.append({
                "name": entry.name,
                "category": entry.category,
                "era": entry.era,
                "purpose": entry.purpose[:100] + "..." if len(entry.purpose) > 100 else entry.purpose,
            })
        return results

    def search(self, query: str) -> List[Dict]:
        """Search patterns by keyword in name, purpose, or context."""
        query_lower = query.lower()
        results = []
        for entry in ENTRIES.values():
            searchable = f"{entry.name} {entry.purpose} {entry.mainframe_context} {entry.modern_equivalent}".lower()
            if query_lower in searchable:
                results.append(self.lookup(entry.name))
        return results
