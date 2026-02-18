# Handoff Package: cobol-legacy-ledger

This directory contains the complete specification for the **cobol-legacy-ledger** system — a non-invasive cryptographic integrity layer for inter-bank COBOL batch settlement.

## Documents

| Doc | Purpose | For Whom |
|-----|---------|----------|
| `COBOL_STYLE_REFERENCE.md` | Smoke test, reference program with annotations, GnuCOBOL cheat sheet | COBOL implementer — **read before any COBOL coding** |
| `COBOL_SUPPLEMENTS.md` | Batch trace format spec, KNOWN_ISSUES template, program header template, talking points | COBOL implementer |
| `01_MASTER_OVERVIEW.md` | Vision, architecture, phasing, constraints | Everyone — read this first |
| `02_COBOL_AND_DATA.md` | COBOL programs, copybooks, record layouts, bank seeding, batch scripts, account roster | COBOL implementer, data engineer |
| `03_PYTHON_BACKEND.md` | Bridge, integrity engine, auth, CLI, Python environment setup | Python backend engineer |
| `04_FRONTEND_AND_DEMO.md` | § Phase 1 demo script + verification; § Phase 3 static console (HTML/CSS/JS) | Frontend engineer, QA |

## Getting Started

1. **Read** `01_MASTER_OVERVIEW.md` (10 min)
2. **Understand** the three-phase architecture
3. **Check** which phase you're implementing
4. **Reference** the phase-specific document
5. **Build** the artifacts described

## Implementation Order

**Phase 1** (this handoff) — COBOL foundation + Python bridge (gate: 6 nodes seed + bridge can read accounts)

**Phase 2** — Settlement coordinator + cross-node integrity verification (gate: corrupt BANK_C, caught by other 4 in <100ms)

**Phase 3** — Static HTML console + demo script deployment (gate: full demo runs end-to-end)

## Critical Decisions (Locked)

- **COBOL source:** Write our own (6-node foundation already seeded with copybooks)
- **COBOL bugs:** DO NOT FIX. Copy v1 code exactly. These are intentional interview talking points.
- **Node count:** 6 nodes (5 banks + central clearing house)
- **Account types:** Customer accounts (banks) vs. nostro accounts (clearing house)
- **No Node.js:** Ever. Dropped entirely. Phase 3 is static HTML served by Python.
- **Pitch:** "The COBOL never changes. The .DAT files never change. We just wrapped them in cryptographic verification."

## File Structure (Final)

```
cobol-legacy-ledger/
├── cobol/
│   ├── src/
│   │   ├── ACCOUNTS.cob
│   │   ├── TRANSACT.cob
│   │   ├── VALIDATE.cob
│   │   └── REPORTS.cob
│   ├── copybooks/
│   │   ├── ACCTREC.cpy
│   │   ├── TRANSREC.cpy
│   │   └── COMCODE.cpy
│   ├── bin/              (gitignored, generated)
│   └── KNOWN_ISSUES.md
├── banks/
│   ├── BANK_A/ ─┐
│   ├── BANK_B/  │ (8: BANK_A/C/E; 7: BANK_B; 6: BANK_D)
│   ├── BANK_C/  │
│   ├── BANK_D/  │
│   ├── BANK_E/ ─┘
│   └── CLEARING/         (5 nostro accounts)
├── python/
│   ├── bridge.py
│   ├── integrity.py
│   ├── auth.py
│   ├── cli.py                ← CLI commands (init-db, seed-demo, etc.)
│   ├── requirements.txt
│   └── tests/
├── scripts/
│   ├── build.sh
│   ├── setup.sh
│   └── seed.sh
├── docs/
│   ├── README.md         (project overview)
│   ├── ARCHITECTURE.md   (90-second read for senior dev)
│   └── handoff/          (← you are here)
│       ├── 00_README.md  (this file)
│       ├── 01_MASTER_OVERVIEW.md
│       ├── 02_COBOL_AND_DATA.md
│       ├── 03_PYTHON_BACKEND.md
│       └── 04_FRONTEND_AND_DEMO.md
├── console/              (reserved for Phase 3)
├── arcade/               (reserved for Phase 4)
├── data/                 (gitignored, generated)
└── .gitignore
```

## .gitignore Contents

```
cobol/bin/
data/
python/venv/
__pycache__/
*.pyc
*.db
.server_key
.api_keys
*.egg-info/
.DS_Store
```

---

## Quick Questions?

**Q: Can I fix bugs I find in the COBOL?**
A: No. Copy exactly as-is from v1. Document bugs in `cobol/KNOWN_ISSUES.md`. These are intentional and serve a narrative purpose in interviews.

**Q: What do I do if I hit a blocker?**
A: Check the Phase 1 verification gate in `01_MASTER_OVERVIEW.md`. If you're blocked on something not in that gate, it's Phase 2.

**Q: Is the clearing house data structure different?**
A: No. Same COBOL programs, same ACCOUNTS.DAT format. CLEARING just contains 5 nostro accounts instead of customer accounts. COBOL doesn't know the difference.

**Q: What if `cobc` (GnuCOBOL) isn't installed?**
A: Phase 1 gate skips compilation with a clear message. The system is designed to work with or without COBOL. The Python bridge can execute if COBOL is available; otherwise it read-only demonstrates the SQLite layer.

---

**Start with `01_MASTER_OVERVIEW.md`.**
