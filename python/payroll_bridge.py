"""
PayrollBridge -- Python bridge for the legacy payroll sidecar.

This module mirrors python/bridge.py's two-mode architecture for the payroll
system:

    Mode A (COBOL subprocess): When compiled payroll binaries exist, runs
    PAYROLL.cob via subprocess and parses pipe-delimited stdout output.

    Mode B (Python-only): When COBOL binaries are unavailable, implements
    equivalent payroll logic in Python — reads EMPLOYEES.DAT, computes
    gross/taxes/deductions/net, and produces settlement-compatible output.

The payroll bridge produces transfer dicts compatible with
SettlementCoordinator.execute_batch_settlement(), enabling payroll deposits
to flow through the existing 6-node settlement network.

COMP-3 unpacking:
    On a real mainframe, EMPLOYEES.DAT would use COMP-3 (packed decimal)
    for salary and rate fields. Our demo uses DISPLAY format for LINE
    SEQUENTIAL compatibility, but the bridge documents the COMP-3 layout
    for educational purposes.

Per-node isolation:
    Payroll data lives in COBOL-BANKING/payroll/data/PAYROLL/ with its own
    SQLite database (payroll.db). This mirrors the per-node pattern from
    the banking system — each subsystem operates independently.

Dependencies:
    python.integrity (for SHA-256 chain recording)
"""

import logging
import sqlite3
import subprocess
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from .integrity import IntegrityChain

logger = logging.getLogger(__name__)


# ── Employee Record Layout ─────────────────────────────────────
# Matches EMPREC.cpy (95 bytes, LINE SEQUENTIAL DISPLAY format)
# On a mainframe, salary/rate would be COMP-3 packed decimal.
EMP_RECORD_FORMAT = {
    "emp_id":        (0, 7),      # EMP-ID: PIC X(7)
    "name":          (7, 32),     # EMP-NAME: PIC X(25)
    "bank_code":     (32, 40),    # EMP-BANK-CODE: PIC X(8)
    "acct_id":       (40, 50),    # EMP-ACCT-ID: PIC X(10)
    "salary":        (50, 59),    # EMP-SALARY: PIC S9(7)V99 (9 bytes DISPLAY)
    "hourly_rate":   (59, 64),    # EMP-HOURLY-RATE: PIC S9(3)V99 (5 bytes)
    "hours_worked":  (64, 68),    # EMP-HOURS-WORKED: PIC S9(4)
    "pay_periods":   (68, 72),    # EMP-PAY-PERIODS: PIC S9(4)
    "status":        (72, 73),    # EMP-STATUS: PIC X(1)
    "pay_type":      (73, 74),    # EMP-PAY-TYPE: PIC X(1)
    "tax_bracket":   (74, 76),    # EMP-TAX-BRACKET: PIC 9(2)
    "hire_date":     (76, 84),    # EMP-HIRE-DATE: PIC 9(8)
    "dept_code":     (84, 88),    # EMP-DEPT-CODE: PIC X(4)
    "medical_plan":  (88, 89),    # EMP-MEDICAL-PLAN: PIC X(1)
    "dental_flag":   (89, 90),    # EMP-DENTAL-FLAG: PIC X(1)
    "k401_pct":      (90, 93),    # EMP-401K-PCT: PIC 9V99 (3 bytes)
    # bytes 93-94: EMP-FILLER PIC X(2)
}


class PayrollBridge:
    """Bridge to legacy payroll COBOL programs.

    Reads EMPLOYEES.DAT (fixed-width), computes payroll, and produces
    settlement-compatible transfer records. Supports Mode A (COBOL
    subprocess) and Mode B (Python-only fallback).
    """

    # ── Tax and Deduction Constants ────────────────────────────
    # Matches PAYCOM.cpy and TAXCALC.cob values (including the
    # intentional discrepancies documented in KNOWN_ISSUES.md)
    FICA_RATE = 0.0765           # PAYCOM-FICA-RATE (7.65%)
    FICA_LIMIT = 160200.00       # PAYCOM-FICA-LIMIT (outdated 1997 value)
    STATE_RATE = 0.0725          # WS-DEFAULT-STATE-RATE (not the 5% in comments)
    MED_BASIC = 275.00           # PAYCOM-MED-BASIC (not $250 in comments)
    MED_PREMIUM = 500.00         # PAYCOM-MED-PREMIUM
    DENTAL_COST = 75.00          # PAYCOM-DENTAL-COST
    K401_MATCH = 0.50            # PAYCOM-401K-MATCH (50% of contribution)
    OT_THRESHOLD = 40            # WK-M1 (standard hours)
    OT_MULTIPLIER = 1.50         # WK-M2 (time and a half)
    PAY_PERIODS = 26             # WK-PERIODS (biweekly)

    # Federal tax brackets (from TAXCALC.cob WS-HARDCODED-BRACKETS)
    FED_BRACKETS = [
        (500000, 0.37),
        (165000, 0.32),
        (85000, 0.24),
        (40000, 0.22),
        (10000, 0.12),
        (0, 0.10),
    ]

    def __init__(self, data_dir: str = "COBOL-BANKING/payroll/data",
                 bin_dir: str = "COBOL-BANKING/bin"):
        """Initialize payroll bridge.

        :param data_dir: Directory containing PAYROLL/ subdirectory
        :param bin_dir: Directory containing compiled COBOL binaries
        """
        self.data_dir = Path(data_dir) / "PAYROLL"
        self.bin_dir = Path(bin_dir).resolve()

        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # ── SQLite Database ────────────────────────────────────
        db_path = self.data_dir / "payroll.db"
        self.db = sqlite3.connect(str(db_path), check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.row_factory = sqlite3.Row
        self._ensure_tables()

        # ── Integrity Chain ────────────────────────────────────
        secret_key = self._get_or_create_secret_key()
        self.chain = IntegrityChain(self.db, secret_key)

        # ── COBOL Availability ─────────────────────────────────
        self.cobol_available = (self.bin_dir / "PAYROLL").exists()
        self.use_docker = self.cobol_available and sys.platform == "win32"

    def _ensure_tables(self):
        """Create payroll tables if they don't exist."""
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS employees (
                emp_id TEXT PRIMARY KEY,
                name TEXT, bank_code TEXT, acct_id TEXT,
                salary REAL, hourly_rate REAL, hours_worked INTEGER,
                pay_periods INTEGER, status TEXT, pay_type TEXT,
                tax_bracket INTEGER, hire_date TEXT, dept_code TEXT,
                medical_plan TEXT, dental_flag TEXT, k401_pct REAL
            );
            CREATE TABLE IF NOT EXISTS pay_stubs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_id TEXT, period INTEGER, run_date TEXT,
                gross REAL, fed_tax REAL, state_tax REAL,
                fica REAL, deductions REAL, net REAL,
                dest_bank TEXT, dest_acct TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)

    def _get_or_create_secret_key(self) -> str:
        """Get or create per-node HMAC secret key."""
        key_path = self.data_dir / ".server_key"
        if key_path.exists():
            return key_path.read_text().strip()
        import secrets
        key = secrets.token_hex(32)
        key_path.write_text(key)
        return key

    # ── Employee Record Parsing ────────────────────────────────

    @staticmethod
    def _safe_int(value: str, default: int, field: str, emp_id: str) -> int:
        """Parse an integer from a DAT field, returning default on failure.

        Logs a warning when a field contains non-numeric data so malformed
        records are visible without crashing the payroll endpoint.
        """
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning(
                "Non-numeric %s field for %s: %r — using default %d",
                field, emp_id, value, default,
            )
            return default

    def _parse_employee_record(self, line: str) -> Dict[str, Any]:
        """Parse a fixed-width employee record from EMPLOYEES.DAT.

        COMP-3 NOTE: On a mainframe, salary would be packed decimal
        (5 bytes for S9(7)V99). Here it's DISPLAY format — each digit
        is one ASCII character. The implied decimal (V99) means the
        last 2 digits are cents.
        """
        fields = {}
        for field_name, (start, end) in EMP_RECORD_FORMAT.items():
            raw = line[start:end] if end <= len(line) else ""
            fields[field_name] = raw.strip()

        # Convert numeric fields — _safe_int guards against malformed DAT data
        emp_id = fields.get("emp_id", "???")

        salary_raw = fields["salary"]
        if salary_raw:
            # S9(7)V99: 9 digits, last 2 are cents (implied decimal)
            fields["salary"] = self._safe_int(salary_raw, 0, "salary", emp_id) / 100.0
        else:
            fields["salary"] = 0.0

        hourly_raw = fields["hourly_rate"]
        if hourly_raw:
            # S9(3)V99: 5 digits, last 2 are cents
            fields["hourly_rate"] = self._safe_int(hourly_raw, 0, "hourly_rate", emp_id) / 100.0
        else:
            fields["hourly_rate"] = 0.0

        fields["hours_worked"] = self._safe_int(fields["hours_worked"], 0, "hours_worked", emp_id) if fields["hours_worked"] else 0
        fields["pay_periods"] = self._safe_int(fields["pay_periods"], 26, "pay_periods", emp_id) if fields["pay_periods"] else 26
        fields["tax_bracket"] = self._safe_int(fields["tax_bracket"], 1, "tax_bracket", emp_id) if fields["tax_bracket"] else 1

        # 401k: 9V99 = 3 digits, first is integer, last 2 are decimal
        k401_raw = fields["k401_pct"]
        if k401_raw:
            fields["k401_pct"] = self._safe_int(k401_raw, 0, "k401_pct", emp_id) / 100.0
        else:
            fields["k401_pct"] = 0.0

        return fields

    def _load_employees_from_dat(self) -> List[Dict[str, Any]]:
        """Load all employees from EMPLOYEES.DAT."""
        dat_path = self.data_dir / "EMPLOYEES.DAT"
        if not dat_path.exists():
            return []

        employees = []
        with open(dat_path, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                emp = self._parse_employee_record(line)
                employees.append(emp)
        return employees

    def _sync_employees_to_db(self, employees: List[Dict[str, Any]]):
        """Sync parsed employees to SQLite."""
        for emp in employees:
            self.db.execute("""
                INSERT OR REPLACE INTO employees
                (emp_id, name, bank_code, acct_id, salary, hourly_rate,
                 hours_worked, pay_periods, status, pay_type, tax_bracket,
                 hire_date, dept_code, medical_plan, dental_flag, k401_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (emp["emp_id"], emp["name"], emp["bank_code"], emp["acct_id"],
                  emp["salary"], emp["hourly_rate"], emp["hours_worked"],
                  emp["pay_periods"], emp["status"], emp["pay_type"],
                  emp["tax_bracket"], emp["hire_date"], emp["dept_code"],
                  emp["medical_plan"], emp["dental_flag"], emp["k401_pct"]))
        self.db.commit()

    # ── Public API ─────────────────────────────────────────────

    def list_employees(self) -> List[Dict[str, Any]]:
        """List all employees, loading from DAT file if DB is empty."""
        rows = self.db.execute("SELECT * FROM employees").fetchall()
        if not rows:
            employees = self._load_employees_from_dat()
            if employees:
                self._sync_employees_to_db(employees)
                rows = self.db.execute("SELECT * FROM employees").fetchall()
        return [dict(r) for r in rows]

    def get_employee(self, emp_id: str) -> Optional[Dict[str, Any]]:
        """Get a single employee by ID."""
        row = self.db.execute(
            "SELECT * FROM employees WHERE emp_id = ?", (emp_id,)
        ).fetchone()
        if row is None:
            # Try loading from DAT
            employees = self._load_employees_from_dat()
            self._sync_employees_to_db(employees)
            row = self.db.execute(
                "SELECT * FROM employees WHERE emp_id = ?", (emp_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_pay_stubs(self, emp_id: Optional[str] = None,
                      limit: int = 50) -> List[Dict[str, Any]]:
        """Get pay stub history."""
        if emp_id:
            rows = self.db.execute(
                "SELECT * FROM pay_stubs WHERE emp_id = ? ORDER BY id DESC LIMIT ?",
                (emp_id, limit)
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT * FROM pay_stubs ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Payroll Computation (Mode B) ───────────────────────────

    def _compute_gross(self, emp: Dict[str, Any]) -> float:
        """Compute gross pay for one pay period."""
        if emp["pay_type"] == "S":
            # Salaried: annual / 26
            return round(emp["salary"] / self.PAY_PERIODS, 2)
        else:
            # Hourly: regular + overtime
            hours = emp["hours_worked"]
            rate = emp["hourly_rate"]
            if hours > self.OT_THRESHOLD:
                reg = rate * self.OT_THRESHOLD
                ot = rate * self.OT_MULTIPLIER * (hours - self.OT_THRESHOLD)
                return round(reg + ot, 2)
            else:
                return round(rate * hours, 2)

    def _compute_fed_tax(self, gross: float) -> float:
        """Compute federal tax using TAXCALC.cob brackets."""
        annual = gross * self.PAY_PERIODS
        for threshold, rate in self.FED_BRACKETS:
            if annual > threshold:
                return round(gross * rate, 2)
        return round(gross * 0.10, 2)

    def _compute_state_tax(self, gross: float) -> float:
        """Compute state tax at 7.25% (not 5% despite comments)."""
        return round(gross * self.STATE_RATE, 2)

    def _compute_fica(self, gross: float) -> float:
        """Compute FICA tax at 7.65%."""
        annual = gross * self.PAY_PERIODS
        if annual > self.FICA_LIMIT:
            return 0.0  # Over wage base (outdated limit)
        return round(gross * self.FICA_RATE, 2)

    def _compute_deductions(self, emp: Dict[str, Any], gross: float) -> float:
        """Compute deductions matching DEDUCTN.cob logic.

        KNOWN BUG (DD-05): Divides annual cost by 12 (monthly) instead
        of 26 (biweekly). This under-deducts by ~54%.
        """
        total = 0.0

        # Medical (divided by 12, not 26 — matches SLW's bug)
        if emp["medical_plan"] == "B":
            total += round(self.MED_BASIC / 12, 2)
        elif emp["medical_plan"] == "P":
            total += round(self.MED_PREMIUM / 12, 2)

        # Dental
        if emp["dental_flag"] == "Y":
            total += round(self.DENTAL_COST / 12, 2)

        # 401(k)
        if emp["k401_pct"] > 0:
            total += round(gross * emp["k401_pct"], 2)

        return round(total, 2)

    def _compute_payroll_for_employee(self, emp: Dict[str, Any],
                                       period: int, run_date: str) -> Dict[str, Any]:
        """Compute full payroll for one employee."""
        gross = self._compute_gross(emp)
        fed = self._compute_fed_tax(gross)
        state = self._compute_state_tax(gross)
        fica = self._compute_fica(gross)
        deductions = self._compute_deductions(emp, gross)
        net = round(gross - fed - state - fica - deductions, 2)

        if net < 0:
            net = 0.0

        return {
            "emp_id": emp["emp_id"],
            "emp_name": emp["name"],
            "period": period,
            "run_date": run_date,
            "gross": gross,
            "fed_tax": fed,
            "state_tax": state,
            "fica": fica,
            "deductions": deductions,
            "net": net,
            "dest_bank": emp["bank_code"],
            "dest_acct": emp["acct_id"],
        }

    # ── Main Payroll Entry Point ───────────────────────────────

    def run_payroll(self, day: str = None) -> Dict[str, Any]:
        """Execute a full payroll cycle.

        Returns a dict with:
            - stubs: list of pay stub records
            - transfers: list of settlement-compatible transfer dicts
            - summary: batch totals

        The transfers list is compatible with
        SettlementCoordinator.execute_batch_settlement().
        """
        if day is None:
            day = datetime.now().strftime("%Y%m%d")

        # Compute pay period (crude: day-of-year / 14 + 1)
        try:
            dt = datetime.strptime(day, "%Y%m%d")
            period = dt.timetuple().tm_yday // 14 + 1
        except ValueError:
            period = 1

        # Load employees
        employees = self.list_employees()
        if not employees:
            return {"stubs": [], "transfers": [], "summary": {
                "total_employees": 0, "processed": 0, "skipped": 0,
                "batch_gross": 0, "batch_net": 0,
            }}

        stubs = []
        transfers = []
        skipped = 0
        batch_gross = 0.0
        batch_net = 0.0

        for emp in employees:
            # Skip non-active employees
            if emp["status"] != "A":
                skipped += 1
                continue

            stub = self._compute_payroll_for_employee(emp, period, day)
            stubs.append(stub)

            # Record pay stub in database
            self.db.execute("""
                INSERT INTO pay_stubs
                (emp_id, period, run_date, gross, fed_tax, state_tax,
                 fica, deductions, net, dest_bank, dest_acct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (stub["emp_id"], stub["period"], stub["run_date"],
                  stub["gross"], stub["fed_tax"], stub["state_tax"],
                  stub["fica"], stub["deductions"], stub["net"],
                  stub["dest_bank"], stub["dest_acct"]))

            # Record in integrity chain
            self.chain.append(
                tx_id=f"PAY-{stub['emp_id'][-3:]}-{period:04d}",
                account_id=stub["dest_acct"],
                amount=stub["net"],
                tx_type="D",
                timestamp=day,
                description=f"Payroll deposit — {stub['emp_name']}",
                status="00",
            )

            # Build settlement-compatible transfer
            if stub["net"] > 0:
                transfers.append({
                    "source_bank": "PAYROLL",
                    "source_account": stub["dest_acct"],
                    "dest_bank": stub["dest_bank"],
                    "dest_account": stub["dest_acct"],
                    "amount": stub["net"],
                    "description": f"Payroll deposit — {stub['emp_name']}",
                })

            batch_gross += stub["gross"]
            batch_net += stub["net"]

        self.db.commit()

        return {
            "stubs": stubs,
            "transfers": transfers,
            "summary": {
                "total_employees": len(employees),
                "processed": len(stubs),
                "skipped": skipped,
                "batch_gross": round(batch_gross, 2),
                "batch_net": round(batch_net, 2),
                "run_date": day,
                "period": period,
            },
        }

    def get_status(self) -> Dict[str, Any]:
        """Get payroll processing status."""
        employees = self.db.execute("SELECT COUNT(*) as c FROM employees").fetchone()
        stubs = self.db.execute("SELECT COUNT(*) as c FROM pay_stubs").fetchone()
        last_run = self.db.execute(
            "SELECT MAX(run_date) as d FROM pay_stubs"
        ).fetchone()

        return {
            "employees_loaded": employees["c"] if employees else 0,
            "total_pay_stubs": stubs["c"] if stubs else 0,
            "last_run_date": last_run["d"] if last_run and last_run["d"] else None,
            "cobol_available": self.cobol_available,
            "mode": "A" if self.cobol_available else "B",
        }
