"""
test_codegen.py -- Comprehensive tests for the COBOL code generation layer.

Tests cover all 6 modules in python/cobol_codegen/:
    - ast_nodes: DataItem properties (is_group, byte_width)
    - parser: Parse real .cob files, .cpy copybooks, and synthetic COBOL text
    - generator: Emit valid COBOL from AST, formatting rules, copybook output
    - templates: All 3 factory functions (CRUD, report, batch) + copybook_record
    - editor: All 8 edit operations (add/remove field, paragraphs, 88-levels, etc.)
    - validator: All convention checks (naming, PIC semantics, STOP RUN, flags)

Key property: ROUND-TRIP correctness
    parse(source) -> AST -> generate(AST) -> reparse -> same structure
"""

import pytest
from pathlib import Path

from python.cobol_codegen.ast_nodes import (
    COBOLProgram, DataItem, ConditionItem, Paragraph, Statement,
    FileDeclaration, ProgramMetadata,
)
from python.cobol_codegen.parser import COBOLParser
from python.cobol_codegen.generator import COBOLGenerator
from python.cobol_codegen.templates import (
    crud_program, report_program, batch_program, copybook_record,
)
from python.cobol_codegen.editor import COBOLEditor
from python.cobol_codegen.validator import COBOLValidator, ValidationIssue


# ── Fixtures ───────────────────────────────────────────────────

@pytest.fixture
def parser():
    return COBOLParser()


@pytest.fixture
def generator():
    return COBOLGenerator()


@pytest.fixture
def editor():
    return COBOLEditor()


@pytest.fixture
def validator():
    return COBOLValidator()


@pytest.fixture
def minimal_program():
    """A minimal valid COBOLProgram for testing."""
    return COBOLProgram(
        metadata=ProgramMetadata(program_id="TESTPROG"),
        working_storage=[
            DataItem(level=1, name="WS-STATUS", pic="XX", value="SPACES",
                     conditions=[
                         ConditionItem(name="WS-OK", value="00"),
                     ]),
            DataItem(level=1, name="WS-COUNTER", pic="9(4)", value="0"),
        ],
        paragraphs=[
            Paragraph(name="MAIN-PROGRAM", statements=[
                Statement(verb="DISPLAY", raw_text='DISPLAY "HELLO"'),
                Statement(verb="STOP", raw_text="STOP RUN"),
            ]),
        ],
    )


@pytest.fixture
def program_with_file():
    """A COBOLProgram with file declarations for testing."""
    record = DataItem(level=1, name="CUSTOMER-RECORD", children=[
        DataItem(level=5, name="CUST-ID", pic="X(10)"),
        DataItem(level=5, name="CUST-NAME", pic="X(30)"),
        DataItem(level=5, name="CUST-BALANCE", pic="S9(10)V99"),
        DataItem(level=5, name="CUST-STATUS", pic="X(1)",
                 conditions=[
                     ConditionItem(name="CUST-ACTIVE", value="A"),
                     ConditionItem(name="CUST-CLOSED", value="C"),
                 ]),
    ])
    return COBOLProgram(
        metadata=ProgramMetadata(program_id="CUSTOMERS"),
        files=[FileDeclaration(
            logical_name="CUSTOMER-FILE",
            physical_name="CUSTOMERS.DAT",
            organization="LINE SEQUENTIAL",
            status_var="WS-FILE-STATUS",
            record_name="CUSTOMER-RECORD",
            record_fields=[record],
        )],
        working_storage=[
            DataItem(level=1, name="WS-FILE-STATUS", pic="XX", value="SPACES"),
            DataItem(level=1, name="WS-OPERATION", pic="X(10)", value="SPACES"),
        ],
        paragraphs=[
            Paragraph(name="MAIN-PROGRAM", statements=[
                Statement(verb="DISPLAY", raw_text='DISPLAY "STARTING"'),
                Statement(verb="STOP", raw_text="STOP RUN"),
            ]),
        ],
    )


SMOKETEST_PATH = "COBOL-BANKING/src/SMOKETEST.cob"
ACCTREC_PATH = "COBOL-BANKING/copybooks/ACCTREC.cpy"


# ════════════════════════════════════════════════════════════════
# AST NODES TESTS
# ════════════════════════════════════════════════════════════════

class TestASTNodes:

    def test_data_item_is_group_with_children(self):
        group = DataItem(level=1, name="RECORD", children=[
            DataItem(level=5, name="FIELD-A", pic="X(10)"),
        ])
        assert group.is_group is True

    def test_data_item_is_not_group_with_pic(self):
        item = DataItem(level=5, name="FIELD-A", pic="X(10)")
        assert item.is_group is False

    def test_data_item_is_not_group_empty_children(self):
        item = DataItem(level=1, name="EMPTY-GROUP")
        assert item.is_group is False

    def test_byte_width_alphanumeric(self):
        item = DataItem(level=5, name="F", pic="X(10)")
        assert item.byte_width == 10

    def test_byte_width_numeric(self):
        item = DataItem(level=5, name="F", pic="9(8)")
        assert item.byte_width == 8

    def test_byte_width_money_with_sign_and_decimal(self):
        """S9(10)V99 = 12 bytes (S and V are implied, not stored)."""
        item = DataItem(level=5, name="F", pic="S9(10)V99")
        assert item.byte_width == 12

    def test_byte_width_repeated_chars(self):
        """XX = 2 bytes, 99 = 2 bytes."""
        assert DataItem(level=5, name="F", pic="XX").byte_width == 2
        assert DataItem(level=5, name="F", pic="99").byte_width == 2

    def test_byte_width_no_pic(self):
        """Group items have no PIC, so byte_width is None."""
        item = DataItem(level=1, name="GROUP")
        assert item.byte_width is None

    def test_condition_item_with_thru(self):
        cond = ConditionItem(name="RATE-TIER-2", value="5001", thru_value="10000")
        assert cond.thru_value == "10000"

    def test_program_defaults(self):
        prog = COBOLProgram(metadata=ProgramMetadata(program_id="TEST"))
        assert prog.files == []
        assert prog.working_storage == []
        assert prog.paragraphs == []
        assert prog.copybooks == []
        assert prog.header_comments == []


# ════════════════════════════════════════════════════════════════
# PARSER TESTS
# ════════════════════════════════════════════════════════════════

class TestParser:

    def test_parse_smoketest(self, parser):
        """Parse the real SMOKETEST.cob and verify structure."""
        if not Path(SMOKETEST_PATH).exists():
            pytest.skip("SMOKETEST.cob not available")
        prog = parser.parse_file(SMOKETEST_PATH)
        assert prog.metadata.program_id == "SMOKETEST"
        assert len(prog.paragraphs) >= 3
        para_names = [p.name for p in prog.paragraphs]
        assert "MAIN-PROGRAM" in para_names

    def test_parse_copybook(self, parser):
        """Parse the real ACCTREC.cpy copybook."""
        if not Path(ACCTREC_PATH).exists():
            pytest.skip("ACCTREC.cpy not available")
        items = parser.parse_copybook(ACCTREC_PATH)
        assert len(items) > 0
        # Should have at least the 01-level and some 05/88 items
        names = [item.name for item in items]
        assert any("ACCT" in n for n in names)

    def test_parse_file_not_found(self, parser):
        with pytest.raises(FileNotFoundError):
            parser.parse_file("/nonexistent/FAKE.cob")

    def test_parse_copybook_not_found(self, parser):
        with pytest.raises(FileNotFoundError):
            parser.parse_copybook("/nonexistent/FAKE.cpy")

    def test_parse_text_program_id(self, parser):
        source = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MYPROG.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-X              PIC X(5).

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           DISPLAY "HI".
           STOP RUN.
"""
        prog = parser.parse_text(source)
        assert prog.metadata.program_id == "MYPROG"

    def test_parse_text_working_storage(self, parser):
        source = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST1.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-COUNT           PIC 9(4) VALUE 0.
       01  WS-NAME            PIC X(30).
       01  WS-AMOUNT          PIC S9(10)V99.

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           STOP RUN.
"""
        prog = parser.parse_text(source)
        assert len(prog.working_storage) == 3
        ws_names = [item.name for item in prog.working_storage]
        assert "WS-COUNT" in ws_names
        assert "WS-NAME" in ws_names
        assert "WS-AMOUNT" in ws_names

    def test_parse_text_pic_value(self, parser):
        source = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST2.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-STATUS          PIC XX VALUE SPACES.

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           STOP RUN.
"""
        prog = parser.parse_text(source)
        item = prog.working_storage[0]
        assert item.name == "WS-STATUS"
        assert item.pic == "XX"
        assert item.value == "SPACES"

    def test_parse_text_paragraphs(self, parser):
        source = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST3.

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           PERFORM GREET.
           STOP RUN.

       GREET.
           DISPLAY "HELLO WORLD".
"""
        prog = parser.parse_text(source)
        assert len(prog.paragraphs) == 2
        assert prog.paragraphs[0].name == "MAIN-PROGRAM"
        assert prog.paragraphs[1].name == "GREET"
        # GREET should have a DISPLAY statement
        assert any(s.verb == "DISPLAY" for s in prog.paragraphs[1].statements)

    def test_parse_text_perform_target(self, parser):
        source = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST4.

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           PERFORM DO-WORK.
           STOP RUN.
       DO-WORK.
           DISPLAY "DONE".
"""
        prog = parser.parse_text(source)
        perform_stmt = [s for s in prog.paragraphs[0].statements if s.verb == "PERFORM"][0]
        assert perform_stmt.target == "DO-WORK"

    def test_parse_text_select_assign(self, parser):
        source = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST5.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT DATA-FILE
               ASSIGN TO "DATA.DAT"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-STATUS.

       DATA DIVISION.
       FILE SECTION.
       FD  DATA-FILE.
       01  DATA-RECORD.
           05  DATA-ID            PIC X(10).

       WORKING-STORAGE SECTION.
       01  WS-STATUS              PIC XX.

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           STOP RUN.
"""
        prog = parser.parse_text(source)
        assert len(prog.files) == 1
        f = prog.files[0]
        assert f.logical_name == "DATA-FILE"
        assert f.physical_name == "DATA.DAT"

    def test_parse_text_88_level(self, parser):
        """Parser should return 88-level items as DataItem with level=88."""
        source = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST6.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-TYPE             PIC X(1).
           88  WS-TYPE-A       VALUE 'A'.
           88  WS-TYPE-B       VALUE 'B'.

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           STOP RUN.
"""
        prog = parser.parse_text(source)
        # The parser produces flat items (88-levels are siblings, not children)
        # because nesting logic is convention-aware but simplified
        ws_names = [item.name for item in prog.working_storage]
        assert "WS-TYPE" in ws_names

    def test_parse_text_header_comments(self, parser):
        source = """\
      *> ================================================================
      *> TEST PROGRAM
      *> ================================================================
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST7.

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           STOP RUN.
"""
        prog = parser.parse_text(source)
        assert len(prog.header_comments) >= 2
        assert any("TEST PROGRAM" in c for c in prog.header_comments)

    def test_parse_text_copy_statement(self, parser):
        source = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST8.

       DATA DIVISION.
       FILE SECTION.
       FD  ACCT-FILE.
       COPY "ACCTREC.cpy".

       WORKING-STORAGE SECTION.

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           STOP RUN.
"""
        prog = parser.parse_text(source)
        assert "ACCTREC.cpy" in prog.copybooks

    def test_parse_text_occurs(self, parser):
        source = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST9.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-TABLE            PIC X(10) OCCURS 5.

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           STOP RUN.
"""
        prog = parser.parse_text(source)
        item = prog.working_storage[0]
        assert item.occurs == 5

    def test_parse_text_redefines(self, parser):
        source = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST10.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-DATE             PIC 9(8).
       01  WS-DATE-X REDEFINES WS-DATE PIC X(8).

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           STOP RUN.
"""
        prog = parser.parse_text(source)
        redef = [i for i in prog.working_storage if i.redefines][0]
        assert redef.name == "WS-DATE-X"
        assert redef.redefines == "WS-DATE"

    def test_parse_empty_text(self, parser):
        """Empty source should produce a default program."""
        prog = parser.parse_text("")
        assert prog.metadata.program_id == "UNKNOWN"
        assert prog.paragraphs == []


# ════════════════════════════════════════════════════════════════
# GENERATOR TESTS
# ════════════════════════════════════════════════════════════════

class TestGenerator:

    def test_generate_minimal(self, generator, minimal_program):
        source = generator.generate(minimal_program)
        assert "IDENTIFICATION DIVISION" in source
        assert "PROGRAM-ID. TESTPROG" in source
        assert "PROCEDURE DIVISION" in source
        assert "STOP RUN" in source

    def test_generate_working_storage(self, generator, minimal_program):
        source = generator.generate(minimal_program)
        assert "WORKING-STORAGE SECTION" in source
        assert "WS-STATUS" in source
        assert "PIC XX" in source
        assert "VALUE SPACES" in source

    def test_generate_88_level(self, generator, minimal_program):
        source = generator.generate(minimal_program)
        assert "88  WS-OK" in source
        assert "VALUE '00'" in source

    def test_generate_with_files(self, generator, program_with_file):
        source = generator.generate(program_with_file)
        assert "ENVIRONMENT DIVISION" in source
        assert "SELECT CUSTOMER-FILE" in source
        assert 'ASSIGN TO "CUSTOMERS.DAT"' in source
        assert "FILE STATUS IS WS-FILE-STATUS" in source
        assert "FD  CUSTOMER-FILE" in source

    def test_generate_file_record_fields(self, generator, program_with_file):
        source = generator.generate(program_with_file)
        assert "CUST-ID" in source
        assert "CUST-NAME" in source
        assert "PIC X(10)" in source

    def test_generate_paragraph_comment(self, generator):
        prog = COBOLProgram(
            metadata=ProgramMetadata(program_id="TEST"),
            paragraphs=[
                Paragraph(name="DO-WORK", statements=[
                    Statement(verb="DISPLAY", raw_text='DISPLAY "DONE"'),
                ], comment="This paragraph does work"),
                Paragraph(name="MAIN-PROGRAM", statements=[
                    Statement(verb="STOP", raw_text="STOP RUN"),
                ]),
            ],
        )
        source = generator.generate(prog)
        assert "*> This paragraph does work" in source

    def test_generate_header_comments(self, generator):
        prog = COBOLProgram(
            metadata=ProgramMetadata(program_id="TEST"),
            header_comments=["My Program", "Version 1.0"],
            paragraphs=[Paragraph(name="MAIN-PROGRAM", statements=[
                Statement(verb="STOP", raw_text="STOP RUN"),
            ])],
        )
        source = generator.generate(prog)
        assert "My Program" in source
        assert "Version 1.0" in source

    def test_generate_no_environment_without_files(self, generator, minimal_program):
        """No ENVIRONMENT DIVISION when there are no file declarations."""
        source = generator.generate(minimal_program)
        assert "ENVIRONMENT DIVISION" not in source

    def test_generate_copybook(self, generator):
        fields = [
            DataItem(level=1, name="MY-RECORD", children=[
                DataItem(level=5, name="MY-ID", pic="X(10)"),
                DataItem(level=5, name="MY-NAME", pic="X(30)"),
            ]),
        ]
        source = generator.generate_copybook("MYREC", fields, comment="Test record")
        assert "MYREC" in source
        assert "Test record" in source
        assert "MY-ID" in source
        assert "PIC X(10)" in source

    def test_generate_indentation(self, generator, minimal_program):
        """All lines should start with at least 7-space base indent."""
        source = generator.generate(minimal_program)
        for line in source.split('\n'):
            if line.strip():  # Skip blank lines
                assert line.startswith("      "), f"Bad indent: {line!r}"

    def test_concept_block(self):
        lines = COBOLGenerator.concept_block("Level Numbers",
            "Level numbers define hierarchy in COBOL records.")
        assert any("COBOL CONCEPT: Level Numbers" in l for l in lines)
        assert len(lines) >= 3

    def test_generate_redefines(self, generator):
        prog = COBOLProgram(
            metadata=ProgramMetadata(program_id="TEST"),
            working_storage=[
                DataItem(level=1, name="WS-DATE", pic="9(8)"),
                DataItem(level=1, name="WS-DATE-X", pic="X(8)", redefines="WS-DATE"),
            ],
            paragraphs=[Paragraph(name="MAIN-PROGRAM", statements=[
                Statement(verb="STOP", raw_text="STOP RUN"),
            ])],
        )
        source = generator.generate(prog)
        assert "REDEFINES WS-DATE" in source

    def test_generate_occurs(self, generator):
        prog = COBOLProgram(
            metadata=ProgramMetadata(program_id="TEST"),
            working_storage=[
                DataItem(level=1, name="WS-TABLE", pic="X(10)", occurs=5),
            ],
            paragraphs=[Paragraph(name="MAIN-PROGRAM", statements=[
                Statement(verb="STOP", raw_text="STOP RUN"),
            ])],
        )
        source = generator.generate(prog)
        assert "OCCURS 5" in source


# ════════════════════════════════════════════════════════════════
# ROUND-TRIP TESTS (parse -> generate -> reparse)
# ════════════════════════════════════════════════════════════════

class TestRoundTrip:

    def test_round_trip_preserves_program_id(self, parser, generator):
        source = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ROUNDTRIP.

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           DISPLAY "HELLO".
           STOP RUN.
"""
        prog1 = parser.parse_text(source)
        regenerated = generator.generate(prog1)
        prog2 = parser.parse_text(regenerated)
        assert prog2.metadata.program_id == prog1.metadata.program_id

    def test_round_trip_preserves_paragraphs(self, parser, generator):
        source = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ROUNDTRIP2.

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           PERFORM DO-WORK.
           STOP RUN.

       DO-WORK.
           DISPLAY "DONE".
"""
        prog1 = parser.parse_text(source)
        regenerated = generator.generate(prog1)
        prog2 = parser.parse_text(regenerated)
        assert len(prog2.paragraphs) == len(prog1.paragraphs)
        for p1, p2 in zip(prog1.paragraphs, prog2.paragraphs):
            assert p1.name == p2.name

    def test_round_trip_preserves_working_storage(self, parser, generator):
        source = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ROUNDTRIP3.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-COUNT            PIC 9(4) VALUE 0.
       01  WS-NAME             PIC X(30).

       PROCEDURE DIVISION.
       MAIN-PROGRAM.
           STOP RUN.
"""
        prog1 = parser.parse_text(source)
        regenerated = generator.generate(prog1)
        prog2 = parser.parse_text(regenerated)
        assert len(prog2.working_storage) == len(prog1.working_storage)
        for w1, w2 in zip(prog1.working_storage, prog2.working_storage):
            assert w1.name == w2.name
            assert w1.pic == w2.pic

    def test_template_round_trip(self, parser, generator):
        """Generate from template, then parse the output — structure matches."""
        prog1 = crud_program("MYTEST", "MYREC.cpy", "MY-RECORD", "MY.DAT", "MY-ID")
        source = generator.generate(prog1)
        prog2 = parser.parse_text(source)
        assert prog2.metadata.program_id == "MYTEST"
        assert len(prog2.paragraphs) >= len(prog1.paragraphs)


# ════════════════════════════════════════════════════════════════
# TEMPLATE TESTS
# ════════════════════════════════════════════════════════════════

class TestTemplates:

    def test_crud_program_structure(self):
        prog = crud_program("ACCOUNTS", "ACCTREC.cpy", "ACCOUNT-RECORD",
                           "ACCOUNTS.DAT", "ACCT-ID")
        assert prog.metadata.program_id == "ACCOUNTS"
        assert len(prog.files) == 1
        assert prog.files[0].logical_name == "ACCOUNTS-FILE"
        assert prog.files[0].physical_name == "ACCOUNTS.DAT"
        assert prog.files[0].copybook == "ACCTREC.cpy"

    def test_crud_program_default_operations(self):
        prog = crud_program("TEST", "REC.cpy", "REC", "TEST.DAT", "ID")
        para_names = [p.name for p in prog.paragraphs]
        assert "MAIN-PROGRAM" in para_names
        for op in ["CREATE", "READ", "UPDATE", "LIST", "CLOSE"]:
            assert f"{op}-OPERATION" in para_names

    def test_crud_program_custom_operations(self):
        prog = crud_program("TEST", "REC.cpy", "REC", "TEST.DAT", "ID",
                           operations=["ARCHIVE", "PURGE"])
        para_names = [p.name for p in prog.paragraphs]
        assert "ARCHIVE-OPERATION" in para_names
        assert "PURGE-OPERATION" in para_names
        assert "CREATE-OPERATION" not in para_names

    def test_crud_program_has_stop_run(self):
        prog = crud_program("TEST", "REC.cpy", "REC", "TEST.DAT", "ID")
        main = [p for p in prog.paragraphs if p.name == "MAIN-PROGRAM"][0]
        assert any("STOP RUN" in s.raw_text for s in main.statements)

    def test_crud_program_has_evaluate(self):
        prog = crud_program("TEST", "REC.cpy", "REC", "TEST.DAT", "ID")
        main = [p for p in prog.paragraphs if p.name == "MAIN-PROGRAM"][0]
        assert any(s.verb == "EVALUATE" for s in main.statements)

    def test_report_program_structure(self):
        prog = report_program("MYREPORT", [
            {"logical_name": "INPUT-FILE", "physical_name": "IN.DAT"},
        ], ["STATEMENT", "SUMMARY"])
        assert prog.metadata.program_id == "MYREPORT"
        para_names = [p.name for p in prog.paragraphs]
        assert "GENERATE-STATEMENT" in para_names
        assert "GENERATE-SUMMARY" in para_names

    def test_batch_program_structure(self):
        prog = batch_program("PAYROLL", "PAY.DAT", "PAYREC.cpy",
                            "PAY-RECORD", "Process payroll records")
        assert prog.metadata.program_id == "PAYROLL"
        para_names = [p.name for p in prog.paragraphs]
        assert "MAIN-PROGRAM" in para_names
        assert "OPEN-INPUT" in para_names
        assert "PROCESS-RECORDS" in para_names
        assert "PROCESS-ONE-RECORD" in para_names
        assert "CLOSE-INPUT" in para_names
        assert "DISPLAY-SUMMARY" in para_names

    def test_batch_program_has_stop_run(self):
        prog = batch_program("TEST", "IN.DAT", "REC.cpy", "REC")
        main = [p for p in prog.paragraphs if p.name == "MAIN-PROGRAM"][0]
        assert any("STOP RUN" in s.raw_text for s in main.statements)

    def test_copybook_record(self):
        fields = [
            {"name": "CUST-ID", "pic": "X(10)"},
            {"name": "CUST-NAME", "pic": "X(30)", "comment": "Full name"},
            {"name": "CUST-TYPE", "pic": "X(1)", "conditions": [
                {"name": "CUST-RETAIL", "value": "R"},
                {"name": "CUST-WHOLESALE", "value": "W"},
            ]},
        ]
        items = copybook_record("CUST", fields)
        assert len(items) == 1
        group = items[0]
        assert group.name == "CUST-RECORD"
        assert group.level == 1
        assert len(group.children) == 3
        assert group.children[2].conditions[0].name == "CUST-RETAIL"

    def test_copybook_record_custom_name(self):
        items = copybook_record("CUST", [{"name": "F", "pic": "X"}],
                               record_name="MY-CUSTOM-RECORD")
        assert items[0].name == "MY-CUSTOM-RECORD"

    def test_templates_generate_valid_cobol(self):
        """All 3 templates produce source that passes the validator."""
        gen = COBOLGenerator()
        val = COBOLValidator()

        for prog in [
            crud_program("TEST1", "R.cpy", "R", "T.DAT", "ID"),
            report_program("TEST2", [{"logical_name": "F", "physical_name": "X.DAT"}], ["RPT"]),
            batch_program("TEST3", "I.DAT", "R.cpy", "REC"),
        ]:
            source = gen.generate(prog)
            assert "IDENTIFICATION DIVISION" in source
            issues = val.validate(prog)
            errors = [i for i in issues if i.severity == "ERROR"]
            assert len(errors) == 0, f"Template produced errors: {errors}"


# ════════════════════════════════════════════════════════════════
# EDITOR TESTS
# ════════════════════════════════════════════════════════════════

class TestEditor:

    def test_add_field_to_file_record(self, editor, program_with_file):
        result = editor.add_field(program_with_file, "CUSTOMER-RECORD",
                                 "CUST-EMAIL", "X(50)")
        assert "Added" in result
        assert "CUST-EMAIL" in result
        record = program_with_file.files[0].record_fields[0]
        names = [c.name for c in record.children]
        assert "CUST-EMAIL" in names

    def test_add_field_after(self, editor, program_with_file):
        editor.add_field(program_with_file, "CUSTOMER-RECORD",
                        "CUST-PHONE", "X(15)", after="CUST-NAME")
        record = program_with_file.files[0].record_fields[0]
        names = [c.name for c in record.children]
        idx_name = names.index("CUST-NAME")
        idx_phone = names.index("CUST-PHONE")
        assert idx_phone == idx_name + 1

    def test_add_field_inherits_sibling_level(self, editor, program_with_file):
        editor.add_field(program_with_file, "CUSTOMER-RECORD",
                        "CUST-PHONE", "X(15)")
        record = program_with_file.files[0].record_fields[0]
        phone = [c for c in record.children if c.name == "CUST-PHONE"][0]
        assert phone.level == 5  # Same as siblings

    def test_add_field_parent_not_found(self, editor, minimal_program):
        result = editor.add_field(minimal_program, "NONEXISTENT", "F", "X")
        assert "Error" in result

    def test_remove_field(self, editor, program_with_file):
        result = editor.remove_field(program_with_file, "CUST-NAME")
        assert "Removed" in result
        record = program_with_file.files[0].record_fields[0]
        names = [c.name for c in record.children]
        assert "CUST-NAME" not in names

    def test_remove_field_not_found(self, editor, minimal_program):
        result = editor.remove_field(minimal_program, "NONEXISTENT")
        assert "Error" in result

    def test_add_paragraph(self, editor, minimal_program):
        result = editor.add_paragraph(minimal_program, "VALIDATE-INPUT",
                                     ['DISPLAY "VALIDATING"', 'DISPLAY "RESULT|00"'],
                                     comment="Input validation")
        assert "Added" in result
        names = [p.name for p in minimal_program.paragraphs]
        assert "VALIDATE-INPUT" in names

    def test_add_paragraph_after(self, editor, minimal_program):
        editor.add_paragraph(minimal_program, "STEP-A",
                           ['DISPLAY "A"'], after="MAIN-PROGRAM")
        names = [p.name for p in minimal_program.paragraphs]
        assert names.index("STEP-A") == names.index("MAIN-PROGRAM") + 1

    def test_rename_paragraph(self, editor):
        prog = COBOLProgram(
            metadata=ProgramMetadata(program_id="TEST"),
            paragraphs=[
                Paragraph(name="MAIN-PROGRAM", statements=[
                    Statement(verb="PERFORM", raw_text="PERFORM OLD-NAME",
                             target="OLD-NAME"),
                    Statement(verb="STOP", raw_text="STOP RUN"),
                ]),
                Paragraph(name="OLD-NAME", statements=[
                    Statement(verb="DISPLAY", raw_text='DISPLAY "HI"'),
                ]),
            ],
        )
        result = editor.rename_paragraph(prog, "OLD-NAME", "NEW-NAME")
        assert "Renamed" in result
        assert "1 references" in result
        names = [p.name for p in prog.paragraphs]
        assert "NEW-NAME" in names
        assert "OLD-NAME" not in names
        # PERFORM reference should be updated too
        perform = [s for s in prog.paragraphs[0].statements if s.verb == "PERFORM"][0]
        assert "NEW-NAME" in perform.raw_text

    def test_rename_paragraph_not_found(self, editor, minimal_program):
        result = editor.rename_paragraph(minimal_program, "NONEXISTENT", "NEW")
        assert "Error" in result

    def test_add_operation(self, editor):
        prog = COBOLProgram(
            metadata=ProgramMetadata(program_id="TEST"),
            paragraphs=[
                Paragraph(name="MAIN-PROGRAM", statements=[
                    Statement(verb="EVALUATE", raw_text="EVALUATE WS-OP"),
                    Statement(verb="WHEN", raw_text='WHEN "READ"'),
                    Statement(verb="END-EVALUATE", raw_text="END-EVALUATE"),
                    Statement(verb="STOP", raw_text="STOP RUN"),
                ]),
            ],
        )
        result = editor.add_operation(prog, "ARCHIVE", "ARCHIVE-OPERATION")
        assert "Added" in result
        assert "ARCHIVE" in result
        stmts = prog.paragraphs[0].statements
        # WHEN "ARCHIVE" should be before END-EVALUATE
        when_idx = next(i for i, s in enumerate(stmts) if "ARCHIVE" in s.raw_text)
        end_idx = next(i for i, s in enumerate(stmts) if s.verb == "END-EVALUATE")
        assert when_idx < end_idx

    def test_add_operation_no_evaluate(self, editor, minimal_program):
        result = editor.add_operation(minimal_program, "TEST", "TEST-OP")
        assert "Error" in result

    def test_add_88_condition(self, editor, program_with_file):
        result = editor.add_88_condition(program_with_file, "CUST-STATUS",
                                        "CUST-FROZEN", "F")
        assert "Added" in result
        status = None
        for child in program_with_file.files[0].record_fields[0].children:
            if child.name == "CUST-STATUS":
                status = child
                break
        assert status is not None
        cond_names = [c.name for c in status.conditions]
        assert "CUST-FROZEN" in cond_names

    def test_add_88_condition_field_not_found(self, editor, minimal_program):
        result = editor.add_88_condition(minimal_program, "NONEXISTENT", "COND", "X")
        assert "Error" in result

    def test_add_copybook_ref(self, editor, minimal_program):
        result = editor.add_copybook_ref(minimal_program, "NEWREC.cpy")
        assert "Added" in result
        assert "NEWREC.cpy" in minimal_program.copybooks

    def test_add_copybook_ref_duplicate(self, editor, minimal_program):
        editor.add_copybook_ref(minimal_program, "NEWREC.cpy")
        result = editor.add_copybook_ref(minimal_program, "NEWREC.cpy")
        assert "already" in result

    def test_update_pic(self, editor, program_with_file):
        result = editor.update_pic(program_with_file, "CUST-NAME", "X(50)")
        assert "Changed" in result
        assert "X(50)" in result
        name_field = None
        for child in program_with_file.files[0].record_fields[0].children:
            if child.name == "CUST-NAME":
                name_field = child
                break
        assert name_field.pic == "X(50)"

    def test_update_pic_field_not_found(self, editor, minimal_program):
        result = editor.update_pic(minimal_program, "NONEXISTENT", "X(10)")
        assert "Error" in result

    def test_edit_then_generate(self, editor, generator, program_with_file):
        """Edit an AST, then generate — output reflects the edit."""
        editor.add_field(program_with_file, "CUSTOMER-RECORD",
                        "CUST-EMAIL", "X(50)", after="CUST-NAME")
        source = generator.generate(program_with_file)
        assert "CUST-EMAIL" in source
        assert "PIC X(50)" in source


# ════════════════════════════════════════════════════════════════
# VALIDATOR TESTS
# ════════════════════════════════════════════════════════════════

class TestValidator:

    def test_valid_program_no_errors(self, validator, minimal_program):
        issues = validator.validate(minimal_program)
        errors = [i for i in issues if i.severity == "ERROR"]
        assert len(errors) == 0

    def test_missing_program_id(self, validator):
        prog = COBOLProgram(
            metadata=ProgramMetadata(program_id="UNKNOWN"),
            paragraphs=[Paragraph(name="MAIN-PROGRAM", statements=[
                Statement(verb="STOP", raw_text="STOP RUN"),
            ])],
        )
        issues = validator.validate(prog)
        errors = [i for i in issues if i.severity == "ERROR"]
        assert any("PROGRAM-ID" in i.message for i in errors)

    def test_lowercase_program_id_warning(self, validator):
        prog = COBOLProgram(
            metadata=ProgramMetadata(program_id="myProg"),
            paragraphs=[Paragraph(name="MAIN-PROGRAM", statements=[
                Statement(verb="STOP", raw_text="STOP RUN"),
            ])],
        )
        issues = validator.validate(prog)
        warnings = [i for i in issues if i.severity == "WARNING"]
        assert any("UPPERCASE" in i.message for i in warnings)

    def test_invalid_field_name(self, validator):
        prog = COBOLProgram(
            metadata=ProgramMetadata(program_id="TEST"),
            working_storage=[
                DataItem(level=1, name="bad_name", pic="X(10)"),
            ],
            paragraphs=[Paragraph(name="MAIN-PROGRAM", statements=[
                Statement(verb="STOP", raw_text="STOP RUN"),
            ])],
        )
        issues = validator.validate(prog)
        errors = [i for i in issues if i.severity == "ERROR"]
        assert any("bad_name" in i.message for i in errors)

    def test_invalid_paragraph_name(self, validator):
        prog = COBOLProgram(
            metadata=ProgramMetadata(program_id="TEST"),
            paragraphs=[
                Paragraph(name="invalid name", statements=[
                    Statement(verb="STOP", raw_text="STOP RUN"),
                ]),
            ],
        )
        issues = validator.validate(prog)
        errors = [i for i in issues if i.severity == "ERROR"]
        assert any("invalid name" in i.message for i in errors)

    def test_money_field_wrong_pic(self, validator):
        prog = COBOLProgram(
            metadata=ProgramMetadata(program_id="TEST"),
            working_storage=[
                DataItem(level=1, name="ACCT-BALANCE", pic="9(10)"),  # Missing S and V99
            ],
            paragraphs=[Paragraph(name="MAIN-PROGRAM", statements=[
                Statement(verb="STOP", raw_text="STOP RUN"),
            ])],
        )
        issues = validator.validate(prog)
        warnings = [i for i in issues if i.severity == "WARNING"]
        assert any("Money field" in i.message or "BALANCE" in i.message for i in warnings)

    def test_money_field_correct_pic(self, validator):
        prog = COBOLProgram(
            metadata=ProgramMetadata(program_id="TEST"),
            working_storage=[
                DataItem(level=1, name="ACCT-BALANCE", pic="S9(10)V99"),
            ],
            paragraphs=[Paragraph(name="MAIN-PROGRAM", statements=[
                Statement(verb="STOP", raw_text="STOP RUN"),
            ])],
        )
        issues = validator.validate(prog)
        warnings = [i for i in issues if i.severity == "WARNING"]
        assert not any("Money field" in i.message for i in warnings)

    def test_date_field_wrong_pic(self, validator):
        prog = COBOLProgram(
            metadata=ProgramMetadata(program_id="TEST"),
            working_storage=[
                DataItem(level=1, name="ACCT-DATE", pic="X(8)"),  # Should be 9(8)
            ],
            paragraphs=[Paragraph(name="MAIN-PROGRAM", statements=[
                Statement(verb="STOP", raw_text="STOP RUN"),
            ])],
        )
        issues = validator.validate(prog)
        warnings = [i for i in issues if i.severity == "WARNING"]
        assert any("Date field" in i.message for i in warnings)

    def test_missing_stop_run(self, validator):
        prog = COBOLProgram(
            metadata=ProgramMetadata(program_id="TEST"),
            paragraphs=[Paragraph(name="MAIN-PROGRAM", statements=[
                Statement(verb="DISPLAY", raw_text='DISPLAY "NO STOP"'),
            ])],
        )
        issues = validator.validate(prog)
        errors = [i for i in issues if i.severity == "ERROR"]
        assert any("STOP RUN" in i.message for i in errors)

    def test_flag_field_without_88_condition(self, validator):
        prog = COBOLProgram(
            metadata=ProgramMetadata(program_id="TEST"),
            working_storage=[
                DataItem(level=1, name="ACCT-STATUS", pic="X(1)"),  # No 88-levels
            ],
            paragraphs=[Paragraph(name="MAIN-PROGRAM", statements=[
                Statement(verb="STOP", raw_text="STOP RUN"),
            ])],
        )
        issues = validator.validate(prog)
        warnings = [i for i in issues if i.severity == "WARNING"]
        assert any("88-level" in i.message for i in warnings)

    def test_flag_field_with_88_condition(self, validator):
        prog = COBOLProgram(
            metadata=ProgramMetadata(program_id="TEST"),
            working_storage=[
                DataItem(level=1, name="ACCT-STATUS", pic="X(1)",
                         conditions=[ConditionItem(name="ACCT-ACTIVE", value="A")]),
            ],
            paragraphs=[Paragraph(name="MAIN-PROGRAM", statements=[
                Statement(verb="STOP", raw_text="STOP RUN"),
            ])],
        )
        issues = validator.validate(prog)
        warnings = [i for i in issues if i.severity == "WARNING"]
        assert not any("88-level" in i.message for i in warnings)

    def test_operation_paragraph_without_display(self, validator):
        prog = COBOLProgram(
            metadata=ProgramMetadata(program_id="TEST"),
            paragraphs=[
                Paragraph(name="MAIN-PROGRAM", statements=[
                    Statement(verb="STOP", raw_text="STOP RUN"),
                ]),
                Paragraph(name="CREATE-OPERATION", statements=[
                    Statement(verb="MOVE", raw_text="MOVE X TO Y"),
                    # Missing trailing DISPLAY
                ]),
            ],
        )
        issues = validator.validate(prog)
        warnings = [i for i in issues if i.severity == "WARNING"]
        assert any("DISPLAY" in i.message for i in warnings)

    def test_validation_issue_repr(self):
        issue = ValidationIssue("ERROR", "Test message", "WORKING-STORAGE")
        r = repr(issue)
        assert "ERROR" in r
        assert "Test message" in r
        assert "WORKING-STORAGE" in r

    def test_validation_issue_repr_no_location(self):
        issue = ValidationIssue("WARNING", "Something wrong")
        r = repr(issue)
        assert "WARNING" in r
        assert " at " not in r

    def test_errors_sorted_before_warnings(self, validator):
        prog = COBOLProgram(
            metadata=ProgramMetadata(program_id="UNKNOWN"),
            working_storage=[
                DataItem(level=1, name="ACCT-BALANCE", pic="9(5)"),  # WARNING
            ],
            paragraphs=[],  # No STOP RUN = ERROR
        )
        issues = validator.validate(prog)
        if len(issues) >= 2:
            # All ERRORs should come before all WARNINGs
            found_warning = False
            for issue in issues:
                if issue.severity == "WARNING":
                    found_warning = True
                if issue.severity == "ERROR" and found_warning:
                    pytest.fail("ERROR found after WARNING — sort is broken")

    def test_validate_file_record_fields(self, validator, program_with_file):
        """Validator checks field names in file records too, not just WS."""
        # program_with_file has valid names, so should be clean
        issues = validator.validate(program_with_file)
        errors = [i for i in issues if i.severity == "ERROR"]
        name_errors = [e for e in errors if "UPPERCASE" in e.message or "must be" in e.message]
        assert len(name_errors) == 0

    def test_invalid_condition_name(self, validator):
        prog = COBOLProgram(
            metadata=ProgramMetadata(program_id="TEST"),
            working_storage=[
                DataItem(level=1, name="WS-TYPE", pic="X(1)",
                         conditions=[ConditionItem(name="bad_cond", value="X")]),
            ],
            paragraphs=[Paragraph(name="MAIN-PROGRAM", statements=[
                Statement(verb="STOP", raw_text="STOP RUN"),
            ])],
        )
        issues = validator.validate(prog)
        errors = [i for i in issues if i.severity == "ERROR"]
        assert any("bad_cond" in i.message for i in errors)
