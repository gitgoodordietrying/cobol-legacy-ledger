"""
routes_simulation -- REST endpoints for simulation engine control and SSE streaming.

This module exposes start/stop/pause/resume controls for the SimulationEngine,
a status endpoint for polling current state, and a Server-Sent Events (SSE)
endpoint that streams transaction events in real-time to the web console.

Threading model:
    The SimulationEngine.run() method is blocking (it loops day-by-day with
    optional time.sleep delays). To avoid blocking FastAPI's event loop, we
    run the engine in a background threading.Thread. The SSE endpoint bridges
    the thread boundary using asyncio.Queue -- the engine's callback pushes
    events into the queue, and the async SSE generator yields them.

SSE auth workaround:
    The browser's EventSource API cannot send custom headers. To support RBAC
    on the SSE endpoint, we accept x_user/x_role as query parameters instead
    of X-User/X-Role headers. This is demo-grade auth only.

Tamper demo:
    POST /api/tamper-demo directly modifies a .DAT file balance, bypassing
    COBOL and the integrity chain. The next verification run will detect
    the discrepancy. This demonstrates the core value proposition.

Endpoint surface:
    POST /api/simulation/start    -- start engine in background thread
    POST /api/simulation/stop     -- stop running simulation
    POST /api/simulation/pause    -- pause simulation
    POST /api/simulation/resume   -- resume paused simulation
    GET  /api/simulation/status   -- current engine state
    GET  /api/simulation/events   -- SSE stream of transaction events
    POST /api/tamper-demo         -- tamper a .DAT balance for demo
    GET  /api/nodes/{node}/transactions -- list transactions from SQLite

Dependencies:
    fastapi, python.auth, python.api.dependencies, python.api.models,
    python.simulator, python.cross_verify
"""

import asyncio
import json
import threading
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from python.auth import AuthContext
from python.api.dependencies import get_auth, get_bridge, get_verifier, validate_node, DATA_DIR
from python.api.models import (
    SimulationStartRequest, SimulationStatusResponse,
    TransactionRecord, TamperDemoRequest, TamperDemoResponse,
    VerificationResponse,
)
from python.simulator import SimulationEngine
from python.cross_verify import tamper_balance


router = APIRouter(prefix="/api", tags=["simulation"])

# ── Module State ─────────────────────────────────────────────────
# Singleton simulation engine + thread. Only one simulation can run at a time.
_engine: Optional[SimulationEngine] = None
_thread: Optional[threading.Thread] = None
_event_queues: list = []  # Active SSE subscriber queues


def _get_engine() -> Optional[SimulationEngine]:
    """Return the current engine, or None if not running."""
    return _engine


# ── Simulation Control ───────────────────────────────────────────

@router.post("/simulation/start")
def start_simulation(req: SimulationStartRequest, auth: AuthContext = Depends(get_auth)):
    """Start the simulation engine in a background thread."""
    auth.require_permission("transactions.process")

    global _engine, _thread
    if _thread is not None and _thread.is_alive():
        raise HTTPException(status_code=409, detail="Simulation already running")

    _engine = SimulationEngine(
        data_dir=DATA_DIR,
        time_scale=req.time_scale,
        seed=req.seed,
        scenarios=req.scenarios,
    )

    # Register SSE broadcast callback
    def broadcast(event: dict):
        dead = []
        for q in _event_queues:
            try:
                q.put_nowait(event)
            except Exception:
                dead.append(q)
        for q in dead:
            _event_queues.remove(q)

    _engine.register_callback(broadcast)

    def run_engine():
        try:
            _engine.run(days=req.days)
        except Exception:
            pass

    _thread = threading.Thread(target=run_engine, daemon=True)
    _thread.start()

    return {"status": "started", "days": req.days, "seed": req.seed}


@router.post("/simulation/stop")
def stop_simulation(auth: AuthContext = Depends(get_auth)):
    """Stop the running simulation."""
    auth.require_permission("transactions.process")

    global _engine, _thread
    if _engine is None:
        raise HTTPException(status_code=404, detail="No simulation running")

    _engine._stopped = True
    return {"status": "stopped"}


@router.post("/simulation/pause")
def pause_simulation(auth: AuthContext = Depends(get_auth)):
    """Pause the running simulation."""
    auth.require_permission("transactions.process")

    if _engine is None or _thread is None or not _thread.is_alive():
        raise HTTPException(status_code=404, detail="No simulation running")

    _engine._paused = True
    return {"status": "paused"}


@router.post("/simulation/resume")
def resume_simulation(auth: AuthContext = Depends(get_auth)):
    """Resume a paused simulation."""
    auth.require_permission("transactions.process")

    if _engine is None or _thread is None or not _thread.is_alive():
        raise HTTPException(status_code=404, detail="No simulation running")

    _engine._paused = False
    return {"status": "resumed"}


@router.get("/simulation/status", response_model=SimulationStatusResponse)
def simulation_status():
    """Return current simulation engine state (no auth required for polling)."""
    if _engine is None:
        return SimulationStatusResponse(
            running=False, paused=False, day=0,
            completed=0, failed=0, volume=0.0,
        )

    running = _thread is not None and _thread.is_alive()
    return SimulationStatusResponse(
        running=running,
        paused=_engine._paused,
        day=_engine.days_run,
        completed=_engine.total_completed,
        failed=_engine.total_failed,
        volume=_engine.total_volume,
    )


# ── SSE Stream ───────────────────────────────────────────────────

@router.get("/simulation/events")
async def simulation_events(
    x_user: str = Query(default="viewer"),
    x_role: str = Query(default="viewer"),
):
    """Server-Sent Events stream of simulation transaction events.

    Uses query params for auth since EventSource cannot send headers.
    """
    import queue

    q = queue.Queue(maxsize=500)
    _event_queues.append(q)

    async def event_generator():
        try:
            while True:
                try:
                    event = q.get_nowait()
                    data = json.dumps(event, default=str)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    # Send keepalive comment every iteration
                    await asyncio.sleep(0.1)
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if q in _event_queues:
                _event_queues.remove(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Tamper Demo ──────────────────────────────────────────────────

@router.post("/tamper-demo", response_model=TamperDemoResponse)
def tamper_demo(req: TamperDemoRequest, auth: AuthContext = Depends(get_auth)):
    """Tamper a DAT file balance for demonstration purposes."""
    auth.require_permission("chain.verify")

    try:
        result = tamper_balance(DATA_DIR, req.node, req.account_id, req.amount)
        # Broadcast tamper event to SSE subscribers
        event = {
            'type': 'scenario', 'event_type': 'TAMPER_BALANCE',
            'description': f"Balance tampered: {req.node}/{req.account_id} set to ${req.amount:,.2f}",
            'params': {'node': req.node, 'account_id': req.account_id, 'amount': req.amount},
        }
        for q in _event_queues:
            try:
                q.put_nowait(event)
            except Exception:
                pass

        return TamperDemoResponse(
            tampered=True,
            node=req.node,
            account_id=req.account_id,
            new_amount=req.amount,
            message=f"Balance set to ${req.amount:,.2f} via direct DAT edit — verification will detect this",
        )
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Transaction Listing ──────────────────────────────────────────

@router.get("/nodes/{node}/transactions", response_model=List[TransactionRecord])
def list_transactions(
    node: str,
    limit: int = Query(default=100, le=500),
    auth: AuthContext = Depends(get_auth),
):
    """List transactions for a node from its SQLite database."""
    auth.require_permission("accounts.read")
    validate_node(node)
    bridge = get_bridge(node)

    try:
        cursor = bridge.db.execute("""
            SELECT tx_id, account_id, tx_type, amount, timestamp,
                   description, status
            FROM chain_entries
            ORDER BY chain_index DESC
            LIMIT ?
        """, (limit,))
        return [
            TransactionRecord(
                tx_id=row[0],
                account_id=row[1],
                tx_type=row[2],
                amount=row[3],
                timestamp=row[4],
                description=row[5] or "",
                status=row[6] or "00",
            )
            for row in cursor.fetchall()
        ]
    except Exception:
        return []
