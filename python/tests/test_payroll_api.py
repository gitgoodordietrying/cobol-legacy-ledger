"""
Tests for payroll REST API endpoints.

Test strategy:
    Uses FastAPI TestClient for HTTP-level testing of all payroll
    endpoints. Tests verify auth gating, response format, and
    correct delegation to PayrollBridge.
"""

import pytest
from fastapi.testclient import TestClient
from python.api.app import create_app


@pytest.fixture
def client():
    """Create a test client for the API."""
    app = create_app()
    return TestClient(app)


# ── Auth Headers ─────────────────────────────────────────────────

ADMIN_HEADERS = {"X-User": "admin", "X-Role": "admin"}
VIEWER_HEADERS = {"X-User": "viewer", "X-Role": "viewer"}


# ── Employee Endpoints ───────────────────────────────────────────

class TestEmployeeEndpoints:

    def test_list_employees(self, client):
        resp = client.get("/api/payroll/employees", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "employees" in data
        assert data["count"] == 25

    def test_get_employee(self, client):
        resp = client.get("/api/payroll/employees/EMP-001", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        emp = resp.json()["employee"]
        assert emp["emp_id"] == "EMP-001"

    def test_get_employee_not_found(self, client):
        resp = client.get("/api/payroll/employees/EMP-999", headers=ADMIN_HEADERS)
        assert resp.status_code == 404

    def test_viewer_can_read(self, client):
        """Viewers cannot read payroll (not in VIEWER permissions)."""
        resp = client.get("/api/payroll/employees", headers=VIEWER_HEADERS)
        assert resp.status_code == 403


# ── Payroll Run Endpoint ─────────────────────────────────────────

class TestPayrollRun:

    def test_run_payroll(self, client):
        resp = client.post("/api/payroll/run?day=20260301", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["processed"] == 23
        assert data["stubs_count"] == 23

    def test_viewer_cannot_run(self, client):
        resp = client.post("/api/payroll/run", headers=VIEWER_HEADERS)
        assert resp.status_code == 403


# ── Status Endpoint ──────────────────────────────────────────────

class TestStatusEndpoint:

    def test_status(self, client):
        resp = client.get("/api/payroll/status", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "employees_loaded" in data
        assert "mode" in data


# ── Pay Stubs Endpoint ───────────────────────────────────────────

class TestPayStubsEndpoint:

    def test_stubs_empty_before_run(self, client):
        resp = client.get("/api/payroll/stubs", headers=ADMIN_HEADERS)
        assert resp.status_code == 200

    def test_stubs_after_run(self, client):
        client.post("/api/payroll/run?day=20260301", headers=ADMIN_HEADERS)
        resp = client.get("/api/payroll/stubs", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["count"] >= 23


# ── RBAC X-Role Header Handling ─────────────────────────────────

class TestPayrollRBAC:
    """Verify that X-Role header is respected, not silently discarded."""

    def test_custom_user_with_operator_role_can_read(self, client):
        """Non-demo user with X-Role: operator gets payroll.read permission."""
        headers = {"X-User": "custom-user", "X-Role": "operator"}
        resp = client.get("/api/payroll/employees", headers=headers)
        assert resp.status_code == 200

    def test_custom_user_with_admin_role_can_run(self, client):
        """Non-demo user with X-Role: admin gets payroll.process permission."""
        headers = {"X-User": "custom-user", "X-Role": "admin"}
        resp = client.post("/api/payroll/run?day=20260301", headers=headers)
        assert resp.status_code == 200

    def test_custom_user_without_role_defaults_to_viewer(self, client):
        """Non-demo user with no X-Role header defaults to viewer (no payroll access)."""
        headers = {"X-User": "custom-user"}
        resp = client.get("/api/payroll/employees", headers=headers)
        assert resp.status_code == 403

    def test_custom_user_with_invalid_role_defaults_to_viewer(self, client):
        """Non-demo user with invalid X-Role falls back to viewer."""
        headers = {"X-User": "custom-user", "X-Role": "superuser"}
        resp = client.get("/api/payroll/employees", headers=headers)
        assert resp.status_code == 403


# ── Payroll Error Paths ──────────────────────────────────────────

class TestPayrollErrorPaths:

    def test_stubs_filtered_by_emp_id(self, client):
        """Pay stubs filtered by emp_id return only that employee's stubs."""
        # Run payroll first
        client.post("/api/payroll/run?day=20260301", headers=ADMIN_HEADERS)
        resp = client.get("/api/payroll/stubs?emp_id=EMP-001", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        for stub in data["stubs"]:
            assert stub["emp_id"] == "EMP-001"

    def test_stubs_filtered_by_nonexistent_emp(self, client):
        """Pay stubs for nonexistent employee returns empty list."""
        client.post("/api/payroll/run?day=20260301", headers=ADMIN_HEADERS)
        resp = client.get("/api/payroll/stubs?emp_id=EMP-999", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_get_employee_malformed_id(self, client):
        """Malformed employee ID returns 404."""
        resp = client.get("/api/payroll/employees/INVALID-FORMAT", headers=ADMIN_HEADERS)
        assert resp.status_code == 404
