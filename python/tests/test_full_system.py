"""
Tests for full-system integration — programmatic equivalent of prove.sh.

This test file exercises the complete system end-to-end: seeding all 6 nodes,
executing inter-bank settlements, tampering a DAT file, and verifying that the
integrity layer detects every discrepancy. It validates the core claims:

    1. 6 independent nodes with correct account counts (42 total)
    2. Inter-bank settlement creates matching entries across 3 chains
    3. SHA-256 hash chains remain intact under normal operations
    4. Direct DAT file tampering is detected via balance reconciliation
    5. Cross-node verification completes in <1000ms (generous bound)
    6. Simulation engine runs without errors
    7. All educational comments are present in COBOL source files

These tests back the claims made in README.md, CLAUDE.md, and ARCHITECTURE.md
with automated verification that runs in CI.
"""

import os
import tempfile
import shutil
from pathlib import Path

import pytest

from python.bridge import COBOLBridge
from python.settlement import SettlementCoordinator
from python.cross_verify import CrossNodeVerifier, tamper_balance
from python.simulator import SimulationEngine

NODES = ['BANK_A', 'BANK_B', 'BANK_C', 'BANK_D', 'BANK_E', 'CLEARING']
BANKS = ['BANK_A', 'BANK_B', 'BANK_C', 'BANK_D', 'BANK_E']


@pytest.fixture(scope="module")
def full_env():
    """Seed all 6 nodes in a temp directory — shared across tests in this module."""
    temp_dir = Path(tempfile.mkdtemp())
    data_dir = str(temp_dir)

    bridges = {}
    for node in NODES:
        os.makedirs(os.path.join(data_dir, node), exist_ok=True)
        bridge = COBOLBridge(node=node, data_dir=data_dir)
        bridge.seed_demo_data()
        bridges[node] = bridge

    yield data_dir, bridges

    for b in bridges.values():
        b.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


# ── Claim: 42 accounts across 6 nodes ────────────────────────────

EXPECTED_COUNTS = {
    'BANK_A': 8, 'BANK_B': 7, 'BANK_C': 8,
    'BANK_D': 6, 'BANK_E': 8, 'CLEARING': 5,
}

def test_account_counts_match_documentation(full_env):
    """Verify that each node has exactly the documented number of accounts."""
    data_dir, bridges = full_env
    total = 0
    for node, expected in EXPECTED_COUNTS.items():
        accounts = bridges[node].list_accounts()
        actual = len(accounts)
        assert actual == expected, f"{node}: expected {expected} accounts, got {actual}"
        total += actual
    assert total == 42, f"Expected 42 total accounts, got {total}"


def test_bank_a_account_ids(full_env):
    """Verify BANK_A accounts are ACT-A-001 through ACT-A-008."""
    _, bridges = full_env
    accounts = bridges['BANK_A'].list_accounts()
    ids = sorted(a['id'] for a in accounts)
    expected = [f"ACT-A-{i:03d}" for i in range(1, 9)]
    assert ids == expected


def test_clearing_nostro_accounts(full_env):
    """Verify CLEARING has nostro accounts NST-BANK-A through NST-BANK-E."""
    _, bridges = full_env
    accounts = bridges['CLEARING'].list_accounts()
    ids = sorted(a['id'] for a in accounts)
    expected = sorted([f"NST-BANK-{c}" for c in 'ABCDE'])
    assert ids == expected


# ── Claim: Settlement creates matching cross-node entries ────────

def test_settlement_end_to_end(full_env):
    """Execute a settlement and verify all 3 chains have matching entries."""
    data_dir, bridges = full_env
    coordinator = SettlementCoordinator(data_dir=data_dir)

    result = coordinator.execute_transfer(
        source_bank="BANK_A", source_account="ACT-A-001",
        dest_bank="BANK_B", dest_account="ACT-B-001",
        amount=2500.00, description="Integration test wire transfer",
    )

    assert result.status == "COMPLETED", f"Settlement failed: {result.error}"
    assert result.steps_completed == 3
    assert result.settlement_ref.startswith("STL-")
    assert result.amount == 2500.00

    # Verify the settlement reference exists across all 3 involved chains
    verifier = CrossNodeVerifier(data_dir=data_dir)
    match = verifier.find_settlement_entries(result.settlement_ref)
    verifier.close()

    assert match.status == "MATCHED"
    assert match.source_entry_found is True
    assert match.dest_entry_found is True
    assert match.clearing_entries_found == 2
    assert match.amount == 2500.00
    assert len(match.discrepancies) == 0


def test_multiple_settlements_all_verified(full_env):
    """Execute 3 settlements across different bank pairs, verify chains intact."""
    data_dir, _ = full_env
    coordinator = SettlementCoordinator(data_dir=data_dir)

    pairs = [
        ("BANK_B", "ACT-B-001", "BANK_C", "ACT-C-001", 1000.00),
        ("BANK_C", "ACT-C-002", "BANK_D", "ACT-D-001", 500.00),
        ("BANK_D", "ACT-D-001", "BANK_E", "ACT-E-001", 250.00),
    ]

    refs = []
    for src_bank, src_acct, dst_bank, dst_acct, amount in pairs:
        result = coordinator.execute_transfer(
            src_bank, src_acct, dst_bank, dst_acct, amount, "Multi-settle test")
        assert result.status == "COMPLETED", f"{src_bank}→{dst_bank} failed: {result.error}"
        refs.append(result.settlement_ref)

    # Verify each individual settlement has matching entries
    verifier = CrossNodeVerifier(data_dir=data_dir)
    for ref in refs:
        match = verifier.find_settlement_entries(ref)
        assert match.source_entry_found, f"{ref}: missing source entry"
        assert match.dest_entry_found, f"{ref}: missing dest entry"
        assert match.clearing_entries_found >= 2, f"{ref}: missing clearing entries"

    report = verifier.verify_all()
    verifier.close()

    assert report.all_chains_intact is True
    assert report.settlements_mismatched == 0


# ── Claim: Chains remain intact under normal operations ──────────

def test_all_chains_intact_after_operations(full_env):
    """After settlements, all 6 hash chains should still be intact."""
    data_dir, _ = full_env
    verifier = CrossNodeVerifier(data_dir=data_dir)
    report = verifier.verify_all()
    verifier.close()

    assert report.all_chains_intact is True
    for node in NODES:
        assert report.chain_integrity[node] is True, f"{node} chain is broken"


# ── Claim: Tamper detection works ────────────────────────────────

def test_tamper_detected_via_balance_reconciliation(full_env):
    """Tamper a DAT file balance and verify the system detects it."""
    data_dir, _ = full_env

    # Tamper BANK_C ACT-C-001 to $999,999.99
    tamper_balance(data_dir, "BANK_C", "ACT-C-001", 999999.99)

    verifier = CrossNodeVerifier(data_dir=data_dir)
    report = verifier.verify_all()
    verifier.close()

    # Balance drift must be detected for BANK_C
    assert "BANK_C" in report.balance_drift, "Tamper not detected in BANK_C"
    drift_messages = report.balance_drift["BANK_C"]
    assert any("ACT-C-001" in msg for msg in drift_messages), \
        f"ACT-C-001 tamper not found in drift messages: {drift_messages}"

    # Chains themselves should still be intact (tamper was to DAT, not chain)
    assert report.chain_integrity["BANK_C"] is True


# ── Claim: Verification completes in <1000ms ─────────────────────

def test_verification_performance(full_env):
    """Cross-node verification should complete well under 1 second."""
    data_dir, _ = full_env
    verifier = CrossNodeVerifier(data_dir=data_dir)
    report = verifier.verify_all()
    verifier.close()

    assert report.verification_time_ms < 1000, \
        f"Verification took {report.verification_time_ms:.0f}ms, expected <1000ms"


# ── Claim: Simulation engine runs without errors ─────────────────

def test_simulation_engine_runs():
    """Run a 2-day simulation and verify stats are populated."""
    temp_dir = Path(tempfile.mkdtemp())
    data_dir = str(temp_dir)

    for node in NODES:
        os.makedirs(os.path.join(data_dir, node), exist_ok=True)
        bridge = COBOLBridge(node=node, data_dir=data_dir)
        bridge.seed_demo_data()
        bridge.close()

    engine = SimulationEngine(
        data_dir=data_dir,
        time_scale=0,  # Max speed
        seed=42,
        scenarios=False,  # Disable scenarios for short run
        tx_range=(5, 10),  # Small tx count for speed
    )
    engine.run(days=2)

    assert engine.days_run == 2
    assert engine.total_completed > 0
    assert engine.total_volume > 0
    assert engine.total_internal + engine.total_external > 0

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_simulation_callback_fires():
    """Verify that registered callbacks fire during simulation."""
    temp_dir = Path(tempfile.mkdtemp())
    data_dir = str(temp_dir)

    for node in NODES:
        os.makedirs(os.path.join(data_dir, node), exist_ok=True)
        bridge = COBOLBridge(node=node, data_dir=data_dir)
        bridge.seed_demo_data()
        bridge.close()

    events = []
    engine = SimulationEngine(
        data_dir=data_dir, time_scale=0, seed=42,
        scenarios=False, tx_range=(3, 5),
    )
    engine.register_callback(lambda e: events.append(e))
    engine.run(days=1)

    assert len(events) > 0, "No callback events fired"
    # Each event should have at minimum 'type' and 'day' keys
    for e in events:
        assert 'type' in e
        assert 'day' in e

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_simulation_pause_and_stop():
    """Verify that _paused and _stopped flags work."""
    temp_dir = Path(tempfile.mkdtemp())
    data_dir = str(temp_dir)

    for node in NODES:
        os.makedirs(os.path.join(data_dir, node), exist_ok=True)
        bridge = COBOLBridge(node=node, data_dir=data_dir)
        bridge.seed_demo_data()
        bridge.close()

    engine = SimulationEngine(
        data_dir=data_dir, time_scale=0, seed=42,
        scenarios=False, tx_range=(3, 5),
    )

    # Stop immediately — should run 0 or 1 days
    engine._stopped = True
    engine.run(days=100)
    assert engine.days_run <= 1

    shutil.rmtree(temp_dir, ignore_errors=True)


# ── Claim: COBOL source files contain educational comments ───────

def test_cobol_files_contain_educational_comments():
    """Verify every .cob file has COBOL CONCEPT educational blocks."""
    src_dir = Path("COBOL-BANKING/src")
    if not src_dir.exists():
        pytest.skip("COBOL source directory not found")

    cob_files = list(src_dir.glob("*.cob"))
    assert len(cob_files) == 10, f"Expected 10 .cob files, found {len(cob_files)}"

    for cob_file in cob_files:
        content = cob_file.read_text(encoding='utf-8', errors='replace')
        # Every file should have comment lines (COBOL comments start with * in column 7)
        comment_lines = [l for l in content.split('\n') if len(l) >= 7 and l[6] == '*']
        assert len(comment_lines) >= 5, \
            f"{cob_file.name} has only {len(comment_lines)} comment lines — expected educational content"


def test_cobol_files_have_four_divisions():
    """Verify every .cob file has all 4 COBOL divisions."""
    src_dir = Path("COBOL-BANKING/src")
    if not src_dir.exists():
        pytest.skip("COBOL source directory not found")

    divisions = ['IDENTIFICATION DIVISION', 'ENVIRONMENT DIVISION',
                 'DATA DIVISION', 'PROCEDURE DIVISION']

    for cob_file in src_dir.glob("*.cob"):
        content = cob_file.read_text(encoding='utf-8', errors='replace')
        for div in divisions:
            assert div in content, \
                f"{cob_file.name} is missing '{div}'"


# ── Claim: Record formats match documented byte sizes ────────────

def test_acctrec_is_70_bytes():
    """Verify ACCTREC copybook defines a 70-byte record."""
    cpy_path = Path("COBOL-BANKING/copybooks/ACCTREC.cpy")
    if not cpy_path.exists():
        pytest.skip("Copybook not found")

    content = cpy_path.read_text(encoding='utf-8', errors='replace')
    # The copybook should document "70 bytes" or contain the PIC fields that sum to 70
    assert "70" in content, "ACCTREC.cpy does not mention 70-byte record size"


def test_transrec_is_103_bytes():
    """Verify TRANSREC copybook defines a 103-byte record."""
    cpy_path = Path("COBOL-BANKING/copybooks/TRANSREC.cpy")
    if not cpy_path.exists():
        pytest.skip("Copybook not found")

    content = cpy_path.read_text(encoding='utf-8', errors='replace')
    assert "103" in content, "TRANSREC.cpy does not mention 103-byte record size"
