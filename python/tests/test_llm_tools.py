"""
Tests for LLM tool definitions and RBAC-based role filtering.

Test strategy:
    Tests verify the TOOLS list structure and the get_tools_for_role() filtering
    function. No fixtures are needed because tool definitions are pure data
    (plain dicts with no external dependencies or state).

Test groups:
    - ToolDefinitions: structural validation (required fields, unique names, schemas)
    - RoleFiltering: RBAC-based tool visibility per role (admin, viewer, auditor, operator)

Fixture isolation:
    None required — tool definitions are module-level constants that are never
    mutated. Each test reads the same immutable TOOLS list.

Naming convention:
    test_{aspect}_{assertion} — e.g., test_all_tools_have_required_fields
"""

import pytest
from python.auth import Role
from python.llm.tools import TOOLS, get_tools_for_role, get_tool_definition


# ── Tool Definitions ──────────────────────────────────────────────
# Structural validation: every tool must have the required keys and valid schemas.

class TestToolDefinitions:
    """Verify all tool definitions have required fields and valid schemas."""

    def test_all_tools_have_required_fields(self):
        """Every tool has name, description, required_permission, and input_schema."""
        required = {"name", "description", "required_permission", "input_schema"}
        for tool in TOOLS:
            assert required.issubset(tool.keys()), f"Tool {tool.get('name', '?')} missing fields"

    def test_all_tools_have_unique_names(self):
        """No duplicate tool names in the TOOLS list."""
        names = [t["name"] for t in TOOLS]
        assert len(names) == len(set(names))

    def test_all_input_schemas_are_objects(self):
        """Every input_schema has type 'object' (JSON Schema convention)."""
        for tool in TOOLS:
            assert tool["input_schema"]["type"] == "object"

    def test_tool_count(self):
        """Exactly 12 tools defined (8 banking + 4 codegen)."""
        assert len(TOOLS) == 12

    def test_get_tool_definition_found(self):
        """get_tool_definition returns the tool dict for a known name."""
        tool = get_tool_definition("list_accounts")
        assert tool is not None
        assert tool["name"] == "list_accounts"

    def test_get_tool_definition_not_found(self):
        """get_tool_definition returns None for unknown tool name."""
        assert get_tool_definition("nonexistent") is None


# ── Role Filtering ────────────────────────────────────────────────
# Verify that get_tools_for_role returns the correct subset per role.

class TestRoleFiltering:
    """Verify get_tools_for_role returns correct tools per role."""

    def test_admin_sees_all_tools(self):
        """Admin role has all permissions, sees all 12 tools."""
        tools = get_tools_for_role(Role.ADMIN)
        assert len(tools) == 12

    def test_viewer_sees_read_only_tools(self):
        """Viewer sees accounts.read, transactions.read, chain.view, batch.read tools only."""
        tools = get_tools_for_role(Role.VIEWER)
        names = {t["name"] for t in tools}
        # VIEWER has: accounts.read, transactions.read, chain.view, batch.read
        assert "list_accounts" in names
        assert "get_account" in names
        assert "view_chain" in names
        # VIEWER should NOT see write tools
        assert "process_transaction" not in names
        assert "transfer" not in names
        assert "verify_chain" not in names

    def test_auditor_sees_verification_tools(self):
        """Auditor sees chain.verify tools and COBOL read tools."""
        tools = get_tools_for_role(Role.AUDITOR)
        names = {t["name"] for t in tools}
        assert "verify_chain" in names
        assert "verify_all_nodes" in names
        assert "parse_cobol" in names  # cobol.read permission
        assert "process_transaction" not in names

    def test_operator_sees_transaction_tools(self):
        """Operator sees transaction tools but not verification tools."""
        tools = get_tools_for_role(Role.OPERATOR)
        names = {t["name"] for t in tools}
        assert "process_transaction" in names
        assert "transfer" in names
        assert "list_accounts" in names
        # Operator cannot verify chains (separation of duties)
        assert "verify_chain" not in names
        assert "verify_all_nodes" not in names

    def test_filtered_tools_exclude_internal_fields(self):
        """Filtered tools strip required_permission (internal RBAC field)."""
        tools = get_tools_for_role(Role.ADMIN)
        for t in tools:
            assert "required_permission" not in t  # Stripped before sending to LLM
            assert "name" in t
            assert "description" in t
            assert "input_schema" in t
