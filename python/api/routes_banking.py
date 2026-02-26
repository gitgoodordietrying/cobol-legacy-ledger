"""
routes_banking -- REST endpoints for account CRUD, transactions, chain ops, and settlement.

This is the largest route module, exposing 8 endpoints that wrap the existing
bridge, settlement coordinator, and cross-node verifier. Every endpoint enforces
RBAC via the auth dependency and validates node names via the 6-node set.

Endpoint surface:
    GET  /api/nodes                        — List all 6 nodes with status
    GET  /api/nodes/{node}/accounts        — List accounts for a node
    GET  /api/nodes/{node}/accounts/{id}   — Get single account
    POST /api/nodes/{node}/transactions    — Process deposit/withdraw/transfer
    GET  /api/nodes/{node}/chain           — View integrity chain entries
    POST /api/nodes/{node}/chain/verify    — Verify chain integrity
    POST /api/settlement/transfer          — Execute inter-bank settlement
    POST /api/settlement/verify            — Cross-node verification

RBAC model:
    accounts.read        — VIEWER, OPERATOR, AUDITOR, ADMIN
    transactions.process — OPERATOR, ADMIN
    chain.view           — VIEWER, OPERATOR, AUDITOR, ADMIN
    chain.verify         — AUDITOR, ADMIN

Why Pydantic re-mapping at the boundary:
    The bridge returns dicts with keys like "id" (Mode A) or "account_id"
    (Mode B). The route layer normalizes these into consistent Pydantic models
    using `a.get("id", a.get("account_id", ""))` so the API contract is stable
    regardless of which execution mode the bridge uses.

Dependencies:
    fastapi, python.auth, python.api.dependencies, python.api.models
"""

import dataclasses
from typing import List
from fastapi import APIRouter, Depends, HTTPException

from python.auth import AuthContext
from python.api.dependencies import (
    get_auth, get_bridge, get_coordinator, get_verifier, validate_node, VALID_NODES,
)
from python.api.models import (
    AccountResponse, TransactionRequest, TransactionResponse,
    TransferRequest, TransferResponse,
    ChainEntry, ChainVerifyResponse,
    VerificationResponse, NodeInfo,
)

router = APIRouter(prefix="/api", tags=["banking"])


# ── Node Routes ───────────────────────────────────────────────────
# System-wide node listing. Returns status for all 6 nodes.

@router.get("/nodes", response_model=List[NodeInfo])
def list_nodes(auth: AuthContext = Depends(get_auth)):
    """List all 6 banking nodes with account counts and chain status."""
    auth.require_permission("accounts.read")
    nodes = []
    for node_name in sorted(VALID_NODES):
        bridge = get_bridge(node_name)
        accounts = bridge.list_accounts()
        chain_result = bridge.chain.verify_chain()
        nodes.append(NodeInfo(
            node=node_name,
            account_count=len(accounts),
            chain_length=chain_result.get("entries_checked", 0),
            chain_valid=chain_result.get("valid", False),
        ))
    return nodes


# ── Account Routes ────────────────────────────────────────────────
# Per-node account listing and single-account lookup.

@router.get("/nodes/{node}/accounts", response_model=List[AccountResponse])
def list_accounts(node: str, auth: AuthContext = Depends(get_auth)):
    """List all accounts for a node."""
    auth.require_permission("accounts.read")
    validate_node(node)
    bridge = get_bridge(node)
    accounts = bridge.list_accounts()
    return [
        AccountResponse(
            account_id=a.get("id", a.get("account_id", "")),  # Mode A returns "id", Mode B returns "account_id"
            name=a.get("name", ""),
            account_type=a.get("type", ""),
            balance=a.get("balance", 0.0),
            status=a.get("status", ""),
            open_date=a.get("open_date", ""),
            last_activity=a.get("last_activity", ""),
        )
        for a in accounts
    ]


@router.get("/nodes/{node}/accounts/{account_id}", response_model=AccountResponse)
def get_account(node: str, account_id: str, auth: AuthContext = Depends(get_auth)):
    """Get a single account by ID."""
    auth.require_permission("accounts.read")
    validate_node(node)
    bridge = get_bridge(node)
    a = bridge.get_account(account_id)
    if a is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")
    return AccountResponse(
        account_id=a.get("id", a.get("account_id", "")),  # Normalize Mode A/B key difference
        name=a.get("name", ""),
        account_type=a.get("type", ""),
        balance=a.get("balance", 0.0),
        status=a.get("status", ""),
        open_date=a.get("open_date", ""),
        last_activity=a.get("last_activity", ""),
    )


# ── Transaction Routes ────────────────────────────────────────────
# Process deposits, withdrawals, and intra-node transfers.

@router.post("/nodes/{node}/transactions", response_model=TransactionResponse)
def process_transaction(node: str, req: TransactionRequest, auth: AuthContext = Depends(get_auth)):
    """Process a transaction (deposit, withdraw, transfer, interest, or fee).

    1. Validate RBAC (transactions.process required)
    2. Validate node name against 6-node set
    3. Delegate to bridge.process_transaction()
    4. Map result dict to TransactionResponse model

    Returns COBOL status codes: 00=success, 01=NSF, 02=limit, 04=frozen.
    """
    auth.require_permission("transactions.process")
    validate_node(node)
    bridge = get_bridge(node)
    result = bridge.process_transaction(
        account_id=req.account_id,
        tx_type=req.tx_type,
        amount=req.amount,
        description=req.description,
        target_id=req.target_id,
    )
    return TransactionResponse(
        status=result.get("status", "99"),
        tx_id=result.get("tx_id"),
        new_balance=result.get("new_balance"),
        message=result.get("message", ""),
    )


# ── Chain Routes ──────────────────────────────────────────────────
# View and verify the SHA-256 integrity chain for a node.

@router.get("/nodes/{node}/chain", response_model=List[ChainEntry])
def view_chain(node: str, limit: int = 50, offset: int = 0, auth: AuthContext = Depends(get_auth)):
    """View chain entries for a node with pagination."""
    auth.require_permission("chain.view")
    validate_node(node)
    bridge = get_bridge(node)
    entries = bridge.chain.get_chain_for_display(limit=limit, offset=offset)
    return [
        ChainEntry(
            chain_index=e.get("chain_index", 0),
            tx_id=e.get("tx_id", ""),
            account_id=e.get("account_id", ""),
            tx_type=e.get("tx_type", ""),
            amount=e.get("amount", 0.0),
            timestamp=e.get("timestamp", ""),
            tx_hash=e.get("tx_hash", ""),
            prev_hash=e.get("prev_hash", ""),
        )
        for e in entries
    ]


@router.post("/nodes/{node}/chain/verify", response_model=ChainVerifyResponse)
def verify_chain(node: str, auth: AuthContext = Depends(get_auth)):
    """Verify the SHA-256 integrity chain for a node.

    Recomputes every hash in the chain and checks linkage + HMAC signatures.
    Returns valid=False with first_break index if tampering is detected.
    """
    auth.require_permission("chain.verify")
    validate_node(node)
    bridge = get_bridge(node)
    result = bridge.chain.verify_chain()
    return ChainVerifyResponse(
        valid=result.get("valid", False),
        entries_checked=result.get("entries_checked", 0),
        time_ms=result.get("time_ms", 0.0),
        first_break=result.get("first_break"),
        break_type=result.get("break_type"),
    )


# ── Settlement Routes ─────────────────────────────────────────────
# Inter-bank transfer (3-leg settlement) and cross-node verification.

@router.post("/settlement/transfer", response_model=TransferResponse)
def execute_transfer(req: TransferRequest, auth: AuthContext = Depends(get_auth)):
    """Execute an inter-bank settlement transfer.

    1. Debit source account at source bank
    2. Record both legs at clearing house (nostro accounts)
    3. Credit destination account at destination bank

    Each leg is recorded in its node's SHA-256 chain. The settlement reference
    (STL-YYYYMMDD-NNNNNN) links all three legs for cross-node verification.
    """
    auth.require_permission("transactions.process")
    coordinator = get_coordinator()
    result = coordinator.execute_transfer(
        source_bank=req.source_bank,
        source_account=req.source_account,
        dest_bank=req.dest_bank,
        dest_account=req.dest_account,
        amount=req.amount,
        description=req.description,
    )
    return TransferResponse(
        status=result.status,
        settlement_ref=result.settlement_ref,
        source_trx_id=result.source_trx_id,
        dest_trx_id=result.dest_trx_id,
        amount=result.amount,
        steps_completed=result.steps_completed,
        error=result.error,
    )


@router.post("/settlement/verify", response_model=VerificationResponse)
def verify_settlement(auth: AuthContext = Depends(get_auth)):
    """Run cross-node verification across all 6 nodes.

    Three verification layers:
    1. Per-chain hash integrity (structural tampering)
    2. DAT-vs-SQLite balance reconciliation (content tampering)
    3. Cross-node settlement reference matching (distributed consistency)
    """
    auth.require_permission("chain.verify")
    verifier = get_verifier()
    report = verifier.verify_all()
    return VerificationResponse(
        timestamp=report.timestamp,
        chain_integrity=report.chain_integrity,
        chain_lengths=report.chain_lengths,
        all_chains_intact=report.all_chains_intact,
        all_settlements_matched=report.all_settlements_matched,
        settlements_checked=report.settlements_checked,
        settlements_matched=report.settlements_matched,
        settlements_mismatched=report.settlements_mismatched,
        anomalies=report.anomalies,
        verification_time_ms=report.verification_time_ms,
    )
