"""
routes_analysis -- REST endpoints for COBOL static analysis tools.

Five endpoints wrapping the cobol_analyzer package: call graph, execution
tracing, data flow, dead code detection, and complexity scoring.

Endpoint surface:
    POST /api/analysis/call-graph   — Build paragraph dependency graph
    POST /api/analysis/trace        — Trace execution path from entry point
    POST /api/analysis/data-flow    — Field read/write analysis
    POST /api/analysis/dead-code    — Unreachable paragraph detection
    POST /api/analysis/complexity   — Per-paragraph complexity scoring
    POST /api/analysis/compare      — Side-by-side complexity comparison

Dependencies:
    fastapi, python.cobol_analyzer
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any

from python.cobol_analyzer import (
    CallGraphAnalyzer, DataFlowAnalyzer, DeadCodeAnalyzer,
    ComplexityAnalyzer, KnowledgeBase,
)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

# Shared analyzer instances (stateless — safe to share)
_cg = CallGraphAnalyzer()
_df = DataFlowAnalyzer()
_dc = DeadCodeAnalyzer()
_cx = ComplexityAnalyzer()
_kb = KnowledgeBase()


# ── Request/Response Models ──────────────────────────────────────

class SourceRequest(BaseModel):
    source_text: str = Field(..., description="COBOL source code to analyze")

class TraceRequest(BaseModel):
    source_text: str
    entry_point: str = Field(..., description="Paragraph name to start tracing from")
    max_steps: int = Field(100, ge=1, le=500)

class DataFlowRequest(BaseModel):
    source_text: str
    field_name: Optional[str] = Field(None, description="Trace a specific field (omit for all)")

class DeadCodeRequest(BaseModel):
    source_text: str
    entry_point: Optional[str] = Field(None, description="Entry paragraph (defaults to first)")

class CompareRequest(BaseModel):
    source_a: str = Field(..., description="First COBOL source (e.g., spaghetti)")
    source_b: str = Field(..., description="Second COBOL source (e.g., clean)")
    label_a: str = Field("Program A", description="Label for first source")
    label_b: str = Field("Program B", description="Label for second source")


# ── Endpoints ────────────────────────────────────────────────────

@router.post("/call-graph")
def call_graph(req: SourceRequest) -> Dict[str, Any]:
    """Build a paragraph dependency graph from COBOL source.

    Returns paragraphs, edges (PERFORM, GO TO, ALTER, PERFORM_THRU,
    FALL_THROUGH), and ALTER targets.
    """
    graph = _cg.analyze(req.source_text)
    return graph.to_dict()


@router.post("/trace")
def trace_execution(req: TraceRequest) -> Dict[str, Any]:
    """Trace execution path from an entry point through GO TO chains.

    Returns ordered list of paragraphs that will execute, following
    GO TO chains, ALTER modifications, and fall-throughs.
    """
    path = _cg.trace_execution(req.source_text, req.entry_point, req.max_steps)
    return {"execution_path": path, "steps": len(path)}


@router.post("/data-flow")
def data_flow(req: DataFlowRequest) -> Dict[str, Any]:
    """Analyze field read/write patterns in COBOL source.

    If field_name is provided, traces that specific field across all
    paragraphs. Otherwise, analyzes all fields.
    """
    if req.field_name:
        trace = _df.trace_field(req.source_text, req.field_name)
        return {"field": req.field_name, "accesses": trace, "count": len(trace)}
    result = _df.analyze(req.source_text)
    return result.to_dict()


@router.post("/dead-code")
def dead_code(req: DeadCodeRequest) -> Dict[str, Any]:
    """Detect unreachable paragraphs in COBOL source.

    Classifies each paragraph as REACHABLE, DEAD, or ALTER_CONDITIONAL.
    """
    result = _dc.analyze(req.source_text, entry_point=req.entry_point)
    return result.to_dict()


@router.post("/complexity")
def complexity(req: SourceRequest) -> Dict[str, Any]:
    """Score each paragraph by complexity (GO TO, ALTER, nested IF, etc.)."""
    result = _cx.analyze(req.source_text)
    return result.to_dict()


@router.post("/compare")
def compare(req: CompareRequest) -> Dict[str, Any]:
    """Compare complexity of two COBOL programs side by side.

    Used by the compare viewer to show spaghetti vs clean code.
    """
    result_a = _cx.analyze(req.source_a)
    result_b = _cx.analyze(req.source_b)
    dead_a = _dc.analyze(req.source_a)
    dead_b = _dc.analyze(req.source_b)

    return {
        "a": {
            "label": req.label_a,
            "complexity": result_a.to_dict(),
            "dead_code": dead_a.to_dict(),
        },
        "b": {
            "label": req.label_b,
            "complexity": result_b.to_dict(),
            "dead_code": dead_b.to_dict(),
        },
    }
