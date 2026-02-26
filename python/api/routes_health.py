"""
routes_health -- Unauthenticated system health check endpoint.

A single GET /api/health endpoint that reports system status without requiring
authentication. This is intentionally unauthenticated so monitoring tools,
load balancers, and students can check system health without credentials.

Health logic:
    status = "healthy" if all 6 node data directories exist, else "degraded".
    This reflects whether seed.sh has been run, not whether COBOL is compiled
    (the system works in Mode B without COBOL binaries).

Provider checks:
    Ollama: HTTP GET to /api/tags with a 2-second timeout. Fast enough for
    health checks, short enough to not block if Ollama isn't running.

    Anthropic: Environment variable check only (ANTHROPIC_API_KEY). We don't
    make an API call because (a) it would cost money and (b) the key might
    have rate limits. Presence of the key is sufficient for health reporting.

Dependencies:
    fastapi, httpx (for Ollama check), python.api.models, python.api.dependencies
"""

import os
from fastapi import APIRouter
from python.api.models import HealthResponse
from python.api.dependencies import VALID_NODES, DATA_DIR

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    """System health: node availability, provider status, DB status.

    Unauthenticated by design — monitoring tools and students can call this
    without credentials to check if the system is running.
    """
    # ── Node Availability ─────────────────────────────────────────
    # Count data directories that exist (one per node, created by seed.sh).
    nodes_available = sum(
        1 for n in VALID_NODES
        if os.path.isdir(os.path.join(DATA_DIR, n))
    )

    # ── Ollama Check ──────────────────────────────────────────────
    # Quick HTTP probe with 2s timeout. Ollama runs locally on port 11434.
    ollama_available = False
    try:
        import httpx
        resp = httpx.get(
            os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434") + "/api/tags",
            timeout=2.0,  # Short timeout — don't block health checks
        )
        ollama_available = resp.status_code == 200
    except Exception:
        pass  # Ollama not running — that's fine, report it as unavailable

    # ── Anthropic Check ───────────────────────────────────────────
    # Env-var only — no API call (costs money, may be rate-limited).
    anthropic_configured = bool(os.environ.get("ANTHROPIC_API_KEY"))

    # ── Status Decision ───────────────────────────────────────────
    # "healthy" = all 6 nodes seeded, "degraded" = some missing.
    db_status = "ok" if nodes_available > 0 else "no_data"

    return HealthResponse(
        status="healthy" if nodes_available == 6 else "degraded",
        nodes_available=nodes_available,
        ollama_available=ollama_available,
        anthropic_configured=anthropic_configured,
        db_status=db_status,
        version="3.0.0",
    )
