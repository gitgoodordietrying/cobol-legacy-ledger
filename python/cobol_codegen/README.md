# COBOL Code Generation Package

AST-based COBOL code generation pipeline: parse → transform → emit. This package enables Python to read, parse, generate, and modify COBOL source code programmatically.

## Pipeline

```
COBOL Source Text
    │
    ▼
COBOLParser.parse_text()
    │
    ▼
COBOLProgram (AST)
    ├── metadata: ProgramMetadata (program_id, author, date)
    ├── working_storage: List[DataItem] (fields, 88-level conditions)
    ├── files: List[FileDeclaration] (SELECT/ASSIGN bindings)
    ├── paragraphs: List[Paragraph] (PROCEDURE DIVISION logic)
    └── copybooks: List[str] (COPY references)
    │
    ├── COBOLEditor.add_field() / .add_paragraph() / .update_pic() / ...
    │
    ▼
COBOLGenerator.generate()
    │
    ▼
Valid COBOL Source Text
```

## Module Reference

| Module | Purpose |
|--------|---------|
| `ast_nodes.py` | Data classes: COBOLProgram, DataItem, Paragraph, Statement, etc. |
| `parser.py` | Parse .cob/.cpy files into COBOLProgram AST nodes |
| `generator.py` | Emit valid COBOL source from COBOLProgram AST |
| `templates.py` | Factory functions: crud_program, report_program, batch_program, copybook_record |
| `editor.py` | High-level AST edit operations (add/remove fields, paragraphs) |
| `validator.py` | Convention checking against project standards |

## Template Catalog

| Template | Function | Output |
|----------|----------|--------|
| `crud` | `crud_program(name, ...)` | Full CRUD program with file I/O |
| `report` | `report_program(name, ...)` | Read-only reporting program |
| `batch` | `batch_program(name, ...)` | Batch processing with pipe-delimited input |
| `copybook` | `copybook_record(name, fields)` | Shared record definition (.cpy) |

## Validator Rules

| Rule | Severity | Description |
|------|----------|-------------|
| Missing PROGRAM-ID | ERROR | IDENTIFICATION DIVISION must have PROGRAM-ID |
| Missing STOP RUN | WARNING | PROCEDURE DIVISION should end with STOP RUN |
| Unnamed paragraphs | WARNING | All paragraphs should have descriptive names |
| PIC clause format | WARNING | PIC clauses should follow project conventions |
| Missing COPY | WARNING | Programs should use copybooks for shared records |

## Usage Examples

### Parse

```python
from python.cobol_codegen import COBOLParser

parser = COBOLParser()
program = parser.parse_file("COBOL-BANKING/src/ACCOUNTS.cob")
print(program.metadata.program_id)  # "ACCOUNTS"
print([p.name for p in program.paragraphs])  # ["MAIN-PARAGRAPH", ...]
```

### Generate

```python
from python.cobol_codegen import crud_program, COBOLGenerator

program = crud_program("CUSTOMER", record_name="CUSTREC")
source = COBOLGenerator().generate(program)
print(source)  # Valid COBOL source text
```

### Edit

```python
from python.cobol_codegen import COBOLParser, COBOLEditor, COBOLGenerator

parser = COBOLParser()
editor = COBOLEditor()
generator = COBOLGenerator()

program = parser.parse_text(source)
editor.add_paragraph(program, name="CLEANUP", statements=["CLOSE ACCOUNT-FILE"])
modified = generator.generate(program)
```

### Validate

```python
from python.cobol_codegen import COBOLParser, COBOLValidator

program = COBOLParser().parse_text(source)
issues = COBOLValidator().validate(program)
for issue in issues:
    print(f"[{issue.severity}] {issue.message}")
```
