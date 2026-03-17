# ================================================================
# Dockerfile — cobol-legacy-ledger
# Multi-stage build: GnuCOBOL + Python + FastAPI
# Usage: docker build -t cobol-legacy-ledger .
# ================================================================

# ── Stage 1: Build COBOL binaries ────────────────────────────────
FROM ubuntu:22.04 AS cobol-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gnucobol4 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY COBOL-BANKING/ COBOL-BANKING/

# Compile banking programs
RUN mkdir -p COBOL-BANKING/bin && \
    for prog in SMOKETEST ACCOUNTS TRANSACT VALIDATE SETTLE SIMULATE INTEREST FEES RECONCILE REPORTS; do \
      cobc -x -free -o COBOL-BANKING/bin/$prog \
        -I COBOL-BANKING/copybooks \
        COBOL-BANKING/src/$prog.cob 2>/dev/null || true; \
    done

# Compile payroll sidecar programs
RUN for prog in PAYROLL TAXCALC DEDUCTN PAYBATCH MERCHANT FEEENGN DISPUTE RISKCHK; do \
      cobc -x -free -o COBOL-BANKING/bin/$prog \
        -I COBOL-BANKING/payroll/copybooks \
        -I COBOL-BANKING/copybooks \
        COBOL-BANKING/payroll/src/$prog.cob 2>/dev/null || true; \
    done

# ── Stage 2: Python application ─────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install runtime COBOL dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcob4 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY python/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY python/ python/
COPY console/ console/
COPY scripts/ scripts/
COPY COBOL-BANKING/ COBOL-BANKING/

# Copy compiled binaries from builder
COPY --from=cobol-builder /build/COBOL-BANKING/bin/ COBOL-BANKING/bin/

# Ensure Python can find the application modules
ENV PYTHONPATH=/app
# Force Mode B (Python file I/O) — COBOL subprocess paths don't resolve in containers
ENV FORCE_MODE_B=true

# Create data directories (files excluded by .dockerignore, seeded at startup)
RUN mkdir -p COBOL-BANKING/data/BANK_A COBOL-BANKING/data/BANK_B \
    COBOL-BANKING/data/BANK_C COBOL-BANKING/data/BANK_D \
    COBOL-BANKING/data/BANK_E COBOL-BANKING/data/CLEARING \
    COBOL-BANKING/payroll/data/PAYROLL

# Seed data on first run
RUN chmod +x scripts/*.sh

EXPOSE 8000

# Seed data and start server (PORT env var for Railway compatibility)
CMD sh -c "python scripts/seed_docker.py && python -m uvicorn python.api.app:app --host 0.0.0.0 --port ${PORT:-8000}"
