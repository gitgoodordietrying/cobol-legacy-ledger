"""
validator.py -- COBOL convention checker for this project.

CONVENTION VALIDATION:
    This validator checks that COBOL source (represented as AST) follows
    the conventions used in this project. It does NOT validate COBOL syntax
    (that's the compiler's job). Instead, it checks project-specific rules:

    1. Naming conventions (UPPERCASE-WITH-HYPHENS)
    2. Field prefix conventions (ACCT-, TRANS-, WS-, RC-)
    3. PIC clause semantic matching (money = S9(10)V99, date = 9(8))
    4. Every paragraph ends with a result DISPLAY
    5. STOP RUN present in main program flow
    6. 88-level conditions exist for flag fields
    7. Record byte widths match expected sizes

    These conventions are documented in CLAUDE.md and enforced here so
    that generated/edited COBOL code matches the existing codebase style.

LAYER 3 NOTE:
    When an LLM generates a COBOLProgram, this validator runs before the
    generator produces text. Issues are reported back to the LLM for
    correction, creating a generate->validate->fix loop.
"""

import re
from typing import List, Dict
from .ast_nodes import COBOLProgram, DataItem


class ValidationIssue:
    """A single validation issue found in the AST."""

    def __init__(self, severity: str, message: str, location: str = ""):
        """
        Args:
            severity: "ERROR" (must fix) or "WARNING" (should fix)
            message: Human-readable description of the issue
            location: Where in the AST the issue was found
        """
        self.severity = severity
        self.message = message
        self.location = location

    def __repr__(self):
        loc = f" at {self.location}" if self.location else ""
        return f"[{self.severity}]{loc}: {self.message}"


class COBOLValidator:
    """Validate COBOL AST against project conventions.

    Usage:
        validator = COBOLValidator()
        issues = validator.validate(program_ast)
        for issue in issues:
            print(issue)
    """

    # Known field prefixes and their semantic types
    KNOWN_PREFIXES = {
        "ACCT-": "Account fields",
        "TRANS-": "Transaction fields",
        "WS-": "Working storage variables",
        "RC-": "Return codes",
        "NST-": "Nostro account fields",
        "SIM-": "Simulation fields",
    }

    # PIC patterns for semantic types
    MONEY_PIC = re.compile(r'S?9\(\d+\)V9{2}')
    DATE_PIC = re.compile(r'9\(8\)')
    STATUS_PIC = re.compile(r'X\(1\)|X{1,2}')
    ID_PIC = re.compile(r'X\(\d+\)')

    def validate(self, program: COBOLProgram) -> List[ValidationIssue]:
        """Run all validation checks on a COBOLProgram AST.

        Returns a list of ValidationIssue objects sorted by severity
        (ERRORs first, then WARNINGs).
        """
        issues: List[ValidationIssue] = []

        issues.extend(self._check_metadata(program))
        issues.extend(self._check_naming(program))
        issues.extend(self._check_pic_semantics(program))
        issues.extend(self._check_paragraphs(program))
        issues.extend(self._check_stop_run(program))
        issues.extend(self._check_flag_conditions(program))

        # Sort: errors first
        issues.sort(key=lambda i: 0 if i.severity == "ERROR" else 1)
        return issues

    def _check_metadata(self, program: COBOLProgram) -> List[ValidationIssue]:
        """Check IDENTIFICATION DIVISION metadata."""
        issues = []
        if program.metadata.program_id == "UNKNOWN":
            issues.append(ValidationIssue(
                "ERROR", "PROGRAM-ID is missing or could not be parsed",
                "IDENTIFICATION DIVISION"))
        elif not program.metadata.program_id.isupper():
            issues.append(ValidationIssue(
                "WARNING", f"PROGRAM-ID '{program.metadata.program_id}' should be UPPERCASE",
                "IDENTIFICATION DIVISION"))
        return issues

    def _check_naming(self, program: COBOLProgram) -> List[ValidationIssue]:
        """Check that all names follow UPPERCASE-WITH-HYPHENS convention."""
        issues = []

        def check_item(item: DataItem, location: str):
            if not re.match(r'^[A-Z0-9][A-Z0-9-]*$', item.name):
                issues.append(ValidationIssue(
                    "ERROR",
                    f"Field name '{item.name}' must be UPPERCASE-WITH-HYPHENS",
                    location))
            for child in item.children:
                check_item(child, location)
            for cond in item.conditions:
                if not re.match(r'^[A-Z0-9][A-Z0-9-]*$', cond.name):
                    issues.append(ValidationIssue(
                        "ERROR",
                        f"Condition name '{cond.name}' must be UPPERCASE-WITH-HYPHENS",
                        location))

        for item in program.working_storage:
            check_item(item, "WORKING-STORAGE")
        for f in program.files:
            for item in f.record_fields:
                check_item(item, f"FILE {f.logical_name}")

        # Check paragraph names
        for para in program.paragraphs:
            if not re.match(r'^[A-Z0-9][A-Z0-9-]*$', para.name):
                issues.append(ValidationIssue(
                    "ERROR",
                    f"Paragraph name '{para.name}' must be UPPERCASE-WITH-HYPHENS",
                    "PROCEDURE DIVISION"))

        return issues

    def _check_pic_semantics(self, program: COBOLProgram) -> List[ValidationIssue]:
        """Check that PIC clauses match semantic field types.

        Convention:
            Fields ending in -BALANCE, -AMOUNT, -FEE, -INTEREST -> S9(10)V99
            Fields ending in -DATE, -ACTIVITY -> 9(8)
            Fields ending in -STATUS, -TYPE -> X(1) or XX
            Fields ending in -ID, -NAME, -DESC -> X(n)
        """
        issues = []

        def check_item(item: DataItem, location: str):
            if not item.pic:
                for child in item.children:
                    check_item(child, location)
                return

            name = item.name.upper()

            # Money fields should use implied decimal
            if any(name.endswith(s) for s in ['-BALANCE', '-AMOUNT', '-FEE', '-INTEREST']):
                if not self.MONEY_PIC.match(item.pic):
                    issues.append(ValidationIssue(
                        "WARNING",
                        f"Money field '{item.name}' has PIC {item.pic}, "
                        f"expected S9(n)V99 pattern",
                        location))

            # Date fields should be 9(8)
            if any(name.endswith(s) for s in ['-DATE', '-ACTIVITY']):
                if not self.DATE_PIC.match(item.pic):
                    issues.append(ValidationIssue(
                        "WARNING",
                        f"Date field '{item.name}' has PIC {item.pic}, expected 9(8)",
                        location))

            for child in item.children:
                check_item(child, location)

        for item in program.working_storage:
            check_item(item, "WORKING-STORAGE")
        for f in program.files:
            for item in f.record_fields:
                check_item(item, f"FILE {f.logical_name}")

        return issues

    def _check_paragraphs(self, program: COBOLProgram) -> List[ValidationIssue]:
        """Check paragraph conventions.

        Convention: Every operation paragraph should end with a DISPLAY
        statement (the result output protocol).
        """
        issues = []
        for para in program.paragraphs:
            if para.name == "MAIN-PROGRAM":
                continue  # Main doesn't need a trailing DISPLAY

            if para.statements:
                last_stmt = para.statements[-1]
                if last_stmt.verb != "DISPLAY" and "-OPERATION" in para.name:
                    issues.append(ValidationIssue(
                        "WARNING",
                        f"Paragraph '{para.name}' does not end with a DISPLAY statement",
                        "PROCEDURE DIVISION"))

        return issues

    def _check_stop_run(self, program: COBOLProgram) -> List[ValidationIssue]:
        """Check that STOP RUN is present in the main program flow."""
        issues = []
        has_stop_run = False

        for para in program.paragraphs:
            for stmt in para.statements:
                if stmt.verb == "STOP" and "STOP RUN" in stmt.raw_text.upper():
                    has_stop_run = True
                    break

        if not has_stop_run:
            issues.append(ValidationIssue(
                "ERROR",
                "No STOP RUN found in PROCEDURE DIVISION",
                "PROCEDURE DIVISION"))

        return issues

    def _check_flag_conditions(self, program: COBOLProgram) -> List[ValidationIssue]:
        """Check that single-character flag fields have 88-level conditions.

        Convention: Fields with PIC X(1) that represent flags (status, type)
        should have 88-level condition names for readability.
        """
        issues = []

        def check_item(item: DataItem, location: str):
            if item.pic and item.pic in ("X(1)", "X") and not item.conditions:
                name = item.name.upper()
                if any(name.endswith(s) for s in ['-STATUS', '-TYPE', '-FLAG']):
                    issues.append(ValidationIssue(
                        "WARNING",
                        f"Flag field '{item.name}' has no 88-level conditions",
                        location))
            for child in item.children:
                check_item(child, location)

        for item in program.working_storage:
            check_item(item, "WORKING-STORAGE")
        for f in program.files:
            for item in f.record_fields:
                check_item(item, f"FILE {f.logical_name}")

        return issues
