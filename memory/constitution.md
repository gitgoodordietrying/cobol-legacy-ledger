# Project Constitution: cobol-legacy-ledger

**Version**: 1.0.0
**Ratification Date**: 2026-02-17
**Last Amended**: 2026-02-17

## Purpose

A non-invasive Python cryptographic integrity layer for inter-bank COBOL batch settlement systems. Demonstrates how to wrap legacy financial systems with modern observability and verification without replacing the underlying COBOL.

---

## Core Principles

### Principle 1: COBOL Immutability

The compiled COBOL binaries MUST NOT be modified. All business logic execution remains in unmodified COBOL code. The Python layer observes, verifies, and records — but never changes COBOL behavior.

**Rationale**: Legacy financial systems cannot be altered without extensive testing and regulatory approval. Wrapping instead of replacing preserves production stability and audit trails.

---

### Principle 2: Cryptographic Integrity at Every Step

All transactions MUST be recorded in a tamper-evident SHA-256 hash chain with HMAC signatures. Detection of any modification MUST occur in <100ms. No transaction is trusted until it passes three-point verification: chain linkage, hash match, and signature validity.

**Rationale**: Financial transactions require proof of integrity. Detecting tampering quickly prevents cascading failures across the network.

---

### Principle 3: Per-Node Database Isolation

Each of the 6 nodes (5 banks + clearing house) MUST have its own SQLite database file (bank_a.db, bank_b.db, clearing.db, etc.). No shared ledger. No cross-node table joins at the database layer.

**Rationale**: In production, nodes operate independently with eventual consistency. Node isolation ensures the system works if the network partitions. Cross-node verification happens at the application layer (Phase 2).

---

### Principle 4: Specification-Driven Implementation

All COBOL implementation MUST follow the detailed specification in `02_COBOL_AND_DATA.md`. No "copy from v1 repo" shortcuts. Every program, copybook, and data format is explicitly defined.

**Rationale**: AI agents execute specs consistently. Spec-driven development prevents vague instructions and catches ambiguities before coding begins.

---

### Principle 5: 6-Node Fixed Architecture

Exactly 6 nodes: BANK_A, BANK_B, BANK_C, BANK_D, BANK_E, CLEARING. No shortcuts to 2-node systems. No dynamic node discovery. The clearing house is a hub; banks are spokes.

**Rationale**: Financial settlement networks use hub-and-spoke topology. This design allows Phase 2 cross-node verification where the clearing house's authoritative record proves what should have happened.

---

### Principle 6: Production-Grade COBOL

All COBOL source MUST include production-style headers (System, Node, Author, Purpose, Operations, Files, Copybooks, Output Format, Exit Codes, Dependencies, Change Log). All known bugs MUST be documented in `cobol/KNOWN_ISSUES.md` with production fix recommendations.

**Rationale**: Legacy systems are not toys. Headers and documentation ensure maintainability and signal authenticity in interviews.

---

### Principle 7: Phase Gates Enforce Quality

Phase 1 gate (build.sh + seed.sh + accounts + transaction + chain) MUST pass before Phase 2 planning. No partial implementations. No "it works on my machine" claims without verified gates.

**Rationale**: Gates catch issues early. Incomplete phases cascade problems downstream.

---

### Principle 8: Testability at Boundaries

Every requirement MUST be testable. If you can't write a test, the requirement is too vague. Smoke test runs first (SMOKETEST.cob) before any other COBOL work.

**Rationale**: Vague specs cause rework. Testable requirements align human and agent expectations.

---

### Principle 9: No Node.js Ever

Frontend is static HTML/CSS/JavaScript served by Python. No npm, no build process, no webpack, no React. Phase 3 assets are pure files, deployable to GitHub Pages.

**Rationale**: Financial institutions distrust JavaScript build systems. Static files are simple, auditable, and require zero infrastructure.

---

### Principle 10: Clear Error Paths

Every COBOL program MUST handle and display error codes (00=success, 01=NSF, 02=limit, 03=invalid account, 04=frozen, 99=file error). The Python bridge MUST parse these and report them clearly. No silent failures.

**Rationale**: Financial errors must be visible. Silent failures hide money.

---

## Governance

- **MAJOR version**: Principle changes (requires project lead approval)
- **MINOR version**: New principles (requires consensus)
- **PATCH version**: Clarifications to existing principles

All specs and plans MUST include a **Constitution Check** documenting how they respect each principle.

---

## Interview Narrative (Principle 11: Authenticity)

The deliverable tells a story:
1. **The Problem**: "Banks connect through COBOL batch settlement systems written in the 1970s. When something goes wrong in the middle, detection depends on manual reconciliation."
2. **The Solution**: "I built a Python observation layer that proves every transaction is intact and consistent. No changes to COBOL. No changes to data files. Just cryptographic verification."
3. **The Demo**: "Five banks, one clearing house. Money flows between them. We corrupt one bank's ledger. The clearing house independently detects it because the transaction it records doesn't match the bank's ledger."
4. **The Lesson**: "COBOL isn't the problem. Lack of observability is. You can build modern infrastructure around legacy systems without replacing them."

**Rationale**: Interview credibility comes from authenticity. Production-grade systems, documented bugs, realistic constraints, and clear narrative win trust.
