# Phase 1 Requirements Checklist

**Feature**: Phase 1 Foundation (cobol-legacy-ledger)
**Status**: Specification Complete — Ready for Clarification
**Date**: 2026-02-17

---

## Specification Completeness

### Mandatory Sections Present

- [x] Overview + MVP success criteria
- [x] 6 user stories (P1 priority) with acceptance scenarios
- [x] 30+ functional requirements (FR-001 through FR-030)
- [x] 10 success criteria (SC-001 through SC-010)
- [x] Out-of-scope section (Phase 2+)
- [x] Edge cases (EC-001 through EC-006)
- [x] Dependencies & integration
- [x] Constitution check (all 10 principles covered)

### User Stories Testability

- [x] US1 (COBOL Foundation) — acceptance scenarios are testable
- [x] US2 (Data Seeding) — can verify account counts and formats
- [x] US3 (Python Bridge) — can call methods and assert return values
- [x] US4 (Integrity Chain) — can corrupt data and detect tampering
- [x] US5 (Seeding Modes) — can run both Mode A and Mode B
- [x] US6 (Verification Gate) — 5-step gate is executable

### Functional Requirements Clarity

- [x] All COBOL programs named (ACCOUNTS, TRANSACT, VALIDATE, REPORTS)
- [x] All data formats specified (70-byte ACCTREC, 103-byte TRANSREC)
- [x] All API methods specified (list_accounts, get_account, process_transaction)
- [x] All error codes specified (00, 01, 02, 03, 04, 99)
- [x] All file paths explicit (cobol/src/, cobol/copybooks/, banks/, python/)
- [x] All scripts named (build.sh, seed.sh, setup.sh, demo.sh)

### Edge Cases Documented

- [x] Balance going negative (BATCH-FEE bug)
- [x] Daily limit reset per run (documented, not fixed)
- [x] Account ID clobbering (fragile TRANSFER pattern)
- [x] OCCURS overflow (101st account lost)
- [x] No COBOL fallback (Mode B)
- [x] Empty chain handling

---

## Technical Specifications Review

### COBOL Layer

- [x] All 4 programs specified with operations
- [x] All 3 copybooks specified (ACCTREC, TRANSREC, COMCODE)
- [x] Record layouts precise (byte counts, field specs)
- [x] NOSTRO ID format fixed (NST-BANK-A, 10 chars)
- [x] Known issues section required
- [x] Production headers required (from COBOL_SUPPLEMENTS.md)
- [x] Smoke test referenced (SMOKETEST.cob must run first)

### Python Layer

- [x] COBOLBridge class interface fully specified
- [x] Database schema specified (accounts, transactions, chain_entries)
- [x] Error handling specified (status codes)
- [x] Path resolution clarified (absolute binary path, relative cwd)
- [x] Subprocess execution documented
- [x] Fallback mode (Mode B without COBOL) documented

### Data Files

- [x] ACCOUNTS.DAT format (fixed-width, 70 bytes)
- [x] TRANSACT.DAT format (fixed-width, 103 bytes)
- [x] BATCH-INPUT.DAT format (pipe-delimited, 4-5 fields)
- [x] Account counts per node (8+7+8+6+8 customers, 5 nostro)
- [x] NOSTRO account IDs (NST-BANK-A through NST-BANK-E)
- [x] Sample batches for all 6 nodes (provided in 02_COBOL_AND_DATA.md)

### Database Schema

- [x] Per-node database isolation (bank_a.db, bank_b.db, etc.)
- [x] Tables: accounts, transactions, chain_entries, api_keys
- [x] Chain entry fields: chain_index, tx_id, tx_hash, prev_hash, signature, status
- [x] Integrity fields: SHA-256 hash, HMAC signature
- [x] Verification logic: chain linkage + hash match + signature validity

### Scripts

- [x] build.sh: compiles COBOL with `-I ../copybooks` flag
- [x] seed.sh: creates ACCOUNTS.DAT, TRANSACT.DAT, BATCH-INPUT.DAT for all 6 nodes
- [x] setup.sh: creates venv and installs dependencies
- [x] demo.sh: runs Phase 1 scenario end-to-end
- [x] All scripts handle errors gracefully

---

## Ambiguities Check

### Resolved Ambiguities

- [x] Database scheme: Clarified as per-node (bank_a.db, clearing.db, etc.)
- [x] NOSTRO IDs: Fixed as NST-BANK-A (10 chars, not NOSTRO-BANK-A)
- [x] Account total: 42 (37 customer + 5 nostro, not 37)
- [x] Build flags: `-I ../copybooks` required for COPY statements
- [x] COBOL source: Implement from spec, not copy from v1 repo
- [x] Fallback behavior: Python-only mode if COBOL unavailable

### Remaining Ambiguities

- [ ] None identified — spec is complete and testable

---

## Gate Status

**Gate**: Specification must be complete and pass ambiguity review before clarification.

**Result**: ✅ PASS

All sections complete. No critical ambiguities. Ready for `/speckit.clarify` phase.

---

## Constitution Alignment

- [x] COBOL Immutability — Spec preserves COBOL unchanged
- [x] Cryptographic Integrity — SHA-256 + HMAC specified in FR-019 through FR-023
- [x] Per-Node Database — Per-node db_path default specified in FR-013
- [x] Specification-Driven — All implementation follows 02_COBOL_AND_DATA.md
- [x] 6-Node Architecture — Exactly 6 nodes, hub-and-spoke topology
- [x] Production COBOL — Headers and KNOWN_ISSUES.md required
- [x] Phase Gates — 5-step Phase 1 gate blocks Phase 2
- [x] Testability — All acceptance scenarios are testable
- [x] No Node.js — Static HTML/CSS/JS only (Phase 3)
- [x] Clear Error Paths — Status codes specified (00, 01, 02, 03, 04, 99)

---

## Next Steps

1. Run `/speckit.clarify` to identify any remaining ambiguities
2. Update spec based on clarification answers
3. Run `/speckit.plan` to create technical implementation plan
4. Run `/speckit.tasks` to generate task breakdown
5. Run `/speckit.build` to execute Phase 1 implementation

---

**Spec Status**: COMPLETE AND READY ✅
