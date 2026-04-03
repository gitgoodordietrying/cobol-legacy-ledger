"""
routes_mainframe -- Compile endpoint for the COBOL Mainframe Dashboard.

Provides a single endpoint that accepts COBOL source text, compiles it
using GnuCOBOL (cobc), and returns compiler output in a structured
response.  Falls back to validation-only mode when cobc is not installed.

Mode A (cobc available):
    Write source to a temp file, invoke cobc with -x flag, capture
    stdout/stderr/return_code, clean up the temp file, return result.

Mode B (cobc not available):
    Parse the source with COBOLParser, validate with COBOLValidator,
    return validation issues as a structured response.

Endpoint surface:
    POST /api/mainframe/compile  -- Compile or validate COBOL source

Security:
    - Max source size: 100KB (102400 bytes)
    - Compilation timeout: 10 seconds
    - Temp files cleaned in finally block
    - CRLF normalized to LF before write
    - No execution of compiled programs (compile only)
"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/mainframe", tags=["mainframe"])


# ── cobc detection (once at import time) ─────────────────────────

_COBC_PATH: Optional[str] = shutil.which("cobc")


# ── Request / Response Models ────────────────────────────────────

class CompileRequest(BaseModel):
    source_text: str = Field(..., description="COBOL source code to compile")
    format: str = Field("free", description="Source format: 'fixed' or 'free'")
    program_name: str = Field("STUDENT", description="Program name for temp file")
    dialect: str = Field("default", description="Dialect flag: default, ibm, mf, cobol2014")


class ValidationIssue(BaseModel):
    level: str
    message: str


class CompileResponse(BaseModel):
    success: bool
    return_code: int
    stdout: str = ""
    stderr: str = ""
    mode: str  # "compile" or "validate"
    validation: Optional[List[Dict[str, Any]]] = None


# ── Constants ────────────────────────────────────────────────────

MAX_SOURCE_BYTES = 102400   # 100 KB
COMPILE_TIMEOUT_S = 10


# ── Endpoint ─────────────────────────────────────────────────────

@router.post("/compile", response_model=CompileResponse)
def compile_source(req: CompileRequest) -> CompileResponse:
    """Compile COBOL source using cobc (Mode A) or validate (Mode B).

    Returns structured compilation result with stdout, stderr,
    return code, and mode indicator.
    """
    # ── Validation ──
    if not req.source_text or not req.source_text.strip():
        raise HTTPException(status_code=400, detail="No source code provided")

    if len(req.source_text.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail=f"Source too large (max {MAX_SOURCE_BYTES // 1024}KB)")

    # Normalize CRLF to LF (Windows compatibility)
    source = req.source_text.replace("\r\n", "\n")

    # ── Mode A: real compilation ──
    if _COBC_PATH:
        return _compile_with_cobc(source, req)

    # ── Mode B: validation-only fallback ──
    return _validate_only(source)


def _compile_with_cobc(source: str, req: CompileRequest) -> CompileResponse:
    """Mode A: compile with GnuCOBOL."""
    tmp_path = None
    try:
        # Write source to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".cob", prefix=f"{req.program_name}_",
            delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(source)
            tmp_path = tmp.name

        # Build cobc command
        fmt_flag = "-fixed" if req.format == "fixed" else "-free"
        cmd = [_COBC_PATH, "-x", fmt_flag]

        # Dialect flag
        if req.dialect and req.dialect != "default":
            cmd.extend(["-std", req.dialect])

        cmd.append(tmp_path)

        # Run compiler with timeout
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=COMPILE_TIMEOUT_S,
            cwd=tempfile.gettempdir(),
        )

        return CompileResponse(
            success=(result.returncode == 0),
            return_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            mode="compile",
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail=f"Compilation timed out after {COMPILE_TIMEOUT_S}s"
        )
    finally:
        # Always clean up temp file and any compiled binary
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
                # cobc -x creates an executable with the same name minus extension
                exe_path = Path(tmp_path).with_suffix("")
                exe_path.unlink(missing_ok=True)
                # On Windows, cobc may create a .exe
                exe_path_win = Path(tmp_path).with_suffix(".exe")
                exe_path_win.unlink(missing_ok=True)
            except OSError:
                pass


def _validate_only(source: str) -> CompileResponse:
    """Mode B: parse and validate without cobc."""
    try:
        from python.cobol_codegen import COBOLParser, COBOLValidator

        parser = COBOLParser()
        program = parser.parse_text(source)
        validator = COBOLValidator()
        issues = validator.validate(program)

        has_errors = any(i.level == "ERROR" for i in issues)

        return CompileResponse(
            success=not has_errors,
            return_code=1 if has_errors else 0,
            stdout="",
            stderr="cobc not available -- showing validation results",
            mode="validate",
            validation=[{"level": i.level, "message": i.message} for i in issues],
        )
    except Exception as e:
        return CompileResponse(
            success=False,
            return_code=99,
            stdout="",
            stderr=f"Validation failed: {str(e)}",
            mode="validate",
            validation=[],
        )
