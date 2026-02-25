"""
Tests for auth.py -- Role-Based Access Control (RBAC).

Test strategy:
    Validates the permission matrix for each of the 4 roles (ADMIN, AUDITOR,
    OPERATOR, VIEWER). Tests verify both positive access (role CAN do X) and
    negative access (role CANNOT do Y). Also tests the AuthContext helper
    methods and the demo user registry.

RBAC CONCEPT:
    Role-Based Access Control assigns permissions to roles rather than users.
    A user inherits all permissions of their assigned role. This simplifies
    access management: instead of granting 20 permissions to each of 100
    users, you define 4 roles and assign users to roles.
"""

import pytest
from ..auth import Role, AuthContext, PERMISSIONS, DEMO_USERS, get_auth_context


# ── Permission Boundaries ─────────────────────────────────────────

def test_admin_has_all_permissions():
    """Test that ADMIN role has the broadest permission set."""
    admin = AuthContext("test-admin", Role.ADMIN)
    assert admin.has_permission("accounts.create")
    assert admin.has_permission("transactions.process")
    assert admin.has_permission("chain.verify")
    assert admin.has_permission("chain.tamper-detect")
    assert admin.has_permission("node.manage")
    assert admin.has_permission("cobol.compile")


def test_auditor_read_only_plus_chain():
    """Test that AUDITOR has read + chain verification but not write."""
    auditor = AuthContext("test-auditor", Role.AUDITOR)
    # Can read and verify
    assert auditor.has_permission("accounts.read")
    assert auditor.has_permission("chain.verify")
    assert auditor.has_permission("chain.tamper-detect")
    assert auditor.has_permission("batch.audit")
    # Cannot write or process
    assert not auditor.has_permission("accounts.create")
    assert not auditor.has_permission("transactions.process")
    assert not auditor.has_permission("node.manage")


def test_operator_can_transact_not_verify():
    """Test that OPERATOR can process transactions but not verify chains."""
    operator = AuthContext("test-operator", Role.OPERATOR)
    assert operator.has_permission("transactions.process")
    assert operator.has_permission("accounts.read")
    assert operator.has_permission("chain.view")
    # Cannot verify or detect tampering
    assert not operator.has_permission("chain.verify")
    assert not operator.has_permission("chain.tamper-detect")
    assert not operator.has_permission("accounts.create")


def test_viewer_read_only():
    """Test that VIEWER has the most restricted permission set."""
    viewer = AuthContext("test-viewer", Role.VIEWER)
    assert viewer.has_permission("accounts.read")
    assert viewer.has_permission("transactions.read")
    assert viewer.has_permission("chain.view")
    # Cannot do anything else
    assert not viewer.has_permission("transactions.process")
    assert not viewer.has_permission("chain.verify")
    assert not viewer.has_permission("accounts.create")
    assert not viewer.has_permission("node.manage")


# ── require_permission ────────────────────────────────────────────

def test_require_permission_passes_for_allowed():
    """Test that require_permission does NOT raise when permission exists."""
    admin = AuthContext("admin", Role.ADMIN)
    # Should not raise
    admin.require_permission("accounts.create")
    admin.require_permission("node.manage")


def test_require_permission_raises_for_unauthorized():
    """Test that require_permission raises PermissionError when unauthorized."""
    viewer = AuthContext("viewer", Role.VIEWER)
    with pytest.raises(PermissionError) as exc_info:
        viewer.require_permission("transactions.process")
    assert "viewer" in str(exc_info.value).lower()
    assert "transactions.process" in str(exc_info.value)


def test_require_permission_error_message_includes_role():
    """Test that PermissionError message identifies the user and role."""
    operator = AuthContext("bob", Role.OPERATOR)
    with pytest.raises(PermissionError) as exc_info:
        operator.require_permission("node.manage")
    assert "bob" in str(exc_info.value)
    assert "operator" in str(exc_info.value)


# ── can_access_node ──────────────────────────────────────────────

def test_admin_can_access_all_nodes():
    """Test that admin can access any node."""
    admin = AuthContext("admin", Role.ADMIN)
    assert admin.can_access_node("BANK_A") is True
    assert admin.can_access_node("CLEARING") is True


def test_viewer_can_access_all_nodes():
    """Test that even viewer can access nodes (Phase 1: no per-node ACLs)."""
    viewer = AuthContext("viewer", Role.VIEWER)
    assert viewer.can_access_node("BANK_A") is True
    assert viewer.can_access_node("BANK_E") is True


# ── Demo Users ───────────────────────────────────────────────────

def test_demo_users_exist():
    """Test that all 4 demo users are registered."""
    assert "admin" in DEMO_USERS
    assert "auditor" in DEMO_USERS
    assert "operator" in DEMO_USERS
    assert "viewer" in DEMO_USERS


def test_demo_users_correct_roles():
    """Test that demo users have their expected roles."""
    assert DEMO_USERS["admin"].role == Role.ADMIN
    assert DEMO_USERS["auditor"].role == Role.AUDITOR
    assert DEMO_USERS["operator"].role == Role.OPERATOR
    assert DEMO_USERS["viewer"].role == Role.VIEWER


# ── get_auth_context ─────────────────────────────────────────────

def test_get_auth_context_returns_demo_user():
    """Test that known demo user IDs return pre-configured contexts."""
    ctx = get_auth_context("admin")
    assert ctx.role == Role.ADMIN
    assert ctx.user_id == "admin"


def test_get_auth_context_unknown_user_defaults_to_viewer():
    """Test that unknown users default to VIEWER role."""
    ctx = get_auth_context("stranger")
    assert ctx.role == Role.VIEWER


def test_get_auth_context_custom_role():
    """Test creating a context with a specific role for unknown users."""
    ctx = get_auth_context("custom-user", Role.OPERATOR)
    assert ctx.role == Role.OPERATOR
    assert ctx.user_id == "custom-user"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
