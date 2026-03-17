#!/usr/bin/env python3
"""Seed all 6 banking nodes with demo data for Docker/Railway deployment."""

from python.bridge import COBOLBridge

NODES = ["BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E", "CLEARING"]

for node in NODES:
    b = COBOLBridge(node=node, data_dir="COBOL-BANKING/data", bin_dir="COBOL-BANKING/bin", force_mode_b=True)
    b.seed_demo_data()
    b.close()
    print(f"  Seeded {node}")

print(f"Seeded {len(NODES)} nodes successfully")
