"""
api -- FastAPI REST layer for cobol-legacy-ledger.

This package exposes the entire COBOL banking system, integrity verification,
codegen pipeline, and LLM tool-use interface as HTTP endpoints. It is the
topmost integration layer -- every request flows through FastAPI dependency
injection down to the existing bridge/settlement/codegen modules.

Why FastAPI (not Flask or Django):
    FastAPI was chosen for three reasons: (1) automatic OpenAPI/Swagger docs
    at /docs, which lets students explore the API interactively; (2) Pydantic
    request/response models that tie back to COBOL record formats with field-
    level validation; (3) native async support for the LLM chat endpoint,
    which calls external providers (Ollama/Anthropic) over HTTP.

Data flow:
    HTTP request → FastAPI route → Depends() injects auth + bridge/coordinator
    → route calls bridge/settlement/codegen method → result mapped to Pydantic
    response model → JSON response

Route modules:
    routes_banking.py  — Account CRUD, transactions, chain ops, settlement
    routes_codegen.py  — COBOL parse, generate, edit, validate
    routes_chat.py     — LLM conversation with tool-use resolution
    routes_health.py   — System status (node count, provider availability)

Auth model:
    Demo-grade header-based auth (X-User / X-Role headers). Four roles map
    to the same RBAC permission matrix used by the CLI and LLM layers.
    Production would replace this with JWT or OAuth2.

Dependencies:
    fastapi, pydantic, python.bridge, python.settlement, python.cross_verify,
    python.auth, python.cobol_codegen, python.llm
"""

__all__ = [
    'app',
    'dependencies',
    'models',
    'routes_banking',
    'routes_codegen',
    'routes_chat',
    'routes_health',
]
