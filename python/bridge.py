"""
COBOLBridge -- Subprocess executor for COBOL programs + fixed-width DAT file parser.

This is the central integration point between COBOL and Python. It operates in
two modes:

    Mode A (COBOL subprocess): When compiled COBOL binaries exist in
    COBOL-BANKING/bin/, the bridge calls them via subprocess.run(), passes
    arguments, and parses their pipe-delimited stdout output. This preserves
    COBOL immutability -- the COBOL programs are never modified, only invoked.

    Mode B (Python-only): When COBOL binaries are not available (CI servers,
    developer machines without GnuCOBOL, Windows without Docker), the bridge
    implements equivalent business logic in Python. This ensures the full system
    can be tested and demonstrated without requiring a COBOL compiler.

Why subprocess wrapping (not FFI or shared memory):
    COBOL programs are batch-oriented -- they read files, process records, and
    write output. Subprocess execution matches this paradigm perfectly. It also
    means zero modifications to the COBOL source: no API adapters, no library
    wrappers, no recompilation. The COBOL programs don't even know Python exists.

Data flow:
    Python writes DAT files -> COBOL reads them -> COBOL writes output to
    stdout (pipe-delimited) -> Python parses stdout -> Python records in SQLite
    + integrity chain

Fixed-width record parsing:
    COBOL uses fixed-width records (no delimiters, no headers). ACCOUNTS.DAT
    records are exactly 70 bytes: 10 for ID, 30 for name, 1 for type, 12 for
    balance (PIC S9(10)V99 with implied decimal), 1 for status, 8 for open date,
    8 for last activity. Python slices these byte ranges to extract fields.

Per-node isolation:
    Each COBOLBridge instance represents one banking node. It has its own data
    directory, SQLite database, and integrity chain. This mirrors real banking
    architecture where each institution operates independently.
"""

import subprocess
import sqlite3
import os
import sys
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
    - COBOL binaries are shared in COBOL-BANKING/bin/
    - Per-node data lives in COBOL-BANKING/data/{NODE}/ with ACCOUNTS.DAT, TRANSACT.DAT, etc.
    - Per-node keys live in COBOL-BANKING/data/{NODE}/.server_key
    """

    # ── Node Code Mapping ─────────────────────────────────────────
    # Single-letter codes used in transaction IDs to identify which node
    # generated them. Transaction IDs must fit in PIC X(12) -- exactly
    # 12 characters -- so we use TRX-{code}-{6-digit seq} format.
    NODE_CODES = {
        "BANK_A": "A",
        "BANK_B": "B",
        "BANK_C": "C",
        "BANK_D": "D",
        "BANK_E": "E",
        "CLEARING": "Z",  # Clearing house uses 'Z'
    }

    # ── ACCTREC Fixed-Width Layout ────────────────────────────────
    # Maps field names to (start, end) byte positions in ACCOUNTS.DAT.
    # Total record length: 70 bytes. This matches the COBOL copybook
    # ACCTREC.cpy exactly. ORGANIZATION IS LINE SEQUENTIAL means each
    # record is followed by a newline (not counted in the 70 bytes).
    ACCT_RECORD_FORMAT = {
        "id": (0, 10),           # ACCT-ID: PIC X(10)
        "name": (10, 40),        # ACCT-NAME: PIC X(30) -- note: ends at byte 40, so (10, 40)
        "type": (40, 41),        # ACCT-TYPE: PIC X(1)
        "balance": (41, 53),     # ACCT-BALANCE: PIC S9(10)V99 (12 bytes fixed)
        "status": (53, 54),      # ACCT-STATUS: PIC X(1)
        "open_date": (54, 62),   # ACCT-OPEN-DATE: PIC 9(8)
        "last_activity": (62, 70), # ACCT-LAST-ACTIVITY: PIC 9(8)
    }

    # ── TRANSREC Fixed-Width Layout ───────────────────────────────
    # Maps field names to (start, end) byte positions in TRANSACT.DAT.
    # Total record length: 103 bytes. Matches TRANSREC.cpy.
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

    def __init__(self, node: str, data_dir: str = "COBOL-BANKING/data", bin_dir: str = "COBOL-BANKING/bin"):
        """
        Initialize bridge for a specific node (e.g., 'BANK_A', 'CLEARING').

        :param node: Node identifier (BANK_A, BANK_B, ..., CLEARING)
        :param data_dir: Directory containing per-node subdirectories
        :param bin_dir: Directory containing compiled COBOL binaries
        """
        self.node = node
        self.data_dir = Path(data_dir) / node  # Fixed: use node directly (BANK_A not bank-a)
        self.bin_dir = Path(bin_dir).resolve()
        self.work_dir = self.data_dir  # Working directory for COBOL subprocess

        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # ── Per-Node SQLite Database ──────────────────────────────
        # Each node gets its own database file (bank_a.db, clearing.db, etc.)
        # co-located with its data files. This enforces isolation: BANK_A
        # cannot read BANK_B's database.
        db_path = self.data_dir / f"{self.node.lower()}.db"  # bank_a.db format
        self.db = sqlite3.connect(str(db_path))
        self.db.row_factory = sqlite3.Row  # Return dicts instead of tuples

        # Ensure required tables exist
        self._ensure_tables()

        # ── Integrity Chain Initialization ────────────────────────
        # Each node has its own integrity chain with its own secret key.
        # The chain records every transaction that passes through this node.
        secret_key = self._get_or_create_secret_key()
        self.chain = IntegrityChain(self.db, secret_key)

        # ── COBOL Availability Detection ──────────────────────────
        # If the ACCOUNTS binary exists, we're in Mode A (COBOL subprocess).
        # Otherwise, we fall back to Mode B (Python-only).
        self.cobol_available = (self.bin_dir / "ACCOUNTS").exists()

        # On Windows, COBOL binaries are Linux ELF format and need Docker
        self.use_docker = self.cobol_available and sys.platform == "win32"

    def _run_cobol_program(self, program: str, args: list, cwd: str = None, timeout: int = 5) -> subprocess.CompletedProcess:
        """
        Run a COBOL program, routing through Docker on Windows.
        On Linux/Docker, runs binary directly. On Windows, uses docker run.

        The Docker routing is transparent to callers -- they just call
        _run_cobol_program("TRANSACT", ["DEPOSIT", "ACT-A-001", "500.00"])
        and get the same stdout/stderr regardless of platform.
        """
        if self.use_docker:
            # Route through Docker: mount project root at /app, cd to node dir
            project_root = Path(self.bin_dir).resolve().parent.parent
            # Convert Windows path to Docker-compatible format
            docker_path = str(project_root)
            # Convert backslashes to forward slashes for Docker volume mount
            docker_path = docker_path.replace('\\', '/')
            # Convert drive letter: B:/... -> //b/... for Git Bash / Docker on Windows
            if len(docker_path) >= 2 and docker_path[1] == ':':
                docker_path = '/' + docker_path[0].lower() + docker_path[2:]

            # Build the command to run inside Docker
            node_dir = f"/app/COBOL-BANKING/data/{self.node}"
            cobol_bin = f"/app/COBOL-BANKING/bin/{program}"
            # Shell-escape each argument to handle special chars (|, &, etc.)
            import shlex
            escaped_args = ' '.join(shlex.quote(a) for a in args)
            inner_cmd = f"cd {node_dir} && {cobol_bin} {escaped_args}"

            docker_cmd = [
                "docker", "run", "--rm",
                "-v", f"{docker_path}:/app",
                "-w", "/app",
                "cobol-dev",
                "bash", "-c", inner_cmd
            ]

            # MSYS_NO_PATHCONV prevents Git Bash from mangling /app paths
            env = os.environ.copy()
            env["MSYS_NO_PATHCONV"] = "1"

            return subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 10,  # Extra time for Docker overhead
                env=env
            )
        else:
            # Direct execution (inside Docker or on Linux)
            cmd = [str(self.bin_dir / program)] + args
            return subprocess.run(
                cmd,
                cwd=cwd or str(self.work_dir),
                capture_output=True,
                text=True,
                timeout=timeout
            )

    def _ensure_tables(self):
        """Ensure required database tables exist."""
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

    def _get_or_create_secret_key(self) -> str:
        """Get or create per-node HMAC secret key from .server_key file.

        Each node has a unique secret key stored in a dotfile. This key is
        used for HMAC signatures in the integrity chain. If the key file
        doesn't exist (first run), one is generated from the node name + timestamp.
        """
        key_file = self.data_dir / ".server_key"
        if key_file.exists():
            return key_file.read_text().strip()

        # Create a new per-node key
        import hashlib
        key = hashlib.sha256(f"{self.node}-{datetime.now().isoformat()}".encode()).hexdigest()
        key_file.write_text(key)
        key_file.chmod(0o600)  # Restrict to owner
        return key

    # ── Balance Parsing ───────────────────────────────────────────
    # COBOL's PIC S9(10)V99 stores numbers as fixed-point with an IMPLIED
    # decimal point. The decimal is never stored in the file -- instead,
    # the last 2 digits are always fractional cents. So 000001234567 means
    # $12,345.67 (not $1,234,567). GnuCOBOL can also output explicit
    # decimals (+0000012345.67) after processing, so we handle both formats.

    def _parse_balance(self, balance_bytes: bytes) -> float:
        """
        Parse 12-byte balance field (PIC S9(10)V99 with implied decimal).
        GnuCOBOL stores signed numeric as ASCII digits with sign indicator.

        Two formats supported:
        1. Implied decimal (seed format): b'000001234567' -> 12345.67 (12 ASCII digits)
        2. Explicit decimal (after COBOL update): '+0000012345.67' or '-0000012345.67' (14 chars with sign+period)

        Examples:
        - b'000001234567' -> 12345.67 (10 digits + 2 fractional, no decimal)
        - b'+0000012345.67' -> 12345.67 (GnuCOBOL output format with literal decimal)
        """
        try:
            # Decode as ASCII text (GnuCOBOL line-sequential format)
            balance_str = balance_bytes.decode('ascii').strip()

            # Handle sign (leading +/- or trailing negative indicator)
            is_negative = False
            if balance_str.startswith('-'):
                is_negative = True
                balance_str = balance_str[1:]
            elif balance_str.startswith('+'):
                balance_str = balance_str[1:]
            elif balance_str.endswith('-'):
                is_negative = True
                balance_str = balance_str[:-1]

            # CRITICAL: GnuCOBOL may output explicit decimal: +0000012345.67 format
            # Check if we have explicit decimal point (newer COBOL format)
            if '.' in balance_str:
                # Explicit decimal format: parse directly
                balance = float(balance_str)
            elif len(balance_str) == 12 and balance_str.isdigit():
                # Implied decimal format (10 digits + 2 fractional): split manually
                integer_part = int(balance_str[:10])
                fraction_part = int(balance_str[10:12])
                balance = integer_part + (fraction_part / 100.0)
            else:
                # Fallback: try direct float conversion
                if len(balance_str) >= 2 and '.' not in balance_str:
                    # Insert decimal point 2 positions from right
                    balance = float(balance_str[:-2] + '.' + balance_str[-2:])
                else:
                    balance = float(balance_str)

            if is_negative:
                balance = -balance

            return balance
        except Exception as e:
            raise ValueError(f"Cannot parse balance {balance_bytes!r}: {e}")

    # ── DAT File I/O (Mode B) ────────────────────────────────────
    # These methods read and write COBOL's fixed-width data files directly
    # from Python. In Mode A, COBOL reads/writes these files; Python only
    # reads them for syncing to SQLite. In Mode B, Python does everything.

    def load_accounts_from_dat(self, filename: str = "ACCOUNTS.DAT") -> List[Dict[str, Any]]:
        """
        Load accounts from fixed-width ACCOUNTS.DAT file (Mode B -- Python-only).
        Called when COBOL binaries are not available.

        Each line is exactly 70 bytes (plus newline). Fields are extracted by
        byte-slicing according to ACCT_RECORD_FORMAT -- no delimiters, no headers.
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

                # Parse each field by slicing the byte range
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

    # ── COBOL Subprocess Output Parsing (Mode A) ──────────────────
    # COBOL programs write pipe-delimited output to stdout. The bridge
    # parses specific prefixes to extract structured data:
    #   ACCOUNT|id|name|type|balance|status|...  (from ACCOUNTS LIST)
    #   OK|type|tx_id|account|balance            (from TRANSACT success)
    #   RESULT|status_code                       (from any program)

    def load_accounts_from_cobol(self) -> List[Dict[str, Any]]:
        """
        Load accounts by executing ACCOUNTS binary as subprocess (Mode A -- with COBOL).
        Parses pipe-delimited output: ACCOUNT|{ID}|{NAME}|{TYPE}|{BALANCE}|{STATUS}|...
        """
        if not self.cobol_available:
            return []

        accounts = []
        try:
            result = self._run_cobol_program("ACCOUNTS", ["LIST"])

            for line in result.stdout.strip().split('\n'):
                if not line or not line.startswith("ACCOUNT|"):
                    continue

                parts = line.split('|')
                if len(parts) < 7:  # ACCOUNT|id|name|type|balance|status|date|activity
                    continue

                try:
                    account = {
                        "id": parts[1].strip(),
                        "name": parts[2].strip(),
                        "type": parts[3].strip(),
                        "balance": float(parts[4].strip()) if parts[4].strip() else 0.0,
                        "status": parts[5].strip(),
                        "open_date": parts[6].strip() if len(parts) > 6 else "",
                        "last_activity": parts[7].strip() if len(parts) > 7 else "",
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

    def process_transaction_via_cobol(self, tx_type: str, account_id: str, amount: float,
                                     description: str, target_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a transaction by calling COBOL TRANSACT binary (Mode A).
        Parses output: OK|{TYPE}|{TX_ID}|{ACCOUNT}|{BALANCE} and RESULT|{STATUS}

        Note: Description is NOT passed to COBOL because multi-word strings
        break COBOL's UNSTRING DELIMITED BY SPACE parsing. Description stays
        Python-side only (stored in SQLite and the integrity chain).
        """
        if not self.cobol_available:
            return {"status": "99", "message": "COBOL not available"}

        result = {"status": "99", "message": "Unknown error"}
        try:
            # Map type codes to COBOL operation keywords
            op_map = {"D": "DEPOSIT", "W": "WITHDRAW", "T": "TRANSFER",
                       "I": "DEPOSIT", "F": "WITHDRAW"}
            operation = op_map.get(tx_type.upper(), tx_type.upper())
            # TRANSACT.cob UNSTRING order: OPERATION ACCT-ID AMOUNT TARGET-ID
            # Don't pass description to COBOL -- multi-word descriptions break
            # UNSTRING DELIMITED BY SPACE. COBOL generates its own TRANS-DESC.
            # Description stays Python-side only (SQLite + integrity chain).
            cobol_args = [operation, account_id.strip(), str(amount)]
            if target_id:
                cobol_args.append(target_id.strip())

            proc = self._run_cobol_program("TRANSACT", cobol_args)

            # Parse output: RESULT|{STATUS} at end, and OK|... if success
            for line in proc.stdout.strip().split('\n'):
                if line.startswith("RESULT|"):
                    result["status"] = line.split('|')[1] if len(line.split('|')) > 1 else "99"
                elif line.startswith("OK|"):
                    parts = line.split('|')
                    if len(parts) >= 5:
                        bal_str = parts[4].strip()
                        result.update({
                            "message": f"Transaction {tx_type} processed",
                            "tx_id": parts[2].strip(),
                            "new_balance": float(bal_str) if bal_str else 0.0
                        })

        except subprocess.TimeoutExpired:
            result["message"] = "TRANSACT program timed out"
        except Exception as e:
            result["message"] = f"Error executing TRANSACT: {e}"

        return result

    def validate_transaction_via_cobol(self, account_id: str, amount: float) -> Dict[str, str]:
        """
        Validate a transaction against business rules.

        Mode A: Calls COBOL VALIDATE binary, parses RESULT|{STATUS} output.
        Mode B: Runs the same 4-check sequence in Python (exists, frozen, NSF, limit).

        Validation order matches VALIDATE.cob:
            1. Account exists     -> status 03 if not found
            2. Account not frozen -> status 04 if frozen
            3. Sufficient funds   -> status 01 if NSF (withdrawals only)
            4. Within daily limit -> status 02 if over $50K
        """
        if self.cobol_available:
            result = {"status": "99", "message": "Unknown error"}
            try:
                proc = self._run_cobol_program("VALIDATE", [account_id.strip(), str(amount)])

                for line in proc.stdout.strip().split('\n'):
                    if line.startswith("RESULT|"):
                        result["status"] = line.split('|')[1] if len(line.split('|')) > 1 else "99"
                        result["message"] = self._status_code_to_message(result["status"])

            except subprocess.TimeoutExpired:
                result["message"] = "VALIDATE program timed out"
            except Exception as e:
                result["message"] = f"Error executing VALIDATE: {e}"

            return result

        # Mode B: Python-only validation (mirrors VALIDATE.cob logic)
        return self._mode_b_validate(account_id, amount)

    def _mode_b_validate(self, account_id: str, amount: float) -> Dict[str, str]:
        """
        Mode B validation implementing the same 4 checks as VALIDATE.cob.

        DESIGN PATTERN: This method is the single source of truth for Mode B
        validation logic. Both validate_transaction_via_cobol() (when COBOL
        is unavailable) and process_transaction() (Mode B path) use the same
        validation order. Keeping it in one place prevents drift between the
        two code paths.

        Returns:
            Dict with 'status' (2-char code) and 'message' (human-readable).
        """
        # 1. Account exists
        account = self.get_account(account_id)
        if not account:
            return {"status": "03", "message": "Invalid account"}

        # 2. Account not frozen
        if account["status"] == "F":
            return {"status": "04", "message": "Account frozen"}

        # 3. Sufficient funds (for withdrawals/transfers)
        if account["balance"] < amount:
            return {"status": "01", "message": "Insufficient funds"}

        # 4. Daily limit check ($50,000 from TRANSACT.cob WS-DAILY-LIMIT)
        DAILY_LIMIT = 50000.00
        if amount > DAILY_LIMIT:
            return {"status": "02", "message": "Limit exceeded"}

        return {"status": "00", "message": "Validation passed"}

    def get_reports_via_cobol(self, report_type: str, account_id: Optional[str] = None) -> List[str]:
        """
        Get reports from the banking node.

        Mode A: Calls COBOL REPORTS binary, returns pipe-delimited output lines.
        Mode B: Generates equivalent reports from SQLite + DAT file data.

        Report types:
            STATEMENT — Transaction history for one account
            LEDGER    — All transactions across all accounts
            EOD       — End-of-day summary (totals, counts)
            AUDIT     — Full account listing with chain verification status
        """
        if self.cobol_available:
            report_lines = []
            try:
                cobol_args = [report_type.upper()]
                if account_id and report_type.upper() == "STATEMENT":
                    cobol_args.append(account_id)

                proc = self._run_cobol_program("REPORTS", cobol_args)

                for line in proc.stdout.strip().split('\n'):
                    if not line.startswith("RESULT|"):
                        report_lines.append(line)

            except subprocess.TimeoutExpired:
                report_lines.append("ERROR: REPORTS program timed out")
            except Exception as e:
                report_lines.append(f"ERROR executing REPORTS: {e}")

            return report_lines

        # Mode B: Python-only report generation
        return self._mode_b_report(report_type, account_id)

    def _mode_b_report(self, report_type: str, account_id: Optional[str] = None) -> List[str]:
        """
        Mode B report generation from SQLite data.

        Produces the same pipe-delimited output format as COBOL REPORTS.cob
        so that downstream consumers (CLI, tests) work identically regardless
        of which mode generated the report.
        """
        rtype = report_type.upper()
        lines = []

        if rtype == "STATEMENT":
            if not account_id:
                return ["ERROR|Account ID required for STATEMENT report"]
            account = self.get_account(account_id)
            if not account:
                return [f"ERROR|Account {account_id} not found"]
            lines.append(f"STATEMENT|{account_id}|{account['name']}|Balance: ${account['balance']:.2f}")
            cursor = self.db.execute(
                "SELECT tx_id, type, amount, timestamp, description, status "
                "FROM transactions WHERE account_id = ? ORDER BY timestamp",
                (account_id,)
            )
            for row in cursor.fetchall():
                lines.append(
                    f"STATEMENT|{row[0]}|{row[1]}|{row[2]:.2f}|{row[3]}|{row[4]}|{row[5]}"
                )

        elif rtype == "LEDGER":
            cursor = self.db.execute(
                "SELECT tx_id, account_id, type, amount, timestamp, description, status "
                "FROM transactions ORDER BY timestamp"
            )
            for row in cursor.fetchall():
                lines.append(
                    f"LEDGER|{row[0]}|{row[1]}|{row[2]}|{row[3]:.2f}|{row[4]}|{row[5]}|{row[6]}"
                )

        elif rtype == "EOD":
            accounts = self.list_accounts()
            total_balance = sum(a['balance'] for a in accounts)
            cursor = self.db.execute("SELECT COUNT(*) FROM transactions")
            tx_count = cursor.fetchone()[0]
            lines.append(f"EOD|{self.node}|Accounts: {len(accounts)}|Transactions: {tx_count}|Total Balance: ${total_balance:.2f}")

        elif rtype == "AUDIT":
            accounts = self.list_accounts()
            chain_result = self.chain.verify_chain()
            chain_status = "INTACT" if chain_result['valid'] else "BROKEN"
            lines.append(f"AUDIT|{self.node}|Chain: {chain_status}|Entries: {chain_result['entries_checked']}")
            for acct in accounts:
                lines.append(
                    f"AUDIT|{acct['id']}|{acct['name']}|{acct['type']}|${acct['balance']:.2f}|{acct['status']}"
                )

        else:
            lines.append(f"ERROR|Unknown report type: {report_type}")

        return lines

    def process_batch_via_cobol(self, batch_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a batch of transactions from a pipe-delimited input file.

        Mode A: Calls COBOL TRANSACT BATCH binary, parses columnar output.
        Mode B: Reads the batch file in Python and processes each line
                through process_transaction().

        Batch file format (pipe-delimited, one per line):
            ACCOUNT_ID|TYPE|AMOUNT|DESCRIPTION          (D/W/I/F types)
            ACCOUNT_ID|T|AMOUNT|DESCRIPTION|TARGET_ID   (transfers only)

        Returns:
            Dict with status, output lines, and summary counts.
        """
        if self.cobol_available:
            result = {"status": "99", "message": "Unknown error", "output": [], "summary": {}}
            try:
                proc = self._run_cobol_program("TRANSACT", ["BATCH"], timeout=30)

                output_lines = proc.stdout.strip().split('\n')
                result["output"] = output_lines

                # Parse summary lines (after "--- END BATCH RUN ---")
                in_summary = False
                for line in output_lines:
                    if "--- END BATCH RUN ---" in line:
                        in_summary = True
                        continue
                    if in_summary and "Total transactions read:" in line:
                        result["summary"]["total"] = int(line.split(":")[-1].strip())
                    elif in_summary and "Successful:" in line:
                        result["summary"]["success"] = int(line.split(":")[-1].strip())
                    elif in_summary and "Failed:" in line:
                        result["summary"]["failed"] = int(line.split(":")[-1].strip())

                # Check for RESULT| line
                for line in output_lines:
                    if line.startswith("RESULT|"):
                        result["status"] = line.split('|')[1] if len(line.split('|')) > 1 else "99"

            except subprocess.TimeoutExpired:
                result["message"] = "TRANSACT BATCH timed out"
            except Exception as e:
                result["message"] = f"Error executing TRANSACT BATCH: {e}"

            return result

        # Mode B: Python-only batch processing
        return self._mode_b_batch(batch_file)

    def _mode_b_batch(self, batch_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Mode B batch processing -- reads pipe-delimited BATCH-INPUT.DAT and
        processes each line through process_transaction().

        DESIGN PATTERN: Batch processing in COBOL reads a sequential file
        record by record. This Python equivalent reads line by line and
        delegates to the same transaction engine, producing identical
        status codes and chain entries.
        """
        if batch_file is None:
            batch_file = str(self.data_dir / "BATCH-INPUT.DAT")

        batch_path = Path(batch_file)
        if not batch_path.exists():
            return {"status": "99", "message": f"Batch file not found: {batch_file}",
                    "output": [], "summary": {"total": 0, "success": 0, "failed": 0}}

        output_lines = []
        success = 0
        failed = 0
        total = 0

        with open(batch_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                total += 1
                parts = line.split('|')
                if len(parts) < 4:
                    output_lines.append(f"LINE {line_num}|ERROR|Bad format: {line}")
                    failed += 1
                    continue

                account_id = parts[0].strip()
                tx_type = parts[1].strip().upper()
                try:
                    amount = float(parts[2].strip())
                except ValueError:
                    output_lines.append(f"LINE {line_num}|ERROR|Invalid amount: {parts[2]}")
                    failed += 1
                    continue
                description = parts[3].strip()
                target_id = parts[4].strip() if len(parts) > 4 else None

                result = self.process_transaction(account_id, tx_type, amount, description, target_id)

                if result['status'] == '00':
                    success += 1
                    output_lines.append(
                        f"LINE {line_num}|OK|{result['tx_id']}|{account_id}|{tx_type}|{amount:.2f}"
                    )
                else:
                    failed += 1
                    output_lines.append(
                        f"LINE {line_num}|FAIL|{result['status']}|{result['message']}"
                    )

        return {
            "status": "00" if failed == 0 else "01",
            "message": f"Batch complete: {success} success, {failed} failed",
            "output": output_lines,
            "summary": {"total": total, "success": success, "failed": failed},
        }

    # ── Status Code Translation ───────────────────────────────────
    # COBOL programs return 2-character status codes (PIC X(2)).
    # These match the project convention defined in COMCODE.cpy:
    #   00=success, 01=NSF, 02=limit, 03=invalid, 04=frozen, 99=error

    def _status_code_to_message(self, code: str) -> str:
        """Convert status code to human-readable message."""
        messages = {
            "00": "Success",
            "01": "Insufficient funds",
            "02": "Limit exceeded",
            "03": "Invalid account",
            "04": "Account frozen",
            "99": "System error",
        }
        return messages.get(code, f"Unknown status: {code}")

    # ── Account Operations ────────────────────────────────────────
    # These methods provide a unified API regardless of Mode A or B.
    # On first call, accounts are loaded from DAT (via COBOL or Python)
    # and cached in SQLite. Subsequent calls read from SQLite.

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

    def update_account_status(self, account_id: str, new_status: str) -> Dict[str, Any]:
        """
        Update account status in both DAT file and SQLite.

        Mode A: Calls COBOL ACCOUNTS UPDATE binary first, then syncs.
        Mode B: Direct file + DB update with integrity chain recording.

        Statuses: A=active, F=frozen, C=closed.
        """
        if new_status not in ('A', 'F', 'C'):
            return {'status': '03', 'message': f'Invalid status: {new_status}'}

        account = self.get_account(account_id)
        if not account:
            return {'status': '03', 'message': f'Account {account_id} not found'}

        old_status = account['status']

        # Mode A: Route through COBOL ACCOUNTS UPDATE binary
        if self.cobol_available:
            try:
                proc = self._run_cobol_program(
                    "ACCOUNTS", ["UPDATE", account_id.strip(), f"STATUS={new_status}"]
                )
                # Resync DAT -> SQLite after COBOL modified the file
                self._sync_accounts_to_db()
            except Exception:
                pass  # Fall through to Mode B update below

        # Update SQLite (both modes -- ensures consistency)
        self.db.execute(
            "UPDATE accounts SET status = ?, last_activity = ? WHERE id = ?",
            (new_status, datetime.now().strftime('%Y%m%d'), account_id)
        )
        self.db.commit()

        # Update DAT file -- read all accounts from DB, rewrite
        cursor = self.db.execute(
            "SELECT id, name, type, balance, status, open_date, last_activity FROM accounts"
        )
        all_accounts = [dict(row) for row in cursor.fetchall()]
        self._write_accounts_to_dat(all_accounts)

        # Record in integrity chain
        ts_now = datetime.now().isoformat()
        node_code = self.NODE_CODES.get(self.node, 'X')
        tx_id = f"STS-{node_code}-{datetime.now().strftime('%H%M%S')}"[:12]
        self.chain.append(
            tx_id=tx_id,
            account_id=account_id,
            tx_type='S',  # Status change
            amount=0.0,
            timestamp=ts_now,
            description=f"Status {old_status}->{new_status}",
            status='00',
        )

        return {
            'status': '00',
            'message': f'{account_id} status changed {old_status}->{new_status}',
            'old_status': old_status,
            'new_status': new_status,
        }

    # ── SQLite Sync ───────────────────────────────────────────────
    # After every COBOL operation, the bridge syncs account data from DAT
    # files into SQLite. This creates a "snapshot" of what COBOL reported.
    # The cross_verify module later compares this snapshot against the
    # current DAT file to detect unauthorized changes.

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

    # ── Transaction Processing ────────────────────────────────────
    # The main entry point for all transaction types. In Mode A, delegates
    # to COBOL and then wraps the result with integrity chain + SQLite
    # recording. In Mode B, implements the full validation logic in Python.

    def process_transaction(self, account_id: str, tx_type: str, amount: float,
                           description: str, target_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a transaction (D=deposit, W=withdraw, T=transfer, etc.).
        Uses COBOL subprocess (Mode A) if available, falls back to Python validation (Mode B).
        Returns {status, tx_id, message, new_balance, ...}
        """
        # ── Mode A: Delegate to COBOL ─────────────────────────────
        # COBOL handles validation + balance update. Python wraps the
        # result with integrity chain recording and SQLite sync.
        if self.cobol_available:
            result = self.process_transaction_via_cobol(tx_type, account_id, amount, description, target_id)
            if result["status"] == "00":
                # Record in integrity chain (Python layer wraps COBOL)
                ts_now = datetime.now().isoformat()
                tx_id = result.get("tx_id", "")
                if tx_id:
                    self.chain.append(
                        tx_id=tx_id,
                        account_id=account_id,
                        tx_type=tx_type,
                        amount=amount,
                        timestamp=ts_now,
                        description=description,
                        status="00"
                    )
                    # Also record in SQLite for reporting
                    self.db.execute(
                        """INSERT INTO transactions
                           (tx_id, account_id, type, amount, timestamp, description, status)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (tx_id, account_id, tx_type, amount, ts_now, description, "00")
                    )
                    # Sync account balance from COBOL output to SQLite
                    new_balance = result.get("new_balance")
                    if new_balance is not None:
                        self.db.execute(
                            "UPDATE accounts SET balance = ? WHERE id = ?",
                            (new_balance, account_id.strip())
                        )
                    self.db.commit()
            return result

        # ── Mode B: Python-Only Validation ────────────────────────
        # Implements the same business rules as COBOL's VALIDATE.cob
        # and TRANSACT.cob, but in Python. Status codes match exactly.
        # Validation order matches VALIDATE.cob: exists -> frozen -> NSF -> limit.

        # 1. Validate account exists
        account = self.get_account(account_id)
        if not account:
            return {"status": "03", "message": "Invalid account"}

        # 2. Check account status (frozen accounts reject ALL operations)
        if account["status"] == "F":
            return {"status": "04", "message": "Account frozen"}

        # 3. Check balance for withdrawals/transfers (NSF)
        if tx_type in ("W", "T"):
            if account["balance"] < amount:
                return {"status": "01", "message": "Insufficient funds"}

        # 4. Check daily limits (50000.00 from TRANSACT.cob)
        DAILY_LIMIT = 50000.00
        if amount > DAILY_LIMIT:
            return {"status": "02", "message": "Limit exceeded"}

        # ── Transaction ID Generation ─────────────────────────────
        # Format: TRX-{node_code}-{6-digit seq} (exactly 12 chars for PIC X(12))
        # Example: TRX-A-000001 (3 + 1 + 1 + 1 + 6 = 12 chars)
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

        # Update source account balance in DB
        new_balance = account["balance"] + (amount if tx_type == "D" else -amount if tx_type in ("W", "T") else 0)
        self.db.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_balance, account_id))

        # ── Transfer: Credit Destination ──────────────────────────
        # For intra-bank transfers (type T), we also credit the target
        # account and create a matching deposit transaction.
        if tx_type == "T" and target_id:
            dest_account = self.get_account(target_id)
            if dest_account:
                dest_new_balance = dest_account["balance"] + amount
                self.db.execute("UPDATE accounts SET balance = ? WHERE id = ?", (dest_new_balance, target_id))

                # Generate dest-side transaction
                cursor2 = self.db.execute("SELECT MAX(CAST(substr(tx_id, 7) AS INTEGER)) FROM transactions")
                last_seq2 = cursor2.fetchone()[0] or 0
                dest_tx_id = f"TRX-{node_code}-{str(last_seq2 + 1).zfill(6)}"

                self.db.execute(
                    """INSERT INTO transactions (tx_id, account_id, type, amount, timestamp, description, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (dest_tx_id, target_id, 'D', amount, ts_now, description, "00")
                )
                self.chain.append(tx_id=dest_tx_id, account_id=target_id, tx_type='D',
                                  amount=amount, timestamp=ts_now,
                                  description=description, status="00")

        self.db.commit()

        return {
            "status": "00",
            "tx_id": tx_id,
            "message": f"Transaction {tx_type} processed",
            "new_balance": new_balance
        }

    # ── Canonical Seed Data ───────────────────────────────────────
    # Single source of truth for all 6 nodes' initial account data.
    # Each tuple is: (ID, name, type, balance, status, open_date, last_activity)
    # Used by seed_demo_data() to write fresh DAT files and populate SQLite.
    # The clearing house has 5 nostro accounts (one per bank), each funded
    # with $10M working capital for settlement.
    SEED_ACCOUNTS = {
        "BANK_A": [
            ("ACT-A-001", "Maria Santos",      "C",    5000.00, "A", "20260217", "20260217"),
            ("ACT-A-002", "James Wilson",       "S",   12500.00, "A", "20260217", "20260217"),
            ("ACT-A-003", "Chen Liu",           "C",     850.50, "A", "20260217", "20260217"),
            ("ACT-A-004", "Patricia Kumar",     "S",   25000.00, "A", "20260217", "20260217"),
            ("ACT-A-005", "Robert Brown",       "C",    3200.00, "A", "20260217", "20260217"),
            ("ACT-A-006", "Sophie Martin",      "S",   75000.00, "A", "20260217", "20260217"),
            ("ACT-A-007", "David Garcia",       "C",    1500.00, "A", "20260217", "20260217"),
            ("ACT-A-008", "Emma Johnson",       "S",   45000.00, "A", "20260217", "20260217"),
        ],
        "BANK_B": [
            ("ACT-B-001", "Acme Manufacturing",   "C",  350000.00, "A", "20260217", "20260217"),
            ("ACT-B-002", "Global Logistics",      "C",  125000.00, "A", "20260217", "20260217"),
            ("ACT-B-003", "TechStart Ventures",    "S",  500000.00, "A", "20260217", "20260217"),
            ("ACT-B-004", "Peninsula Holdings",    "C",   75000.00, "A", "20260217", "20260217"),
            ("ACT-B-005", "NorthSide Insurance",   "C",  250000.00, "A", "20260217", "20260217"),
            ("ACT-B-006", "Pacific Shipping",      "C",  180000.00, "A", "20260217", "20260217"),
            ("ACT-B-007", "Greenfield Properties",  "S", 1000000.00, "A", "20260217", "20260217"),
        ],
        "BANK_C": [
            ("ACT-C-001", "Lisa Wong",          "S",  150000.00, "A", "20260217", "20260217"),
            ("ACT-C-002", "Michael O'Brien",    "C",   45000.00, "A", "20260217", "20260217"),
            ("ACT-C-003", "Alicia Patel",       "S",  200000.00, "A", "20260217", "20260217"),
            ("ACT-C-004", "Nina Kumar",         "S",  320000.00, "A", "20260217", "20260217"),
            ("ACT-C-005", "Thomas Anderson",    "C",   25000.00, "A", "20260217", "20260217"),
            ("ACT-C-006", "Rachel Green",       "S",  550000.00, "A", "20260217", "20260217"),
            ("ACT-C-007", "Christopher Lee",    "C",   80000.00, "A", "20260217", "20260217"),
            ("ACT-C-008", "Sophia Rivera",      "S",  400000.00, "A", "20260217", "20260217"),
        ],
        "BANK_D": [
            ("ACT-D-001", "Westchester Trust Corp",  "C",  5000000.00, "A", "20260217", "20260217"),
            ("ACT-D-002", "Birch Estate Partners",   "S", 12000000.00, "A", "20260217", "20260217"),
            ("ACT-D-003", "Alpine Investment Club",  "C",   750000.00, "A", "20260217", "20260217"),
            ("ACT-D-004", "Laurel Foundation",       "S",  2500000.00, "A", "20260217", "20260217"),
            ("ACT-D-005", "Strategic Capital Fund",  "C",  8000000.00, "A", "20260217", "20260217"),
            ("ACT-D-006", "Legacy Trust Settlement", "S", 15000000.00, "A", "20260217", "20260217"),
        ],
        "BANK_E": [
            ("ACT-E-001", "Metro Community Fund",      "C", 1200000.00, "A", "20260217", "20260217"),
            ("ACT-E-002", "Angela Rodriguez",          "C",   45000.00, "A", "20260217", "20260217"),
            ("ACT-E-003", "SBA Loan Pool",             "S", 2500000.00, "A", "20260217", "20260217"),
            ("ACT-E-004", "Marcus Thompson",           "S",  125000.00, "A", "20260217", "20260217"),
            ("ACT-E-005", "Metro Food Bank",           "C",  500000.00, "A", "20260217", "20260217"),
            ("ACT-E-006", "Urban Development Proj",    "S", 3000000.00, "A", "20260217", "20260217"),
            ("ACT-E-007", "Women Entrepreneurs Fund",  "C",  750000.00, "A", "20260217", "20260217"),
            ("ACT-E-008", "Youth Skills Initiative",   "S",  850000.00, "A", "20260217", "20260217"),
        ],
        "CLEARING": [
            ("NST-BANK-A", "Nostro Account - BANK_A", "C", 10000000.00, "A", "20260217", "20260217"),
            ("NST-BANK-B", "Nostro Account - BANK_B", "C", 10000000.00, "A", "20260217", "20260217"),
            ("NST-BANK-C", "Nostro Account - BANK_C", "C", 10000000.00, "A", "20260217", "20260217"),
            ("NST-BANK-D", "Nostro Account - BANK_D", "C", 10000000.00, "A", "20260217", "20260217"),
            ("NST-BANK-E", "Nostro Account - BANK_E", "C", 10000000.00, "A", "20260217", "20260217"),
        ],
    }

    def seed_demo_data(self):
        """
        Write fresh DAT files from canonical seed data and populate SQLite.
        Always overwrites DAT to ensure clean state (no tampered leftovers).
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

        # Write fresh DAT files from seed data (overwrites any tampered files)
        seed = self.SEED_ACCOUNTS.get(self.node, [])
        if seed:
            accounts = []
            for acct_id, name, acct_type, balance, status, open_date, last_activity in seed:
                accounts.append({
                    'id': acct_id, 'name': name, 'type': acct_type,
                    'balance': balance, 'status': status,
                    'open_date': open_date, 'last_activity': last_activity,
                })
            self._write_accounts_to_dat(accounts)

            # Create empty TRANSACT.DAT if it doesn't exist
            transact_file = self.data_dir / "TRANSACT.DAT"
            if not transact_file.exists():
                transact_file.touch()

        # Sync DAT -> SQLite
        self._sync_accounts_to_db()

    # ── Interest Batch (INTEREST.cob / Mode B) ────────────────────
    # Monthly interest accrual for savings accounts. In Mode A, calls the
    # COBOL INTEREST binary. In Mode B, implements tiered rate calculation:
    #   <$10K  = 0.50% APR
    #   $10K-$100K = 1.50% APR
    #   >$100K = 2.00% APR
    # Interest = balance * rate / 12 (monthly accrual)

    def run_interest_batch(self) -> Dict[str, Any]:
        """
        Run INTEREST.cob to accrue monthly interest for all savings accounts.
        Returns {status, accounts_processed, total_interest, output}.
        Falls back to Python-only Mode B if COBOL unavailable.
        """
        result = {"status": "99", "message": "Unknown error", "output": [],
                  "accounts_processed": 0, "total_interest": 0.0}

        if self.cobol_available:
            try:
                proc = self._run_cobol_program("INTEREST", [], timeout=30)
                output_lines = proc.stdout.strip().split('\n') if proc.stdout else []
                result["output"] = output_lines

                for line in output_lines:
                    if line.startswith("RESULT|"):
                        result["status"] = line.split('|')[1] if len(line.split('|')) > 1 else "99"
                    elif line.startswith("SUMMARY|"):
                        parts = line.split('|')
                        if len(parts) >= 3:
                            result["accounts_processed"] = int(parts[1].strip())
                            result["total_interest"] = float(parts[2].strip())
                    elif line.startswith("INTEREST|"):
                        parts = line.split('|')
                        if len(parts) >= 4:
                            # Record in integrity chain
                            acct_id = parts[1].strip()
                            amount = float(parts[2].strip())
                            ts_now = datetime.now().isoformat()
                            tx_id = f"INT-{self.NODE_CODES.get(self.node, '?')}-{datetime.now().strftime('%H%M%S')}"
                            self.chain.append(
                                tx_id=tx_id, account_id=acct_id,
                                tx_type='I', amount=amount,
                                timestamp=ts_now,
                                description=f"Monthly interest accrual",
                                status="00"
                            )
                # Resync accounts from DAT after COBOL modified them
                self._sync_accounts_to_db()
                return result
            except Exception as e:
                result["message"] = f"Error executing INTEREST: {e}"
                return result

        # Mode B: Python-only interest calculation
        accounts = self.load_accounts_from_dat()
        total_interest = 0.0
        processed = 0
        ts_now = datetime.now().isoformat()

        for acct in accounts:
            if acct['type'] != 'S' or acct['status'] != 'A' or acct['balance'] <= 0:
                continue

            # Tiered rates
            bal = acct['balance']
            if bal < 10000:
                rate = 0.0050
            elif bal < 100000:
                rate = 0.0150
            else:
                rate = 0.0200

            interest = round(bal * rate / 12, 2)
            acct['balance'] += interest
            total_interest += interest
            processed += 1

            # Record transaction
            node_code = self.NODE_CODES.get(self.node, "?")
            cursor = self.db.execute("SELECT MAX(CAST(substr(tx_id, 7) AS INTEGER)) FROM transactions")
            last_seq = cursor.fetchone()[0] or 0
            tx_id = f"TRX-{node_code}-{str(last_seq + 1).zfill(6)}"

            self.db.execute(
                """INSERT INTO transactions (tx_id, account_id, type, amount, timestamp, description, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (tx_id, acct['id'], 'I', interest, ts_now, "Monthly interest accrual", "00")
            )
            self.chain.append(tx_id=tx_id, account_id=acct['id'], tx_type='I',
                              amount=interest, timestamp=ts_now,
                              description="Monthly interest accrual", status="00")

            # Update account balance in DB
            self.db.execute("UPDATE accounts SET balance = ? WHERE id = ?",
                            (acct['balance'], acct['id']))

        self.db.commit()

        # Write updated accounts back to DAT (Mode B)
        self._write_accounts_to_dat(accounts)

        result["status"] = "00"
        result["accounts_processed"] = processed
        result["total_interest"] = total_interest
        return result

    # ── Fee Batch (FEES.cob / Mode B) ─────────────────────────────
    # Monthly fee assessment for checking accounts. In Mode B:
    #   Maintenance fee: $12.00/month
    #   Low-balance fee: $8.00 additional if balance < $500
    #   Waiver: No fees if balance > $5,000
    #   Balance floor: Fee skipped if it would cause negative balance

    def run_fee_batch(self) -> Dict[str, Any]:
        """
        Run FEES.cob to assess monthly fees for all checking accounts.
        Returns {status, accounts_assessed, total_fees, output}.
        Falls back to Python-only Mode B if COBOL unavailable.
        """
        result = {"status": "99", "message": "Unknown error", "output": [],
                  "accounts_assessed": 0, "total_fees": 0.0}

        if self.cobol_available:
            try:
                proc = self._run_cobol_program("FEES", [], timeout=30)
                output_lines = proc.stdout.strip().split('\n') if proc.stdout else []
                result["output"] = output_lines

                for line in output_lines:
                    if line.startswith("RESULT|"):
                        result["status"] = line.split('|')[1] if len(line.split('|')) > 1 else "99"
                    elif line.startswith("SUMMARY|"):
                        parts = line.split('|')
                        if len(parts) >= 3:
                            result["accounts_assessed"] = int(parts[1].strip())
                            result["total_fees"] = float(parts[2].strip())
                    elif line.startswith("FEE|"):
                        parts = line.split('|')
                        if len(parts) >= 5:
                            acct_id = parts[1].strip()
                            amount = float(parts[3].strip())
                            ts_now = datetime.now().isoformat()
                            tx_id = f"FEE-{self.NODE_CODES.get(self.node, '?')}-{datetime.now().strftime('%H%M%S')}"
                            self.chain.append(
                                tx_id=tx_id, account_id=acct_id,
                                tx_type='F', amount=amount,
                                timestamp=ts_now,
                                description="Monthly fee assessment",
                                status="00"
                            )
                self._sync_accounts_to_db()
                return result
            except Exception as e:
                result["message"] = f"Error executing FEES: {e}"
                return result

        # Mode B: Python-only fee calculation
        accounts = self.load_accounts_from_dat()
        total_fees = 0.0
        assessed = 0
        ts_now = datetime.now().isoformat()

        MAINTENANCE_FEE = 12.00
        LOW_BAL_FEE = 8.00
        WAIVER_THRESHOLD = 5000.00
        LOW_BAL_THRESHOLD = 500.00

        for acct in accounts:
            if acct['type'] != 'C' or acct['status'] != 'A':
                continue

            # Check waiver
            if acct['balance'] > WAIVER_THRESHOLD:
                continue

            fee = MAINTENANCE_FEE
            if acct['balance'] < LOW_BAL_THRESHOLD:
                fee += LOW_BAL_FEE

            # Balance floor protection
            if fee > acct['balance']:
                continue

            acct['balance'] -= fee
            total_fees += fee
            assessed += 1

            node_code = self.NODE_CODES.get(self.node, "?")
            cursor = self.db.execute("SELECT MAX(CAST(substr(tx_id, 7) AS INTEGER)) FROM transactions")
            last_seq = cursor.fetchone()[0] or 0
            tx_id = f"TRX-{node_code}-{str(last_seq + 1).zfill(6)}"

            self.db.execute(
                """INSERT INTO transactions (tx_id, account_id, type, amount, timestamp, description, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (tx_id, acct['id'], 'F', fee, ts_now, "Monthly fee assessment", "00")
            )
            self.chain.append(tx_id=tx_id, account_id=acct['id'], tx_type='F',
                              amount=fee, timestamp=ts_now,
                              description="Monthly fee assessment", status="00")
            self.db.execute("UPDATE accounts SET balance = ? WHERE id = ?",
                            (acct['balance'], acct['id']))

        self.db.commit()
        self._write_accounts_to_dat(accounts)

        result["status"] = "00"
        result["accounts_assessed"] = assessed
        result["total_fees"] = total_fees
        return result

    # ── Reconciliation (RECONCILE.cob / Mode B) ──────────────────
    # Verifies that current account balances are consistent with the
    # transaction history. For each account:
    #   net = sum(deposits + interest) - sum(withdrawals + fees + transfers)
    #   implied_opening = current_balance - net
    #   If implied_opening >= 0, the account reconciles (MATCH).

    def run_reconciliation(self) -> Dict[str, Any]:
        """
        Run RECONCILE.cob to verify account balances match transaction sums.
        Returns {status, matched, mismatched, total, output}.
        Falls back to Python-only Mode B if COBOL unavailable.
        """
        result = {"status": "99", "message": "Unknown error", "output": [],
                  "matched": 0, "mismatched": 0, "total": 0}

        if self.cobol_available:
            try:
                proc = self._run_cobol_program("RECONCILE", [], timeout=30)
                output_lines = proc.stdout.strip().split('\n') if proc.stdout else []
                result["output"] = output_lines

                for line in output_lines:
                    if line.startswith("RESULT|"):
                        result["status"] = line.split('|')[1] if len(line.split('|')) > 1 else "99"
                    elif line.startswith("RECON-SUMMARY|"):
                        parts = line.split('|')
                        if len(parts) >= 4:
                            result["matched"] = int(parts[1].strip())
                            result["mismatched"] = int(parts[2].strip())
                            result["total"] = int(parts[3].strip())
                return result
            except Exception as e:
                result["message"] = f"Error executing RECONCILE: {e}"
                return result

        # Mode B: Python-only reconciliation (mirrors RECONCILE.cob algorithm)
        # For each account:
        #   credits = sum of D+I amounts where status='00'
        #   debits  = sum of W+F+T amounts where status='00'
        #   net = credits - debits
        #   implied_opening = current_balance - net
        #   No txns -> MATCH; implied_opening >= 0 -> MATCH; else MISMATCH
        accounts = self.load_accounts_from_dat()
        cursor = self.db.execute("SELECT * FROM transactions WHERE status = '00'")
        transactions = [dict(row) for row in cursor.fetchall()]

        matched = 0
        mismatched = 0

        for acct in accounts:
            acct_txs = [t for t in transactions if t['account_id'] == acct['id']]

            if not acct_txs:
                # No transactions -- balance is seed value, always MATCH
                matched += 1
                continue

            credits = sum(t['amount'] for t in acct_txs if t['type'] in ('D', 'I'))
            debits = sum(t['amount'] for t in acct_txs if t['type'] in ('W', 'F', 'T'))
            net = credits - debits
            implied_opening = acct['balance'] - net

            if implied_opening >= 0:
                matched += 1
            else:
                mismatched += 1

        result["status"] = "00" if mismatched == 0 else "01"
        result["matched"] = matched
        result["mismatched"] = mismatched
        result["total"] = len(accounts)
        return result

    def _write_accounts_to_dat(self, accounts: List[Dict[str, Any]]):
        """Write accounts back to ACCOUNTS.DAT file (Mode B helper).

        Produces exactly 70 bytes per record (ACCTREC layout). Each field
        is padded/truncated to its exact byte width. The balance is
        formatted as 12-digit implied decimal (cents).
        """
        dat_file = self.data_dir / "ACCOUNTS.DAT"
        with open(dat_file, 'wb') as f:
            for acct in accounts:
                # Format balance: PIC S9(10)V99 = 12 ASCII digits, implied decimal
                # E.g., 5000.00 -> "000000500000", -100.50 -> "-00000010050"
                bal_cents = int(round(abs(acct['balance']) * 100))
                bal_str = f"{bal_cents:012d}"
                if acct['balance'] < 0:
                    bal_str = "-" + bal_str[1:]
                open_date = acct.get('open_date') or '00000000'
                last_activity = acct.get('last_activity') or '00000000'
                record = (
                    acct['id'].ljust(10)[:10].encode('ascii') +          # 10 bytes
                    acct['name'].ljust(30)[:30].encode('ascii') +        # 30 bytes
                    acct['type'].encode('ascii')[:1] +                   #  1 byte
                    bal_str.encode('ascii') +                            # 12 bytes
                    acct['status'].encode('ascii')[:1] +                 #  1 byte
                    open_date.ljust(8)[:8].encode('ascii') +             # 8 bytes
                    last_activity.ljust(8)[:8].encode('ascii')           # 8 bytes
                )
                f.write(record + b'\n')  # LINE SEQUENTIAL

    def close(self):
        """Close database connection."""
        if self.db:
            self.db.close()
