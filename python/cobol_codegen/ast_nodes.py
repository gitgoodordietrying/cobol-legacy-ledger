"""
ast_nodes.py -- COBOL Abstract Syntax Tree node definitions.

AST PATTERN:
    An Abstract Syntax Tree represents source code as a tree of typed nodes.
    Instead of working with raw text (fragile string manipulation), we work
    with structured objects that know their meaning. For example, a DataItem
    node knows it has a level number, a name, and a PIC clause -- we don't
    need to regex-match these from a text string every time.

    The parser converts COBOL text -> AST nodes.
    The generator converts AST nodes -> COBOL text.
    The editor modifies AST nodes in place.

    This separation means each component only needs to understand one
    direction of the transformation, and they can be developed and tested
    independently.

Why dataclasses:
    Python dataclasses provide typed, immutable-by-convention structures
    with automatic __init__, __repr__, and __eq__. They're the Python
    equivalent of COBOL's level-structured records: both define a schema
    with named, typed fields.

COBOL program structure (4 divisions):
    IDENTIFICATION DIVISION  -> ProgramMetadata
    ENVIRONMENT DIVISION     -> FileDeclaration list
    DATA DIVISION            -> DataItem tree (groups + elementary items)
    PROCEDURE DIVISION       -> Paragraph list -> Statement list
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ProgramMetadata:
    """Metadata from the IDENTIFICATION DIVISION.

    COBOL CONCEPT: IDENTIFICATION DIVISION
    Every COBOL program starts with PROGRAM-ID, which names the compilation
    unit. Optional entries (AUTHOR, DATE-WRITTEN, etc.) are documentation
    only -- the compiler ignores them but they appear in listings.
    """
    program_id: str
    author: str = ""
    date_written: str = ""
    purpose: str = ""
    compile_command: str = ""


@dataclass
class ConditionItem:
    """An 88-level condition name attached to a data item.

    COBOL CONCEPT: 88-level condition names
    Level 88 creates a named boolean test on the parent field's value.
    "88 ACCT-CHECKING VALUE 'C'" means IF ACCT-CHECKING tests whether
    ACCT-TYPE equals 'C'. Multiple values can be specified with THRU.
    """
    name: str
    value: str
    thru_value: Optional[str] = None


@dataclass
class DataItem:
    """A COBOL data item (field declaration) in WORKING-STORAGE or FILE SECTION.

    COBOL CONCEPT: Level numbers and group items
    Level numbers define hierarchy:
        01 = record (top-level group)
        02-49 = subordinate items (05, 10, 15 are conventional)
        77 = standalone item (no hierarchy)
        88 = condition name (boolean alias)

    A group item (no PIC) contains child items. An elementary item
    (has PIC) holds actual data. This mirrors XML/JSON nesting:
        01 PERSON.          (group - like a JSON object)
           05 FIRST-NAME.   (elementary - like a string field)
           05 AGE.          (elementary - like a number field)
    """
    level: int
    name: str
    pic: Optional[str] = None
    value: Optional[str] = None
    occurs: Optional[int] = None
    redefines: Optional[str] = None
    children: List['DataItem'] = field(default_factory=list)
    conditions: List[ConditionItem] = field(default_factory=list)
    comment: str = ""

    @property
    def is_group(self) -> bool:
        """Group items have children but no PIC clause."""
        return self.pic is None and len(self.children) > 0

    @property
    def byte_width(self) -> Optional[int]:
        """Calculate storage size from PIC clause.

        PIC X(10) = 10 bytes, PIC 9(8) = 8 bytes,
        PIC S9(10)V99 = 12 bytes (V is implied, not stored).
        """
        if not self.pic:
            return None
        import re
        # Strip S (sign) and V (implied decimal) -- they don't add bytes
        cleaned = self.pic.replace('S', '').replace('V', '')
        total = 0
        # Match patterns like X(10), 9(8), XX, 99
        for match in re.finditer(r'([X9])(?:\((\d+)\))?', cleaned):
            char_type, count = match.groups()
            total += int(count) if count else 1
        return total if total > 0 else None


@dataclass
class FileDeclaration:
    """A file declaration from ENVIRONMENT + DATA divisions.

    COBOL CONCEPT: SELECT...ASSIGN and FD
    COBOL file handling has two parts:
        1. SELECT (in ENVIRONMENT) maps a logical name to a physical file
        2. FD (in DATA) links a record layout to that logical name

    The separation allows changing file names without touching business logic.
    """
    logical_name: str       # e.g., "ACCOUNT-FILE"
    physical_name: str = "" # e.g., "ACCOUNTS.DAT"
    organization: str = "LINE SEQUENTIAL"
    status_var: str = ""    # e.g., "WS-FILE-STATUS"
    record_name: str = ""   # e.g., "ACCOUNT-RECORD"
    copybook: str = ""      # e.g., "ACCTREC.cpy"
    record_fields: List[DataItem] = field(default_factory=list)


@dataclass
class Statement:
    """A single COBOL statement (one executable instruction).

    COBOL CONCEPT: Verbs
    COBOL statements begin with a verb (MOVE, ADD, DISPLAY, PERFORM, IF,
    EVALUATE, OPEN, READ, WRITE, CLOSE, etc.). The verb determines the
    operation; everything after it is operands.

    We store the raw text because COBOL statements can span multiple lines
    and have complex syntax (nested IF/EVALUATE, inline PERFORM, etc.).
    For common verbs, structured fields provide easier programmatic access.
    """
    verb: str
    raw_text: str
    # Structured fields for common verbs (populated by parser when possible)
    target: str = ""        # MOVE ... TO target / PERFORM target
    source: str = ""        # MOVE source TO ...
    condition: str = ""     # IF condition / EVALUATE condition


@dataclass
class Paragraph:
    """A named paragraph in the PROCEDURE DIVISION.

    COBOL CONCEPT: Paragraphs
    Paragraphs are COBOL's subroutines. A paragraph name followed by a
    period marks the start; the next paragraph name marks the end.
    PERFORM paragraph-name transfers control there and returns.
    Unlike functions, paragraphs have no parameters or return values --
    all communication is through WORKING-STORAGE variables.
    """
    name: str
    statements: List[Statement] = field(default_factory=list)
    comment: str = ""


@dataclass
class COBOLProgram:
    """Complete representation of a COBOL program.

    This is the root AST node. It contains everything needed to regenerate
    a complete, compilable COBOL source file:
        - Metadata (IDENTIFICATION DIVISION)
        - File declarations (ENVIRONMENT + DATA FILE SECTION)
        - Working storage (DATA WORKING-STORAGE SECTION)
        - Paragraphs (PROCEDURE DIVISION)
        - Copybook references
        - Comment blocks (preserved from source)

    DESIGN NOTE FOR LAYER 3:
    An LLM can produce a COBOLProgram object by filling in these fields
    (e.g., from a template + user description). The generator then handles
    all COBOL formatting rules (indentation, column positions, PIC alignment).
    The LLM never needs to produce raw COBOL text.
    """
    metadata: ProgramMetadata
    files: List[FileDeclaration] = field(default_factory=list)
    working_storage: List[DataItem] = field(default_factory=list)
    paragraphs: List[Paragraph] = field(default_factory=list)
    copybooks: List[str] = field(default_factory=list)
    header_comments: List[str] = field(default_factory=list)
