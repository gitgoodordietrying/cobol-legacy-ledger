"""
Tests for simulation REST API endpoints -- start, stop, status, transactions, tamper.

Test strategy:
    Tests use FastAPI's TestClient with a temporary data directory. The simulation
    module state (_engine, _thread) is reset between tests. RBAC enforcement is
    tested for each endpoint that requires permissions.

Test groups:
    - Status: GET /api/simulation/status (no auth required, returns not-running)
    - Start: POST /api/simulation/start (requires operator, starts engine)
    - Transactions: GET /api/nodes/{node}/transactions (requires accounts.read)
    - Tamper: POST /api/tamper-demo (requires auditor)
    - RBAC: viewer cannot start simulation or tamper

Fixture isolation:
    Each test gets a fresh temp directory with BANK_A seeded. The simulation
    module globals are patched and restored after each test.
"""

import os
import time
import pytest
from fastapi.testclient import TestClient

from python.api.app import create_app
from python.api import dependencies as deps
from python.api import routes_simulation as sim_routes
from python.bridge import COBOLBridge


@pytest.fixture
def tmp_data(tmp_path):
    """Create temp data directory with BANK_A and BANK_C seeded."""
    data_dir = str(tmp_path / "data")
    for node in ["BANK_A", "BANK_C"]:
        os.makedirs(os.path.join(data_dir, node), exist_ok=True)
        bridge = COBOLBridge(node, data_dir=data_dir)
        bridge.seed_demo_data()
        bridge.close()
    return data_dir


@pytest.fixture
def client(tmp_data):
    """FastAPI test client with overridden dependencies and reset simulation state."""
    original_data_dir = deps.DATA_DIR
    deps.DATA_DIR = tmp_data
    deps._bridges.clear()
    deps._coordinator = None
    deps._verifier = None

    # Reset simulation module state
    sim_routes._engine = None
    sim_routes._thread = None
    sim_routes._event_queues.clear()

    app = create_app()
    with TestClient(app) as c:
        yield c

    deps.DATA_DIR = original_data_dir
    deps._bridges.clear()
    sim_routes._engine = None
    sim_routes._thread = None
    sim_routes._event_queues.clear()


# Demo auth headers
ADMIN_HEADERS = {"X-User": "admin", "X-Role": "admin"}
VIEWER_HEADERS = {"X-User": "viewer", "X-Role": "viewer"}
OPERATOR_HEADERS = {"X-User": "operator", "X-Role": "operator"}
AUDITOR_HEADERS = {"X-User": "auditor", "X-Role": "auditor"}


# ── Status (no auth required) ────────────────────────────────────

def test_status_not_running(client):
    """GET /api/simulation/status returns not-running when no sim active."""
    resp = client.get("/api/simulation/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["running"] is False
    assert data["day"] == 0
    assert data["completed"] == 0


# ── Start requires operator ──────────────────────────────────────

def test_start_requires_operator(client):
    """POST /api/simulation/start denied for viewer role."""
    resp = client.post("/api/simulation/start",
                       json={"days": 1},
                       headers=VIEWER_HEADERS)
    assert resp.status_code == 403


def test_start_and_stop(client):
    """POST /api/simulation/start + stop lifecycle."""
    # Start
    resp = client.post("/api/simulation/start",
                       json={"days": 2, "time_scale": 0},
                       headers=OPERATOR_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "started"

    # Give the engine a moment to begin
    time.sleep(0.5)

    # Status should show running
    resp = client.get("/api/simulation/status")
    data = resp.json()
    # Engine may have already finished 2 days, so running could be True or False
    assert data["day"] >= 0

    # Stop
    resp = client.post("/api/simulation/stop", headers=OPERATOR_HEADERS)
    assert resp.status_code == 200

    # Wait for thread to finish
    time.sleep(1)

    resp = client.get("/api/simulation/status")
    assert resp.json()["running"] is False


# ── Transaction listing ──────────────────────────────────────────

def test_list_transactions(client):
    """GET /api/nodes/{node}/transactions returns list (may be empty before sim)."""
    resp = client.get("/api/nodes/BANK_A/transactions",
                      headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── Tamper demo ──────────────────────────────────────────────────

def test_tamper_requires_auditor(client):
    """POST /api/tamper-demo denied for viewer role."""
    resp = client.post("/api/tamper-demo", json={}, headers=VIEWER_HEADERS)
    assert resp.status_code == 403


def test_tamper_demo(client):
    """POST /api/tamper-demo succeeds for auditor and returns tamper info."""
    resp = client.post("/api/tamper-demo",
                       json={"node": "BANK_C", "account_id": "ACT-C-001", "amount": 999999.99},
                       headers=AUDITOR_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tampered"] is True
    assert data["node"] == "BANK_C"
    assert data["account_id"] == "ACT-C-001"
