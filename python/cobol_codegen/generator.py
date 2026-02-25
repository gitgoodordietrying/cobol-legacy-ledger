"""
generator.py -- Emit valid COBOL source from AST nodes.

COBOL FORMATTING RULES:
    This project uses free-format COBOL (GnuCOBOL -free flag), which relaxes
    the traditional fixed-format column rules. However, we maintain consistent
    indentation conventions:
        - Base indent: 7 spaces (matches traditional Area A)
        - Nesting: 4 spaces per level within a division/section
        - Comments: *> prefix, aligned with surrounding code
        - PIC clauses: right-aligned for readability
        - Line length: max 80 characters (soft limit)

    The generator handles all formatting so that AST consumers (editors,
    templates, future LLM integration) never need to worry about it.

OUTPUT PROTOCOL:
    Programs in this project use pipe-delimited DISPLAY statements for
    machine-readable output. The generator includes this protocol in
    generated programs:
        DISPLAY "RESULT|00"          -- success
        DISPLAY "RESULT|03"          -- invalid account
        DISPLAY "SUMMARY|" count "|" total
"""

from typing import List
from .ast_nodes import (
    COBOLProgram, DataItem, ConditionItem, Paragraph, Statement,
    FileDeclaration, ProgramMetadata,
)


class COBOLGenerator:
    """Generate valid COBOL source from AST nodes.

    Usage:
        gen = COBOLGenerator()
        source = gen.generate(program_ast)
        Path("NEW_PROGRAM.cob").write_text(source)
    """

    BASE_INDENT = "       "     # 7 spaces (traditional Area A)
    NEST_INDENT = "    "        # 4 spaces per nesting level
    CONCEPT_WIDTH = 59          # Width of COBOL CONCEPT comment blocks

    def generate(self, program: COBOLProgram) -> str:
        """Generate complete COBOL source from a COBOLProgram AST."""
        lines: List[str] = []

        # Header comments
        if program.header_comments:
            lines.extend(self._format_header_comments(program))
            lines.append("")

        # IDENTIFICATION DIVISION
        lines.extend(self._generate_identification(program.metadata))
        lines.append("")

        # ENVIRONMENT DIVISION (only if files are declared)
        if program.files:
            lines.extend(self._generate_environment(program.files))
            lines.append("")

        # DATA DIVISION
        lines.extend(self._generate_data(program))
        lines.append("")

        # PROCEDURE DIVISION
        lines.extend(self._generate_procedure(program.paragraphs))

        return "\n".join(lines) + "\n"

    def generate_copybook(self, name: str, fields: List[DataItem],
                          comment: str = "") -> str:
        """Generate a copybook (.cpy) file from a list of data items."""
        lines: List[str] = []

        # Header comment
        lines.append(f"*> {'=' * 64}")
        lines.append(f"*> {name} -- Record Layout")
        if comment:
            lines.append(f"*> {comment}")
        lines.append(f"*> {'=' * 64}")
        lines.append("")

        # Data items
        for item in fields:
            lines.extend(self._format_data_item(item, indent_level=0))

        return "\n".join(lines) + "\n"

    # ── IDENTIFICATION DIVISION ───────────────────────────────────

    def _generate_identification(self, meta: ProgramMetadata) -> List[str]:
        lines = [
            f"{self.BASE_INDENT}IDENTIFICATION DIVISION.",
            f"{self.BASE_INDENT}PROGRAM-ID. {meta.program_id}.",
        ]
        if meta.author:
            lines.append(f"{self.BASE_INDENT}AUTHOR. {meta.author}.")
        if meta.date_written:
            lines.append(f"{self.BASE_INDENT}DATE-WRITTEN. {meta.date_written}.")
        return lines

    # ── ENVIRONMENT DIVISION ──────────────────────────────────────

    def _generate_environment(self, files: List[FileDeclaration]) -> List[str]:
        lines = [
            f"{self.BASE_INDENT}ENVIRONMENT DIVISION.",
            f"{self.BASE_INDENT}INPUT-OUTPUT SECTION.",
            f"{self.BASE_INDENT}FILE-CONTROL.",
        ]
        for f in files:
            lines.append(f"{self.BASE_INDENT}{self.NEST_INDENT}SELECT {f.logical_name}")
            lines.append(f"{self.BASE_INDENT}{self.NEST_INDENT}    ASSIGN TO \"{f.physical_name}\"")
            if f.organization:
                lines.append(f"{self.BASE_INDENT}{self.NEST_INDENT}    ORGANIZATION IS {f.organization}")
            if f.status_var:
                lines.append(f"{self.BASE_INDENT}{self.NEST_INDENT}    FILE STATUS IS {f.status_var}.")
            else:
                # Close the SELECT with a period
                lines[-1] += "."
        return lines

    # ── DATA DIVISION ─────────────────────────────────────────────

    def _generate_data(self, program: COBOLProgram) -> List[str]:
        lines = [f"{self.BASE_INDENT}DATA DIVISION."]

        # FILE SECTION
        if program.files:
            lines.append(f"{self.BASE_INDENT}FILE SECTION.")
            for f in program.files:
                lines.append(f"{self.BASE_INDENT}FD  {f.logical_name}.")
                if f.copybook:
                    lines.append(f"{self.BASE_INDENT}COPY \"{f.copybook}\".")
                else:
                    for item in f.record_fields:
                        lines.extend(self._format_data_item(item, indent_level=0))
            lines.append("")

        # WORKING-STORAGE SECTION
        if program.working_storage:
            lines.append(f"{self.BASE_INDENT}WORKING-STORAGE SECTION.")
            for item in program.working_storage:
                lines.extend(self._format_data_item(item, indent_level=0))

        return lines

    # ── PROCEDURE DIVISION ────────────────────────────────────────

    def _generate_procedure(self, paragraphs: List[Paragraph]) -> List[str]:
        lines = [f"{self.BASE_INDENT}PROCEDURE DIVISION."]

        for para in paragraphs:
            lines.append(f"{self.BASE_INDENT}{para.name}.")
            if para.comment:
                lines.append(f"{self.BASE_INDENT}*> {para.comment}")

            for stmt in para.statements:
                indent = self.BASE_INDENT + self.NEST_INDENT
                lines.append(f"{indent}{stmt.raw_text}")

            lines.append("")

        return lines

    # ── Data Item Formatting ──────────────────────────────────────

    def _format_data_item(self, item: DataItem, indent_level: int) -> List[str]:
        """Format a single data item with proper indentation and PIC alignment."""
        lines = []
        indent = self.BASE_INDENT + (self.NEST_INDENT * indent_level)

        if item.comment:
            lines.append(f"{indent}*> {item.comment}")

        # Build the declaration line
        level_str = f"{item.level:02d}"
        parts = [f"{indent}{level_str}  {item.name}"]

        if item.redefines:
            parts.append(f"REDEFINES {item.redefines}")

        if item.pic:
            # Pad name to align PIC clauses (column ~40)
            name_part = f"{level_str}  {item.name}"
            if item.redefines:
                name_part += f" REDEFINES {item.redefines}"
            padding = max(1, 30 - len(name_part))
            parts = [f"{indent}{name_part}{' ' * padding}PIC {item.pic}"]

        if item.value is not None:
            parts.append(f"VALUE {item.value}")

        if item.occurs:
            parts.append(f"OCCURS {item.occurs}")

        line = " ".join(parts) if not item.pic else parts[0]
        if item.value is not None and item.pic:
            line += f" VALUE {item.value}"
        if item.occurs and item.pic:
            line += f" OCCURS {item.occurs}"

        lines.append(line + ".")

        # 88-level conditions
        for cond in item.conditions:
            cond_indent = indent + self.NEST_INDENT
            cond_line = f"{cond_indent}88  {cond.name}"
            padding = max(1, 26 - len(cond.name))
            cond_line += f"{' ' * padding}VALUE '{cond.value}'"
            if cond.thru_value:
                cond_line += f" THRU '{cond.thru_value}'"
            lines.append(cond_line + ".")

        # Child items (for group items)
        for child in item.children:
            lines.extend(self._format_data_item(child, indent_level + 1))

        return lines

    # ── Header Comments ───────────────────────────────────────────

    def _format_header_comments(self, program: COBOLProgram) -> List[str]:
        """Format the file header comment block."""
        lines = []
        lines.append(f"      *> {'=' * self.CONCEPT_WIDTH}")
        for comment in program.header_comments:
            lines.append(f"      *> {comment}")
        lines.append(f"      *> {'=' * self.CONCEPT_WIDTH}")
        return lines

    # ── Concept Block Helper ──────────────────────────────────────

    @staticmethod
    def concept_block(title: str, explanation: str) -> List[str]:
        """Generate a COBOL CONCEPT comment block for educational programs.

        These blocks are the teaching backbone of this project. Each one
        explains a COBOL concept with context for modern developers.
        """
        lines = []
        lines.append(f"      *> {'═' * 59}")
        lines.append(f"      *> COBOL CONCEPT: {title}")
        # Word-wrap explanation to ~55 chars per line
        words = explanation.split()
        current_line = "      *> "
        for word in words:
            if len(current_line) + len(word) + 1 > 66:
                lines.append(current_line.rstrip())
                current_line = "      *> " + word + " "
            else:
                current_line += word + " "
        if current_line.strip() != "*>":
            lines.append(current_line.rstrip())
        lines.append(f"      *> {'═' * 59}")
        return lines
