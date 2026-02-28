"""
ToolExecutor -- RBAC-gated dispatch pipeline for LLM tool calls.

When an LLM requests a tool call (e.g., "list_accounts" with {"node": "BANK_A"}),
the ToolExecutor processes it through a 4-layer pipeline before returning results:

    Layer 1 — RBAC Gate: Check the user's role against the tool's
        required_permission. A VIEWER calling process_transaction gets
        an immediate denial without touching any data.

    Layer 2 — Input Validation: Verify node names are in the 6-node set,
        account IDs match the ACT-X-NNN or NST-BANK-X pattern, amounts
        are positive. Catches bad input before it reaches the bridge.

    Layer 3 — Dispatch: Route the tool call to the correct bridge, settlement,
        or codegen method. Banking tools use COBOLBridge instances (one per
        node); codegen tools use the parser/generator/editor/validator pipeline.

    Layer 4 — Audit: Record every invocation (permitted or denied) in the
        SQLite audit log with timestamp, user, role, tool, params, and result.

Why own singletons (independent of FastAPI):
    The ToolExecutor maintains its own bridge dict, coordinator, and verifier
    rather than sharing with the FastAPI dependency injection layer. This is
    because the executor can also be used outside FastAPI (e.g., from a CLI
    or test harness). Each context manages its own lifecycle.

Audit-every-call guarantee:
    The audit.record() call happens on every code path — success, RBAC denial,
    validation error, and dispatch exception. There is no path through execute()
    that skips audit logging.

Dependencies:
    python.auth, python.bridge, python.settlement, python.cross_verify,
    python.cobol_codegen, python.llm.tools, python.llm.audit
"""

import dataclasses
import re
from typing import Dict, Any, Optional

from python.auth import AuthContext
from python.bridge import COBOLBridge
from python.settlement import SettlementCoordinator
from python.cross_verify import CrossNodeVerifier
from python.cobol_codegen import (
    COBOLParser, COBOLGenerator, COBOLEditor, COBOLValidator,
    crud_program, report_program, batch_program, copybook_record,
)
from python.cobol_analyzer import (
    CallGraphAnalyzer, DataFlowAnalyzer, DeadCodeAnalyzer,
    ComplexityAnalyzer, KnowledgeBase,
)
from python.llm.tools import get_tool_definition
from python.llm.audit import AuditLog


# ── Constants ─────────────────────────────────────────────────────
# Validation patterns matching the 6-node architecture and COBOL record formats.
VALID_NODES = {"BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E", "CLEARING"}
ACCOUNT_PATTERN = re.compile(r"^(ACT-[A-E]-\d{3}|NST-BANK-[A-E])$")  # Matches ACCT-ID PIC X(10) format


class ToolExecutor:
    """Executes LLM tool calls through the 4-layer RBAC/validation/dispatch/audit pipeline.

    Each instance maintains its own bridge cache, coordinator, and verifier.
    Created once per ToolExecutor lifetime (typically one per API process or
    test fixture). Thread-safety is not guaranteed — acceptable for demo use.
    """

    def __init__(self, data_dir: str = "COBOL-BANKING/data", audit_log: Optional[AuditLog] = None):
        """Initialize the tool executor.

        :param data_dir: Root data directory containing node subdirectories
        :param audit_log: AuditLog instance (creates default if None)
        """
        self.data_dir = data_dir
        self.audit = audit_log or AuditLog()
        self._bridges: Dict[str, COBOLBridge] = {}     # Cached per-node bridges
        self._coordinator: Optional[SettlementCoordinator] = None
        self._verifier: Optional[CrossNodeVerifier] = None
        self._parser = COBOLParser()
        self._generator = COBOLGenerator()
        self._editor = COBOLEditor()
        self._validator = COBOLValidator()
        self._cg_analyzer = CallGraphAnalyzer()
        self._df_analyzer = DataFlowAnalyzer()
        self._dc_analyzer = DeadCodeAnalyzer()
        self._cx_analyzer = ComplexityAnalyzer()
        self._kb = KnowledgeBase()

    def _get_bridge(self, node: str) -> COBOLBridge:
        """Get or create a COBOLBridge for the given node."""
        if node not in self._bridges:
            self._bridges[node] = COBOLBridge(node, data_dir=self.data_dir)
        return self._bridges[node]

    def _get_coordinator(self) -> SettlementCoordinator:
        """Get or create the singleton SettlementCoordinator."""
        if self._coordinator is None:
            self._coordinator = SettlementCoordinator(data_dir=self.data_dir)
        return self._coordinator

    def _get_verifier(self) -> CrossNodeVerifier:
        """Get or create the singleton CrossNodeVerifier."""
        if self._verifier is None:
            self._verifier = CrossNodeVerifier(data_dir=self.data_dir)
        return self._verifier

    def execute(self, tool_name: str, params: Dict[str, Any], auth: AuthContext, provider: str = "") -> Dict[str, Any]:
        """Execute a tool call through the 4-layer pipeline.

        1. Look up tool definition (reject unknown tools)
        2. RBAC gate — check user's role has required_permission
        3. Input validation — verify node, account_id, amount formats
        4. Dispatch — route to bridge/settlement/codegen method
        5. Audit — log the invocation regardless of outcome

        Returns:
            Dict with tool results on success, or {"error": "..."} on failure.
            RBAC denials also include {"permitted": False}.
        """
        tool_def = get_tool_definition(tool_name)
        if tool_def is None:
            error = f"Unknown tool: {tool_name}"
            self.audit.record(auth.user_id, auth.role.value, tool_name, params, permitted=False, provider=provider, error=error)
            return {"error": error}

        # ── RBAC Gate ─────────────────────────────────────────────
        # Check permission before touching any data.
        required_perm = tool_def["required_permission"]
        if not auth.has_permission(required_perm):
            error = f"Permission denied: {auth.role.value} lacks {required_perm}"
            self.audit.record(auth.user_id, auth.role.value, tool_name, params, permitted=False, provider=provider, error=error)
            return {"error": error, "permitted": False}

        # ── Input Validation ──────────────────────────────────────
        # Catch bad node names, account formats, negative amounts.
        validation_error = self._validate_params(tool_name, params)
        if validation_error:
            self.audit.record(auth.user_id, auth.role.value, tool_name, params, permitted=True, provider=provider, error=validation_error)
            return {"error": validation_error}

        # ── Dispatch ──────────────────────────────────────────────
        # Route to the correct bridge/codegen method.
        try:
            result = self._dispatch(tool_name, params)
        except Exception as e:
            error = str(e)
            self.audit.record(auth.user_id, auth.role.value, tool_name, params, permitted=True, provider=provider, error=error)
            return {"error": error}

        # ── Audit ─────────────────────────────────────────────────
        # Record successful execution with full result.
        self.audit.record(auth.user_id, auth.role.value, tool_name, params, result=result, permitted=True, provider=provider)
        return result

    def _validate_params(self, tool_name: str, params: Dict[str, Any]) -> Optional[str]:
        """Validate tool parameters against expected formats.

        Returns error string if validation fails, None if all checks pass.
        """
        # Node name must be in the 6-node set
        node = params.get("node")
        if node is not None and node not in VALID_NODES:
            return f"Invalid node: {node}"

        # Account ID must match ACT-X-NNN or NST-BANK-X pattern
        account_id = params.get("account_id")
        if account_id is not None and not ACCOUNT_PATTERN.match(account_id):
            return f"Invalid account_id format: {account_id}"

        # Target ID (for transfers) has the same format
        target_id = params.get("target_id")
        if target_id is not None and not ACCOUNT_PATTERN.match(target_id):
            return f"Invalid target_id format: {target_id}"

        # Amount must be positive (COBOL checks this too, but catch early)
        amount = params.get("amount")
        if amount is not None and amount <= 0:
            return "Amount must be positive"

        # Transfer-specific: source/dest bank must be valid nodes
        for field in ("source_bank", "dest_bank"):
            val = params.get(field)
            if val is not None and val not in VALID_NODES:
                return f"Invalid {field}: {val}"

        # Transfer-specific: source/dest account format
        for field in ("source_account", "dest_account"):
            val = params.get(field)
            if val is not None and not ACCOUNT_PATTERN.match(val):
                return f"Invalid {field} format: {val}"

        return None

    def _dispatch(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch tool call to the appropriate module method.

        Returns a dict with the tool's result. Raises on unexpected errors.
        """
        # ── Banking Dispatch ──────────────────────────────────────
        if tool_name == "list_accounts":
            bridge = self._get_bridge(params["node"])
            accounts = bridge.list_accounts()
            return {"accounts": accounts, "count": len(accounts)}

        elif tool_name == "get_account":
            bridge = self._get_bridge(params["node"])
            account = bridge.get_account(params["account_id"])
            if account is None:
                return {"error": f"Account {params['account_id']} not found"}
            return {"account": account}

        elif tool_name == "process_transaction":
            bridge = self._get_bridge(params["node"])
            return bridge.process_transaction(
                account_id=params["account_id"],
                tx_type=params["tx_type"],
                amount=params["amount"],
                description=params.get("description", ""),
                target_id=params.get("target_id"),
            )

        elif tool_name == "verify_chain":
            bridge = self._get_bridge(params["node"])
            return bridge.chain.verify_chain()

        elif tool_name == "view_chain":
            bridge = self._get_bridge(params["node"])
            limit = params.get("limit", 20)
            entries = bridge.chain.get_chain_for_display(limit=limit)
            return {"entries": entries, "count": len(entries)}

        elif tool_name == "transfer":
            coordinator = self._get_coordinator()
            result = coordinator.execute_transfer(
                source_bank=params["source_bank"],
                source_account=params["source_account"],
                dest_bank=params["dest_bank"],
                dest_account=params["dest_account"],
                amount=params["amount"],
                description=params.get("description", ""),
            )
            return dataclasses.asdict(result)  # SettlementResult → dict

        elif tool_name == "verify_all_nodes":
            verifier = self._get_verifier()
            report = verifier.verify_all()
            return {
                "all_chains_intact": report.all_chains_intact,
                "all_settlements_matched": report.all_settlements_matched,
                "chain_integrity": report.chain_integrity,
                "chain_lengths": report.chain_lengths,
                "settlements_checked": report.settlements_checked,
                "settlements_matched": report.settlements_matched,
                "anomalies": report.anomalies,
                "verification_time_ms": report.verification_time_ms,
            }

        elif tool_name == "run_reconciliation":
            bridge = self._get_bridge(params["node"])
            return bridge.run_reconciliation()

        # ── Codegen Dispatch ──────────────────────────────────────
        elif tool_name == "parse_cobol":
            program = self._parser.parse_text(params["source_text"])
            return {
                "program_id": program.metadata.program_id,
                "paragraphs": [p.name for p in program.paragraphs],
                "files": [f.logical_name for f in program.files],
                "copybooks": program.copybooks,
                "working_storage_fields": len(program.working_storage),
            }

        elif tool_name == "generate_cobol":
            template = params["template"]
            name = params["name"]
            tparams = params.get("params", {})

            if template == "copybook":
                fields = tparams.get("fields", [])          # Copybook uses fields list, not program factory
                items = copybook_record(name, fields)
                source = self._generator.generate_copybook(name, items)
            else:
                factories = {"crud": crud_program, "report": report_program, "batch": batch_program}
                factory = factories.get(template)
                if not factory:
                    return {"error": f"Unknown template: {template}"}
                program = factory(name, **tparams)
                source = self._generator.generate(program)

            return {"source": source, "line_count": source.count("\n") + 1}

        elif tool_name == "edit_cobol":
            program = self._parser.parse_text(params["source_text"])
            operations = {
                "add_field": self._editor.add_field,
                "remove_field": self._editor.remove_field,
                "add_paragraph": self._editor.add_paragraph,
                "rename_paragraph": self._editor.rename_paragraph,
                "add_operation": self._editor.add_operation,
                "add_88_condition": self._editor.add_88_condition,
                "add_copybook_ref": self._editor.add_copybook_ref,
                "update_pic": self._editor.update_pic,
            }
            op_func = operations.get(params["operation"])
            if not op_func:
                return {"error": f"Unknown operation: {params['operation']}"}
            message = op_func(program, **params.get("params", {}))
            source = self._generator.generate(program)
            return {"source": source, "message": message}

        elif tool_name == "validate_cobol":
            program = self._parser.parse_text(params["source_text"])
            issues = self._validator.validate(program)
            return {
                "valid": all(i.severity != "ERROR" for i in issues),
                "issues": [{"severity": i.severity, "message": i.message, "location": i.location} for i in issues],
            }

        # ── COBOL Analysis Dispatch ──────────────────────────────────
        elif tool_name == "analyze_call_graph":
            graph = self._cg_analyzer.analyze(params["source_text"])
            return graph.to_dict()

        elif tool_name == "trace_execution":
            path = self._cg_analyzer.trace_execution(
                params["source_text"],
                params["entry_point"],
                max_steps=params.get("max_steps", 100),
            )
            return {"execution_path": path, "steps": len(path)}

        elif tool_name == "analyze_data_flow":
            field_name = params.get("field_name")
            if field_name:
                trace = self._df_analyzer.trace_field(params["source_text"], field_name)
                return {"field": field_name, "accesses": trace, "count": len(trace)}
            else:
                result = self._df_analyzer.analyze(params["source_text"])
                return result.to_dict()

        elif tool_name == "detect_dead_code":
            result = self._dc_analyzer.analyze(
                params["source_text"],
                entry_point=params.get("entry_point"),
            )
            return result.to_dict()

        elif tool_name == "explain_cobol_pattern":
            entry = self._kb.lookup(params["pattern_name"])
            if entry is None:
                suggestions = self._kb.search(params["pattern_name"])
                return {
                    "error": f"Pattern '{params['pattern_name']}' not found",
                    "suggestions": suggestions,
                }
            return entry

        return {"error": f"Unimplemented tool: {tool_name}"}
