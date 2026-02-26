"""
auth -- Role-based access control (RBAC) for cobol-legacy-ledger.

This module implements a 4-role permission model that gates access to all
banking, chain, and codegen operations. The same permission matrix is enforced
by three layers: the CLI (cli.py), the REST API (routes_banking.py), and the
LLM tool executor (tool_executor.py). A VIEWER cannot process transactions
regardless of whether they use the CLI, hit the API, or chat with the LLM.

Why 4 roles (not 2 or 10):
    The role set mirrors real banking access tiers: ADMIN (full control),
    AUDITOR (read + verify — the external auditor pattern), OPERATOR (can
    transact but cannot tamper-detect — separation of duties), and VIEWER
    (read-only — the trainee or dashboard user). More roles would add
    complexity without teaching new concepts; fewer would lose the
    separation-of-duties lesson.

Permission model:
    Each role maps to a set of permission strings (e.g., "accounts.read",
    "transactions.process", "chain.verify"). Operations check permissions
    via AuthContext.has_permission() or AuthContext.require_permission().
    The permission strings are hierarchical by convention (domain.action)
    but not by implementation — each is a flat string in a set.

Demo-only caveat:
    This module provides demo-grade auth for teaching. There is no password
    checking, token validation, or session management. The DEMO_USERS dict
    provides built-in accounts that the API layer's X-User/X-Role headers
    map to directly. Production would replace this with JWT or OAuth2.

Dependencies:
    None (standard library only)
"""

from enum import Enum
from typing import Set, Dict, Optional


# ── Role Definitions ──────────────────────────────────────────────
# Four access tiers, matching real banking separation of duties.

class Role(Enum):
    """System roles with increasing access tiers.

    Each role maps to a permission set in the PERMISSIONS dict below.
    Roles are stored as lowercase strings for JSON serialization.
    """
    ADMIN = "admin"           # Full access — system administrator
    AUDITOR = "auditor"       # Read + verify — external auditor pattern
    OPERATOR = "operator"     # Can transact — bank teller / operations staff
    VIEWER = "viewer"         # Read-only — trainee, dashboard, monitoring


# ── Permission Matrix ─────────────────────────────────────────────
# Maps each role to its set of allowed operations. Permission strings
# follow domain.action convention (e.g., "accounts.read").

PERMISSIONS: Dict[Role, Set[str]] = {
    Role.ADMIN: {
        # Account operations
        "accounts.create", "accounts.read", "accounts.update", "accounts.close",
        # Transaction operations
        "transactions.process",    # CLI: transact, transfer, settle
        "transactions.read",       # CLI: list transactions
        "transactions.batch",      # CLI: batch processing
        # Chain operations
        "chain.verify",            # CLI: verify (recompute hashes)
        "chain.view",              # CLI: chain (display entries)
        "chain.tamper-detect",     # CLI: tamper-demo
        # Reporting
        "batch.read",              # CLI: batch results
        "batch.audit",             # CLI: audit trail
        # COBOL operations
        "cobol.read",              # LLM: parse, generate, edit, validate
        "cobol.compile",           # scripts: build.sh
        # Node management
        "node.manage",             # scripts: seed.sh
        "node.configure",          # Environment configuration
    },
    Role.AUDITOR: {
        # Read accounts — needed to verify balances
        "accounts.read",
        # Read transactions — needed to trace settlements
        "transactions.read",
        # Full chain verification and audit — the auditor's primary job
        "chain.verify", "chain.view", "chain.tamper-detect",
        # Read batch results
        "batch.read", "batch.audit",
        # Read COBOL source — for code review
        "cobol.read",
    },
    Role.OPERATOR: {
        # Read accounts — needed to verify balance before transaction
        "accounts.read",
        # Process transactions — the operator's primary job
        "transactions.process", "transactions.read",
        # View chain — but cannot verify/tamper-detect (separation of duties)
        "chain.view",
        # Read batch results
        "batch.read",
    },
    Role.VIEWER: {
        # Read-only — cannot modify anything
        "accounts.read",
        "transactions.read",
        "chain.view",
        "batch.read",
    },
}


# ── Auth Context ──────────────────────────────────────────────────
# Holds a user's identity and role, provides permission checking.

class AuthContext:
    """Authentication context for a user or API client.

    Created per-request (API) or per-session (CLI/LLM). Holds identity,
    role, and the resolved permission set. All permission checks go through
    this object — no direct access to the PERMISSIONS dict.
    """

    def __init__(self, user_id: str, role: Role, api_key: Optional[str] = None):
        """Initialize auth context.

        :param user_id: Unique identifier (username, service name, etc.)
        :param role: User's role (determines permissions via PERMISSIONS dict)
        :param api_key: Optional API key (reserved for service-to-service auth)
        """
        self.user_id = user_id
        self.role = role
        self.api_key = api_key
        self.permissions = PERMISSIONS.get(role, set())  # Resolve once at init

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions

    def require_permission(self, permission: str) -> None:
        """Raise PermissionError if user lacks permission.

        Used by route handlers and the ToolExecutor to enforce RBAC.
        The error message includes role and missing permission for debugging.
        """
        if not self.has_permission(permission):
            raise PermissionError(
                f"User {self.user_id} (role: {self.role.value}) lacks permission: {permission}"
            )

    def can_access_node(self, node: str) -> bool:
        """Check if user can access a specific node.

        Currently all authenticated users can access all nodes. A future
        enhancement could restrict operators to their assigned bank
        (e.g., BANK_A operators can only transact on BANK_A).
        """
        return True

    def __repr__(self) -> str:
        return f"AuthContext(user={self.user_id}, role={self.role.value})"


# ── Demo Accounts ─────────────────────────────────────────────────
# Pre-built auth contexts for demo and testing. The API layer maps
# X-User header values to these accounts via get_auth_context().

DEMO_USERS: Dict[str, AuthContext] = {
    "admin": AuthContext("admin", Role.ADMIN),
    "auditor": AuthContext("auditor", Role.AUDITOR),
    "operator": AuthContext("operator", Role.OPERATOR),
    "viewer": AuthContext("viewer", Role.VIEWER),
}


# ── Factory ───────────────────────────────────────────────────────
# Creates or retrieves auth contexts. Demo users take priority.

def get_auth_context(user_id: str, role: Optional[Role] = None) -> AuthContext:
    """Get or create an auth context for a user.

    If user_id matches a DEMO_USERS entry, returns the pre-built context
    (ignoring the role parameter — demo accounts have fixed roles).
    Otherwise, creates a new context with the given role (default: VIEWER).
    """
    if user_id in DEMO_USERS:
        return DEMO_USERS[user_id]  # Demo accounts override role parameter

    # Default to VIEWER if role not specified — least privilege
    if role is None:
        role = Role.VIEWER

    return AuthContext(user_id, role)
