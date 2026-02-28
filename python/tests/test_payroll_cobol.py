"""
Tests for payroll COBOL sidecar — anti-pattern verification and format validation.

Test strategy:
    These tests verify the spaghetti COBOL payroll system at the source level:
    syntax-only compilation (when cobc available), fixed-width record format,
    anti-pattern presence, KNOWN_ISSUES completeness, and output compatibility
    with the existing settlement pipeline.

    All tests run without COBOL compilation when cobc is unavailable — they
    verify source text patterns and data file formats directly.

Test groups:
    - Compilation: Each .cob compiles with cobc -fsyntax-only (skipped if no cobc)
    - Data format: EMPLOYEES.DAT has valid fixed-width records
    - Anti-patterns: Grep for GO TO, ALTER, PERFORM THRU, COMP-3, nested IF
    - Documentation: KNOWN_ISSUES.md covers every anti-pattern used
    - Copybooks: Field definitions present and consistent
    - Output format: Pipe-delimited output matches settlement format
"""

import os
import subprocess
import pytest
from pathlib import Path


# ── Fixtures ─────────────────────────────────────────────────────

PAYROLL_DIR = Path(__file__).resolve().parent.parent.parent / "COBOL-BANKING" / "payroll"
PAYROLL_SRC = PAYROLL_DIR / "src"
PAYROLL_COPYBOOKS = PAYROLL_DIR / "copybooks"
PAYROLL_DATA = PAYROLL_DIR / "data" / "PAYROLL"
KNOWN_ISSUES = PAYROLL_DIR / "KNOWN_ISSUES.md"

PROGRAMS = ["PAYROLL", "TAXCALC", "DEDUCTN", "PAYBATCH"]
COPYBOOKS = ["EMPREC", "TAXREC", "PAYREC", "PAYCOM"]


def _has_cobc():
    """Check if cobc (GnuCOBOL compiler) is available."""
    try:
        subprocess.run(["cobc", "--version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _read_source(name: str) -> str:
    """Read a COBOL source file."""
    return (PAYROLL_SRC / f"{name}.cob").read_text(encoding="ascii", errors="replace")


def _read_copybook(name: str) -> str:
    """Read a copybook file."""
    return (PAYROLL_COPYBOOKS / f"{name}.cpy").read_text(encoding="ascii", errors="replace")


# ── Source File Existence Tests ──────────────────────────────────

class TestFileExistence:
    """Verify all expected files are present."""

    @pytest.mark.parametrize("prog", PROGRAMS)
    def test_source_exists(self, prog):
        assert (PAYROLL_SRC / f"{prog}.cob").exists(), f"{prog}.cob not found"

    @pytest.mark.parametrize("cpy", COPYBOOKS)
    def test_copybook_exists(self, cpy):
        assert (PAYROLL_COPYBOOKS / f"{cpy}.cpy").exists(), f"{cpy}.cpy not found"

    def test_employees_dat_exists(self):
        assert (PAYROLL_DATA / "EMPLOYEES.DAT").exists()

    def test_known_issues_exists(self):
        assert KNOWN_ISSUES.exists()

    def test_readme_exists(self):
        assert (PAYROLL_DIR / "README.md").exists()


# ── Compilation Tests ────────────────────────────────────────────

class TestCompilation:
    """Verify COBOL programs compile with cobc -fsyntax-only."""

    @pytest.mark.skipif(not _has_cobc(), reason="cobc not installed")
    @pytest.mark.parametrize("prog", PROGRAMS)
    def test_syntax_check(self, prog):
        """Each program should pass cobc syntax-only check."""
        result = subprocess.run(
            ["cobc", "-fsyntax-only", "-free",
             "-I", str(PAYROLL_COPYBOOKS),
             str(PAYROLL_SRC / f"{prog}.cob")],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, (
            f"{prog}.cob failed syntax check:\n{result.stderr}"
        )


# ── EMPLOYEES.DAT Format Tests ──────────────────────────────────

class TestEmployeeData:
    """Verify EMPLOYEES.DAT has valid fixed-width records."""

    def _load_employees(self):
        path = PAYROLL_DATA / "EMPLOYEES.DAT"
        # Don't strip trailing spaces — they're part of FILLER fields
        text = path.read_text(encoding="ascii", errors="replace")
        lines = text.split('\n')
        # Remove empty trailing line from final newline
        return [l for l in lines if l]

    def test_employee_count(self):
        lines = self._load_employees()
        assert len(lines) == 25, f"Expected 25 employees, got {len(lines)}"

    def test_employee_id_format(self):
        """EMP-ID should be 7 chars: EMP-NNN"""
        for line in self._load_employees():
            emp_id = line[0:7]
            assert emp_id.startswith("EMP-"), f"Bad EMP-ID: {emp_id}"
            assert emp_id[4:7].isdigit(), f"Bad EMP-ID number: {emp_id}"

    def test_bank_codes_valid(self):
        """Each employee maps to one of the 5 banks."""
        valid_banks = {"BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E"}
        for line in self._load_employees():
            # EMP-BANK-CODE: bytes 33-40 (offset 32-39)
            bank = line[32:40].strip()
            assert bank in valid_banks, f"Invalid bank code: '{bank}'"

    def test_account_id_format(self):
        """Account IDs should match ACT-X-NNN pattern."""
        import re
        pattern = re.compile(r"^ACT-[A-E]-\d{3}$")
        for line in self._load_employees():
            # EMP-ACCT-ID: bytes 41-50 (offset 40-49)
            acct = line[40:50].strip()
            assert pattern.match(acct), f"Bad account ID: '{acct}'"

    def test_five_per_bank(self):
        """5 employees per bank."""
        banks = {}
        for line in self._load_employees():
            bank = line[32:40].strip()
            banks[bank] = banks.get(bank, 0) + 1
        for bank, count in banks.items():
            assert count == 5, f"{bank} has {count} employees, expected 5"

    def test_status_codes_valid(self):
        """Status should be A (active), T (terminated), or L (on leave)."""
        for line in self._load_employees():
            # EMP-STATUS: byte 73 (offset 72)
            status = line[72:73]
            assert status in ('A', 'T', 'L'), f"Invalid status: '{status}'"

    def test_pay_type_valid(self):
        """Pay type should be S (salaried) or H (hourly)."""
        for line in self._load_employees():
            # EMP-PAY-TYPE: byte 74 (offset 73)
            pay_type = line[73:74]
            assert pay_type in ('S', 'H'), f"Invalid pay type: '{pay_type}'"

    def test_record_length(self):
        """Each record should be exactly 95 bytes."""
        for i, line in enumerate(self._load_employees()):
            assert len(line) == 95, f"Record {i+1} is {len(line)} bytes, expected 95"


# ── Anti-Pattern Verification Tests ──────────────────────────────

class TestAntiPatterns:
    """Verify spaghetti anti-patterns are present in source code."""

    def test_payroll_has_goto(self):
        """PAYROLL.cob must contain GO TO statements."""
        source = _read_source("PAYROLL")
        assert source.count("GO TO") >= 8, "PAYROLL.cob needs 8+ GO TO statements"

    def test_payroll_has_alter(self):
        """PAYROLL.cob must contain ALTER statements."""
        source = _read_source("PAYROLL")
        assert "ALTER" in source, "PAYROLL.cob must use ALTER"
        assert source.count("ALTER") >= 2, "PAYROLL.cob needs 2+ ALTER statements"

    def test_payroll_has_dead_paragraph(self):
        """PAYROLL.cob must have at least one dead paragraph."""
        source = _read_source("PAYROLL")
        assert "P-085" in source, "Dead paragraph P-085 missing"

    def test_payroll_has_magic_numbers(self):
        """PAYROLL.cob must have cryptic variable names."""
        source = _read_source("PAYROLL")
        for name in ["WK-M1", "WK-M2", "WK-M3"]:
            assert name in source, f"Magic number variable {name} missing"

    def test_taxcalc_has_nested_if(self):
        """TAXCALC.cob must have deep nested IF without END-IF."""
        source = _read_source("TAXCALC")
        # Count IF statements in COMPUTE-FEDERAL section
        lines = source.split('\n')
        in_federal = False
        if_count = 0
        for line in lines:
            if 'COMPUTE-FEDERAL' in line and not line.strip().startswith('*>'):
                in_federal = True
            if in_federal and 'COMPUTE-STATE' in line:
                break
            if in_federal and 'IF ' in line.upper() and not line.strip().startswith('*>'):
                if_count += 1
        assert if_count >= 5, f"Need 5+ nested IFs, found {if_count}"

    def test_taxcalc_has_perform_thru(self):
        """TAXCALC.cob must use PERFORM THRU."""
        source = _read_source("TAXCALC")
        assert "PERFORM" in source and "THRU" in source

    def test_taxcalc_has_misleading_comment(self):
        """TAXCALC.cob must have misleading 5% comment with 7.25% code."""
        source = _read_source("TAXCALC")
        assert "5%" in source, "Missing '5%' comment"
        assert "0.0725" in source, "Missing actual 7.25% rate"

    def test_deductn_has_mixed_comp(self):
        """DEDUCTN.cob must have mixed COMP types."""
        source = _read_source("DEDUCTN")
        assert "COMP-3" in source, "Missing COMP-3"
        assert "COMP." in source or "COMP\n" in source, "Missing COMP (binary)"

    def test_deductn_has_goto_and_perform(self):
        """DEDUCTN.cob must mix structured and spaghetti styles."""
        source = _read_source("DEDUCTN")
        assert "GO TO" in source, "Missing GO TO (spaghetti part)"
        assert "PERFORM" in source, "Missing PERFORM (structured part)"

    def test_paybatch_has_y2k_code(self):
        """PAYBATCH.cob must have Y2K remediation artifacts."""
        source = _read_source("PAYBATCH")
        assert "Y2K" in source, "Missing Y2K references"
        assert "WS-Y2K-PIVOT" in source, "Missing Y2K pivot year"

    def test_paybatch_has_excessive_display(self):
        """PAYBATCH.cob must have excessive DISPLAY tracing."""
        source = _read_source("PAYBATCH")
        display_count = source.count("DISPLAY")
        assert display_count >= 15, f"Expected 15+ DISPLAYs, found {display_count}"

    def test_paybatch_has_dead_code(self):
        """PAYBATCH.cob must have dead Y2K code."""
        source = _read_source("PAYBATCH")
        assert "Y2K-REVERSE-CONVERT" in source
        assert "DEAD-REPORT-FORMAT" in source


# ── Copybook Tests ───────────────────────────────────────────────

class TestCopybooks:
    """Verify copybook content and anti-patterns."""

    def test_emprec_documents_comp3(self):
        """EMPREC must document COMP-3 concept."""
        source = _read_copybook("EMPREC")
        assert "COMP-3" in source, "EMPREC should document COMP-3 concept"

    def test_programs_use_comp3(self):
        """Programs must use COMP-3 in WORKING-STORAGE for computation."""
        # The anti-pattern lives in WORKING-STORAGE, not the file record
        source = _read_source("PAYROLL")
        assert "COMP-3" in source, "PAYROLL.cob should use COMP-3 in working storage"

    def test_programs_use_mixed_comp(self):
        """DEDUCTN must mix COMP-3 and COMP types."""
        source = _read_source("DEDUCTN")
        assert "COMP-3" in source, "DEDUCTN.cob needs COMP-3"
        assert "COMP." in source, "DEDUCTN.cob needs COMP (binary)"

    def test_paycom_has_conflicting_values(self):
        """PAYCOM must have conflicting daily limit values."""
        source = _read_copybook("PAYCOM")
        assert "500000" in source, "Missing WK-B2 value"
        assert "750000" in source, "Missing PAYCOM-DAILY-LIMIT value"

    def test_paycom_has_dead_section(self):
        """PAYCOM must have dead garnishment constants."""
        source = _read_copybook("PAYCOM")
        assert "PAYCOM-DEAD-SECTION" in source or "PAYCOM-GARN" in source

    def test_paycom_has_comment_value_mismatch(self):
        """PAYCOM must have $250 comment but 275 value for medical."""
        source = _read_copybook("PAYCOM")
        assert "250" in source, "Missing $250 comment"
        assert "275" in source, "Missing actual 275 value"


# ── KNOWN_ISSUES.md Coverage Tests ───────────────────────────────

class TestKnownIssuesCoverage:
    """Verify KNOWN_ISSUES.md documents all anti-patterns."""

    def _load_known_issues(self):
        return KNOWN_ISSUES.read_text(encoding="utf-8")

    def test_covers_goto(self):
        ki = self._load_known_issues()
        assert "GO TO" in ki

    def test_covers_alter(self):
        ki = self._load_known_issues()
        assert "ALTER" in ki

    def test_covers_perform_thru(self):
        ki = self._load_known_issues()
        assert "PERFORM THRU" in ki or "PERFORM" in ki and "THRU" in ki

    def test_covers_nested_if(self):
        ki = self._load_known_issues()
        assert "Nested IF" in ki or "nested IF" in ki

    def test_covers_dead_code(self):
        ki = self._load_known_issues()
        assert "Dead" in ki or "dead" in ki

    def test_covers_mixed_comp(self):
        ki = self._load_known_issues()
        assert "COMP" in ki

    def test_covers_misleading_comments(self):
        ki = self._load_known_issues()
        assert "comment" in ki.lower() and ("misleading" in ki.lower() or "mismatch" in ki.lower())

    def test_covers_y2k(self):
        ki = self._load_known_issues()
        assert "Y2K" in ki

    def test_covers_magic_numbers(self):
        ki = self._load_known_issues()
        assert "magic" in ki.lower() or "Magic" in ki

    def test_all_programs_documented(self):
        ki = self._load_known_issues()
        for prog in PROGRAMS:
            assert prog in ki, f"{prog} not documented in KNOWN_ISSUES.md"
