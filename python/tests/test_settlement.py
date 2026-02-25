"""
Tests for SettlementCoordinator -- inter-bank transfer orchestration.

Test strategy:
    All tests use temporary data directories with fresh bridges in Mode B.
    Each test seeds the required nodes with demo data, then exercises the
    settlement coordinator's 3-step transfer logic.

Test groups:
    - Happy path: Full 3-step settlement completes successfully
    - NSF rejection: Transfer fails at Step 1 due to insufficient funds
    - Limit rejection: Transfer fails when amount exceeds $50K daily limit
    - Summary verification: Net positions balance across all banks
    - Batch processing: Multiple transfers with mixed success/failure
    - steps_completed accuracy: Correct count on partial failures
"""

import pytest
import tempfile
from pathlib import Path
from ..bridge import COBOLBridge
from ..settlement import SettlementCoordinator, DEMO_SETTLEMENT_BATCH


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def seeded_coordinator(temp_data_dir):
    """Create a SettlementCoordinator with seeded nodes.

    Seeds all 6 nodes (5 banks + CLEARING) with demo data so that
    settlements have accounts and balances to work with.
    """
    data_dir = str(temp_data_dir)
    for node in ['BANK_A', 'BANK_B', 'BANK_C', 'BANK_D', 'BANK_E', 'CLEARING']:
        bridge = COBOLBridge(node=node, data_dir=data_dir)
        bridge.seed_demo_data()
        bridge.close()

    return SettlementCoordinator(data_dir=data_dir)


# ── Happy Path ──────────────────────────────────────────────────

def test_settlement_happy_path(seeded_coordinator):
    """Test that a normal inter-bank transfer completes all 3 steps."""
    result = seeded_coordinator.execute_transfer(
        source_bank="BANK_A",
        source_account="ACT-A-001",
        dest_bank="BANK_B",
        dest_account="ACT-B-003",
        amount=500.00,
        description="Test wire transfer"
    )

    assert result.status == "COMPLETED"
    assert result.steps_completed == 3
    assert result.error == ""
    assert result.source_trx_id != ""
    assert result.clearing_deposit_id != ""
    assert result.clearing_withdraw_id != ""
    assert result.dest_trx_id != ""
    assert result.amount == 500.00
    assert result.settlement_ref.startswith("STL-")


def test_settlement_updates_balances(seeded_coordinator):
    """Test that settlement correctly debits source and credits destination."""
    coord = seeded_coordinator

    # Get initial balances
    source_bridge = coord.nodes["BANK_A"]
    dest_bridge = coord.nodes["BANK_B"]
    source_before = source_bridge.get_account("ACT-A-001")['balance']
    dest_before = dest_bridge.get_account("ACT-B-003")['balance']

    result = coord.execute_transfer(
        source_bank="BANK_A", source_account="ACT-A-001",
        dest_bank="BANK_B", dest_account="ACT-B-003",
        amount=100.00, description="Balance check test"
    )

    assert result.status == "COMPLETED"
    source_after = source_bridge.get_account("ACT-A-001")['balance']
    dest_after = dest_bridge.get_account("ACT-B-003")['balance']

    assert source_after == source_before - 100.00
    assert dest_after == dest_before + 100.00


# ── Failure Cases ───────────────────────────────────────────────

def test_settlement_nsf_rejection(seeded_coordinator):
    """Test that NSF at source bank fails at Step 1 with 0 steps completed."""
    result = seeded_coordinator.execute_transfer(
        source_bank="BANK_A",
        source_account="ACT-A-003",  # Chen Liu: $850.50
        dest_bank="BANK_B",
        dest_account="ACT-B-003",
        amount=5000.00,  # More than balance
        description="Should fail NSF"
    )

    assert result.status == "FAILED"
    assert result.steps_completed == 0
    assert "Step 1" in result.error


def test_settlement_limit_exceeded(seeded_coordinator):
    """Test that amount over $50K daily limit fails at Step 1."""
    result = seeded_coordinator.execute_transfer(
        source_bank="BANK_D",
        source_account="ACT-D-001",  # Westchester Trust: $5M
        dest_bank="BANK_A",
        dest_account="ACT-A-001",
        amount=50001.00,  # Over $50K limit
        description="Should fail limit"
    )

    assert result.status == "FAILED"
    assert result.steps_completed == 0
    assert "Step 1" in result.error


# ── Summary Verification ─────────────────────────────────────────

def test_settlement_summary_balances(seeded_coordinator):
    """Test that nostro positions net to zero for completed transfers."""
    coord = seeded_coordinator

    # Execute two transfers in opposite directions
    results = []
    results.append(coord.execute_transfer(
        "BANK_A", "ACT-A-001", "BANK_B", "ACT-B-003", 500.00, "Forward"))
    results.append(coord.execute_transfer(
        "BANK_B", "ACT-B-001", "BANK_A", "ACT-A-002", 300.00, "Reverse"))

    summary = coord.get_settlement_summary(results)

    assert summary['completed'] == 2
    assert summary['failed'] == 0
    # Nostro net should be zero (every deposit has a matching withdrawal)
    assert summary['clearing_balance_check'] is True
    assert abs(summary['nostro_net']) < 0.01


# ── Batch Settlement ──────────────────────────────────────────────

def test_batch_settlement_mixed_results(seeded_coordinator):
    """Test batch settlement with normal transfers and an expected failure."""
    transfers = [
        {"source_bank": "BANK_A", "source_account": "ACT-A-001",
         "dest_bank": "BANK_B", "dest_account": "ACT-B-003",
         "amount": 500.00, "description": "Normal transfer"},
        {"source_bank": "BANK_A", "source_account": "ACT-A-003",
         "dest_bank": "BANK_C", "dest_account": "ACT-C-001",
         "amount": 9999.00, "description": "NSF - should fail"},
    ]

    results = seeded_coordinator.execute_batch_settlement(transfers)

    assert len(results) == 2
    assert results[0].status == "COMPLETED"
    assert results[1].status == "FAILED"

    summary = seeded_coordinator.get_settlement_summary(results)
    assert summary['completed'] == 1
    assert summary['failed'] == 1


# ── steps_completed Accuracy ─────────────────────────────────────

def test_steps_completed_on_step1_failure(seeded_coordinator):
    """Test steps_completed = 0 when Step 1 fails."""
    result = seeded_coordinator.execute_transfer(
        "BANK_A", "ACT-A-003", "BANK_B", "ACT-B-001", 9999.00, "NSF")

    assert result.steps_completed == 0
    assert result.status == "FAILED"


def test_settlement_ref_format(seeded_coordinator):
    """Test that settlement references follow STL-YYYYMMDD-NNNNNN format."""
    result = seeded_coordinator.execute_transfer(
        "BANK_A", "ACT-A-001", "BANK_B", "ACT-B-003", 100.00, "Ref test")

    import re
    assert re.match(r'STL-\d{8}-\d{6}', result.settlement_ref)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
