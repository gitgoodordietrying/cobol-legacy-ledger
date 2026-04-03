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
    ComplexityAnalyzer, KnowledgeBase, CrossFileAnalyzer,
)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

# Shared analyzer instances (stateless — safe to share)
_cg = CallGraphAnalyzer()
_df = DataFlowAnalyzer()
_dc = DeadCodeAnalyzer()
_cx = ComplexityAnalyzer()
_kb = KnowledgeBase()
_xf = CrossFileAnalyzer()


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

class CrossFileRequest(BaseModel):
    sources: Dict[str, str] = Field(..., description="Dict mapping filename to COBOL source text")

class ExplainParagraphRequest(BaseModel):
    source_text: str = Field(..., description="COBOL source code")
    paragraph_name: str = Field(..., description="Paragraph name to explain")


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


@router.post("/cross-file")
def cross_file(req: CrossFileRequest) -> Dict[str, Any]:
    """Analyze CALL/COPY dependencies across multiple COBOL source files.

    Accepts a dict of {filename: source_text} and returns a unified
    dependency graph with inter-file CALL_EXTERNAL and COPY_DEPENDENCY edges.
    """
    if len(req.sources) < 2:
        raise HTTPException(status_code=400, detail="Cross-file analysis requires at least 2 files")
    result = _xf.analyze(req.sources)
    return result.to_dict()


@router.post("/explain-paragraph")
def explain_paragraph(req: ExplainParagraphRequest) -> Dict[str, Any]:
    """Run all analyzers on a specific paragraph and return a structured explanation.

    Combines call graph, complexity, dead code, and data flow analysis
    focused on a single paragraph for detailed understanding.
    """
    graph = _cg.analyze(req.source_text)
    complexity = _cx.analyze(req.source_text)
    dead_code = _dc.analyze(req.source_text)
    data_flow = _df.analyze(req.source_text)

    para_name = req.paragraph_name
    if para_name not in graph.paragraphs:
        raise HTTPException(status_code=404, detail=f"Paragraph '{para_name}' not found")

    # Collect edges from/to this paragraph
    edges_from = [{"target": e.target, "type": e.edge_type} for e in graph.get_edges_from(para_name)]
    edges_to = [{"source": e.source, "type": e.edge_type} for e in graph.get_edges_to(para_name)]

    # Complexity for this paragraph
    para_cx = complexity.paragraphs.get(para_name)
    cx_info = {
        "score": para_cx.score if para_cx else 0,
        "factors": para_cx.factors if para_cx else [],
    }

    # Dead code status
    dead_info = dead_code.to_dict()
    is_dead = para_name in dead_info.get("dead", [])
    is_alter_conditional = para_name in dead_info.get("alter_conditional", [])

    # Data flow for this paragraph
    df_dict = data_flow.to_dict()
    fields_read = df_dict.get("paragraph_reads", {}).get(para_name, [])
    fields_written = df_dict.get("paragraph_writes", {}).get(para_name, [])

    return {
        "paragraph": para_name,
        "complexity": cx_info,
        "calls_to": edges_from,
        "called_by": edges_to,
        "is_dead": is_dead,
        "is_alter_conditional": is_alter_conditional,
        "fields_read": fields_read,
        "fields_written": fields_written,
    }
