"""
create_app -- FastAPI application factory for cobol-legacy-ledger.

This module uses the factory pattern so that test suites can create isolated
app instances with overridden dependencies (e.g., temporary data directories,
mock providers). The single module-level `app = create_app()` at the bottom
is the default instance used by `uvicorn python.api.app:app`.

Configuration choices:
    CORS is fully permissive (allow_origins=["*"]) because this is a teaching
    demo, not a production deployment. Students run the API on localhost and
    hit it from browser-based tools or curl.

    The chat router is imported inside a try/except because it depends on the
    LLM layer (python.llm), which has optional dependencies (httpx, anthropic).
    If those aren't installed, the rest of the API still works -- students can
    explore banking and codegen endpoints without LLM support.

    The global PermissionError->403 handler converts RBAC denials from the auth
    module into proper HTTP 403 responses with a JSON body, keeping error
    handling consistent across all routes.

Static file mounts:
    /console/       -- Web dashboard SPA (glass morphism UI)
    /cobol-source/  -- Raw COBOL source files for the viewer panel

Dependencies:
    fastapi, python.api.routes_banking, python.api.routes_codegen,
    python.api.routes_health, python.api.routes_simulation,
    python.api.routes_chat (optional)
"""

import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # Load .env before any os.environ reads

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from python.api.routes_banking import router as banking_router
from python.api.routes_codegen import router as codegen_router
from python.api.routes_health import router as health_router
from python.api.routes_simulation import router as simulation_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    1. Instantiate FastAPI with OpenAPI metadata
    2. Add CORS middleware (permissive for demo use)
    3. Mount banking, codegen, health, and simulation routers
    4. Attempt to mount chat router (graceful skip if LLM deps missing)
    5. Mount static file directories (console UI, COBOL source)
    6. Register global PermissionError -> 403 exception handler

    Returns:
        Configured FastAPI instance ready for uvicorn.
    """
    app = FastAPI(
        title="COBOL Legacy Ledger API",
        description="REST API for the inter-bank settlement system — wraps COBOL banking, integrity chains, and LLM tool-use",
        version="6.1.0",
    )

    # ── Middleware ─────────────────────────────────────────────────
    # Permissive CORS for local development and classroom demos.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],       # Any origin — demo only
        allow_credentials=True,
        allow_methods=["*"],       # All HTTP methods
        allow_headers=["*"],       # All headers (including X-User, X-Role)
    )

    # ── Route Registration ────────────────────────────────────────
    # Each router is a self-contained module with its own prefix and tags.
    app.include_router(banking_router)
    app.include_router(codegen_router)
    app.include_router(health_router)
    app.include_router(simulation_router)

    # Payroll sidecar router (Layer 5 — legacy payroll integration).
    try:
        from python.api.routes_payroll import router as payroll_router
        app.include_router(payroll_router)
    except ImportError:
        pass  # Payroll bridge not available

    # COBOL analysis router (Layer 5 — static analysis tools).
    try:
        from python.api.routes_analysis import router as analysis_router
        app.include_router(analysis_router)
    except ImportError:
        pass  # Analysis module not available

    # Chat router depends on python.llm (optional httpx/anthropic packages).
    # If the LLM layer isn't importable, the API still serves banking and
    # codegen endpoints — graceful degradation for minimal installs.
    try:
        from python.api.routes_chat import router as chat_router
        app.include_router(chat_router)
    except ImportError:
        pass  # LLM dependencies not installed — chat endpoints unavailable

    # ── Root Redirect ─────────────────────────────────────────────
    # Redirect / to the web console for convenience.
    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse(url="/console/index.html")

    # ── Static File Mounts ────────────────────────────────────────
    # Mount the web console SPA and COBOL source files for the viewer.
    # These are checked at startup -- if directories don't exist yet
    # (e.g., during testing), the mounts are skipped gracefully.
    console_dir = Path(__file__).resolve().parent.parent.parent / "console"
    cobol_src_dir = Path(__file__).resolve().parent.parent.parent / "COBOL-BANKING" / "src"

    if console_dir.exists():
        app.mount("/console", StaticFiles(directory=str(console_dir), html=True), name="console")

    # Mount payroll sub-path BEFORE the parent /cobol-source mount.
    # FastAPI matches the first mount, so /cobol-source/payroll must be
    # registered first — otherwise requests go to COBOL-BANKING/src/payroll/
    # which doesn't exist.
    payroll_src_dir = Path(__file__).resolve().parent.parent.parent / "COBOL-BANKING" / "payroll" / "src"
    if payroll_src_dir.exists():
        app.mount("/cobol-source/payroll", StaticFiles(directory=str(payroll_src_dir)), name="cobol-source-payroll")

    if cobol_src_dir.exists():
        app.mount("/cobol-source", StaticFiles(directory=str(cobol_src_dir)), name="cobol-source")

    # Favicon redirect — serve the SVG from the console directory
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return RedirectResponse(url="/console/favicon.svg")

    # ── Exception Handlers ────────────────────────────────────────
    # AuthContext.require_permission() raises PermissionError on RBAC denial.
    # Convert to HTTP 403 with a JSON body so clients get structured errors.
    @app.exception_handler(PermissionError)
    async def permission_error_handler(request: Request, exc: PermissionError):
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    return app


app = create_app()
