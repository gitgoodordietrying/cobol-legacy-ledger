"""
Tests for the LLM tool executor -- RBAC gate, input validation, dispatch, audit logging.

Test strategy:
    All tests use a real COBOLBridge (Mode B) with temporary data directories
    and a real AuditLog with a temporary SQLite database. No mocking of the
    bridge or audit layer — these tests verify the full 4-layer pipeline:
    RBAC gate → input validation → dispatch → audit.

Test groups:
    - RBACGate: permission enforcement (denied/allowed per role)
    - InputValidation: node, account_id, amount format checks
    - BankingDispatch: correct results from bridge methods
    - CodegenDispatch: correct results from codegen pipeline
    - AuditLogging: every invocation logged (success, denial, error)

Fixture isolation:
    Each test gets fresh tmp_data (seeded BANK_A), audit_log (temp DB), and
    executor. The admin/viewer/operator fixtures provide AuthContext instances
    with known roles for RBAC testing.

Naming convention:
    test_{layer}_{scenario} — e.g., test_viewer_denied_transaction, test_list_accounts
"""

import os
import tempfile
import pytest
from python.auth import AuthContext, Role
from python.llm.tool_executor import ToolExecutor
from python.llm.audit import AuditLog
from python.bridge import COBOLBridge


@pytest.fixture
def tmp_data(tmp_path):
    """Create a temporary data directory with BANK_A seeded.

    Provides enough data for all banking dispatch tests without the overhead
    of seeding all 6 nodes.
    """
    data_dir = str(tmp_path / "data")
    os.makedirs(os.path.join(data_dir, "BANK_A"), exist_ok=True)
    bridge = COBOLBridge("BANK_A", data_dir=data_dir)
    bridge.seed_demo_data()
    bridge.close()
    return data_dir


@pytest.fixture
def audit_log(tmp_path):
    """Create an AuditLog with a temporary database file."""
    return AuditLog(db_path=str(tmp_path / "audit.db"))


@pytest.fixture
def executor(tmp_data, audit_log):
    """Create a ToolExecutor wired to temp data and temp audit log."""
    return ToolExecutor(data_dir=tmp_data, audit_log=audit_log)


@pytest.fixture
def admin():
    """Admin auth context — has all permissions."""
    return AuthContext("test-admin", Role.ADMIN)


@pytest.fixture
def viewer():
    """Viewer auth context — read-only, no transaction or verify permissions."""
    return AuthContext("test-viewer", Role.VIEWER)


@pytest.fixture
def operator():
    """Operator auth context — can transact but cannot verify chains."""
    return AuthContext("test-operator", Role.OPERATOR)


# ── RBAC Gate ─────────────────────────────────────────────────────
# Layer 1: permission checks before any data access.

class TestRBACGate:
    """RBAC denies unauthorized tool calls."""

    def test_viewer_denied_transaction(self, executor, viewer):
        """Viewer lacks transactions.process — denied with permitted=False."""
        result = executor.execute("process_transaction", {
            "node": "BANK_A", "account_id": "ACT-A-001", "tx_type": "D", "amount": 100
        }, viewer)
        assert result.get("permitted") is False
        assert "denied" in result["error"].lower()

    def test_admin_allowed_transaction(self, executor, admin):
        """Admin has all permissions — transaction succeeds."""
        result = executor.execute("process_transaction", {
            "node": "BANK_A", "account_id": "ACT-A-001", "tx_type": "D", "amount": 100,
            "description": "test deposit"
        }, admin)
        assert "error" not in result or result.get("status") == "00"

    def test_viewer_allowed_list_accounts(self, executor, viewer):
        """Viewer has accounts.read — list accounts succeeds."""
        result = executor.execute("list_accounts", {"node": "BANK_A"}, viewer)
        assert "accounts" in result

    def test_viewer_denied_verify_chain(self, executor, viewer):
        """Viewer lacks chain.verify — denied."""
        result = executor.execute("verify_chain", {"node": "BANK_A"}, viewer)
        assert result.get("permitted") is False

    def test_unknown_tool_returns_error(self, executor, admin):
        """Unknown tool name returns error without touching any data."""
        result = executor.execute("nonexistent_tool", {}, admin)
        assert "error" in result
        assert "Unknown tool" in result["error"]


# ── Input Validation ──────────────────────────────────────────────
# Layer 2: parameter format checks before dispatch.

class TestInputValidation:
    """Input validation rejects bad data."""

    def test_invalid_node(self, executor, admin):
        """Rejects node name not in the 6-node set."""
        result = executor.execute("list_accounts", {"node": "BANK_Z"}, admin)
        assert "error" in result
        assert "Invalid node" in result["error"]

    def test_invalid_account_id(self, executor, admin):
        """Rejects account ID not matching ACT-X-NNN or NST-BANK-X pattern."""
        result = executor.execute("get_account", {"node": "BANK_A", "account_id": "INVALID"}, admin)
        assert "error" in result
        assert "Invalid account_id" in result["error"]

    def test_negative_amount(self, executor, admin):
        """Rejects negative transaction amount."""
        result = executor.execute("process_transaction", {
            "node": "BANK_A", "account_id": "ACT-A-001", "tx_type": "D", "amount": -50
        }, admin)
        assert "error" in result
        assert "positive" in result["error"].lower()

    def test_valid_nostro_account(self, executor, admin):
        """NST-BANK-A passes account ID validation (even if account not found)."""
        result = executor.execute("get_account", {"node": "BANK_A", "account_id": "NST-BANK-A"}, admin)
        assert "Invalid account_id" not in result.get("error", "")


# ── Banking Dispatch ──────────────────────────────────────────────
# Layer 3: correct results from bridge/settlement methods.

class TestBankingDispatch:
    """Banking tool dispatch returns correct results."""

    def test_list_accounts(self, executor, admin):
        """list_accounts returns accounts list with count."""
        result = executor.execute("list_accounts", {"node": "BANK_A"}, admin)
        assert "accounts" in result
        assert result["count"] >= 1

    def test_get_account(self, executor, admin):
        """get_account returns account details for existing ID."""
        result = executor.execute("get_account", {"node": "BANK_A", "account_id": "ACT-A-001"}, admin)
        assert "account" in result
        assert result["account"]["id"] == "ACT-A-001"

    def test_process_deposit(self, executor, admin):
        """Deposit returns status 00 and transaction ID."""
        result = executor.execute("process_transaction", {
            "node": "BANK_A", "account_id": "ACT-A-001", "tx_type": "D",
            "amount": 100, "description": "test"
        }, admin)
        assert result.get("status") == "00"
        assert result.get("tx_id") is not None

    def test_verify_chain(self, executor, admin):
        """verify_chain returns valid status for unseeded chain."""
        result = executor.execute("verify_chain", {"node": "BANK_A"}, admin)
        assert "valid" in result

    def test_view_chain(self, executor, admin):
        """view_chain returns entries list after seeding a transaction."""
        executor.execute("process_transaction", {
            "node": "BANK_A", "account_id": "ACT-A-001", "tx_type": "D",
            "amount": 50, "description": "seed"
        }, admin)
        result = executor.execute("view_chain", {"node": "BANK_A"}, admin)
        assert "entries" in result

    def test_run_reconciliation(self, executor, admin):
        """run_reconciliation returns status field."""
        result = executor.execute("run_reconciliation", {"node": "BANK_A"}, admin)
        assert "status" in result

    def test_get_nonexistent_account(self, executor, admin):
        """get_account for missing ID returns error with 'not found'."""
        result = executor.execute("get_account", {"node": "BANK_A", "account_id": "ACT-A-999"}, admin)
        assert "error" in result
        assert "not found" in result["error"]


# ── Codegen Dispatch ──────────────────────────────────────────────
# Layer 3: correct results from codegen pipeline methods.

class TestCodegenDispatch:
    """Codegen tool dispatch works correctly."""

    # Minimal COBOL source for parse/validate tests
    SAMPLE_COBOL = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST-PROG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-STATUS PIC XX VALUE "00".
       PROCEDURE DIVISION.
       MAIN-PARAGRAPH.
           DISPLAY "HELLO".
           STOP RUN.
"""

    def test_parse_cobol(self, executor, admin):
        """parse_cobol returns program ID and paragraph names."""
        result = executor.execute("parse_cobol", {"source_text": self.SAMPLE_COBOL}, admin)
        assert result.get("program_id") == "TEST-PROG"
        assert "MAIN-PARAGRAPH" in result.get("paragraphs", [])

    def test_validate_cobol(self, executor, admin):
        """validate_cobol returns valid status and issues list."""
        result = executor.execute("validate_cobol", {"source_text": self.SAMPLE_COBOL}, admin)
        assert "issues" in result
        assert isinstance(result["valid"], bool)

    def test_generate_copybook(self, executor, admin):
        """generate_cobol with copybook template produces source with fields."""
        result = executor.execute("generate_cobol", {
            "template": "copybook",
            "name": "TESTREC",
            "params": {"fields": [
                {"name": "TEST-ID", "pic": "X(10)"},
                {"name": "TEST-AMT", "pic": "S9(10)V99"},
            ]},
        }, admin)
        assert "source" in result
        assert "TEST-ID" in result["source"]

    def test_unknown_template(self, executor, admin):
        """generate_cobol with unknown template returns error."""
        result = executor.execute("generate_cobol", {
            "template": "nonexistent", "name": "FOO"
        }, admin)
        assert "error" in result


# ── Analysis Dispatch ────────────────────────────────────────────
# Layer 3: correct results from analysis pipeline methods.

class TestAnalysisDispatch:
    """Analysis tool dispatch works correctly."""

    SAMPLE_COBOL = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. ANALYSIS-TEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-AMT PIC 9(7)V99 VALUE 0.
       PROCEDURE DIVISION.
       MAIN-PARA.
           MOVE 100 TO WS-AMT
           GO TO END-PARA.
       SKIP-PARA.
           DISPLAY "DEAD".
       END-PARA.
           STOP RUN.
"""

    def test_analyze_call_graph(self, executor, admin):
        """analyze_call_graph returns paragraphs and edges."""
        result = executor.execute("analyze_call_graph", {"source_text": self.SAMPLE_COBOL}, admin)
        assert "paragraphs" in result
        assert "edges" in result

    def test_trace_execution(self, executor, admin):
        """trace_execution returns execution_path and steps."""
        result = executor.execute("trace_execution", {
            "source_text": self.SAMPLE_COBOL, "entry_point": "MAIN-PARA",
        }, admin)
        assert "execution_path" in result
        assert result["steps"] >= 1

    def test_analyze_data_flow(self, executor, admin):
        """analyze_data_flow returns paragraph reads/writes."""
        result = executor.execute("analyze_data_flow", {"source_text": self.SAMPLE_COBOL}, admin)
        assert "paragraph_reads" in result or "paragraph_writes" in result

    def test_analyze_data_flow_field(self, executor, admin):
        """analyze_data_flow with field_name returns field + accesses."""
        result = executor.execute("analyze_data_flow", {
            "source_text": self.SAMPLE_COBOL, "field_name": "WS-AMT",
        }, admin)
        assert result["field"] == "WS-AMT"
        assert "accesses" in result

    def test_detect_dead_code(self, executor, admin):
        """detect_dead_code returns dead and reachable sets."""
        result = executor.execute("detect_dead_code", {"source_text": self.SAMPLE_COBOL}, admin)
        assert "dead" in result
        assert "reachable" in result

    def test_explain_pattern_found(self, executor, admin):
        """explain_cobol_pattern returns name and era for known pattern."""
        result = executor.execute("explain_cobol_pattern", {"pattern_name": "ALTER"}, admin)
        assert "name" in result
        assert "era" in result

    def test_explain_pattern_not_found(self, executor, admin):
        """explain_cobol_pattern returns error and suggestions for unknown."""
        result = executor.execute("explain_cobol_pattern", {"pattern_name": "NONEXISTENT-XYZ"}, admin)
        assert "error" in result
        assert "suggestions" in result

    def test_analysis_rbac_denied(self, executor, viewer):
        """Viewer lacks cobol.read — analysis denied."""
        result = executor.execute("analyze_call_graph", {"source_text": self.SAMPLE_COBOL}, viewer)
        assert result.get("permitted") is False


# ── Audit Logging ─────────────────────────────────────────────────
# Layer 4: every invocation is recorded in the audit log.

class TestAuditLogging:
    """Every tool invocation is logged."""

    def test_successful_call_logged(self, executor, audit_log, admin):
        """Successful tool call is logged with permitted=True."""
        executor.execute("list_accounts", {"node": "BANK_A"}, admin)
        entries = audit_log.get_recent(1)
        assert len(entries) == 1
        assert entries[0]["tool_name"] == "list_accounts"
        assert entries[0]["permitted"] is True

    def test_denied_call_logged(self, executor, audit_log, viewer):
        """RBAC-denied tool call is logged with permitted=False."""
        executor.execute("process_transaction", {
            "node": "BANK_A", "account_id": "ACT-A-001", "tx_type": "D", "amount": 100
        }, viewer)
        entries = audit_log.get_recent(1)
        assert len(entries) == 1
        assert entries[0]["permitted"] is False

    def test_validation_error_logged(self, executor, audit_log, admin):
        """Validation error is logged with non-empty error field."""
        executor.execute("list_accounts", {"node": "INVALID"}, admin)
        entries = audit_log.get_recent(1)
        assert len(entries) == 1
        assert entries[0]["error"] != ""
