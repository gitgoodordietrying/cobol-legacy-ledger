"""
dependencies -- FastAPI dependency injection for shared service instances.

This module provides the Depends()-compatible factory functions that FastAPI
routes use to obtain bridges, coordinators, verifiers, and auth contexts.
All heavy objects are lazily initialized as singletons -- the first request
that needs a COBOLBridge for BANK_A creates it; subsequent requests reuse it.

Why singletons (not per-request):
    COBOLBridge opens a SQLite connection and loads account data from DAT files.
    Creating one per request would be wasteful and slow. Instead, we cache
    bridges in a module-level dict keyed by node name. The SettlementCoordinator
    and CrossNodeVerifier are similarly cached as module-level singletons.

Auth model:
    Demo-grade header-based authentication. The X-User and X-Role headers are
    read from each request and mapped to an AuthContext. If X-Role is missing
    or invalid, the request is treated as VIEWER (least-privilege default).
    This is intentionally insecure -- production would use JWT or OAuth2 --
    but it lets students test RBAC behavior with curl by simply changing headers.

Thread safety:
    FastAPI runs route handlers in a thread pool (for sync routes). The singleton
    dicts are not thread-safe, but this is acceptable for a demo/teaching system.
    Production would use dependency injection with request-scoped sessions.

Dependencies:
    fastapi, python.auth, python.bridge, python.settlement, python.cross_verify
"""

import os
from typing import Dict
from fastapi import Header, HTTPException

from python.auth import AuthContext, Role, get_auth_context
from python.bridge import COBOLBridge
from python.settlement import SettlementCoordinator
from python.cross_verify import CrossNodeVerifier


# ── Constants ─────────────────────────────────────────────────────
# The 6-node architecture is fixed: 5 banks + 1 clearing house.
VALID_NODES = {"BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E", "CLEARING"}
DATA_DIR = os.environ.get("DATA_DIR", "COBOL-BANKING/data")  # Override for tests

# ── Singleton State ───────────────────────────────────────────────
# Lazily initialized on first access. Cleared by test fixtures.
_bridges: Dict[str, COBOLBridge] = {}
_coordinator: SettlementCoordinator = None
_verifier: CrossNodeVerifier = None


# ── Auth Dependency ───────────────────────────────────────────────
# Extracts RBAC context from X-User/X-Role request headers.
# Default: viewer role (least-privilege) if headers are missing.

def get_auth(
    x_user: str = Header(default="viewer"),
    x_role: str = Header(default="viewer"),
) -> AuthContext:
    """Extract auth context from X-User and X-Role request headers.

    If x_role is not a valid Role enum value, falls back to VIEWER.
    If x_user matches a DEMO_USERS entry, returns the pre-built context
    (which may override the provided role).
    """
    try:
        role = Role(x_role.lower())  # Normalize to lowercase before enum lookup
    except ValueError:
        role = Role.VIEWER           # Unknown role → least privilege
    return get_auth_context(x_user, role)


# ── Bridge / Coordinator / Verifier ──────────────────────────────
# Lazy singleton factories. Each returns an existing instance or creates one.

def get_bridge(node: str) -> COBOLBridge:
    """Get or create a COBOLBridge for the given node.

    Raises HTTPException 404 if the node name is not in the 6-node set.
    Bridges are cached in _bridges dict for reuse across requests.
    """
    if node not in VALID_NODES:
        raise HTTPException(status_code=404, detail=f"Unknown node: {node}")
    if node not in _bridges:
        _bridges[node] = COBOLBridge(node, data_dir=DATA_DIR)
    return _bridges[node]


def get_coordinator() -> SettlementCoordinator:
    """Get singleton SettlementCoordinator.

    Creates bridges for all 5 banks + clearing house on first call.
    """
    global _coordinator
    if _coordinator is None:
        _coordinator = SettlementCoordinator(data_dir=DATA_DIR)
    return _coordinator


def get_verifier() -> CrossNodeVerifier:
    """Get singleton CrossNodeVerifier.

    Creates bridges for all 6 nodes and runs 3-layer verification.
    """
    global _verifier
    if _verifier is None:
        _verifier = CrossNodeVerifier(data_dir=DATA_DIR)
    return _verifier


def validate_node(node: str) -> str:
    """Validate node name, raise 404 if invalid.

    Convenience function for routes that receive node as a path parameter
    and need early validation before calling get_bridge().
    """
    if node not in VALID_NODES:
        raise HTTPException(status_code=404, detail=f"Unknown node: {node}")
    return node
