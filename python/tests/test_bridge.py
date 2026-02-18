"""
Tests for COBOLBridge — DAT file parsing, account loading, transactions.
"""

import pytest
import tempfile
import sqlite3
from pathlib import Path
from ..bridge import COBOLBridge


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def bridge(temp_data_dir):
    """Create a COBOLBridge instance for testing."""
    return COBOLBridge(node="BANK_TEST", data_dir=str(temp_data_dir), bin_dir="cobol/bin")


def test_bridge_initialization(bridge):
    """Test that bridge initializes correctly."""
    assert bridge.node == "BANK_TEST"
    assert bridge.db is not None
    assert bridge.chain is not None
    # cobol_available should be False since cobol/bin doesn't exist in temp
    assert bridge.cobol_available is False


def test_parse_balance():
    """Test parsing of PIC S9(10)V99 balance field."""
    bridge = COBOLBridge(node="TEST", data_dir=".", bin_dir="cobol/bin")

    # Test parsing: 12 bytes = 10 digits + 2 fractional
    # Value: 000001234567 → 12345.67
    balance = bridge._parse_balance(b'000001234567')
    assert balance == 12345.67

    # Zero
    balance = bridge._parse_balance(b'000000000000')
    assert balance == 0.00

    # Large value: 999999999999 → 9999999999.99
    balance = bridge._parse_balance(b'999999999999')
    assert balance == 9999999999.99


def test_create_secret_key(bridge):
    """Test that secret key is created and persisted."""
    key1 = bridge._get_or_create_secret_key()
    assert isinstance(key1, str)
    assert len(key1) > 0

    # Call again, should return same key
    bridge2 = COBOLBridge(node="BANK_TEST", data_dir=str(bridge.data_dir), bin_dir="cobol/bin")
    key2 = bridge2._get_or_create_secret_key()

    assert key1 == key2


def test_list_accounts_empty(bridge):
    """Test listing accounts when database is empty."""
    bridge.seed_demo_data()  # Initialize tables
    accounts = bridge.list_accounts()
    assert accounts == []


def test_load_accounts_from_dat(bridge):
    """Test loading accounts from DAT file."""
    # Create a test ACCOUNTS.DAT with one record
    # Record format: 70 bytes (ID 10, NAME 30, TYPE 1, BALANCE 12, STATUS 1, OPEN-DATE 8, LAST-ACTIVITY 8)

    # Write test data directly to DAT file
    accounts_file = bridge.data_dir / "ACCOUNTS.DAT"

    # Build a 70-byte record
    record = (
        b'ACT-T-001 '          # 10 bytes (ID, left-padded with space)
        b'Test Account         '  # 30 bytes (NAME, right-padded with spaces)
        b'C'                     # 1 byte (TYPE)
        b'000000100000'          # 12 bytes (BALANCE: 1000.00)
        b'A'                     # 1 byte (STATUS)
        b'20260217'              # 8 bytes (OPEN-DATE)
        b'20260217'              # 8 bytes (LAST-ACTIVITY)
    )

    assert len(record) == 70

    accounts_file.write_bytes(record + b'\n')

    # Load accounts
    accounts = bridge.load_accounts_from_dat()
    assert len(accounts) == 1
    assert accounts[0]['id'] == 'ACT-T-001'
    assert accounts[0]['name'] == 'Test Account'
    assert accounts[0]['type'] == 'C'
    assert accounts[0]['balance'] == 1000.00
    assert accounts[0]['status'] == 'A'


def test_process_transaction_valid(bridge):
    """Test processing a valid transaction."""
    bridge.seed_demo_data()

    # Insert a test account
    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-B-001", "Bob Account", "C", 5000.00, "A")
    )
    bridge.db.commit()

    # Process deposit
    result = bridge.process_transaction("ACT-B-001", "D", 1000.00, "Test deposit")

    assert result['status'] == '00'
    assert 'TRX-BANK_TEST-' in result['tx_id']
    assert result['new_balance'] == 6000.00


def test_process_transaction_insufficient_funds(bridge):
    """Test that withdrawal is rejected with insufficient funds."""
    bridge.seed_demo_data()

    # Insert a test account with low balance
    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-B-001", "Bob Account", "C", 100.00, "A")
    )
    bridge.db.commit()

    # Try to withdraw more than available
    result = bridge.process_transaction("ACT-B-001", "W", 500.00, "Large withdrawal")

    assert result['status'] == '01'  # NSF
    assert 'funds' in result['message'].lower()


def test_process_transaction_invalid_account(bridge):
    """Test that transaction is rejected for nonexistent account."""
    bridge.seed_demo_data()

    result = bridge.process_transaction("NONEXISTENT", "D", 100.00, "Test")

    assert result['status'] == '03'  # Invalid account


def test_process_transaction_limit_exceeded(bridge):
    """Test that transaction is rejected if amount exceeds daily limit."""
    bridge.seed_demo_data()

    # Insert a test account with high balance
    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-B-001", "Bob Account", "C", 100000.00, "A")
    )
    bridge.db.commit()

    # Try to exceed daily limit (10000.00)
    result = bridge.process_transaction("ACT-B-001", "D", 50000.00, "Large deposit")

    assert result['status'] == '02'  # Limit exceeded


def test_process_transaction_frozen_account(bridge):
    """Test that transaction is rejected if account is frozen."""
    bridge.seed_demo_data()

    # Insert a frozen account
    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-B-001", "Frozen Account", "C", 5000.00, "F")
    )
    bridge.db.commit()

    result = bridge.process_transaction("ACT-B-001", "D", 100.00, "Test")

    assert result['status'] == '04'  # Account frozen


def test_transaction_id_format(bridge):
    """Test that transaction IDs follow TRX-{node_code}-{6-digit seq} format (exactly 12 chars)."""
    bridge.seed_demo_data()

    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-B-001", "Bob", "C", 1000.00, "A")
    )
    bridge.db.commit()

    result1 = bridge.process_transaction("ACT-B-001", "D", 100.00, "Tx 1")
    result2 = bridge.process_transaction("ACT-B-001", "D", 100.00, "Tx 2")

    tx_id_1 = result1['tx_id']
    tx_id_2 = result2['tx_id']

    # Verify format: TRX-?-000001, TRX-?-000002 (12 chars exactly for PIC X(12))
    # Node TEST maps to code '?' in NODE_CODES (fallback)
    assert tx_id_1.startswith("TRX-?-")
    assert tx_id_2.startswith("TRX-?-")
    assert len(tx_id_1) == 12  # TRX- (4) + code (1) + - (1) + 6-digit seq = 12
    assert int(tx_id_1[-6:]) == 1
    assert int(tx_id_2[-6:]) == 2


def test_chain_is_recorded(bridge):
    """Test that transactions are recorded in the integrity chain."""
    bridge.seed_demo_data()

    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-B-001", "Bob", "C", 1000.00, "A")
    )
    bridge.db.commit()

    result = bridge.process_transaction("ACT-B-001", "D", 100.00, "Test deposit")

    # Verify chain has one entry
    chain_result = bridge.chain.verify_chain()
    assert chain_result['valid'] is True
    assert chain_result['entries_checked'] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
