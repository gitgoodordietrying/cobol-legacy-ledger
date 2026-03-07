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
from python.auth import Role, AuthContext
from python.llm.tools import TOOLS, get_tools_for_role, get_tool_definition
from python.llm.tool_executor import ToolExecutor, COBOL_FILES, PAYROLL_FILES, CLEAN_FILES


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
        """Exactly 20 tools defined (8 banking + 4 codegen + 8 analysis)."""
        assert len(TOOLS) == 20

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
        """Admin role has all permissions, sees all 20 tools."""
        tools = get_tools_for_role(Role.ADMIN)
        assert len(tools) == 20

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


# ── Compare Complexity Tool ──────────────────────────────────────
# Tests for the compare_complexity tool: whitelist, file reader, dispatch.

class TestCompareComplexity:
    """Verify compare_complexity tool definition, file reader, and dispatch."""

    def test_compare_complexity_tool_exists(self):
        """compare_complexity is in the TOOLS list with correct schema."""
        tool = get_tool_definition("compare_complexity")
        assert tool is not None
        assert tool["required_permission"] == "cobol.read"
        assert "file_a" in tool["input_schema"]["properties"]
        assert "file_b" in tool["input_schema"]["properties"]

    def test_cobol_files_whitelist_count(self):
        """Whitelist has 18 files: 8 payroll + 10 clean."""
        assert len(COBOL_FILES) == 18
        assert len(PAYROLL_FILES) == 8
        assert len(CLEAN_FILES) == 10

    def test_read_cobol_file_valid(self):
        """_read_cobol_file reads a valid file without error."""
        executor = ToolExecutor(force_mode_b=True)
        source = executor._read_cobol_file("TRANSACT.cob")
        assert "IDENTIFICATION DIVISION" in source

    def test_read_cobol_file_payroll(self):
        """_read_cobol_file reads payroll spaghetti files."""
        executor = ToolExecutor(force_mode_b=True)
        source = executor._read_cobol_file("PAYROLL.cob")
        assert "IDENTIFICATION DIVISION" in source

    def test_read_cobol_file_invalid(self):
        """_read_cobol_file rejects files not in the whitelist."""
        executor = ToolExecutor(force_mode_b=True)
        with pytest.raises(ValueError, match="Unknown COBOL file"):
            executor._read_cobol_file("../../etc/passwd")

    def test_compare_complexity_dispatch(self):
        """compare_complexity dispatch returns structured comparison."""
        executor = ToolExecutor(force_mode_b=True)
        auth = AuthContext(user_id="test", role=Role.ADMIN)
        result = executor.execute("compare_complexity", {
            "file_a": "PAYROLL.cob",
            "file_b": "TRANSACT.cob",
        }, auth)
        assert "error" not in result
        assert "file_a" in result
        assert "file_b" in result
        assert "delta" in result
        assert result["file_a"]["file"] == "PAYROLL.cob"
        assert result["file_b"]["file"] == "TRANSACT.cob"
        assert "total_score" in result["file_a"]
        assert "hotspots" in result["file_a"]
        assert "dead_code_count" in result["file_a"]
        assert "score_difference" in result["delta"]

    def test_compare_complexity_spaghetti_scores_higher(self):
        """Spaghetti PAYROLL.cob should have higher complexity than clean TRANSACT.cob."""
        executor = ToolExecutor(force_mode_b=True)
        auth = AuthContext(user_id="test", role=Role.ADMIN)
        result = executor.execute("compare_complexity", {
            "file_a": "PAYROLL.cob",
            "file_b": "TRANSACT.cob",
        }, auth)
        assert result["file_a"]["total_score"] > result["file_b"]["total_score"]
        assert result["delta"]["score_difference"] > 0
