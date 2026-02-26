"""
Tests for banking REST API endpoints -- account CRUD, transactions, chain, settlement.

Test strategy:
    All tests use FastAPI's TestClient with a temporary data directory. A single
    BANK_A node is seeded with demo accounts. The FastAPI dependency injection
    layer (DATA_DIR, _bridges, _coordinator, _verifier) is overridden per-test
    to use the temp directory, ensuring complete isolation from real data.

Test groups:
    - ListAccounts: GET /api/nodes/{node}/accounts (success, invalid node, viewer)
    - GetAccount: GET /api/nodes/{node}/accounts/{id} (found, not found)
    - Transactions: POST /api/nodes/{node}/transactions (deposit, withdraw, RBAC)
    - Chain: GET/POST chain endpoints (view, verify, RBAC)
    - Settlement: POST /api/settlement/transfer and /verify (happy path, NSF, RBAC)
    - Nodes: GET /api/nodes (list all nodes)
    - Health: GET /api/health (unauthenticated status)

Fixture isolation:
    Each test gets a fresh temp directory with BANK_A seeded. The deps module
    globals are patched and restored after each test to prevent cross-test leaks.

Naming convention:
    test_{endpoint}_{scenario} — e.g., test_deposit_success, test_viewer_denied_transaction
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from python.api.app import create_app
from python.api import dependencies as deps
from python.bridge import COBOLBridge


@pytest.fixture
def tmp_data(tmp_path):
    """Create temp data directory with BANK_A seeded for API testing.

    Only BANK_A is seeded (not all 6 nodes) to keep fixture fast while
    providing enough data for account, transaction, and chain tests.
    """
    data_dir = str(tmp_path / "data")
    os.makedirs(os.path.join(data_dir, "BANK_A"), exist_ok=True)
    bridge = COBOLBridge("BANK_A", data_dir=data_dir)
    bridge.seed_demo_data()
    bridge.close()
    return data_dir


@pytest.fixture
def client(tmp_data):
    """FastAPI test client with dependency injection overridden to use temp data.

    Overrides DATA_DIR and clears singleton caches so each test starts fresh.
    Restores original state after the test completes.
    """
    original_data_dir = deps.DATA_DIR
    deps.DATA_DIR = tmp_data
    deps._bridges.clear()
    deps._coordinator = None
    deps._verifier = None

    app = create_app()
    with TestClient(app) as c:
        yield c

    deps.DATA_DIR = original_data_dir
    deps._bridges.clear()


# Demo auth headers — each maps to a DEMO_USERS entry in auth.py
ADMIN_HEADERS = {"X-User": "admin", "X-Role": "admin"}         # Full access
VIEWER_HEADERS = {"X-User": "viewer", "X-Role": "viewer"}      # Read-only
OPERATOR_HEADERS = {"X-User": "operator", "X-Role": "operator"}  # Can transact


# ── List Accounts ─────────────────────────────────────────────────
# GET /api/nodes/{node}/accounts — lists all accounts for a node.

class TestListAccounts:
    def test_list_accounts_success(self, client):
        """Lists BANK_A accounts with correct ID prefix."""
        resp = client.get("/api/nodes/BANK_A/accounts", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["account_id"].startswith("ACT-A-")

    def test_list_accounts_invalid_node(self, client):
        """Returns 404 for unknown node BANK_Z."""
        resp = client.get("/api/nodes/BANK_Z/accounts", headers=ADMIN_HEADERS)
        assert resp.status_code == 404

    def test_list_accounts_viewer_allowed(self, client):
        """Viewer role has accounts.read permission."""
        resp = client.get("/api/nodes/BANK_A/accounts", headers=VIEWER_HEADERS)
        assert resp.status_code == 200


# ── Get Account ───────────────────────────────────────────────────
# GET /api/nodes/{node}/accounts/{id} — single account lookup.

class TestGetAccount:
    def test_get_account_success(self, client):
        """Returns account details for existing ACT-A-001."""
        resp = client.get("/api/nodes/BANK_A/accounts/ACT-A-001", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["account_id"] == "ACT-A-001"

    def test_get_account_not_found(self, client):
        """Returns 404 for nonexistent account ACT-A-999."""
        resp = client.get("/api/nodes/BANK_A/accounts/ACT-A-999", headers=ADMIN_HEADERS)
        assert resp.status_code == 404


# ── Transactions ──────────────────────────────────────────────────
# POST /api/nodes/{node}/transactions — deposit, withdraw, transfer.

class TestTransactions:
    def test_deposit_success(self, client):
        """Deposit returns status 00 and a transaction ID."""
        resp = client.post("/api/nodes/BANK_A/transactions", headers=ADMIN_HEADERS, json={
            "account_id": "ACT-A-001",
            "tx_type": "D",
            "amount": 100.00,
            "description": "Test deposit",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "00"
        assert resp.json()["tx_id"] is not None

    def test_viewer_denied_transaction(self, client):
        """Viewer role lacks transactions.process permission."""
        resp = client.post("/api/nodes/BANK_A/transactions", headers=VIEWER_HEADERS, json={
            "account_id": "ACT-A-001",
            "tx_type": "D",
            "amount": 50.00,
        })
        assert resp.status_code == 403

    def test_invalid_tx_type(self, client):
        """Pydantic rejects invalid transaction type Z."""
        resp = client.post("/api/nodes/BANK_A/transactions", headers=ADMIN_HEADERS, json={
            "account_id": "ACT-A-001",
            "tx_type": "Z",
            "amount": 50.00,
        })
        assert resp.status_code == 422  # Pydantic validation

    def test_withdraw_success(self, client):
        """Successful withdrawal returns status 00."""
        resp = client.post("/api/nodes/BANK_A/transactions", headers=ADMIN_HEADERS, json={
            "account_id": "ACT-A-001",
            "tx_type": "W",
            "amount": 10.00,
            "description": "Test withdrawal",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "00"

    def test_withdraw_nsf(self, client):
        """Withdrawal exceeding balance returns status 01 (NSF)."""
        resp = client.post("/api/nodes/BANK_A/transactions", headers=ADMIN_HEADERS, json={
            "account_id": "ACT-A-001",
            "tx_type": "W",
            "amount": 999999999.00,
            "description": "Overdraw attempt",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "01"  # NSF

    def test_operator_allowed_transaction(self, client):
        """Operator role has transactions.process permission."""
        resp = client.post("/api/nodes/BANK_A/transactions", headers=OPERATOR_HEADERS, json={
            "account_id": "ACT-A-001",
            "tx_type": "D",
            "amount": 25.00,
            "description": "Operator deposit",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "00"

    def test_invalid_node_transaction(self, client):
        """Transaction on unknown node returns 404."""
        resp = client.post("/api/nodes/BANK_Z/transactions", headers=ADMIN_HEADERS, json={
            "account_id": "ACT-A-001",
            "tx_type": "D",
            "amount": 10.00,
        })
        assert resp.status_code == 404


# ── Chain ─────────────────────────────────────────────────────────
# GET /api/nodes/{node}/chain and POST /api/nodes/{node}/chain/verify.

class TestChain:
    def test_view_chain(self, client):
        """View chain returns 200 after seeding a transaction."""
        client.post("/api/nodes/BANK_A/transactions", headers=ADMIN_HEADERS, json={
            "account_id": "ACT-A-001", "tx_type": "D", "amount": 50.00,
        })
        resp = client.get("/api/nodes/BANK_A/chain", headers=ADMIN_HEADERS)
        assert resp.status_code == 200

    def test_verify_chain(self, client):
        """Chain verification returns valid status."""
        resp = client.post("/api/nodes/BANK_A/chain/verify", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert "valid" in resp.json()

    def test_viewer_denied_verify(self, client):
        """Viewer role lacks chain.verify permission."""
        resp = client.post("/api/nodes/BANK_A/chain/verify", headers=VIEWER_HEADERS)
        assert resp.status_code == 403

    def test_chain_view_empty(self, client):
        """Empty chain returns a valid list."""
        resp = client.get("/api/nodes/BANK_A/chain", headers=ADMIN_HEADERS, params={"limit": 10, "offset": 0})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ── Settlement ────────────────────────────────────────────────────
# POST /api/settlement/transfer and /api/settlement/verify.

class TestSettlement:
    @pytest.fixture(autouse=True)
    def seed_both_banks(self, client, tmp_data):
        """Seed BANK_B and CLEARING for settlement tests.

        Settlement requires source bank, destination bank, and clearing house.
        We seed these nodes and clear the deps caches so they pick up new data.
        """
        for node in ["BANK_B", "CLEARING"]:
            node_dir = os.path.join(tmp_data, node)
            os.makedirs(node_dir, exist_ok=True)
            bridge = COBOLBridge(node, data_dir=tmp_data)
            bridge.seed_demo_data()
            bridge.close()
        deps._bridges.clear()
        deps._coordinator = None
        deps._verifier = None

    def test_settlement_transfer_success(self, client):
        """Inter-bank transfer completes with status SUCCESS."""
        resp = client.post("/api/settlement/transfer", headers=ADMIN_HEADERS, json={
            "source_bank": "BANK_A",
            "source_account": "ACT-A-001",
            "dest_bank": "BANK_B",
            "dest_account": "ACT-B-001",
            "amount": 100.00,
            "description": "API settlement test",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("SUCCESS", "COMPLETED")  # Status depends on coordinator version
        assert data["steps_completed"] == 3

    def test_settlement_transfer_nsf(self, client):
        """Settlement fails when source has insufficient funds."""
        resp = client.post("/api/settlement/transfer", headers=ADMIN_HEADERS, json={
            "source_bank": "BANK_A",
            "source_account": "ACT-A-001",
            "dest_bank": "BANK_B",
            "dest_account": "ACT-B-001",
            "amount": 999999999.00,
            "description": "Overdraw settlement",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] != "SUCCESS"

    def test_settlement_verify(self, client):
        """Cross-node verification returns a report with chain integrity."""
        resp = client.post("/api/settlement/verify", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "all_chains_intact" in data
        assert "chain_integrity" in data

    def test_settlement_verify_viewer_denied(self, client):
        """Viewer lacks chain.verify for settlement verification."""
        resp = client.post("/api/settlement/verify", headers=VIEWER_HEADERS)
        assert resp.status_code == 403


# ── Nodes ─────────────────────────────────────────────────────────
# GET /api/nodes — system-wide node listing.

class TestNodes:
    def test_list_nodes(self, client):
        """List nodes returns at least one node with expected fields."""
        resp = client.get("/api/nodes", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert "node" in data[0]
        assert "account_count" in data[0]
        assert "chain_valid" in data[0]


# ── Health ────────────────────────────────────────────────────────
# GET /api/health — unauthenticated system status.

class TestHealth:
    def test_health_endpoint(self, client):
        """Health check returns version and node count."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "3.0.0"
        assert "nodes_available" in data
