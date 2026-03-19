#!/usr/bin/env python3
"""Seed all 6 banking nodes with demo data for Docker/Railway deployment.

Self-tests COBOL binaries before seeding. If binaries execute successfully,
seeds in Mode A (real COBOL). Otherwise falls back to Mode B (Python-only).

Uses a sentinel file to skip re-seeding on container restart.
"""

import os
import subprocess
from pathlib import Path

from python.bridge import COBOLBridge

# ── Sentinel: skip if already seeded ─────────────────────────
sentinel = Path("COBOL-BANKING/data/.seeded")
if sentinel.exists():
    print("Data already seeded. Skipping.")
    raise SystemExit(0)

# ── Self-test: verify COBOL binaries actually execute ────────
bin_path = Path("COBOL-BANKING/bin/SMOKETEST")
if bin_path.exists():
    try:
        result = subprocess.run(
            [str(bin_path)], capture_output=True, timeout=5
        )
        if result.returncode == 0:
            print("  COBOL self-test passed - using Mode A (real COBOL)")
        else:
            stderr = result.stderr.decode("utf-8", errors="replace").strip() if result.stderr else ""
            raise RuntimeError(f"exit code {result.returncode}: {stderr}")
    except Exception as e:
        print(f"  COBOL self-test failed ({e}) - falling back to Mode B")
        os.environ["FORCE_MODE_B"] = "true"
else:
    print("  No COBOL binaries - using Mode B")
    os.environ["FORCE_MODE_B"] = "true"

# ── Seed all nodes ───────────────────────────────────────────
NODES = ["BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E", "CLEARING"]

for node in NODES:
    b = COBOLBridge(
        node=node,
        data_dir="COBOL-BANKING/data",
        bin_dir="COBOL-BANKING/bin",
    )
    b.seed_demo_data()
    b.close()
    print(f"  Seeded {node}")

print(f"Seeded {len(NODES)} nodes successfully")
sentinel.touch()
