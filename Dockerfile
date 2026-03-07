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

# Seed data on first run
RUN chmod +x scripts/*.sh

EXPOSE 8000

# Seed demo data and start server
CMD ["sh", "-c", "python -c 'from python.bridge import COBOLBridge; [COBOLBridge(node=n, data_dir=\"COBOL-BANKING/data\", bin_dir=\"COBOL-BANKING/bin\").seed_demo_data() or COBOLBridge(node=n, data_dir=\"COBOL-BANKING/data\", bin_dir=\"COBOL-BANKING/bin\").close() for n in [\"BANK_A\",\"BANK_B\",\"BANK_C\",\"BANK_D\",\"BANK_E\",\"CLEARING\"]]' && python -m uvicorn python.api.app:app --host 0.0.0.0 --port 8000"]
