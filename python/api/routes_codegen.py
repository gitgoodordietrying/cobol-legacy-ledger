"""
routes_codegen -- REST endpoints for COBOL code generation pipeline.

Four stateless endpoints that wrap the cobol_codegen package: parse source into
an AST summary, generate source from templates, edit source via AST operations,
and validate source against project conventions.

Endpoint surface:
    POST /api/codegen/parse     — Parse COBOL source → AST summary
    POST /api/codegen/generate  — Template → COBOL source
    POST /api/codegen/edit      — Source + operation → modified source
    POST /api/codegen/validate  — Source → validation issues

Stateless-per-request design:
    Each request creates fresh Parser/Generator/Editor/Validator instances.
    There's no shared state between requests -- the codegen pipeline is pure
    functional (input → output). This keeps the endpoints simple and testable.

Error mapping:
    - Missing input → 400 (neither source_text nor file_path provided)
    - File not found → 404 (file_path doesn't exist on disk)
    - Unknown template/operation → 400 with available options listed
    - Invalid params → 400 with the underlying TypeError/ValueError message

Dependencies:
    fastapi, python.api.models, python.cobol_codegen
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from python.api.models import (
    CodegenParseRequest, CodegenParseResponse,
    CodegenGenerateRequest, CodegenGenerateResponse,
    CodegenEditRequest, CodegenEditResponse,
    CodegenValidateRequest, CodegenValidateResponse, ValidationIssueResponse,
)
from python.cobol_codegen import (
    COBOLParser, COBOLGenerator, COBOLEditor, COBOLValidator,
    crud_program, report_program, batch_program, copybook_record,
)

router = APIRouter(prefix="/api/codegen", tags=["codegen"])


# ── Path Safety ──────────────────────────────────────────────────
# Restrict file_path inputs to known COBOL source directories.
# Prevents path traversal attacks (e.g., "../../../../etc/passwd").

_ALLOWED_COBOL_DIRS = [
    Path("COBOL-BANKING/src"),
    Path("COBOL-BANKING/copybooks"),
    Path("COBOL-BANKING/payroll/src"),
    Path("COBOL-BANKING/payroll/copybooks"),
]


def _validate_cobol_path(file_path: str) -> Path:
    """Resolve file_path and verify it falls within allowed COBOL directories.

    Raises HTTPException 403 if the resolved path escapes the allowed
    source directories. This prevents directory traversal via crafted
    file_path values like '../../../etc/passwd'.
    """
    resolved = Path(file_path).resolve()
    for allowed in _ALLOWED_COBOL_DIRS:
        allowed_resolved = allowed.resolve()
        try:
            resolved.relative_to(allowed_resolved)
            return resolved
        except ValueError:
            continue
    raise HTTPException(
        status_code=403,
        detail="File path not in allowed COBOL source directories",
    )


# ── Parse ─────────────────────────────────────────────────────────
# Convert COBOL source text or file into an AST summary.

@router.post("/parse", response_model=CodegenParseResponse)
def parse_cobol(req: CodegenParseRequest):
    """Parse a COBOL source file or text into an AST summary.

    Accepts either source_text (inline) or file_path (on-disk). Returns the
    program ID, paragraph names, file declarations, copybook references, and
    working-storage field count.
    """
    parser = COBOLParser()
    if req.source_text:
        program = parser.parse_text(req.source_text)
    elif req.file_path:
        safe_path = _validate_cobol_path(req.file_path)
        try:
            program = parser.parse_file(str(safe_path))
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"File not found: {req.file_path}")
    else:
        raise HTTPException(status_code=400, detail="Provide either source_text or file_path")

    return CodegenParseResponse(
        program_id=program.metadata.program_id,
        author=program.metadata.author,
        paragraphs=[p.name for p in program.paragraphs],
        files=[f.logical_name for f in program.files],
        copybooks=program.copybooks,
        working_storage_fields=len(program.working_storage),
    )


# ── Generate ──────────────────────────────────────────────────────
# Create COBOL source from a named template with parameters.

@router.post("/generate", response_model=CodegenGenerateResponse)
def generate_cobol(req: CodegenGenerateRequest):
    """Generate COBOL source from a template.

    1. Look up the template factory (crud, report, batch, or copybook)
    2. For copybook: call copybook_record() then generator.generate_copybook()
    3. For programs: call the factory function then generator.generate()
    4. Return the source text with line count
    """
    generator = COBOLGenerator()

    # Template factory map — each creates a COBOLProgram AST
    template_map = {
        "crud": crud_program,       # Full CRUD program with file I/O
        "report": report_program,   # Read-only reporting program
        "batch": batch_program,     # Batch processing with pipe-delimited input
    }

    # Copybook is special — it generates data items, not a full program
    if req.template == "copybook":
        fields = req.params.get("fields", [])
        record_name = req.params.get("record_name")
        items = copybook_record(req.name, fields, record_name=record_name)
        source = generator.generate_copybook(req.name, items)
        return CodegenGenerateResponse(
            source=source,
            program_id=req.name,
            line_count=source.count("\n") + 1,
        )

    factory = template_map.get(req.template)
    if not factory:
        raise HTTPException(status_code=400, detail=f"Unknown template: {req.template}. Use: crud, report, batch, copybook")

    try:
        program = factory(req.name, **req.params)
    except TypeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid params for {req.template}: {e}")

    source = generator.generate(program)
    return CodegenGenerateResponse(
        source=source,
        program_id=program.metadata.program_id,
        line_count=source.count("\n") + 1,
    )


# ── Edit ──────────────────────────────────────────────────────────
# Apply an AST operation to existing COBOL source.

@router.post("/edit", response_model=CodegenEditResponse)
def edit_cobol(req: CodegenEditRequest):
    """Edit COBOL source via AST operations.

    1. Parse the source text into a COBOLProgram AST
    2. Look up the operation function in the editor
    3. Apply the operation with provided params
    4. Re-generate source from the modified AST
    """
    parser = COBOLParser()
    generator = COBOLGenerator()
    editor = COBOLEditor()

    program = parser.parse_text(req.source_text)

    # Operation dispatch — maps operation name to COBOLEditor method
    # Cross-ref: tool_executor.py uses the same operation names for LLM tools
    operations = {
        "add_field": editor.add_field,
        "remove_field": editor.remove_field,
        "add_paragraph": editor.add_paragraph,
        "rename_paragraph": editor.rename_paragraph,
        "add_operation": editor.add_operation,
        "add_88_condition": editor.add_88_condition,
        "add_copybook_ref": editor.add_copybook_ref,
        "update_pic": editor.update_pic,
    }

    op_func = operations.get(req.operation)
    if not op_func:
        raise HTTPException(status_code=400, detail=f"Unknown operation: {req.operation}. Use: {', '.join(operations.keys())}")

    try:
        message = op_func(program, **req.params)
    except (TypeError, ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"Edit failed: {e}")

    source = generator.generate(program)
    return CodegenEditResponse(
        source=source,
        message=message,
        line_count=source.count("\n") + 1,
    )


# ── Validate ──────────────────────────────────────────────────────
# Check COBOL source against project conventions.

@router.post("/validate", response_model=CodegenValidateResponse)
def validate_cobol(req: CodegenValidateRequest):
    """Validate COBOL source against project conventions.

    Returns a list of issues (ERROR or WARNING severity) and summary counts.
    A source is considered valid if it has zero ERROR-severity issues.
    """
    parser = COBOLParser()
    validator = COBOLValidator()

    if req.source_text:
        program = parser.parse_text(req.source_text)
    elif req.file_path:
        safe_path = _validate_cobol_path(req.file_path)
        try:
            program = parser.parse_file(str(safe_path))
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"File not found: {req.file_path}")
    else:
        raise HTTPException(status_code=400, detail="Provide either source_text or file_path")

    issues = validator.validate(program)
    errors = [i for i in issues if i.severity == "ERROR"]
    warnings = [i for i in issues if i.severity == "WARNING"]

    return CodegenValidateResponse(
        valid=len(errors) == 0,
        issues=[
            ValidationIssueResponse(
                severity=i.severity,
                message=i.message,
                location=i.location,
            )
            for i in issues
        ],
        error_count=len(errors),
        warning_count=len(warnings),
    )
