"""
editor.py -- High-level COBOL AST edit operations.

AST-BASED EDITING:
    Instead of searching and replacing text with regex (fragile, error-prone),
    we modify the AST and regenerate the source. This guarantees that edits
    produce valid COBOL because the generator enforces formatting rules.

    Workflow: parse source -> modify AST -> regenerate source
    The diff between original and regenerated shows exactly what changed.

    Each edit operation is a method that takes a COBOLProgram AST, modifies
    it in place, and returns a description of what changed. Operations can
    be composed: add a field, then add an 88-level condition to it.

AVAILABLE OPERATIONS:
    add_field        — Add a data item to a group record
    remove_field     — Remove a data item (updates byte offsets)
    add_paragraph    — Add a new paragraph to PROCEDURE DIVISION
    rename_paragraph — Rename with all PERFORM references updated
    add_operation    — Add a WHEN branch to the main EVALUATE
    add_88_condition — Add a condition name to a field
    add_copybook_ref — Add a COPY statement
    update_pic       — Change a field's PIC clause
"""

from typing import Optional, List
from .ast_nodes import (
    COBOLProgram, DataItem, ConditionItem, Paragraph, Statement,
)


class COBOLEditor:
    """Modify COBOL AST nodes with high-level edit operations.

    Usage:
        parser = COBOLParser()
        program = parser.parse_file("ACCOUNTS.cob")
        editor = COBOLEditor()
        editor.add_field(program, "ACCOUNT-RECORD", "ACCT-EMAIL", "X(50)")
        source = COBOLGenerator().generate(program)
    """

    def add_field(self, program: COBOLProgram, parent_name: str,
                  field_name: str, pic: str, value: Optional[str] = None,
                  after: Optional[str] = None, comment: str = "") -> str:
        """Add a new field to a group item in WORKING-STORAGE or FILE SECTION.

        Args:
            program: The AST to modify
            parent_name: Name of the parent group item (e.g., "ACCOUNT-RECORD")
            field_name: New field name (e.g., "ACCT-EMAIL")
            pic: PIC clause (e.g., "X(50)")
            value: Optional initial value
            after: Insert after this field name (default: append at end)
            comment: Optional comment for the field

        Returns:
            Description of what was added.
        """
        parent = self._find_item(program, parent_name)
        if not parent:
            return f"Error: parent group '{parent_name}' not found"

        # Determine level number (same as siblings, or parent + 4 convention)
        if parent.children:
            level = parent.children[0].level
        else:
            level = parent.level + 4 if parent.level < 49 else parent.level + 1

        new_item = DataItem(level=level, name=field_name, pic=pic,
                           value=value, comment=comment)

        if after:
            idx = self._find_child_index(parent, after)
            if idx is not None:
                parent.children.insert(idx + 1, new_item)
            else:
                parent.children.append(new_item)
        else:
            parent.children.append(new_item)

        return f"Added {field_name} PIC {pic} to {parent_name}"

    def remove_field(self, program: COBOLProgram, field_name: str) -> str:
        """Remove a field from its parent group.

        Args:
            program: The AST to modify
            field_name: Name of the field to remove

        Returns:
            Description of what was removed.
        """
        for ws_item in program.working_storage:
            result = self._remove_from_parent(ws_item, field_name)
            if result:
                return result

        for f in program.files:
            for rec_item in f.record_fields:
                result = self._remove_from_parent(rec_item, field_name)
                if result:
                    return result

        return f"Error: field '{field_name}' not found"

    def add_paragraph(self, program: COBOLProgram, name: str,
                      statements: List[str], after: Optional[str] = None,
                      comment: str = "") -> str:
        """Add a new paragraph to the PROCEDURE DIVISION.

        Args:
            program: The AST to modify
            name: Paragraph name (e.g., "VALIDATE-EMAIL")
            statements: List of raw COBOL statement strings
            after: Insert after this paragraph name (default: before STOP RUN)
            comment: Optional paragraph comment

        Returns:
            Description of what was added.
        """
        stmts = []
        for text in statements:
            words = text.strip().split()
            verb = words[0].upper() if words else "DISPLAY"
            stmts.append(Statement(verb=verb, raw_text=text.strip()))

        new_para = Paragraph(name=name, statements=stmts, comment=comment)

        if after:
            for i, para in enumerate(program.paragraphs):
                if para.name == after:
                    program.paragraphs.insert(i + 1, new_para)
                    return f"Added paragraph {name} after {after}"

        # Default: insert before last paragraph (usually contains STOP RUN)
        if program.paragraphs:
            program.paragraphs.insert(-1, new_para)
        else:
            program.paragraphs.append(new_para)

        return f"Added paragraph {name}"

    def rename_paragraph(self, program: COBOLProgram, old_name: str,
                         new_name: str) -> str:
        """Rename a paragraph and update all PERFORM references.

        Args:
            program: The AST to modify
            old_name: Current paragraph name
            new_name: New paragraph name

        Returns:
            Description of what was renamed and how many references updated.
        """
        found = False
        ref_count = 0

        for para in program.paragraphs:
            if para.name == old_name:
                para.name = new_name
                found = True

            # Update PERFORM references in all paragraphs
            for stmt in para.statements:
                if stmt.target == old_name:
                    stmt.target = new_name
                    stmt.raw_text = stmt.raw_text.replace(old_name, new_name)
                    ref_count += 1
                elif old_name in stmt.raw_text:
                    stmt.raw_text = stmt.raw_text.replace(old_name, new_name)
                    ref_count += 1

        if not found:
            return f"Error: paragraph '{old_name}' not found"

        return f"Renamed {old_name} -> {new_name} ({ref_count} references updated)"

    def add_operation(self, program: COBOLProgram, op_name: str,
                      paragraph_name: str) -> str:
        """Add a WHEN branch to the main EVALUATE dispatcher.

        Searches for the first EVALUATE statement and adds a new WHEN case.

        Args:
            program: The AST to modify
            op_name: Operation name (e.g., "ARCHIVE")
            paragraph_name: Paragraph to PERFORM for this operation

        Returns:
            Description of what was added.
        """
        for para in program.paragraphs:
            for i, stmt in enumerate(para.statements):
                if stmt.verb == "EVALUATE":
                    # Find the END-EVALUATE and insert before it
                    for j in range(i + 1, len(para.statements)):
                        if para.statements[j].verb == "END-EVALUATE":
                            # Insert WHEN + PERFORM before END-EVALUATE
                            when_stmt = Statement(
                                verb="WHEN",
                                raw_text=f'WHEN "{op_name}"\n                PERFORM {paragraph_name}',
                            )
                            para.statements.insert(j, when_stmt)
                            return f"Added WHEN \"{op_name}\" -> PERFORM {paragraph_name}"

        return "Error: no EVALUATE statement found in PROCEDURE DIVISION"

    def add_88_condition(self, program: COBOLProgram, field_name: str,
                         condition_name: str, value: str) -> str:
        """Add an 88-level condition name to an existing field.

        Args:
            program: The AST to modify
            field_name: Parent field name (e.g., "ACCT-STATUS")
            condition_name: New condition name (e.g., "ACCT-SUSPENDED")
            value: Condition value (e.g., "S")

        Returns:
            Description of what was added.
        """
        item = self._find_item(program, field_name)
        if not item:
            return f"Error: field '{field_name}' not found"

        item.conditions.append(ConditionItem(name=condition_name, value=value))
        return f"Added 88 {condition_name} VALUE '{value}' to {field_name}"

    def add_copybook_ref(self, program: COBOLProgram, copybook_name: str) -> str:
        """Add a COPY statement reference to the program.

        Args:
            program: The AST to modify
            copybook_name: Copybook filename (e.g., "NEWREC.cpy")

        Returns:
            Description of what was added.
        """
        if copybook_name not in program.copybooks:
            program.copybooks.append(copybook_name)
            return f"Added COPY \"{copybook_name}\""
        return f"Copybook {copybook_name} already referenced"

    def update_pic(self, program: COBOLProgram, field_name: str,
                   new_pic: str) -> str:
        """Change a field's PIC clause.

        Args:
            program: The AST to modify
            field_name: Field to update (e.g., "ACCT-NAME")
            new_pic: New PIC clause (e.g., "X(50)")

        Returns:
            Description of the change.
        """
        item = self._find_item(program, field_name)
        if not item:
            return f"Error: field '{field_name}' not found"

        old_pic = item.pic
        item.pic = new_pic
        return f"Changed {field_name} PIC {old_pic} -> PIC {new_pic}"

    # ── Internal Helpers ──────────────────────────────────────────

    def _find_item(self, program: COBOLProgram, name: str) -> Optional[DataItem]:
        """Find a DataItem by name anywhere in the AST."""
        # Search working storage
        for item in program.working_storage:
            found = self._search_item(item, name)
            if found:
                return found

        # Search file record fields
        for f in program.files:
            for item in f.record_fields:
                found = self._search_item(item, name)
                if found:
                    return found

        return None

    def _search_item(self, item: DataItem, name: str) -> Optional[DataItem]:
        """Recursively search for a DataItem by name."""
        if item.name == name:
            return item
        for child in item.children:
            found = self._search_item(child, name)
            if found:
                return found
        return None

    def _find_child_index(self, parent: DataItem, child_name: str) -> Optional[int]:
        """Find the index of a child by name."""
        for i, child in enumerate(parent.children):
            if child.name == child_name:
                return i
        return None

    def _remove_from_parent(self, parent: DataItem, field_name: str) -> Optional[str]:
        """Remove a child from a parent item. Returns description or None."""
        for i, child in enumerate(parent.children):
            if child.name == field_name:
                parent.children.pop(i)
                return f"Removed {field_name} from {parent.name}"
            # Recurse into children
            result = self._remove_from_parent(child, field_name)
            if result:
                return result
        return None
