"""
Tests for COBOLBridge -- DAT file parsing, account loading, transactions.

Test strategy:
    All tests run in Mode B (Python-only validation) using temporary directories.
    This means no COBOL compiler is needed to run the test suite -- making it
    safe for CI pipelines and developer machines without GnuCOBOL installed.

    The tests verify that Mode B correctly implements the same business rules
    as the COBOL programs: status codes, balance math, transaction ID format,
    daily limits, account freezing, and integrity chain recording.

Test groups:
    - Initialization: Bridge creates correctly with Mode B defaults
    - Balance parsing: PIC S9(10)V99 implied-decimal format handled correctly
    - Secret key: Per-node HMAC key is persistent across instances
    - Account loading: Fixed-width DAT file parsed into correct field values
    - Transaction processing: Deposit, withdraw, NSF, limits, frozen accounts
    - Transaction IDs: Format matches PIC X(12) constraint, monotonically increasing
    - Chain recording: Every successful transaction creates an integrity chain entry

Fixture isolation:
    Each test gets a fresh temporary directory (temp_data_dir fixture).
    This prevents test pollution -- one test's database state cannot affect
    another test. The fixture also cleans up after itself.
"""

import pytest
import tempfile
import sqlite3
from pathlib import Path
from ..bridge import COBOLBridge


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for testing.

    Each test gets an isolated temp dir so database state, DAT files,
    and secret keys don't leak between tests.
    """
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def bridge(temp_data_dir):
    """Create a COBOLBridge instance for testing.

    Uses a nonexistent bin_dir to force Mode B (Python-only). This
    ensures tests don't accidentally try to invoke COBOL binaries.
    """
    return COBOLBridge(node="BANK_TEST", data_dir=str(temp_data_dir), bin_dir="COBOL-BANKING/bin")


# ── Initialization Tests ─────────────────────────────────────────
# Verify that the bridge sets up correctly in Mode B.

def test_bridge_initialization(bridge):
    """Test that bridge initializes correctly."""
    assert bridge.node == "BANK_TEST"
    assert bridge.db is not None
    assert bridge.chain is not None
    # cobol_available should be False since COBOL-BANKING/bin doesn't exist in temp
    assert bridge.cobol_available is False


# ── Balance Parsing Tests ─────────────────────────────────────────
# PIC S9(10)V99 means: 10 integer digits + 2 fractional digits, no decimal
# point stored. "000001234567" means $12,345.67 (not $1,234,567).

def test_parse_balance(temp_data_dir):
    """Test parsing of PIC S9(10)V99 balance field.

    Uses temp directory to avoid creating stray database files in the
    working directory. The bridge needs a real directory for initialization.
    """
    bridge = COBOLBridge(node="TEST", data_dir=str(temp_data_dir), bin_dir="COBOL-BANKING/bin")

    # Test parsing: 12 bytes = 10 digits + 2 fractional
    # Value: 000001234567 -> 12345.67
    balance = bridge._parse_balance(b'000001234567')
    assert balance == 12345.67

    # Zero
    balance = bridge._parse_balance(b'000000000000')
    assert balance == 0.00

    # Large value: 999999999999 -> 9999999999.99
    balance = bridge._parse_balance(b'999999999999')
    assert balance == 9999999999.99


# ── Secret Key Persistence ───────────────────────────────────────
# The HMAC secret key must be stable across bridge restarts. If the key
# changes, all existing chain signatures become invalid.

def test_create_secret_key(bridge, temp_data_dir):
    """Test that secret key is created and persisted."""
    key1 = bridge._get_or_create_secret_key()
    assert isinstance(key1, str)
    assert len(key1) > 0

    # Call again with same data_dir root -- should return same key
    # bridge.data_dir is already temp_data_dir/BANK_TEST, so pass the parent
    bridge2 = COBOLBridge(node="BANK_TEST", data_dir=str(temp_data_dir), bin_dir="COBOL-BANKING/bin")
    key2 = bridge2._get_or_create_secret_key()

    assert key1 == key2


# ── Account Loading Tests ────────────────────────────────────────
# Verify that fixed-width DAT files are parsed correctly.

def test_list_accounts_empty(bridge):
    """Test listing accounts when database is empty."""
    bridge.seed_demo_data()  # Initialize tables
    accounts = bridge.list_accounts()
    assert accounts == []


def test_load_accounts_from_dat(bridge):
    """Test loading accounts from DAT file.

    This test constructs a 70-byte record by hand to verify that each
    field is extracted from the correct byte position. This catches
    off-by-one errors in ACCT_RECORD_FORMAT.
    """
    # Create a test ACCOUNTS.DAT with one record
    # Record format: 70 bytes (ID 10, NAME 30, TYPE 1, BALANCE 12, STATUS 1, OPEN-DATE 8, LAST-ACTIVITY 8)

    # Write test data directly to DAT file
    accounts_file = bridge.data_dir / "ACCOUNTS.DAT"

    # Build a 70-byte record -- each field must be exactly the right width
    acct_id   = b'ACT-T-001 '                        # 10 bytes
    acct_name = b'Test Account                  '     # 30 bytes (padded to 30)
    acct_type = b'C'                                  #  1 byte
    balance   = b'000000100000'                       # 12 bytes (1000.00)
    status    = b'A'                                  #  1 byte
    open_date = b'20260217'                           #  8 bytes
    last_act  = b'20260217'                           #  8 bytes

    record = acct_id + acct_name + acct_type + balance + status + open_date + last_act
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


# ── Transaction Processing Tests ─────────────────────────────────
# Each test verifies a specific business rule implemented in Mode B.
# Status codes: 00=success, 01=NSF, 02=limit, 03=invalid, 04=frozen.

def test_process_transaction_valid(bridge):
    """Test processing a valid deposit -- status 00, balance increases."""
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
    # NODE_CODES maps unknown nodes to '?' fallback
    assert result['tx_id'].startswith('TRX-')
    assert result['new_balance'] == 6000.00


def test_process_transaction_insufficient_funds(bridge):
    """Test that withdrawal is rejected with status 01 when balance is too low."""
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
    """Test that transaction is rejected with status 03 for nonexistent account."""
    bridge.seed_demo_data()

    result = bridge.process_transaction("NONEXISTENT", "D", 100.00, "Test")

    assert result['status'] == '03'  # Invalid account


def test_process_transaction_limit_exceeded(bridge):
    """Test that transaction is rejected with status 02 when amount exceeds $50K daily limit."""
    bridge.seed_demo_data()

    # Insert a test account with high balance
    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-B-001", "Bob Account", "C", 100000.00, "A")
    )
    bridge.db.commit()

    # Exceed daily limit ($50,000 -- limit check is amount > 50000.00)
    result = bridge.process_transaction("ACT-B-001", "D", 50001.00, "Over limit deposit")

    assert result['status'] == '02'  # Limit exceeded


def test_process_transaction_frozen_account(bridge):
    """Test that transaction is rejected with status 04 when account is frozen."""
    bridge.seed_demo_data()

    # Insert a frozen account
    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-B-001", "Frozen Account", "C", 5000.00, "F")
    )
    bridge.db.commit()

    result = bridge.process_transaction("ACT-B-001", "D", 100.00, "Test")

    assert result['status'] == '04'  # Account frozen


# ── Transaction ID Format Tests ──────────────────────────────────
# Transaction IDs must fit PIC X(12) -- exactly 12 characters.
# Format: TRX-{node_code}-{6-digit seq} (monotonically increasing).

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


# ── Integrity Chain Recording Tests ──────────────────────────────
# Every successful transaction MUST create a chain entry. This is the
# "observability" guarantee -- if it happened, it's in the chain.

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


# ── Interest Batch Tests (Mode B) ────────────────────────────────
# Verify that monthly interest accrual applies correct tiered rates.

def test_interest_batch_mode_b(bridge):
    """Test Mode B interest accrual on savings accounts."""
    bridge.seed_demo_data()

    # Insert a savings account with $50K (middle tier: 1.50% APR)
    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-T-001", "Savings Test", "S", 50000.00, "A")
    )
    bridge.db.commit()
    bridge._write_accounts_to_dat([{
        'id': 'ACT-T-001', 'name': 'Savings Test', 'type': 'S',
        'balance': 50000.00, 'status': 'A', 'open_date': '20260217', 'last_activity': '20260217'
    }])

    result = bridge.run_interest_batch()

    assert result['status'] == '00'
    assert result['accounts_processed'] == 1
    # 50000 * 0.015 / 12 = 62.50
    assert abs(result['total_interest'] - 62.50) < 0.01


def test_interest_skips_checking_accounts(bridge):
    """Test that interest is NOT applied to checking accounts (type C)."""
    bridge.seed_demo_data()

    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-T-001", "Checking Test", "C", 50000.00, "A")
    )
    bridge.db.commit()
    bridge._write_accounts_to_dat([{
        'id': 'ACT-T-001', 'name': 'Checking Test', 'type': 'C',
        'balance': 50000.00, 'status': 'A', 'open_date': '20260217', 'last_activity': '20260217'
    }])

    result = bridge.run_interest_batch()

    assert result['status'] == '00'
    assert result['accounts_processed'] == 0
    assert result['total_interest'] == 0.0


# ── Fee Batch Tests (Mode B) ─────────────────────────────────────

def test_fee_batch_mode_b(bridge):
    """Test Mode B fee assessment on checking accounts."""
    bridge.seed_demo_data()

    # Checking account with $1000 (maintenance $12 + low-balance $8 = $20)
    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-T-001", "Fee Test", "C", 1000.00, "A")
    )
    bridge.db.commit()
    bridge._write_accounts_to_dat([{
        'id': 'ACT-T-001', 'name': 'Fee Test', 'type': 'C',
        'balance': 1000.00, 'status': 'A', 'open_date': '20260217', 'last_activity': '20260217'
    }])

    result = bridge.run_fee_batch()

    assert result['status'] == '00'
    assert result['accounts_assessed'] == 1
    assert result['total_fees'] == 12.00  # >$500 so no low-balance fee


def test_fee_waived_for_high_balance(bridge):
    """Test that fees are waived when balance exceeds $5,000."""
    bridge.seed_demo_data()

    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-T-001", "High Balance", "C", 10000.00, "A")
    )
    bridge.db.commit()
    bridge._write_accounts_to_dat([{
        'id': 'ACT-T-001', 'name': 'High Balance', 'type': 'C',
        'balance': 10000.00, 'status': 'A', 'open_date': '20260217', 'last_activity': '20260217'
    }])

    result = bridge.run_fee_batch()

    assert result['status'] == '00'
    assert result['accounts_assessed'] == 0
    assert result['total_fees'] == 0.0


# ── Reconciliation Tests (Mode B) ────────────────────────────────

def test_reconciliation_match(bridge):
    """Test reconciliation passes when balances match transaction history."""
    bridge.seed_demo_data()

    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-T-001", "Recon Test", "C", 6000.00, "A")
    )
    bridge.db.commit()
    bridge._write_accounts_to_dat([{
        'id': 'ACT-T-001', 'name': 'Recon Test', 'type': 'C',
        'balance': 6000.00, 'status': 'A', 'open_date': '20260217', 'last_activity': '20260217'
    }])

    # Deposit $1000 through the bridge
    bridge.process_transaction("ACT-T-001", "D", 1000.00, "Deposit for recon")

    result = bridge.run_reconciliation()

    assert result['status'] == '00'
    assert result['matched'] >= 1
    assert result['mismatched'] == 0


# ── Account Status Updates ───────────────────────────────────────

def test_freeze_account(bridge):
    """Test freezing an account updates status to F."""
    bridge.seed_demo_data()

    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-T-001", "Freeze Test", "C", 5000.00, "A")
    )
    bridge.db.commit()

    result = bridge.update_account_status("ACT-T-001", "F")

    assert result['status'] == '00'
    assert result['old_status'] == 'A'
    assert result['new_status'] == 'F'

    # Verify account is now frozen
    account = bridge.get_account("ACT-T-001")
    assert account['status'] == 'F'


def test_frozen_account_rejects_transactions(bridge):
    """Test that transactions are rejected on frozen accounts (status 04)."""
    bridge.seed_demo_data()

    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-T-001", "Frozen Test", "C", 5000.00, "A")
    )
    bridge.db.commit()

    # Freeze the account
    bridge.update_account_status("ACT-T-001", "F")

    # Try to deposit -- should fail with status 04
    result = bridge.process_transaction("ACT-T-001", "D", 100.00, "Should fail")
    assert result['status'] == '04'


# ── Mode B Validate Tests ───────────────────────────────────────

def test_validate_via_cobol_mode_b_pass(bridge):
    """Test Mode B validation passes for valid transaction."""
    bridge.seed_demo_data()

    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-T-001", "Validate Test", "C", 5000.00, "A")
    )
    bridge.db.commit()

    result = bridge.validate_transaction_via_cobol("ACT-T-001", 100.00)
    assert result['status'] == '00'


def test_validate_via_cobol_mode_b_frozen(bridge):
    """Test Mode B validation catches frozen account."""
    bridge.seed_demo_data()

    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-T-001", "Frozen Validate", "C", 5000.00, "F")
    )
    bridge.db.commit()

    result = bridge.validate_transaction_via_cobol("ACT-T-001", 100.00)
    assert result['status'] == '04'


def test_validate_via_cobol_mode_b_nonexistent(bridge):
    """Test Mode B validation catches nonexistent account."""
    bridge.seed_demo_data()

    result = bridge.validate_transaction_via_cobol("NONEXISTENT", 100.00)
    assert result['status'] == '03'


# ── Mode B Reports Tests ────────────────────────────────────────

def test_report_eod_mode_b(bridge):
    """Test Mode B EOD report generation."""
    bridge.seed_demo_data()

    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-T-001", "Report Test", "C", 5000.00, "A")
    )
    bridge.db.commit()

    lines = bridge.get_reports_via_cobol("EOD")
    assert len(lines) >= 1
    assert any("EOD" in line for line in lines)


def test_report_statement_mode_b(bridge):
    """Test Mode B STATEMENT report for a specific account."""
    bridge.seed_demo_data()

    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-T-001", "Statement Test", "C", 5000.00, "A")
    )
    bridge.db.commit()

    bridge.process_transaction("ACT-T-001", "D", 100.00, "Deposit")

    lines = bridge.get_reports_via_cobol("STATEMENT", "ACT-T-001")
    assert len(lines) >= 1
    assert any("STATEMENT" in line for line in lines)


def test_report_audit_mode_b(bridge):
    """Test Mode B AUDIT report includes chain status."""
    bridge.seed_demo_data()
    lines = bridge.get_reports_via_cobol("AUDIT")
    assert len(lines) >= 1
    assert any("AUDIT" in line and "Chain" in line for line in lines)


# ── Mode B Batch Processing Tests ────────────────────────────────

def test_batch_processing_mode_b(bridge, temp_data_dir):
    """Test Mode B batch processing from pipe-delimited file."""
    bridge.seed_demo_data()

    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-T-001", "Batch Test", "C", 5000.00, "A")
    )
    bridge.db.commit()

    # Create a batch file
    batch_file = temp_data_dir / "BANK_TEST" / "BATCH-INPUT.DAT"
    batch_file.write_text("ACT-T-001|D|100.00|Deposit 1\nACT-T-001|D|200.00|Deposit 2\n")

    result = bridge.process_batch_via_cobol(str(batch_file))

    assert result['summary']['total'] == 2
    assert result['summary']['success'] == 2
    assert result['summary']['failed'] == 0


def test_batch_processing_with_failures(bridge, temp_data_dir):
    """Test batch processing handles bad lines gracefully."""
    bridge.seed_demo_data()

    bridge.db.execute(
        "INSERT INTO accounts (id, name, type, balance, status) VALUES (?, ?, ?, ?, ?)",
        ("ACT-T-001", "Batch Fail Test", "C", 100.00, "A")
    )
    bridge.db.commit()

    # Second line will fail (withdrawal > balance)
    batch_file = temp_data_dir / "BANK_TEST" / "BATCH-INPUT.DAT"
    batch_file.write_text("ACT-T-001|D|50.00|Good deposit\nACT-T-001|W|9999.00|Too much\n")

    result = bridge.process_batch_via_cobol(str(batch_file))

    assert result['summary']['total'] == 2
    assert result['summary']['success'] == 1
    assert result['summary']['failed'] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
