# Enterprise Payroll Processor — Fictional History

**System**: ENTERPRISE PAYROLL PROCESSOR
**Original Platform**: IBM System/370 Model 158
**Current Platform**: IBM zSeries 900 (migrated 2002)
**Language**: COBOL-74 / COBOL-85 hybrid

---

## Origin Story (Fictional)

The Enterprise Payroll Processor was first written in March 1974 by **JRK** (initials only — full name lost to time) on an IBM System/370 at First National Insurance Corp. It processed payroll for 200 employees using punch cards for input and line printer for output.

### The Developers

| Initials | Era | Style | Contribution |
|----------|-----|-------|-------------|
| JRK | 1974-1978 | COBOL-68 purist | Original system. GO TO everything. ALTER for flow control. Cryptic names. |
| PMR | 1983-1997 | COBOL-85 adopter | Added tax engine. PERFORM THRU. Better names, but hardcoded values override copybook. |
| SLW | 1991-1995 | Half-and-half | Benefits/deductions. Started structured, reverted to GO TO under pressure. |
| Y2K Team | 1999-2002 | Corporate mandate | Date remediation. Parallel old/new fields. Excessive DISPLAY tracing. Half-finished refactor. |

### Why It Looks Like This

Every anti-pattern in this code exists because it was the correct decision at the time:

- **GO TO networks** (1974): COBOL-68 had no structured programming. GO TO was the only flow control besides PERFORM.
- **ALTER statements** (1974): Runtime flow modification was an "advanced technique" taught in IBM training courses.
- **PERFORM THRU** (1983): The COBOL-85 standard introduced structured constructs, but PERFORM THRU was the bridge — "call this range of paragraphs as one unit."
- **Nested IF without END-IF** (1983): END-IF didn't exist in COBOL-68. PMR used COBOL-85 in some places but fell back to old habits in others.
- **Mixed COMP types** (1991): SLW used whatever USAGE felt right. The compiler handles conversions silently.
- **Dead code everywhere** (1993-2002): Removing code requires a change request, testing, and sign-off. It's easier to "disable" it.
- **Y2K artifacts** (2002): The remediation was done under extreme time pressure. "Add new fields, keep old fields, ship it."

### The Cardinal Rule

> "If it works in production, don't touch it." — Every COBOL maintainer, ever

This system processes 25 employees across 5 banks. In production, it would handle 50,000+ employees with the same code structure. The only difference would be the array sizes and the JCL resource allocations.

---

## Programs

| Program | Lines | Purpose | Key Anti-Patterns |
|---------|-------|---------|-------------------|
| PAYROLL.cob | ~450 | Main controller | GO TO network, ALTER, magic numbers, dead paragraph |
| TAXCALC.cob | ~350 | Tax computation | 6-level nested IF, PERFORM THRU, misleading comments, dead code |
| DEDUCTN.cob | ~300 | Deductions | Structured/spaghetti hybrid, mixed COMP types, dead garnishment code |
| PAYBATCH.cob | ~280 | Batch output | Y2K dead code, excessive DISPLAY tracing, half-finished refactor |

## Output Format

PAYBATCH produces pipe-delimited output compatible with the banking system's settlement format:

```
SOURCE_ACCT|DEST_ACCT|AMOUNT|Payroll deposit — Name|DAY
```

This feeds directly into the existing OUTBOUND.DAT → SETTLE.cob pipeline.

## See Also

- `KNOWN_ISSUES.md` — Detailed catalog of every anti-pattern (the educational crown jewel)
- `../KNOWN_ISSUES.md` — Banking system known issues (clean code issues)
