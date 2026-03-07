# Polish Roadmap — COBOL Legacy Ledger v6.1.0

**Created**: 2026-03-04
**Purpose**: Comprehensive quality pass addressing every issue discovered in the full-codebase audit.
**Goal**: Portfolio-grade polish — exemplary code quality across all layers.

---

## Phase Overview

| Phase | Focus | Issues | Priority |
|-------|-------|--------|----------|
| **Phase 1** | Security & Correctness | 2 critical bugs | P0 — MUST fix |
| **Phase 2** | Python Error Handling & Robustness | 4 backend issues | P1 — Important |
| **Phase 3** | Frontend Bug Fixes | 4 JS/CSS bugs | P1 — Important |
| **Phase 4** | Accessibility (WCAG 2.1) | 3 a11y gaps | P2 — Should fix |
| **Phase 5** | Test Coverage Gaps — Endpoints | 2 untested endpoints + error paths | P2 — Should fix |
| **Phase 6** | Test Coverage Gaps — Edge Cases | Missing boundary/malformed/concurrent tests | P2 — Should fix |
| **Phase 7** | Frontend Polish & Design Tokens | 3 minor CSS/UX items | P3 — Nice to have |
| **Phase 8** | Documentation & Config Cleanup | Stale strings, git hygiene | P3 — Nice to have |
| **Phase 9** | Final Verification | Full test run + Docker build | Gate |

**Total**: 28 discrete issues across 9 phases.

---

## Phase 1: Security & Correctness (P0)

### 1.1 — Path Traversal in Codegen Endpoints

**File**: `python/api/routes_codegen.py` lines 59-63, 190-194
**Risk**: Any authenticated user (including VIEWER) can read arbitrary server files via `{"file_path": "../../../../etc/passwd"}`.

**Fix**:
- Add a `_validate_cobol_path(file_path: str)` helper that resolves the path and asserts it falls within allowed COBOL source directories (`COBOL-BANKING/src/`, `COBOL-BANKING/payroll/src/`, `COBOL-BANKING/copybooks/`, `COBOL-BANKING/payroll/copybooks/`).
- Raise `HTTPException(403)` if the resolved path escapes the allowed directories.
- Apply the guard in both `parse_cobol` (line 59) and `validate_cobol` (line 190) before calling `parser.parse_file()`.
- Add tests: valid path succeeds, `../../../etc/passwd` returns 403, absolute path outside project returns 403.

### 1.2 — Payroll Routes Ignore X-Role Header

**File**: `python/api/routes_payroll.py` lines 55-59
**Bug**: `_get_auth()` reads `X-Role` then discards it — always calls `get_auth_context(user)` without role.

**Fix**:
- Align `_get_auth()` with the canonical implementation in `dependencies.py:get_auth()`: parse `X-Role` via `Role(role_str.lower())`, pass both `user` and `role` to `get_auth_context(user, role)`.
- Better yet: eliminate `_get_auth()` entirely and use the shared `get_auth` dependency from `dependencies.py` (DRY principle — one auth path, not two).
- Add test: non-demo user with `X-Role: operator` gets operator permissions on payroll endpoints, not viewer.

---

## Phase 2: Python Error Handling & Robustness (P1)

### 2.1 — SSE Broadcast Race Condition

**File**: `python/api/routes_simulation.py` lines 65, 93-100, 252-281
**Bug**: `_event_queues` is a plain `list` mutated from background simulation thread (`broadcast()`) and async event loop (`event_generator()`). Can crash with `RuntimeError: list changed size during iteration`.

**Fix**:
- Add `_event_queues_lock = threading.Lock()` at module level.
- Wrap all mutations (`append`, `remove`, iteration in `broadcast`) with `with _event_queues_lock:`.
- In `event_generator()` finally block, acquire lock before removing queue.

### 2.2 — Swallowed Exception in list_transactions

**File**: `python/api/routes_simulation.py` lines 355-360
**Bug**: `except Exception: return []` silently hides corrupt DB, lock errors, missing tables. Violates "Clear Error Paths" principle.

**Fix**:
- Add logging: `logger.error("Failed to list transactions for %s: %s", node, exc)`.
- Raise `HTTPException(500, detail=f"Database error for {node}")` instead of returning empty list.
- Add test: patch `bridge.db.execute` to raise, assert 500 response.

### 2.3 — Unhandled ValueError in Payroll Bridge

**File**: `python/payroll_bridge.py` lines 175-196
**Bug**: `int()` calls on DAT file fields (`salary`, `hourly_rate`, `hours_worked`, `pay_periods`, `tax_bracket`, `k401_pct`) propagate `ValueError` as unhandled 500 if data is non-numeric.

**Fix**:
- Wrap each numeric conversion in a helper: `_safe_int(value, default=0) -> int`.
- Log a warning when a field fails to parse, include the employee ID for traceability.
- Add test: construct a malformed employee record, verify graceful fallback.

### 2.4 — TOCTOU Race on chain_index

**File**: `python/integrity.py` lines 158-167
**Bug**: `SELECT MAX(chain_index)` followed by `INSERT` without wrapping in a transaction. Concurrent `append()` calls can hit `UNIQUE constraint failed`.

**Fix**:
- Wrap the SELECT + INSERT in an explicit transaction (`BEGIN IMMEDIATE` to acquire write lock immediately).
- Alternatively, use `INSERT INTO chain_entries (chain_index, ...) VALUES ((SELECT COALESCE(MAX(chain_index), -1) + 1 FROM chain_entries), ...)` as a single atomic statement.
- Add test: simulate concurrent appends to same chain, verify no UNIQUE violations.

---

## Phase 3: Frontend Bug Fixes (P1)

### 3.1 — showToast('error') Uses Nonexistent CSS Class

**File**: `console/js/analysis.js` — 7 occurrences (lines 40, 84, 183, 294, 314, 363, 385)
**Bug**: CSS defines `toast--success`, `toast--danger`, `toast--warning`, `toast--info`. There is no `toast--error` class. Error toasts render unstyled.

**Fix**:
- Replace all 7 `'error'` arguments with `'danger'` in `analysis.js`.
- Audit all other JS files for `showToast` calls to confirm consistency.

### 3.2 — Chat Double-Send (No In-Flight Guard)

**File**: `console/js/chat.js` lines 72-113
**Bug**: `sendMessage()` has no guard against concurrent submissions. Rapid clicking sends duplicate messages.

**Fix**:
- Add module-level `let _sending = false;` flag.
- At top of `sendMessage()`: `if (_sending) return; _sending = true;`.
- Disable send button and textarea while sending.
- Re-enable in `finally` block: `_sending = false;`.

### 3.3 — Call Graph Node Selection Matches Wrong Nodes

**File**: `console/js/call-graph.js` lines 303-319
**Bug**: `setSelectedNode` matches on truncated display labels. Names >16 chars are truncated to 14 + `..`, so `PROCESS-TRANSFER` and `PROCESS-TRANSFER-BATCH` both match `PROCESS-TRANSFE`.

**Fix**:
- Store the full paragraph name as `data-paragraph` attribute on each `<g>` element during `render()`.
- In `setSelectedNode()`, match on `g.dataset.paragraph === name` instead of label text.

### 3.4 — SSE onerror Reconnect Stacking

**File**: `console/js/dashboard.js` lines 182-195
**Bug**: While the handler has a 2-second delay, rapid SSE errors can still stack multiple `setTimeout` + `pollStatus` calls. No dedup flag prevents concurrent recovery polls.

**Fix**:
- Add `let _sseRecovering = false;` flag.
- Guard: `if (_sseRecovering) return; _sseRecovering = true;`.
- Reset in `.finally()`: `_sseRecovering = false;`.

---

## Phase 4: Accessibility — WCAG 2.1 (P2) ✅ COMPLETE

### 4.1 — Escape Key Dismiss for All Modals

**Files**: `console/js/app.js` or new shared handler
**Gap**: COBOL modal, node popup, and onboarding overlay have no keyboard dismiss. WCAG 2.1.2 (No Keyboard Trap).

**Fix**:
- Add global `keydown` listener in `app.js`:
  ```js
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { /* close visible overlay */ }
  });
  ```
- Close whichever overlay is currently visible (check display/visibility).
- Restore focus to the element that triggered the modal.

### 4.2 — Modal ARIA Roles and Focus Management

**File**: `console/index.html` lines 364-398
**Gap**: Popup overlays lack `role="dialog"`, `aria-modal="true"`, `aria-labelledby`. Screen readers don't announce them as dialogs.

**Fix**:
- Add `role="dialog" aria-modal="true" aria-labelledby="..."` to `#nodePopup` and `#cobolModal`.
- Add `id` to each modal's header text for `aria-labelledby` target.
- On open: move focus into the modal. On close: restore focus to trigger element.

### 4.3 — Nav Tab ARIA Pattern

**File**: `console/index.html` lines 27-31, `console/js/app.js`
**Gap**: Tab buttons lack `role="tab"`, `aria-selected`, `aria-controls`. Not announced as tabs by screen readers.

**Fix**:
- Add `role="tablist"` to `.nav__tabs` container.
- Add `role="tab"` and `aria-controls="view-{name}"` to each tab button.
- In `switchView()`, toggle `aria-selected="true"/"false"` on each button.
- Add `role="tabpanel"` and `id="view-{name}"` to each view section.

---

## Phase 5: Test Coverage — Untested Endpoints & Error Paths (P2) ✅ COMPLETE

### 5.1 — Test `POST /api/analysis/cross-file`

**File to create/extend**: `python/tests/test_api_analysis.py`
**Gap**: Endpoint at `routes_analysis.py:151-161` has zero tests.

**Tests to add**:
- Valid multi-file analysis (2+ files) returns dependency graph.
- Fewer than 2 files returns 400.
- Files with COPY/CALL dependencies produce edges in result.

### 5.2 — Test `POST /api/analysis/explain-paragraph`

**File to extend**: `python/tests/test_api_analysis.py`
**Gap**: Endpoint at `routes_analysis.py:164-209` has zero tests.

**Tests to add**:
- Valid paragraph name returns explanation with complexity and connections.
- Nonexistent paragraph name returns 404.

### 5.3 — Test Codegen Error Paths

**File to extend**: `python/tests/test_api_codegen.py`
**Gap**: `file_path` branch (404), program template TypeError (400), edit ValueError/KeyError (400).

**Tests to add**:
- `POST /api/codegen/parse` with `file_path` to existing COBOL file (happy path).
- `POST /api/codegen/parse` with `file_path` to nonexistent file (404).
- `POST /api/codegen/parse` with `file_path` attempting path traversal (403, after Phase 1 fix).
- `POST /api/codegen/validate` with `file_path` (same 3 variants).
- `POST /api/codegen/generate` with `crud`/`report`/`batch` templates.
- `POST /api/codegen/edit` with invalid params for valid operation (400).

### 5.4 — Test Simulation Error Paths

**File to extend**: `python/tests/test_simulation_comprehensive.py`
**Gap**: Reset-failure 500, tamper-on-unseeded-node 400, list_transactions DB error.

**Tests to add**:
- Patch `COBOLBridge.seed_demo_data` to raise during reset, assert 500.
- Tamper on node that hasn't been seeded, assert 400.
- Patch `bridge.db.execute` to raise, assert 500 (after Phase 2.2 fix).

### 5.5 — Test Health Endpoint Edge Cases

**File to extend**: `python/tests/test_api_banking.py`
**Gap**: Degraded status path, Ollama probe exception.

**Tests to add**:
- No nodes seeded: assert `status == "degraded"`.
- Patch `httpx.get` to raise: assert `ollama_available == false` (graceful fallback).

### 5.6 — Test Chat Error Paths

**File to extend**: `python/tests/test_api_chat.py`
**Gap**: Conversation.chat() 502 path, provider switch with API key.

**Tests to add**:
- Patch conversation to raise unexpected exception, assert 502.
- Switch to Anthropic with `api_key` in request body, assert provider updates.
- Switch to invalid provider name, assert 400.

### 5.7 — Test Payroll Error Paths

**File to extend**: `python/tests/test_payroll_api.py`
**Gap**: Per-employee stub filtering, settle parameter, malformed emp_id.

**Tests to add**:
- `GET /api/payroll/stubs?emp_id=EMP-001` — filtered results.
- `POST /api/payroll/run?settle=true` — settlement integration.
- `GET /api/payroll/employees/INVALID` — malformed ID format.

---

## Phase 6: Test Coverage — Edge Cases & Boundaries (P2) ✅ COMPLETE

### 6.1 — Boundary Value Tests

**File to extend**: `python/tests/test_bridge.py`

**Tests to add**:
- Transaction with `amount=0` — rejected by Pydantic `gt=0`.
- Balance at exact fee threshold `$5,000.00` — fee IS assessed (threshold is `> 5000.00`).
- Interest tier boundary at exactly `$10,000.00`.
- Transaction description at exactly 40 characters (max_length boundary).
- Chain query with `limit=0` and `limit=500` (boundary values).
- Simulation with `days=365` (maximum allowed).

### 6.2 — Malformed Data Tests

**File to extend**: `python/tests/test_bridge.py` and `python/tests/test_payroll_bridge.py`

**Tests to add**:
- DAT record shorter than 70 bytes (truncated) — verify graceful handling.
- DAT file with Windows line endings (`\r\n`) — verify fields parse correctly.
- Same-bank transfer (`source_bank == dest_bank`) — verify behavior.
- Malformed payroll DAT record with non-numeric salary — verify fallback (after Phase 2.3 fix).

### 6.3 — Auth Edge Case Tests

**File to extend**: `python/tests/test_auth.py`

**Tests to add**:
- `X-Role: ADMIN` (uppercase) — verify case normalization works.
- `X-Role: superuser` (invalid) — verify fallback to VIEWER.
- No `X-User` header at all — verify default to "viewer".
- `X-User` with SQL-like characters (`'; DROP TABLE--`) — verify audit log handles safely.

### 6.4 — Empty/Nil Input Tests

**Tests to add across relevant test files**:
- `POST /api/chat` with `session_id: ""` (empty string) — verify behavior.
- `POST /api/analysis/call-graph` with all-whitespace source — verify handling.
- `GET /api/nodes/{node}/chain?offset=999999` — beyond end of chain.

---

## Phase 7: Frontend Polish & Design Tokens (P3) ✅ COMPLETE

### 7.1 — Design Token for Smallest Font Size

**File**: `console/css/variables.css`, `console/css/dashboard.css`
**Gap**: 6 places in `dashboard.css` use hardcoded `0.625rem`, bypassing the token system.

**Fix**:
- Add `--text-2xs: 0.625rem;` to `variables.css`.
- Replace all 6 inline `0.625rem` values in `dashboard.css` with `var(--text-2xs)`.

### 7.2 — Remove Dead CSS Class

**File**: `console/css/layout.css` lines 92-100
**Gap**: `.nav__role` class is fully defined but never used in any HTML element.

**Fix**:
- Delete the `.nav__role` rule block (8 lines).

### 7.3 — Stale Anthropic Model Name

**Files**: `python/api/routes_chat.py:194`, `python/llm/providers.py:249`, `python/api/models.py:224`
**Gap**: Hardcoded `claude-sonnet-4-20250514` — stale model identifier.

**Fix**:
- Update to `claude-sonnet-4-5-20250514` (or the current valid model ID).
- Consider making the default model configurable via environment variable (`ANTHROPIC_MODEL`), consistent with how `OLLAMA_MODEL` is already handled.

---

## Phase 8: Documentation & Config Cleanup (P3) ✅ COMPLETE

### 8.1 — EMPLOYEES.DAT Git Status

**File**: `COBOL-BANKING/payroll/data/PAYROLL/EMPLOYEES.DAT`
**Question**: This is tracked in git but CLAUDE.md says data files are gitignored.

**Decision**: This is an intentional seed fixture (25 employees, deterministic). It SHOULD be tracked — it's a seed template, not runtime data. Add a comment in `.gitignore` clarifying the distinction:
```
# Runtime data is gitignored; seed fixtures (EMPLOYEES.DAT) are tracked
COBOL-BANKING/data/
```

### 8.2 — Version Bump to 6.1.0

After all fixes are applied, bump version strings:
- `pyproject.toml`
- `python/api/app.py`
- `python/api/routes_health.py`
- `python/tests/test_api_banking.py` (health assertion)
- Update all test count references if new tests change the total.

### 8.3 — Update MEMORY.md

Update auto-memory with:
- New test count after Phase 5+6 additions.
- Record of polish roadmap completion.
- Any new patterns discovered during implementation.

---

## Phase 9: Final Verification (Gate) ✅ COMPLETE

### 9.1 — Full Test Suite
```bash
python -m pytest python/tests/ -v --ignore=python/tests/test_e2e_playwright.py -p no:asyncio
```
All tests pass, zero failures.

### 9.2 — Docker Build
```bash
docker build -t cobol-legacy-ledger .
```
Completes without error.

### 9.3 — Stale String Audit
```bash
# No stale version or count strings
grep -rn "claude-sonnet-4-20250514" python/
grep -rn "3\.0\.0" python/tests/
grep -rn "742" *.md python/README.md CONTRIBUTING.md CLAUDE.md
```
All return zero matches.

### 9.4 — Security Spot Check
```bash
# Path traversal blocked
curl -X POST http://localhost:8000/api/codegen/parse \
  -H "Content-Type: application/json" \
  -d '{"file_path": "../../../../etc/passwd"}'
# Expected: 403
```

### 9.5 — Accessibility Spot Check
- Open web console, navigate all 3 views using keyboard only.
- Open modals, dismiss with Escape.
- Verify screen reader announces tabs and dialogs correctly.

---

## Issue Cross-Reference

| # | Phase | Issue | File(s) | Severity |
|---|-------|-------|---------|----------|
| 1 | 1.1 | Path traversal in codegen | `routes_codegen.py` | Critical |
| 2 | 1.2 | Payroll RBAC ignores X-Role | `routes_payroll.py` | Critical |
| 3 | 2.1 | SSE broadcast race condition | `routes_simulation.py` | Important |
| 4 | 2.2 | Swallowed exception in list_transactions | `routes_simulation.py` | Important |
| 5 | 2.3 | Unhandled ValueError in payroll | `payroll_bridge.py` | Important |
| 6 | 2.4 | TOCTOU race on chain_index | `integrity.py` | Important |
| 7 | 3.1 | showToast('error') no CSS class | `analysis.js` | Important |
| 8 | 3.2 | Chat double-send | `chat.js` | Important |
| 9 | 3.3 | Call graph wrong node selection | `call-graph.js` | Important |
| 10 | 3.4 | SSE onerror reconnect stacking | `dashboard.js` | Important |
| 11 | 4.1 | No Escape key dismiss | `app.js` + modals | Moderate |
| 12 | 4.2 | Modal ARIA roles missing | `index.html` | Moderate |
| 13 | 4.3 | Nav tab ARIA pattern missing | `index.html`, `app.js` | Moderate |
| 14 | 5.1 | Untested: cross-file endpoint | `test_api_analysis.py` | Moderate |
| 15 | 5.2 | Untested: explain-paragraph | `test_api_analysis.py` | Moderate |
| 16 | 5.3 | Untested: codegen error paths | `test_api_codegen.py` | Moderate |
| 17 | 5.4 | Untested: simulation error paths | `test_simulation_comprehensive.py` | Moderate |
| 18 | 5.5 | Untested: health edge cases | `test_api_banking.py` | Moderate |
| 19 | 5.6 | Untested: chat error paths | `test_api_chat.py` | Moderate |
| 20 | 5.7 | Untested: payroll error paths | `test_payroll_api.py` | Moderate |
| 21 | 6.1 | Missing boundary value tests | `test_bridge.py` | Moderate |
| 22 | 6.2 | Missing malformed data tests | `test_bridge.py`, `test_payroll_bridge.py` | Moderate |
| 23 | 6.3 | Missing auth edge case tests | `test_auth.py` | Moderate |
| 24 | 6.4 | Missing empty/nil input tests | Various | Moderate |
| 25 | 7.1 | Hardcoded 0.625rem font sizes | `dashboard.css`, `variables.css` | Minor |
| 26 | 7.2 | Dead `.nav__role` CSS class | `layout.css` | Minor |
| 27 | 7.3 | Stale Anthropic model name | `routes_chat.py`, `providers.py`, `models.py` | Minor |
| 28 | 8.1 | EMPLOYEES.DAT git clarification | `.gitignore` | Minor |

---

## Execution Notes

- **Phases 1-3**: Fix code first, then add tests for the fixes in Phase 5.
- **Phase 4**: Accessibility changes are HTML/JS only — low risk, high portfolio impact.
- **Phases 5-6**: Bulk test writing. Run full suite after each batch to catch regressions.
- **Phase 7**: Cosmetic — do last, low risk.
- **Phase 8**: Version bump happens only after all tests pass.
- **Phase 9**: Gate — nothing ships until all checks pass.

**Final test count**: 800 tests (726 unit + 74 E2E).
