"""
parser.py -- COBOL source file parser (convention-aware, not full grammar).

PARSING APPROACH:
    This is NOT a full COBOL grammar parser. COBOL has one of the most complex
    grammars in computing (the COBOL-85 standard is 800+ pages). Building a
    complete parser would be a multi-year project.

    Instead, this is a CONVENTION-AWARE parser tuned to this project's coding
    style. It handles the patterns used in these 10 programs:
        - Free-format source (7-space base indent, 4-space nesting)
        - Division/section structure
        - COPY statements
        - WORKING-STORAGE level numbers with PIC clauses
        - 88-level condition names
        - PROCEDURE DIVISION paragraphs
        - *> comment blocks (including COBOL CONCEPT blocks)
        - SELECT/ASSIGN/FD file declarations

    For arbitrary COBOL from the wild, use a proper COBOL parser like
    GnuCOBOL's -fsyntax-only mode or a commercial tool.

REGEX-BASED PARSING:
    We use regular expressions rather than a formal grammar (ANTLR, PEG, etc.)
    because:
    1. The patterns are well-defined and consistent across our 10 programs
    2. Regex is simpler to understand and maintain for educational purposes
    3. Error recovery is straightforward (skip unrecognized lines)
    4. No build tool dependencies
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple

from .ast_nodes import (
    COBOLProgram, DataItem, ConditionItem, Paragraph, Statement,
    FileDeclaration, ProgramMetadata,
)


class COBOLParser:
    """Parse COBOL source files (.cob, .cpy) into AST nodes.

    Usage:
        parser = COBOLParser()
        program = parser.parse_file("COBOL-BANKING/src/ACCOUNTS.cob")
        print(program.metadata.program_id)  # "ACCOUNTS"
        for para in program.paragraphs:
            print(para.name, len(para.statements), "statements")
    """

    # Regex patterns for COBOL constructs
    _PROGRAM_ID = re.compile(r'PROGRAM-ID\.\s+(\S+?)\.?$', re.IGNORECASE)
    _DIVISION = re.compile(r'^\s*(IDENTIFICATION|ENVIRONMENT|DATA|PROCEDURE)\s+DIVISION', re.IGNORECASE)
    _SECTION = re.compile(r'^\s*(INPUT-OUTPUT|FILE|WORKING-STORAGE|LINKAGE)\s+SECTION', re.IGNORECASE)
    _SELECT = re.compile(r'SELECT\s+(\S+)', re.IGNORECASE)
    _ASSIGN = re.compile(r'ASSIGN\s+TO\s+"?([^"\s]+)"?', re.IGNORECASE)
    _ORGANIZATION = re.compile(r'ORGANIZATION\s+IS\s+([\w\s]+?)(?:\.|$)', re.IGNORECASE)
    _FILE_STATUS = re.compile(r'FILE\s+STATUS\s+IS\s+(\S+?)\.?$', re.IGNORECASE)
    _FD = re.compile(r'^\s*FD\s+(\S+)', re.IGNORECASE)
    _COPY = re.compile(r'COPY\s+"?([^".\s]+(?:\.\w+)?)"?', re.IGNORECASE)
    _LEVEL = re.compile(r'^\s*(\d{2})\s+(\S+?)(?:\s|\.)', re.IGNORECASE)
    _PIC = re.compile(r'PIC(?:TURE)?\s+IS\s+(\S+)|PIC(?:TURE)?\s+(\S+)', re.IGNORECASE)
    _VALUE = re.compile(r'VALUE\s+(?:IS\s+)?(["\'].*?["\']|\S+?)\.?$', re.IGNORECASE)
    _OCCURS = re.compile(r'OCCURS\s+(\d+)', re.IGNORECASE)
    _REDEFINES = re.compile(r'REDEFINES\s+(\S+)', re.IGNORECASE)
    _PARAGRAPH = re.compile(r'^(\s{7}[\w-]+)\.\s*$')
    _COMMENT = re.compile(r'^\s*\*>')
    _CONCEPT_BLOCK = re.compile(r'COBOL CONCEPT:', re.IGNORECASE)

    def parse_file(self, filepath: str) -> COBOLProgram:
        """Parse a .cob or .cpy file into a COBOLProgram AST."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"COBOL source not found: {filepath}")

        text = path.read_text(encoding='ascii', errors='replace')
        return self.parse_text(text, filename=path.name)

    def parse_text(self, text: str, filename: str = "") -> COBOLProgram:
        """Parse COBOL source text into a COBOLProgram AST."""
        lines = text.split('\n')

        metadata = ProgramMetadata(program_id="UNKNOWN")
        files: List[FileDeclaration] = []
        working_storage: List[DataItem] = []
        paragraphs: List[Paragraph] = []
        copybooks: List[str] = []
        header_comments: List[str] = []

        # State machine: track which division/section we're in
        current_division = ""
        current_section = ""
        current_file_decl: Optional[FileDeclaration] = None
        current_paragraph: Optional[Paragraph] = None
        in_header = True  # Before first division

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            i += 1

            # Skip blank lines
            if not stripped:
                continue

            # Collect header comments (before first division)
            if in_header and self._COMMENT.match(line):
                comment_text = stripped.lstrip('*>').strip()
                header_comments.append(comment_text)
                continue

            # Division boundary
            div_match = self._DIVISION.search(stripped)
            if div_match:
                in_header = False
                current_division = div_match.group(1).upper()
                current_section = ""
                continue

            # Section boundary
            sec_match = self._SECTION.search(stripped)
            if sec_match:
                current_section = sec_match.group(1).upper()
                continue

            # IDENTIFICATION DIVISION: extract PROGRAM-ID
            if current_division == "IDENTIFICATION":
                pid_match = self._PROGRAM_ID.search(stripped)
                if pid_match:
                    metadata.program_id = pid_match.group(1).rstrip('.')

            # ENVIRONMENT DIVISION: parse file declarations
            elif current_division == "ENVIRONMENT":
                self._parse_environment_line(stripped, files, current_file_decl)
                # Track current file declaration for multi-line SELECT
                select_match = self._SELECT.search(stripped)
                if select_match:
                    current_file_decl = FileDeclaration(
                        logical_name=select_match.group(1)
                    )
                    files.append(current_file_decl)
                if current_file_decl:
                    assign_match = self._ASSIGN.search(stripped)
                    if assign_match:
                        current_file_decl.physical_name = assign_match.group(1)
                    org_match = self._ORGANIZATION.search(stripped)
                    if org_match:
                        current_file_decl.organization = org_match.group(1).strip()
                    status_match = self._FILE_STATUS.search(stripped)
                    if status_match:
                        current_file_decl.status_var = status_match.group(1).rstrip('.')

            # DATA DIVISION
            elif current_division == "DATA":
                # FD
                fd_match = self._FD.search(stripped)
                if fd_match:
                    fd_name = fd_match.group(1).rstrip('.')
                    # Find matching file declaration
                    for f in files:
                        if f.logical_name == fd_name:
                            current_file_decl = f
                    continue

                # COPY statement
                copy_match = self._COPY.search(stripped)
                if copy_match:
                    copybooks.append(copy_match.group(1))
                    if current_file_decl:
                        current_file_decl.copybook = copy_match.group(1)
                    continue

                # Data items (level numbers)
                if current_section in ("WORKING-STORAGE", "FILE"):
                    item = self._parse_data_item(stripped)
                    if item:
                        if current_section == "WORKING-STORAGE":
                            working_storage.append(item)
                        elif current_file_decl:
                            current_file_decl.record_fields.append(item)

            # PROCEDURE DIVISION: parse paragraphs and statements
            elif current_division == "PROCEDURE":
                # Skip comments in procedure division
                if self._COMMENT.match(line):
                    continue

                # Paragraph name (starts at column 8, ends with period)
                para_match = self._PARAGRAPH.match(line)
                if para_match:
                    para_name = para_match.group(1).strip().rstrip('.')
                    current_paragraph = Paragraph(name=para_name)
                    paragraphs.append(current_paragraph)
                    continue

                # Statement (any non-blank, non-comment line in a paragraph)
                if current_paragraph and stripped and not stripped == '.':
                    stmt = self._parse_statement(stripped)
                    if stmt:
                        current_paragraph.statements.append(stmt)

        return COBOLProgram(
            metadata=metadata,
            files=files,
            working_storage=working_storage,
            paragraphs=paragraphs,
            copybooks=copybooks,
            header_comments=header_comments,
        )

    def parse_copybook(self, filepath: str) -> List[DataItem]:
        """Parse a .cpy copybook file into a list of DataItem nodes."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Copybook not found: {filepath}")

        text = path.read_text(encoding='ascii', errors='replace')
        items = []
        for line in text.split('\n'):
            stripped = line.strip()
            if not stripped or self._COMMENT.match(line):
                continue
            item = self._parse_data_item(stripped)
            if item:
                items.append(item)
        return items

    def _parse_environment_line(self, line: str, files: list,
                                current: Optional[FileDeclaration]) -> None:
        """Parse a line from the ENVIRONMENT DIVISION."""
        # Most parsing is done in the main loop via regex matches
        pass

    def _parse_data_item(self, line: str) -> Optional[DataItem]:
        """Parse a data item declaration (level number + name + PIC + VALUE).

        Examples:
            01  ACCOUNT-RECORD.
            05  ACCT-ID              PIC X(10).
            88  ACCT-CHECKING    VALUE 'C'.
            05  ACCT-BALANCE         PIC S9(10)V99.
            01  WS-COUNTER           PIC 9(4) VALUE 0.
        """
        level_match = self._LEVEL.match(line)
        if not level_match:
            return None

        level = int(level_match.group(1))
        name = level_match.group(2).rstrip('.')

        # 88-level: condition name
        if level == 88:
            value_match = self._VALUE.search(line)
            value = value_match.group(1).strip("'\"") if value_match else ""
            # Return as a DataItem with level 88 (parent will attach as condition)
            return DataItem(level=88, name=name, value=value)

        # PIC clause
        pic = None
        pic_match = self._PIC.search(line)
        if pic_match:
            pic = pic_match.group(1) or pic_match.group(2)
            if pic:
                pic = pic.rstrip('.')

        # VALUE clause
        value = None
        value_match = self._VALUE.search(line)
        if value_match:
            value = value_match.group(1).strip("'\"").rstrip('.')

        # OCCURS clause
        occurs = None
        occurs_match = self._OCCURS.search(line)
        if occurs_match:
            occurs = int(occurs_match.group(1))

        # REDEFINES clause
        redefines = None
        redefines_match = self._REDEFINES.search(line)
        if redefines_match:
            redefines = redefines_match.group(1).rstrip('.')

        return DataItem(
            level=level, name=name, pic=pic, value=value,
            occurs=occurs, redefines=redefines,
        )

    def _parse_statement(self, line: str) -> Optional[Statement]:
        """Parse a PROCEDURE DIVISION statement.

        Extracts the verb (first word) and stores the full text.
        For common verbs, also extracts structured fields.
        """
        # Remove trailing period
        text = line.rstrip('.')
        words = text.split()
        if not words:
            return None

        verb = words[0].upper()

        # Skip non-verb lines (continuation, END-IF, etc.)
        if verb in ('END-IF', 'END-EVALUATE', 'END-READ', 'END-PERFORM',
                     'END-WRITE', 'ELSE', 'WHEN', 'NOT', 'AT', 'ON'):
            return Statement(verb=verb, raw_text=text)

        stmt = Statement(verb=verb, raw_text=text)

        # Extract structured fields for common verbs
        if verb == "PERFORM" and len(words) >= 2:
            stmt.target = words[1]
        elif verb == "MOVE" and " TO " in text.upper():
            parts = re.split(r'\s+TO\s+', text, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2:
                stmt.source = parts[0].replace("MOVE", "").strip()
                stmt.target = parts[1].strip()
        elif verb == "DISPLAY":
            stmt.source = text[len("DISPLAY"):].strip().strip('"')
        elif verb == "IF":
            stmt.condition = text[len("IF"):].strip()

        return stmt
