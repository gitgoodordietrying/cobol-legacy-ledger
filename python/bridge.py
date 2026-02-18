"""
COBOLBridge — Subprocess executor for COBOL programs + fixed-width DAT file parser.
Handles both Mode A (COBOL subprocess) and Mode B (Python-only) seeding.
"""

import subprocess
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import re
from .integrity import IntegrityChain


class COBOLBridge:
    """
    Bridge to COBOL programs (ACCOUNTS, TRANSACT, VALIDATE, REPORTS).
    Also handles fixed-width DAT file parsing for data loading.

    Architecture:
    - Each node is a separate instance (one per bank/clearing)
    - Each node has its own SQLite database and integrity chain
    - COBOL binaries are shared in cobol/bin/
    - Per-node data lives in banks/{NODE}/ with ACCOUNTS.DAT, TRANSACT.DAT, etc.
    - Per-node keys live in banks/{NODE}/.server_key
    """

    # Node code mapping: single-letter codes for transaction IDs (PIC X(12) constraint)
    NODE_CODES = {
        "BANK_A": "A",
        "BANK_B": "B",
        "BANK_C": "C",
        "BANK_D": "D",
        "BANK_E": "E",
        "CLEARING": "Z",  # Clearing house uses 'Z'
    }

    # ACCTREC fixed-width layout (70 bytes per record, ORGANIZATION IS LINE SEQUENTIAL)
    ACCT_RECORD_FORMAT = {
        "id": (0, 10),           # ACCT-ID: PIC X(10)
        "name": (10, 40),        # ACCT-NAME: PIC X(30) — note: ends at byte 40, so (10, 40)
        "type": (40, 41),        # ACCT-TYPE: PIC X(1)
        "balance": (41, 53),     # ACCT-BALANCE: PIC S9(10)V99 (12 bytes fixed)
        "status": (53, 54),      # ACCT-STATUS: PIC X(1)
        "open_date": (54, 62),   # ACCT-OPEN-DATE: PIC 9(8)
        "last_activity": (62, 70), # ACCT-LAST-ACTIVITY: PIC 9(8)
    }

    # TRANSREC fixed-width layout (103 bytes per record)
    TX_RECORD_FORMAT = {
        "id": (0, 12),           # TRANS-ID: PIC X(12)
        "account_id": (12, 22),  # TRANS-ACCT-ID: PIC X(10)
        "type": (22, 23),        # TRANS-TYPE: PIC X(1)
        "amount": (23, 35),      # TRANS-AMOUNT: PIC S9(10)V99 (12 bytes)
        "date": (35, 43),        # TRANS-DATE: PIC 9(8)
        "time": (43, 49),        # TRANS-TIME: PIC 9(6)
        "description": (49, 89), # TRANS-DESC: PIC X(40)
        "status": (89, 91),      # TRANS-STATUS: PIC X(2)
        "batch_id": (91, 103),   # TRANS-BATCH-ID: PIC X(12)
    }

    def __init__(self, node: str, data_dir: str = "banks", bin_dir: str = "cobol/bin"):
        """
        Initialize bridge for a specific node (e.g., 'BANK_A', 'CLEARING').

        :param node: Node identifier (BANK_A, BANK_B, ..., CLEARING)
        :param data_dir: Directory containing per-node subdirectories
        :param bin_dir: Directory containing compiled COBOL binaries
        """
        self.node = node
        self.data_dir = Path(data_dir) / node.lower().replace("_", "-")
        self.bin_dir = Path(bin_dir).resolve()
        self.work_dir = self.data_dir  # Working directory for COBOL subprocess

        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize database (per-node, one SQLite file)
        db_path = self.data_dir / f"{self.node.lower().replace('_', '_')}.db"
        self.db = sqlite3.connect(str(db_path))
        self.db.row_factory = sqlite3.Row  # Return dicts instead of tuples

        # Initialize integrity chain with per-node secret key
        secret_key = self._get_or_create_secret_key()
        self.chain = IntegrityChain(self.db, secret_key)

        # Check if COBOL binaries are available
        self.cobol_available = (self.bin_dir / "ACCOUNTS").exists()

    def _get_or_create_secret_key(self) -> str:
        """Get or create per-node HMAC secret key from .server_key file."""
        key_file = self.data_dir / ".server_key"
        if key_file.exists():
            return key_file.read_text().strip()

        # Create a new per-node key
        import hashlib
        key = hashlib.sha256(f"{self.node}-{datetime.now().isoformat()}".encode()).hexdigest()
        key_file.write_text(key)
        key_file.chmod(0o600)  # Restrict to owner
        return key

    def _parse_balance(self, balance_bytes: bytes) -> float:
        """
        Parse 12-byte balance field (PIC S9(10)V99 with implied decimal).
        GnuCOBOL stores signed numeric as EBCDIC or ASCII digits with sign indicator.
        For simplicity, treat as ASCII string: 10 digits + sign + 2 fractional digits.

        Example: b'000001234567' → 12345.67
        The storage is 12 bytes: 10 digits + 2 fractional digits (no literal decimal).
        """
        try:
            # Decode as ASCII text (GnuCOBOL line-sequential format)
            balance_str = balance_bytes.decode('ascii').strip()

            # Handle sign (leading minus or trailing negative indicator)
            # GnuCOBOL may use trailing '-' or overpunch characters for negatives
            is_negative = False
            if balance_str.startswith('-'):
                is_negative = True
                balance_str = balance_str[1:]
            elif balance_str.endswith('-'):
                is_negative = True
                balance_str = balance_str[:-1]

            # Parse as numeric: 10 + 2 fractional digits
            # If we have 12 digits, split into integer (10) + fraction (2)
            if len(balance_str) == 12 and balance_str.isdigit():
                integer_part = int(balance_str[:10])
                fraction_part = int(balance_str[10:12])
                balance = integer_part + (fraction_part / 100.0)
            else:
                # Fallback: parse directly as float
                # Insert decimal point 2 positions from right if no decimal present
                if '.' not in balance_str:
                    if len(balance_str) >= 2:
                        balance = float(balance_str[:-2] + '.' + balance_str[-2:])
                    else:
                        balance = float(balance_str)
                else:
                    balance = float(balance_str)

            if is_negative:
                balance = -balance

            return balance
        except Exception as e:
            raise ValueError(f"Cannot parse balance {balance_bytes!r}: {e}")

    def load_accounts_from_dat(self, filename: str = "ACCOUNTS.DAT") -> List[Dict[str, Any]]:
        """
        Load accounts from fixed-width ACCOUNTS.DAT file (Mode B — Python-only).
        Called when COBOL binaries are not available.
        """
        accounts = []
        dat_file = self.data_dir / filename

        if not dat_file.exists():
            return accounts

        with open(dat_file, 'rb') as f:
            for line_num, line in enumerate(f, 1):
                # Remove newline if present
                line = line.rstrip(b'\n\r')

                if len(line) < 70:
                    # Pad if needed (shouldn't happen if seed.sh is correct)
                    line = line.ljust(70)

                # Parse each field
                try:
                    record = {}
                    for field_name, (start, end) in self.ACCT_RECORD_FORMAT.items():
                        raw = line[start:end]

                        if field_name == "balance":
                            record[field_name] = self._parse_balance(raw)
                        else:
                            record[field_name] = raw.decode('ascii').strip()

                    accounts.append(record)
                except Exception as e:
                    print(f"Warning: skipping line {line_num} in {filename}: {e}")
                    continue

        return accounts

    def load_accounts_from_cobol(self) -> List[Dict[str, Any]]:
        """
        Load accounts by executing ACCOUNTS binary as subprocess (Mode A — with COBOL).
        Parses pipe-delimited output: ACCOUNT|{ID}|{NAME}|{TYPE}|{BALANCE}|{STATUS}|...
        """
        if not self.cobol_available:
            return []

        accounts = []
        try:
            result = subprocess.run(
                [str(self.bin_dir / "ACCOUNTS"), "LIST"],
                cwd=str(self.work_dir),
                capture_output=True,
                text=True,
                timeout=5
            )

            for line in result.stdout.strip().split('\n'):
                if not line or not line.startswith("ACCOUNT|"):
                    continue

                parts = line.split('|')
                if len(parts) < 7:  # ACCOUNT|id|name|type|balance|status|date|activity
                    continue

                try:
                    account = {
                        "id": parts[1],
                        "name": parts[2],
                        "type": parts[3],
                        "balance": float(parts[4]),  # From COBOL, balance is already formatted
                        "status": parts[5],
                        "open_date": parts[6] if len(parts) > 6 else "",
                        "last_activity": parts[7] if len(parts) > 7 else "",
                    }
                    accounts.append(account)
                except (ValueError, IndexError) as e:
                    print(f"Warning: skipping malformed account line: {line}: {e}")
                    continue

        except subprocess.TimeoutExpired:
            print("Error: ACCOUNTS program timed out")
        except Exception as e:
            print(f"Error executing ACCOUNTS: {e}")

        return accounts

    def list_accounts(self) -> List[Dict[str, Any]]:
        """
        List all accounts. Sync from DAT file if fresh.
        First call loads from DAT (COBOL or Python), subsequent calls read from SQLite.
        """
        # Check if accounts table has data
        cursor = self.db.execute("SELECT COUNT(*) FROM accounts")
        if cursor.fetchone()[0] == 0:
            # Load from DAT and populate database
            self._sync_accounts_to_db()

        cursor = self.db.execute(
            "SELECT id, name, type, balance, status, open_date, last_activity FROM accounts"
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get a single account by ID."""
        cursor = self.db.execute(
            "SELECT id, name, type, balance, status, open_date, last_activity FROM accounts WHERE id = ?",
            (account_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def _sync_accounts_to_db(self):
        """
        Sync accounts from DAT file to SQLite (initial population).
        Uses COBOL if available, falls back to Python file I/O.
        """
        if self.cobol_available:
            accounts = self.load_accounts_from_cobol()
        else:
            accounts = self.load_accounts_from_dat()

        for acct in accounts:
            self.db.execute(
                """INSERT OR REPLACE INTO accounts
                   (id, name, type, balance, status, open_date, last_activity)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (acct['id'], acct['name'], acct['type'], acct['balance'],
                 acct['status'], acct.get('open_date', ''), acct.get('last_activity', ''))
            )
        self.db.commit()

    def process_transaction(self, account_id: str, tx_type: str, amount: float,
                           description: str, target_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a transaction (D=deposit, W=withdraw, T=transfer, etc.).
        Returns {status, tx_id, message, ...}
        """
        # Validate account exists
        account = self.get_account(account_id)
        if not account:
            return {"status": "03", "message": "Invalid account"}

        # Check balance for withdrawals/transfers
        if tx_type in ("W", "T"):
            if account["balance"] < amount:
                return {"status": "01", "message": "Insufficient funds"}

        # Check daily limits
        DAILY_LIMIT = 10000.00  # From COMCODE.cpy
        if amount > DAILY_LIMIT:
            return {"status": "02", "message": "Limit exceeded"}

        # Check account status
        if account["status"] == "F":
            return {"status": "04", "message": "Account frozen"}

        # Generate transaction ID: TRX-{node_code}-{6-digit seq} (exactly 12 chars for PIC X(12))
        # Format: TRX-A-000001 (3 + 1 + 1 + 1 + 6 = 12 chars)
        node_code = self.NODE_CODES.get(self.node, "?")
        cursor = self.db.execute("SELECT MAX(CAST(substr(tx_id, 7) AS INTEGER)) FROM transactions")
        last_seq = cursor.fetchone()[0] or 0
        tx_id = f"TRX-{node_code}-{str(last_seq + 1).zfill(6)}"

        # Record transaction in SQLite
        ts_now = datetime.now().isoformat()
        self.db.execute(
            """INSERT INTO transactions
               (tx_id, account_id, type, amount, timestamp, description, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (tx_id, account_id, tx_type, amount, ts_now, description, "00")
        )

        # Record in integrity chain
        self.chain.append(
            tx_id=tx_id,
            account_id=account_id,
            tx_type=tx_type,
            amount=amount,
            timestamp=ts_now,
            description=description,
            status="00"
        )

        self.db.commit()

        return {
            "status": "00",
            "tx_id": tx_id,
            "message": f"Transaction {tx_type} processed",
            "new_balance": account["balance"] + (amount if tx_type == "D" else -amount if tx_type in ("W", "T") else 0)
        }

    def seed_demo_data(self):
        """
        Create demo account records and populate SQLite.
        This is called during Phase 1 seeding (seed.sh wrapper).
        """
        # Ensure accounts table exists
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                balance REAL NOT NULL,
                status TEXT NOT NULL,
                open_date TEXT,
                last_activity TEXT
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                tx_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                type TEXT NOT NULL,
                amount REAL NOT NULL,
                timestamp TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL
            )
        """)
        self.db.commit()

        # Load from DAT file
        self._sync_accounts_to_db()

    def close(self):
        """Close database connection."""
        if self.db:
            self.db.close()
