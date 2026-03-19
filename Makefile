# ================================================================
# Makefile — cobol-legacy-ledger
# Single entry point for all project operations.
# ================================================================
#
# Quick start for classrooms:
#   make lab-setup    # One command: venv + deps + seed + smoke test
#
# Developer workflow:
#   make build        # Compile COBOL (optional — Mode B fallback)
#   make seed         # Seed all 6 nodes with demo data
#   make test         # Run all 733+ unit tests
#   make run          # Start the FastAPI server
#   make prove        # Full end-to-end proof (compile → seed → settle → verify → tamper → detect)
#
# Classroom workflow:
#   make checkpoint-save LESSON=3    # Snapshot data for lesson 3
#   make checkpoint-restore LESSON=3 # Restore data for lesson 3

SHELL := /bin/bash
PYTHON ?= python
VENV := .venv
SCRIPTS := scripts

.PHONY: build seed test test-e2e run prove clean install lab-setup \
        checkpoint-save checkpoint-restore help

# ── Core Targets ─────────────────────────────────────────────────

build: ## Compile all COBOL programs (requires cobc or Docker)
	@$(SCRIPTS)/build.sh

seed: ## Seed all 6 nodes with demo account data
	@$(SCRIPTS)/seed.sh

test: ## Run all unit tests (733+)
	@$(PYTHON) -m pytest python/tests/ -v --ignore=python/tests/test_e2e_playwright.py -p no:asyncio

test-e2e: ## Run end-to-end Playwright tests (requires running server)
	@$(PYTHON) -m pytest python/tests/test_e2e_playwright.py -v

run: ## Start the FastAPI server on port 8000
	@$(PYTHON) -m uvicorn python.api.app:app --reload --host 0.0.0.0 --port 8000

prove: ## Full end-to-end proof (compile → seed → settle → verify → tamper → detect)
	@$(SCRIPTS)/prove.sh

clean: ## Remove compiled binaries and __pycache__
	@rm -rf COBOL-BANKING/bin/*.exe COBOL-BANKING/bin/SMOKETEST COBOL-BANKING/bin/ACCOUNTS
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned build artifacts and cache files."

# ── Setup Targets ────────────────────────────────────────────────

install: ## Create venv and install Python dependencies
	@$(PYTHON) -m venv $(VENV) 2>/dev/null || true
	@$(VENV)/bin/pip install --quiet --upgrade pip
	@$(VENV)/bin/pip install --quiet -r python/requirements.txt
	@echo "Dependencies installed in $(VENV)/"

lab-setup: install ## Classroom setup: venv + deps + seed + smoke test
	@echo "=== Lab Setup ==="
	@$(VENV)/bin/python -m pytest python/tests/test_integrity.py -v --tb=short -q 2>&1 | tail -5
	@$(SCRIPTS)/seed.sh
	@echo ""
	@echo "=== Lab Ready ==="
	@echo "Run: make run    (start server)"
	@echo "Open: http://localhost:8000"

# ── Checkpoint Targets ───────────────────────────────────────────

checkpoint-save: ## Save data snapshot: make checkpoint-save LESSON=N
ifndef LESSON
	$(error LESSON is required. Usage: make checkpoint-save LESSON=3)
endif
	@$(SCRIPTS)/checkpoint.sh save $(LESSON)

checkpoint-restore: ## Restore data snapshot: make checkpoint-restore LESSON=N
ifndef LESSON
	$(error LESSON is required. Usage: make checkpoint-restore LESSON=3)
endif
	@$(SCRIPTS)/checkpoint.sh restore $(LESSON)

# ── Help ─────────────────────────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
