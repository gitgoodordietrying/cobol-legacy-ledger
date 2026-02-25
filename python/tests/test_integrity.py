"""
Tests for IntegrityChain — hash chain verification and tamper detection.
"""

import os
import pytest
import sqlite3
import tempfile
from pathlib import Path
from ..integrity import IntegrityChain, ChainedTransaction


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing.

    PYTHON CONCEPT: tempfile.mkstemp() returns (fd, path) where fd is an
    integer file descriptor. We must close the fd before SQLite can open
    the file, otherwise the handle leaks. Path(fd) would create a nonsensical
    path like "5" -- always use os.close(fd) instead.
    """
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)  # Close the raw file descriptor so SQLite can open the file
    db = sqlite3.connect(path)
    yield db
    db.close()
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def chain(temp_db):
    """Create an IntegrityChain instance with test database."""
    return IntegrityChain(temp_db, "test-secret-key-12345")


def test_chain_initializes(chain):
    """Test that chain initializes with empty state."""
    result = chain.verify_chain()
    assert result['valid'] is True
    assert result['entries_checked'] == 0
    assert result['first_break'] is None


def test_append_single_transaction(chain):
    """Test appending a single transaction."""
    tx = chain.append(
        tx_id="TRX-A-000001",
        account_id="ACT-A-001",
        tx_type="D",
        amount=1000.00,
        timestamp="2026-02-17T10:30:00",
        description="Test deposit",
        status="00"
    )

    assert isinstance(tx, ChainedTransaction)
    assert tx.chain_index == 0
    assert tx.tx_id == "TRX-A-000001"
    assert tx.prev_hash == "GENESIS"
    assert len(tx.tx_hash) == 64  # SHA-256 hex
    assert len(tx.signature) == 64  # HMAC-SHA256 hex


def test_chain_linkage(chain):
    """Test that chain links correctly across multiple entries."""
    tx1 = chain.append("TRX-A-000001", "ACT-A-001", "D", 1000.00, "2026-02-17T10:30:00", "Deposit 1", "00")
    tx2 = chain.append("TRX-A-000002", "ACT-A-002", "W", 500.00, "2026-02-17T10:31:00", "Withdraw 1", "00")
    tx3 = chain.append("TRX-A-000003", "ACT-A-001", "D", 2000.00, "2026-02-17T10:32:00", "Deposit 2", "00")

    # Verify chain indices
    assert tx1.chain_index == 0
    assert tx2.chain_index == 1
    assert tx3.chain_index == 2

    # Verify linkage: each entry's prev_hash should match previous entry's tx_hash
    assert tx2.prev_hash == tx1.tx_hash
    assert tx3.prev_hash == tx2.tx_hash

    # Verify entire chain is valid
    result = chain.verify_chain()
    assert result['valid'] is True
    assert result['entries_checked'] == 3


def test_detect_linkage_break(chain, temp_db):
    """Test that chain detects broken linkage (tampering)."""
    # Add valid entries
    tx1 = chain.append("TRX-A-000001", "ACT-A-001", "D", 1000.00, "2026-02-17T10:30:00", "Deposit 1", "00")
    tx2 = chain.append("TRX-A-000002", "ACT-A-002", "W", 500.00, "2026-02-17T10:31:00", "Withdraw 1", "00")

    # Tamper: change tx2's prev_hash to simulate chain break
    temp_db.execute(
        "UPDATE chain_entries SET prev_hash = ? WHERE chain_index = ?",
        ("TAMPERED", 1)
    )
    temp_db.commit()

    # Verify detects tampering
    result = chain.verify_chain()
    assert result['valid'] is False
    assert result['break_type'] == 'linkage_break'
    assert result['first_break'] == 1
    assert "mismatch" in result['details'].lower()


def test_detect_signature_tampering(chain, temp_db):
    """Test that chain detects signature tampering."""
    tx1 = chain.append("TRX-A-000001", "ACT-A-001", "D", 1000.00, "2026-02-17T10:30:00", "Deposit 1", "00")

    # Tamper: change the signature
    temp_db.execute(
        "UPDATE chain_entries SET signature = ? WHERE chain_index = ?",
        ("0" * 64, 0)  # All zeros
    )
    temp_db.commit()

    # Verify detects tampering
    result = chain.verify_chain()
    assert result['valid'] is False
    assert result['break_type'] == 'signature_invalid'
    assert result['first_break'] == 0


def test_get_chain_for_display(chain):
    """Test fetching chain entries for display (truncated hashes)."""
    chain.append("TRX-A-000001", "ACT-A-001", "D", 1000.00, "2026-02-17T10:30:00", "Deposit 1", "00")
    chain.append("TRX-A-000002", "ACT-A-002", "W", 500.00, "2026-02-17T10:31:00", "Withdraw 1", "00")

    display = chain.get_chain_for_display(limit=50, offset=0)

    assert len(display) == 2
    assert display[0]['chain_index'] == 0
    assert display[0]['tx_id'] == "TRX-A-000001"
    assert len(display[0]['hash']) == 8  # Truncated to 8 chars
    assert len(display[0]['signature']) == 8


def test_detect_content_tampering(chain, temp_db):
    """Test that chain detects content field tampering (e.g., changed amount).

    This verifies the content hash recomputation (Check 2 in verify_chain).
    An attacker who modifies a transaction field (like amount) but preserves
    the chain linkage will still be caught because the stored tx_hash no
    longer matches SHA256(reconstructed_content).
    """
    tx1 = chain.append("TRX-A-000001", "ACT-A-001", "D", 1000.00, "2026-02-17T10:30:00", "Deposit 1", "00")

    # Tamper: change the amount in the database (but leave hash/linkage intact)
    temp_db.execute(
        "UPDATE chain_entries SET amount = ? WHERE chain_index = ?",
        (9999.00, 0)
    )
    temp_db.commit()

    # Verify detects the content tampering
    result = chain.verify_chain()
    assert result['valid'] is False
    assert result['break_type'] == 'content_hash_mismatch'
    assert result['first_break'] == 0


def test_chain_performance(chain):
    """Test chain verification performance (should be fast for <100 entries)."""
    import time

    # Add 50 entries
    for i in range(50):
        chain.append(
            f"TRX-A-{i:06d}",
            f"ACT-A-{i%8:03d}",
            "D" if i % 2 == 0 else "W",
            (i + 1) * 100.0,
            "2026-02-17T10:30:00",
            f"Transaction {i}",
            "00"
        )

    # Verify performance
    start = time.time()
    result = chain.verify_chain()
    elapsed_ms = (time.time() - start) * 1000

    assert result['valid'] is True
    assert result['entries_checked'] == 50
    assert elapsed_ms < 100  # Should verify <100 entries in <100ms


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
