"""
Authentication and authorization layer for cobol-legacy-ledger.
Implements role-based access control with per-role permission sets.
"""

from enum import Enum
from typing import Set, Dict, Optional


class Role(Enum):
    """System roles with access tiers."""
    ADMIN = "admin"           # Full access
    AUDITOR = "auditor"       # Read-only, chain verification
    OPERATOR = "operator"     # Can execute transactions
    VIEWER = "viewer"         # Read-only, basic queries


# Permission matrix: Role → Set of allowed operations
PERMISSIONS: Dict[Role, Set[str]] = {
    Role.ADMIN: {
        # Account operations
        "accounts.create", "accounts.read", "accounts.update", "accounts.close",
        # Transaction operations
        "transactions.process", "transactions.read", "transactions.batch",
        # Chain operations
        "chain.verify", "chain.view", "chain.tamper-detect",
        # Reporting
        "batch.read", "batch.audit",
        # COBOL operations
        "cobol.read", "cobol.compile",
        # Node management
        "node.manage", "node.configure",
    },
    Role.AUDITOR: {
        # Read accounts
        "accounts.read",
        # Read transactions
        "transactions.read",
        # Full chain verification and audit
        "chain.verify", "chain.view", "chain.tamper-detect",
        # Read batch results
        "batch.read", "batch.audit",
        # Read COBOL source
        "cobol.read",
    },
    Role.OPERATOR: {
        # Read accounts (needed to verify balance before transaction)
        "accounts.read",
        # Process transactions
        "transactions.process", "transactions.read",
        # View chain (but cannot verify/tamper-detect)
        "chain.view",
        # Read batch results
        "batch.read",
    },
    Role.VIEWER: {
        # Read-only
        "accounts.read", "transactions.read", "chain.view", "batch.read",
    },
}


class AuthContext:
    """
    Authentication context for a user/API client.
    Holds identity, role, and provides permission checking.
    """

    def __init__(self, user_id: str, role: Role, api_key: Optional[str] = None):
        """
        Initialize auth context.

        :param user_id: Unique identifier (username, service name, etc.)
        :param role: User's role (determines permissions)
        :param api_key: Optional API key (for service-to-service auth)
        """
        self.user_id = user_id
        self.role = role
        self.api_key = api_key
        self.permissions = PERMISSIONS.get(role, set())

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions

    def require_permission(self, permission: str) -> None:
        """Raise exception if user lacks permission."""
        if not self.has_permission(permission):
            raise PermissionError(
                f"User {self.user_id} (role: {self.role.value}) lacks permission: {permission}"
            )

    def can_access_node(self, node: str) -> bool:
        """
        Check if user can access a specific node.
        For Phase 1, all authenticated users can read all nodes.
        Phase 2 may add per-node ACLs.
        """
        # In Phase 1, authentication is implicit — if you have a context, you're authorized
        # Phase 2 could restrict by node: e.g., only BANK_A operators can transact on BANK_A
        return True

    def __repr__(self) -> str:
        return f"AuthContext(user={self.user_id}, role={self.role.value})"


# Built-in service accounts for demo and tests
DEMO_USERS: Dict[str, AuthContext] = {
    "admin": AuthContext("admin", Role.ADMIN),
    "auditor": AuthContext("auditor", Role.AUDITOR),
    "operator": AuthContext("operator", Role.OPERATOR),
    "viewer": AuthContext("viewer", Role.VIEWER),
}


def get_auth_context(user_id: str, role: Optional[Role] = None) -> AuthContext:
    """
    Get or create an auth context for a user.
    If user_id matches a demo account, return that. Otherwise create a new context.
    """
    if user_id in DEMO_USERS:
        return DEMO_USERS[user_id]

    # Default to VIEWER if role not specified
    if role is None:
        role = Role.VIEWER

    return AuthContext(user_id, role)
