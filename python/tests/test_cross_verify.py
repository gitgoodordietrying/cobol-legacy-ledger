"""
Tests for CrossNodeVerifier -- multi-node integrity verification.

Test strategy:
    Uses temporary data directories with all 6 nodes seeded. Tests verify
    that the three verification layers work correctly:
    1. Per-chain hash integrity (SHA-256 linkage)
    2. Balance reconciliation (DAT vs SQLite)
    3. Settlement cross-referencing (matching entries across nodes)

Test groups:
    - Clean state: All chains intact, no anomalies after seeding
    - After settlement: Cross-references match for completed transfers
    - Tamper detection: DAT file modification caught by balance check
    - Missing settlement leg: Partial transfers reported correctly
"""

import pytest
import tempfile
from pathlib import Path
from ..bridge import COBOLBridge
from ..settlement import SettlementCoordinator
from ..cross_verify import CrossNodeVerifier, tamper_balance


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def seeded_env(temp_data_dir):
    """Seed all 6 nodes and return (data_dir, coordinator, verifier)."""
    data_dir = str(temp_data_dir)
    for node in ['BANK_A', 'BANK_B', 'BANK_C', 'BANK_D', 'BANK_E', 'CLEARING']:
        bridge = COBOLBridge(node=node, data_dir=data_dir)
        bridge.seed_demo_data()
        bridge.close()

    coordinator = SettlementCoordinator(data_dir=data_dir)
    verifier = CrossNodeVerifier(data_dir=data_dir)
    yield data_dir, coordinator, verifier
    verifier.close()


# ── Clean State ──────────────────────────────────────────────────

def test_clean_chains_intact(seeded_env):
    """Test that all chains are intact after fresh seeding (no transactions yet)."""
    data_dir, coordinator, verifier = seeded_env
    report = verifier.verify_all()

    assert report.all_chains_intact is True
    # No settlements yet
    assert report.settlements_checked == 0
    assert len(report.anomalies) == 0


# ── After Settlement ─────────────────────────────────────────────

def test_settlement_cross_reference_match(seeded_env):
    """Test that a completed settlement has matching cross-references."""
    data_dir, coordinator, verifier = seeded_env

    # Execute a transfer
    result = coordinator.execute_transfer(
        "BANK_A", "ACT-A-001", "BANK_B", "ACT-B-003", 500.00, "Test wire")
    assert result.status == "COMPLETED"

    # Re-create verifier to pick up new chain entries
    verifier.close()
    verifier2 = CrossNodeVerifier(data_dir=data_dir)
    report = verifier2.verify_all()
    verifier2.close()

    assert report.all_chains_intact is True
    assert report.settlements_checked >= 1
    assert report.settlements_matched >= 1
    assert report.settlements_mismatched == 0


def test_multiple_settlements_all_matched(seeded_env):
    """Test that multiple completed settlements all match."""
    data_dir, coordinator, verifier = seeded_env

    coordinator.execute_transfer("BANK_A", "ACT-A-001", "BANK_B", "ACT-B-003", 100.00, "T1")
    coordinator.execute_transfer("BANK_B", "ACT-B-001", "BANK_C", "ACT-C-002", 200.00, "T2")

    verifier.close()
    verifier2 = CrossNodeVerifier(data_dir=data_dir)
    report = verifier2.verify_all()
    verifier2.close()

    assert report.settlements_checked >= 2
    assert report.settlements_matched >= 2


# ── Tamper Detection ─────────────────────────────────────────────

def test_tamper_detection_balance_drift(seeded_env):
    """Test that direct DAT file tampering is detected as balance drift."""
    data_dir, coordinator, verifier = seeded_env

    # Execute a transfer to populate chain entries
    coordinator.execute_transfer(
        "BANK_A", "ACT-A-001", "BANK_B", "ACT-B-003", 500.00, "Pre-tamper")

    # Tamper: directly edit BANK_A's DAT file
    tamper_balance(data_dir, "BANK_A", "ACT-A-001", 99999.99)

    # Verify detects the tamper
    verifier.close()
    verifier2 = CrossNodeVerifier(data_dir=data_dir)
    report = verifier2.verify_all()
    verifier2.close()

    # Balance drift should be detected for BANK_A
    assert "BANK_A" in report.balance_drift
    assert any("ACT-A-001" in issue for issue in report.balance_drift["BANK_A"])


# ── Partial Settlement ───────────────────────────────────────────

def test_failed_settlement_partial_in_report(seeded_env):
    """Test that a failed settlement (Step 1 NSF) produces no settlement entries."""
    data_dir, coordinator, verifier = seeded_env

    # This should fail at Step 1 (NSF)
    result = coordinator.execute_transfer(
        "BANK_A", "ACT-A-003", "BANK_B", "ACT-B-003", 9999.00, "NSF test")
    assert result.status == "FAILED"
    assert result.steps_completed == 0

    verifier.close()
    verifier2 = CrossNodeVerifier(data_dir=data_dir)
    report = verifier2.verify_all()
    verifier2.close()

    # No settlement entries were created (failed at Step 1)
    assert report.settlements_checked == 0


def test_find_settlement_entries(seeded_env):
    """Test finding entries for a specific settlement reference."""
    data_dir, coordinator, verifier = seeded_env

    result = coordinator.execute_transfer(
        "BANK_A", "ACT-A-001", "BANK_B", "ACT-B-003", 250.00, "Find test")
    assert result.status == "COMPLETED"

    verifier.close()
    verifier2 = CrossNodeVerifier(data_dir=data_dir)
    match = verifier2.find_settlement_entries(result.settlement_ref)
    verifier2.close()

    assert match.status == "MATCHED"
    assert match.source_entry_found is True
    assert match.dest_entry_found is True
    assert match.clearing_entries_found == 2
    assert match.amount == 250.00


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
