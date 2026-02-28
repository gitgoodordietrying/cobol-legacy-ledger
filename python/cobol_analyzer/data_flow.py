"""
data_flow -- Field read/write tracking per paragraph.

Analyzes COBOL source to determine which fields are read and written in each
paragraph. Supports single-field tracing: given a field name, returns every
paragraph that reads or writes it, in execution order.

This helps an LLM understand data dependencies in spaghetti code where
WORKING-STORAGE fields are shared across many paragraphs with no formal
parameter passing.
"""

import re
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field


@dataclass
class FieldAccess:
    """A single read or write access to a field."""
    field_name: str
    access_type: str   # "READ" or "WRITE"
    paragraph: str
    line_number: int
    statement: str     # The COBOL statement containing the access


@dataclass
class DataFlowResult:
    """Complete data flow analysis for a COBOL program."""
    # Per-paragraph: which fields are read/written
    paragraph_reads: Dict[str, Set[str]] = field(default_factory=dict)
    paragraph_writes: Dict[str, Set[str]] = field(default_factory=dict)
    # Per-field: which paragraphs access it
    field_readers: Dict[str, Set[str]] = field(default_factory=dict)
    field_writers: Dict[str, Set[str]] = field(default_factory=dict)
    # All accesses in order
    accesses: List[FieldAccess] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "paragraph_reads": {k: sorted(v) for k, v in self.paragraph_reads.items()},
            "paragraph_writes": {k: sorted(v) for k, v in self.paragraph_writes.items()},
            "field_readers": {k: sorted(v) for k, v in self.field_readers.items()},
            "field_writers": {k: sorted(v) for k, v in self.field_writers.items()},
        }


class DataFlowAnalyzer:
    """Analyzes field read/write patterns in COBOL source."""

    # ── Write Patterns ────────────────────────────────────────────
    # Patterns for write operations (field appears as target)
    _MOVE_TO = re.compile(r'MOVE\s+.+?\s+TO\s+([\w-]+)', re.IGNORECASE)
    _COMPUTE = re.compile(r'COMPUTE\s+([\w-]+)', re.IGNORECASE)
    _ADD_TO = re.compile(r'ADD\s+.+?\s+TO\s+([\w-]+)', re.IGNORECASE)
    _SUBTRACT = re.compile(r'SUBTRACT\s+.+?\s+FROM\s+([\w-]+)', re.IGNORECASE)
    _MULTIPLY = re.compile(r'MULTIPLY\s+.+?\s+GIVING\s+([\w-]+)', re.IGNORECASE)
    _DIVIDE = re.compile(r'DIVIDE\s+.+?\s+GIVING\s+([\w-]+)', re.IGNORECASE)
    _ACCEPT = re.compile(r'ACCEPT\s+([\w-]+)', re.IGNORECASE)
    _READ_INTO = re.compile(r'READ\s+\S+\s+INTO\s+([\w-]+)', re.IGNORECASE)
    _SET = re.compile(r'SET\s+([\w-]+)\s+TO', re.IGNORECASE)

    # ── Read Patterns ─────────────────────────────────────────────
    # Patterns for read operations (field appears as source)
    _MOVE_FROM = re.compile(r'MOVE\s+([\w-]+)\s+TO', re.IGNORECASE)
    _IF_FIELD = re.compile(r'IF\s+([\w-]+)', re.IGNORECASE)
    _DISPLAY = re.compile(r'DISPLAY\s+.*?([\w-]+)', re.IGNORECASE)

    # ── Structural Patterns ─────────────────────────────────────────
    _PARAGRAPH = re.compile(r'^(\s{7}[\w-]+)\.\s*$', re.MULTILINE)
    _COMMENT = re.compile(r'^\s*\*>')

    # ── Keyword Exclusions ────────────────────────────────────────
    # Known COBOL verbs/keywords to exclude from field detection
    _KEYWORDS = {
        'MOVE', 'TO', 'ADD', 'SUBTRACT', 'FROM', 'MULTIPLY', 'GIVING',
        'DIVIDE', 'COMPUTE', 'IF', 'ELSE', 'END-IF', 'PERFORM', 'THRU',
        'UNTIL', 'VARYING', 'GO', 'STOP', 'RUN', 'DISPLAY', 'ACCEPT',
        'OPEN', 'CLOSE', 'READ', 'WRITE', 'AT', 'END', 'NOT', 'AND',
        'OR', 'WHEN', 'EVALUATE', 'TRUE', 'FALSE', 'EXIT', 'PARAGRAPH',
        'SECTION', 'INPUT', 'OUTPUT', 'EXTEND', 'SIZE', 'DELIMITED',
        'STRING', 'INTO', 'SET', 'FUNCTION', 'ROUNDED', 'VALUE',
        'END-READ', 'END-EVALUATE', 'END-STRING', 'END-COMPUTE',
        'ALTER', 'PROCEED', 'INITIALIZE',
    }

    def analyze(self, source: str, known_fields: Optional[Set[str]] = None) -> DataFlowResult:
        """Analyze data flow in COBOL source.

        :param source: COBOL source text
        :param known_fields: Optional set of known field names to track.
                           If None, discovers fields from WORKING-STORAGE.
        """
        result = DataFlowResult()
        lines = source.split('\n')

        if known_fields is None:
            known_fields = self._discover_fields(lines)

        current_para = None
        in_procedure = False

        for i, line in enumerate(lines):
            if re.search(r'PROCEDURE\s+DIVISION', line, re.IGNORECASE):
                in_procedure = True
                continue

            if not in_procedure:
                continue

            if self._COMMENT.match(line):
                continue

            match = self._PARAGRAPH.match(line)
            if match:
                current_para = match.group(1).strip()
                continue

            if current_para is None:
                continue

            # Analyze writes
            for pattern in [self._MOVE_TO, self._COMPUTE, self._ADD_TO,
                          self._SUBTRACT, self._MULTIPLY, self._DIVIDE,
                          self._ACCEPT, self._READ_INTO, self._SET]:
                for m in pattern.finditer(line):
                    field_name = m.group(1)
                    if field_name in known_fields:
                        self._record_access(result, field_name, "WRITE",
                                          current_para, i + 1, line.strip())

            # Analyze reads (fields used as sources)
            for pattern in [self._MOVE_FROM, self._IF_FIELD]:
                for m in pattern.finditer(line):
                    field_name = m.group(1)
                    if field_name in known_fields:
                        self._record_access(result, field_name, "READ",
                                          current_para, i + 1, line.strip())

            # General field detection: any known field on a non-write line
            for field_name in known_fields:
                if field_name in line and field_name not in self._KEYWORDS:
                    # Check if already recorded as write
                    already = any(
                        a.field_name == field_name and a.line_number == i + 1
                        for a in result.accesses
                    )
                    if not already:
                        self._record_access(result, field_name, "READ",
                                          current_para, i + 1, line.strip())

        return result

    def _record_access(self, result: DataFlowResult, field_name: str,
                       access_type: str, paragraph: str, line: int, stmt: str):
        """Record a field access."""
        access = FieldAccess(field_name, access_type, paragraph, line, stmt)
        result.accesses.append(access)

        if access_type == "WRITE":
            result.paragraph_writes.setdefault(paragraph, set()).add(field_name)
            result.field_writers.setdefault(field_name, set()).add(paragraph)
        else:
            result.paragraph_reads.setdefault(paragraph, set()).add(field_name)
            result.field_readers.setdefault(field_name, set()).add(paragraph)

    def _discover_fields(self, lines: List[str]) -> Set[str]:
        """Discover field names from WORKING-STORAGE and FILE SECTION."""
        fields = set()
        level_pattern = re.compile(r'^\s*(\d{2})\s+([\w-]+)', re.IGNORECASE)

        for line in lines:
            if self._COMMENT.match(line):
                continue
            m = level_pattern.match(line)
            if m:
                level = int(m.group(1))
                name = m.group(2)
                if level in (1, 5, 10, 15, 77) and name not in self._KEYWORDS:
                    fields.add(name)

        return fields

    def trace_field(self, source: str, field_name: str) -> List[Dict]:
        """Trace all accesses to a specific field across the program.

        Returns accesses in source order: [{"paragraph", "type", "line", "statement"}]
        """
        known = {field_name}
        result = self.analyze(source, known_fields=known)
        return [
            {
                "paragraph": a.paragraph,
                "type": a.access_type,
                "line": a.line_number,
                "statement": a.statement,
            }
            for a in sorted(result.accesses, key=lambda a: a.line_number)
        ]
