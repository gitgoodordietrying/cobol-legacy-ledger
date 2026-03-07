"""
routes_payroll -- REST API endpoints for the legacy payroll sidecar.

Provides CRUD access to payroll data and payroll cycle execution. Payroll
runs produce settlement-compatible transfer records that flow through the
existing 6-node settlement network via the SettlementCoordinator.

Endpoints:
    GET  /api/payroll/employees      — List all employees
    GET  /api/payroll/employees/{id} — Employee details
    POST /api/payroll/run            — Execute payroll cycle → settlement
    GET  /api/payroll/stubs          — Pay stub history
    GET  /api/payroll/status         — Processing status

Auth:
    payroll.read — list employees, view stubs, check status
    payroll.process — run payroll cycle

Dependencies:
    python.payroll_bridge, python.settlement, python.auth
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Optional

from python.auth import get_auth_context, Role
from python.payroll_bridge import PayrollBridge
from python.settlement import SettlementCoordinator


router = APIRouter(prefix="/api/payroll", tags=["payroll"])


# ── Singleton Management ──────────────────────────────────────
# Lazy-initialized bridge and coordinator instances.

_bridge: Optional[PayrollBridge] = None
_coordinator: Optional[SettlementCoordinator] = None


def _get_bridge() -> PayrollBridge:
    global _bridge
    if _bridge is None:
        _bridge = PayrollBridge()
    return _bridge


def _get_coordinator() -> SettlementCoordinator:
    global _coordinator
    if _coordinator is None:
        _coordinator = SettlementCoordinator()
    return _coordinator


def _get_auth(request: Request):
    """Extract auth context from request headers.

    Parses X-Role into a Role enum, falling back to VIEWER for unknown
    values. Both user and role are passed to get_auth_context() so that
    non-demo users inherit the correct permissions for their stated role.
    """
    user = request.headers.get("X-User", "viewer")
    role_str = request.headers.get("X-Role", "viewer")
    try:
        role = Role(role_str.lower())
    except ValueError:
        role = Role.VIEWER
    return get_auth_context(user, role)


# ── Endpoints ─────────────────────────────────────────────────

@router.get("/employees")
async def list_employees(request: Request):
    """List all employees from the payroll system."""
    auth = _get_auth(request)
    auth.require_permission("payroll.read")

    bridge = _get_bridge()
    employees = bridge.list_employees()
    return {"employees": employees, "count": len(employees)}


@router.get("/employees/{emp_id}")
async def get_employee(emp_id: str, request: Request):
    """Get details for a specific employee."""
    auth = _get_auth(request)
    auth.require_permission("payroll.read")

    bridge = _get_bridge()
    emp = bridge.get_employee(emp_id)
    if emp is None:
        raise HTTPException(status_code=404, detail=f"Employee {emp_id} not found")
    return {"employee": emp}


@router.post("/run")
async def run_payroll(request: Request, day: Optional[str] = None):
    """Execute a payroll cycle.

    Computes gross/taxes/deductions/net for all active employees,
    records pay stubs, and optionally feeds transfers through the
    settlement network.

    Query params:
        day: Run date in YYYYMMDD format (default: today)
        settle: If true, execute settlement transfers (default: false)
    """
    auth = _get_auth(request)
    auth.require_permission("payroll.process")

    bridge = _get_bridge()
    result = bridge.run_payroll(day=day)

    return {
        "summary": result["summary"],
        "stubs_count": len(result["stubs"]),
        "transfers_count": len(result["transfers"]),
        "stubs": result["stubs"],
    }


@router.get("/stubs")
async def get_pay_stubs(request: Request,
                        emp_id: Optional[str] = None,
                        limit: int = 50):
    """Get pay stub history, optionally filtered by employee."""
    auth = _get_auth(request)
    auth.require_permission("payroll.read")

    bridge = _get_bridge()
    stubs = bridge.get_pay_stubs(emp_id=emp_id, limit=limit)
    return {"stubs": stubs, "count": len(stubs)}


@router.get("/status")
async def get_status(request: Request):
    """Get payroll processing status."""
    auth = _get_auth(request)
    auth.require_permission("payroll.read")

    bridge = _get_bridge()
    return bridge.get_status()
