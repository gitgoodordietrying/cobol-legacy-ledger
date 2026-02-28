"""
Tests for COBOL analysis tool dispatch via ToolExecutor.

Verifies that the 5 analysis tools (analyze_call_graph, trace_execution,
analyze_data_flow, detect_dead_code, explain_cobol_pattern) are correctly
wired through the RBAC → validation → dispatch → audit pipeline.
"""

import pytest
from python.auth import AuthContext, Role
from python.llm.tool_executor import ToolExecutor
from python.llm.tools import get_tool_definition, get_tools_for_role, TOOLS


# ── Fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def executor(tmp_path):
    return ToolExecutor(data_dir=str(tmp_path))


@pytest.fixture
def admin_auth():
    return AuthContext(user_id="test-admin", role=Role.ADMIN)


@pytest.fixture
def viewer_auth():
    return AuthContext(user_id="test-viewer", role=Role.VIEWER)


SAMPLE_COBOL = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SAMPLE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-X               PIC 9 VALUE 0.
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM DO-WORK
           STOP RUN.
       DO-WORK.
           MOVE 1 TO WS-X
           GO TO FINISH-UP.
       DEAD-PARA.
           DISPLAY "DEAD".
       FINISH-UP.
           DISPLAY WS-X.
"""


# ── Tool Definition Tests ────────────────────────────────────────

class TestToolDefinitions:
    """Verify the 5 analysis tools are defined correctly."""

    @pytest.mark.parametrize("name", [
        "analyze_call_graph", "trace_execution", "analyze_data_flow",
        "detect_dead_code", "explain_cobol_pattern",
    ])
    def test_tool_exists(self, name):
        defn = get_tool_definition(name)
        assert defn is not None, f"Tool {name} not found"
        assert defn["name"] == name

    @pytest.mark.parametrize("name", [
        "analyze_call_graph", "trace_execution", "analyze_data_flow",
        "detect_dead_code", "explain_cobol_pattern",
    ])
    def test_tool_has_required_fields(self, name):
        defn = get_tool_definition(name)
        assert "description" in defn
        assert "input_schema" in defn
        assert "required_permission" in defn

    def test_all_analysis_tools_require_cobol_read(self):
        for name in ["analyze_call_graph", "trace_execution", "analyze_data_flow",
                      "detect_dead_code", "explain_cobol_pattern"]:
            defn = get_tool_definition(name)
            assert defn["required_permission"] == "cobol.read"

    def test_tool_count(self):
        # 8 banking + 4 codegen + 5 analysis = 17
        assert len(TOOLS) == 17

    def test_admin_sees_analysis_tools(self):
        tools = get_tools_for_role(Role.ADMIN)
        names = {t["name"] for t in tools}
        assert "analyze_call_graph" in names
        assert "trace_execution" in names

    def test_viewer_no_analysis_tools(self):
        tools = get_tools_for_role(Role.VIEWER)
        names = {t["name"] for t in tools}
        assert "analyze_call_graph" not in names


# ── Dispatch Tests ───────────────────────────────────────────────

class TestAnalysisDispatch:
    """Test that analysis tools dispatch correctly through ToolExecutor."""

    def test_analyze_call_graph(self, executor, admin_auth):
        result = executor.execute(
            "analyze_call_graph",
            {"source_text": SAMPLE_COBOL},
            admin_auth,
        )
        assert "error" not in result or result.get("paragraphs")
        assert "paragraphs" in result
        assert "edges" in result

    def test_trace_execution(self, executor, admin_auth):
        result = executor.execute(
            "trace_execution",
            {"source_text": SAMPLE_COBOL, "entry_point": "MAIN-PARA"},
            admin_auth,
        )
        assert "execution_path" in result
        assert "steps" in result
        assert result["steps"] >= 1

    def test_analyze_data_flow_all(self, executor, admin_auth):
        result = executor.execute(
            "analyze_data_flow",
            {"source_text": SAMPLE_COBOL},
            admin_auth,
        )
        assert "paragraph_writes" in result or "paragraph_reads" in result

    def test_analyze_data_flow_single_field(self, executor, admin_auth):
        result = executor.execute(
            "analyze_data_flow",
            {"source_text": SAMPLE_COBOL, "field_name": "WS-X"},
            admin_auth,
        )
        assert "field" in result
        assert result["field"] == "WS-X"
        assert "accesses" in result

    def test_detect_dead_code(self, executor, admin_auth):
        result = executor.execute(
            "detect_dead_code",
            {"source_text": SAMPLE_COBOL},
            admin_auth,
        )
        assert "dead" in result
        assert "reachable" in result

    def test_explain_cobol_pattern_found(self, executor, admin_auth):
        result = executor.execute(
            "explain_cobol_pattern",
            {"pattern_name": "ALTER"},
            admin_auth,
        )
        assert "error" not in result
        assert "name" in result

    def test_explain_cobol_pattern_not_found(self, executor, admin_auth):
        result = executor.execute(
            "explain_cobol_pattern",
            {"pattern_name": "NONEXISTENT-XYZ"},
            admin_auth,
        )
        assert "error" in result
        assert "suggestions" in result


# ── RBAC Tests ───────────────────────────────────────────────────

class TestAnalysisRBAC:
    """Verify RBAC gating on analysis tools."""

    def test_viewer_denied(self, executor, viewer_auth):
        result = executor.execute(
            "analyze_call_graph",
            {"source_text": SAMPLE_COBOL},
            viewer_auth,
        )
        assert "error" in result
        assert result.get("permitted") is False

    def test_admin_permitted(self, executor, admin_auth):
        result = executor.execute(
            "analyze_call_graph",
            {"source_text": SAMPLE_COBOL},
            admin_auth,
        )
        assert result.get("permitted") is not False
