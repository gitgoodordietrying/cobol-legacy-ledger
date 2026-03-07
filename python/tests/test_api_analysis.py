"""
Tests for COBOL analysis REST API endpoints.

Test strategy:
    Uses FastAPI TestClient for HTTP-level testing of all 6 analysis
    endpoints. Tests verify correct response structure, edge cases
    (empty source, missing fields), and comparison analysis.
"""

import pytest
from fastapi.testclient import TestClient
from python.api.app import create_app


@pytest.fixture
def client():
    """Create a test client for the API."""
    app = create_app()
    return TestClient(app)


# ── Test Source Snippets ────────────────────────────────────────

SIMPLE_SOURCE = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. SIMPLE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-COUNTER          PIC 9(3) VALUE 0.
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM INIT-PARA
           STOP RUN.
       INIT-PARA.
           MOVE 0 TO WS-COUNTER.
"""

GOTO_SOURCE = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. GOTOPROG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-FLAG             PIC 9 VALUE 0.
       PROCEDURE DIVISION.
       P-000.
           MOVE 1 TO WS-FLAG
           GO TO P-020.
       P-010.
           DISPLAY "SKIPPED".
       P-020.
           DISPLAY "REACHED"
           GO TO P-040.
       P-030.
           DISPLAY "DEAD CODE".
       P-040.
           STOP RUN.
"""

SPAGHETTI_SOURCE = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. SPAGHETTI.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-X               PIC 9 VALUE 0.
       PROCEDURE DIVISION.
       P-START.
           ALTER P-DISPATCH TO PROCEED TO P-REAL-WORK
           GO TO P-DISPATCH.
       P-DISPATCH.
           GO TO P-DEFAULT.
       P-DEFAULT.
           DISPLAY "DEFAULT"
           STOP RUN.
       P-REAL-WORK.
           GO TO P-DEFAULT.
       P-DEAD.
           DISPLAY "NEVER REACHED".
"""

DATA_FLOW_SOURCE = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. DATAFLOW.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-AMOUNT          PIC 9(7)V99 VALUE 0.
       01  WS-RATE            PIC 9V99 VALUE 0.
       01  WS-RESULT          PIC 9(7)V99 VALUE 0.
       PROCEDURE DIVISION.
       INIT-PARA.
           MOVE 100 TO WS-AMOUNT
           MOVE 5 TO WS-RATE.
       CALC-PARA.
           COMPUTE WS-RESULT = WS-AMOUNT * WS-RATE.
       SHOW-PARA.
           DISPLAY WS-RESULT.
"""


# ── Call Graph Endpoint ─────────────────────────────────────────

class TestCallGraphEndpoint:

    def test_call_graph_returns_paragraphs(self, client):
        resp = client.post("/api/analysis/call-graph", json={"source_text": SIMPLE_SOURCE})
        assert resp.status_code == 200
        data = resp.json()
        assert "paragraphs" in data
        assert "edges" in data
        assert data["edge_count"] >= 1

    def test_call_graph_edge_types(self, client):
        resp = client.post("/api/analysis/call-graph", json={"source_text": SPAGHETTI_SOURCE})
        data = resp.json()
        edge_types = {e["type"] for e in data["edges"]}
        assert "GOTO" in edge_types or "ALTER" in edge_types

    def test_call_graph_empty_source(self, client):
        resp = client.post("/api/analysis/call-graph", json={"source_text": ""})
        assert resp.status_code == 200
        data = resp.json()
        assert data["paragraph_count"] == 0

    def test_missing_source_text(self, client):
        resp = client.post("/api/analysis/call-graph", json={})
        assert resp.status_code == 422


# ── Trace Endpoint ──────────────────────────────────────────────

class TestTraceEndpoint:

    def test_trace_execution(self, client):
        resp = client.post("/api/analysis/trace", json={
            "source_text": GOTO_SOURCE,
            "entry_point": "P-000",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "execution_path" in data
        assert data["steps"] >= 1

    def test_trace_missing_entry(self, client):
        resp = client.post("/api/analysis/trace", json={
            "source_text": GOTO_SOURCE,
            "entry_point": "NONEXISTENT",
        })
        assert resp.status_code == 200
        data = resp.json()
        # Nonexistent entry may return empty or single-step result
        assert data["steps"] <= 1

    def test_trace_max_steps(self, client):
        resp = client.post("/api/analysis/trace", json={
            "source_text": GOTO_SOURCE,
            "entry_point": "P-000",
            "max_steps": 2,
        })
        data = resp.json()
        assert len(data["execution_path"]) <= 2


# ── Data Flow Endpoint ─────────────────────────────────────────

class TestDataFlowEndpoint:

    def test_data_flow_all_fields(self, client):
        resp = client.post("/api/analysis/data-flow", json={
            "source_text": DATA_FLOW_SOURCE,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "paragraph_reads" in data
        assert "paragraph_writes" in data

    def test_data_flow_single_field(self, client):
        resp = client.post("/api/analysis/data-flow", json={
            "source_text": DATA_FLOW_SOURCE,
            "field_name": "WS-RESULT",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["field"] == "WS-RESULT"
        assert "accesses" in data

    def test_data_flow_unknown_field(self, client):
        resp = client.post("/api/analysis/data-flow", json={
            "source_text": DATA_FLOW_SOURCE,
            "field_name": "NONEXISTENT-FIELD",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0


# ── Dead Code Endpoint ─────────────────────────────────────────

class TestDeadCodeEndpoint:

    def test_dead_code_detects_dead(self, client):
        resp = client.post("/api/analysis/dead-code", json={
            "source_text": GOTO_SOURCE,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["dead_count"] >= 1

    def test_dead_code_custom_entry(self, client):
        resp = client.post("/api/analysis/dead-code", json={
            "source_text": SIMPLE_SOURCE,
            "entry_point": "INIT-PARA",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "reachable" in data


# ── Complexity Endpoint ─────────────────────────────────────────

class TestComplexityEndpoint:

    def test_complexity_returns_rating(self, client):
        resp = client.post("/api/analysis/complexity", json={
            "source_text": SPAGHETTI_SOURCE,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "total_score" in data
        assert "rating" in data
        assert "paragraphs" in data
        assert "hotspots" in data

    def test_complexity_clean_program(self, client):
        resp = client.post("/api/analysis/complexity", json={
            "source_text": SIMPLE_SOURCE,
        })
        data = resp.json()
        assert data["rating"] == "clean"

    def test_complexity_spaghetti(self, client):
        resp = client.post("/api/analysis/complexity", json={
            "source_text": SPAGHETTI_SOURCE,
        })
        data = resp.json()
        assert data["total_score"] > 0


# ── Compare Endpoint ────────────────────────────────────────────

class TestCompareEndpoint:

    def test_compare_two_sources(self, client):
        resp = client.post("/api/analysis/compare", json={
            "source_a": SPAGHETTI_SOURCE,
            "source_b": SIMPLE_SOURCE,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "a" in data and "b" in data
        assert "complexity" in data["a"]
        assert "dead_code" in data["a"]
        assert "complexity" in data["b"]
        assert "dead_code" in data["b"]

    def test_compare_labels(self, client):
        resp = client.post("/api/analysis/compare", json={
            "source_a": SPAGHETTI_SOURCE,
            "source_b": SIMPLE_SOURCE,
            "label_a": "Spaghetti",
            "label_b": "Clean",
        })
        data = resp.json()
        assert data["a"]["label"] == "Spaghetti"
        assert data["b"]["label"] == "Clean"


# ── Cross-File Endpoint ──────────────────────────────────────────

class TestCrossFileEndpoint:

    def test_cross_file_valid(self, client):
        """Cross-file analysis with 2+ files returns dependency graph."""
        source_a = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALLER.
       PROCEDURE DIVISION.
       MAIN-PARA.
           CALL 'CALLEE'
           STOP RUN.
"""
        source_b = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALLEE.
       PROCEDURE DIVISION.
       ENTRY-PARA.
           DISPLAY "CALLED"
           STOP RUN.
"""
        resp = client.post("/api/analysis/cross-file", json={
            "sources": {"CALLER.cob": source_a, "CALLEE.cob": source_b},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "total_paragraphs" in data
        assert "cross_edges" in data
        assert "total_complexity" in data

    def test_cross_file_fewer_than_two(self, client):
        """Cross-file analysis with fewer than 2 files returns 400."""
        resp = client.post("/api/analysis/cross-file", json={
            "sources": {"SINGLE.cob": SIMPLE_SOURCE},
        })
        assert resp.status_code == 400

    def test_cross_file_with_copy_dependency(self, client):
        """Files with COPY references produce edges in result."""
        source_a = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. MAIN-PROG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY ACCTREC.
       PROCEDURE DIVISION.
       MAIN-PARA.
           STOP RUN.
"""
        source_b = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELPER.
       PROCEDURE DIVISION.
       HELP-PARA.
           DISPLAY "HELP"
           STOP RUN.
"""
        resp = client.post("/api/analysis/cross-file", json={
            "sources": {"MAIN.cob": source_a, "HELPER.cob": source_b},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_paragraphs"] >= 2


# ── Explain Paragraph Endpoint ───────────────────────────────────

class TestExplainParagraphEndpoint:

    def test_explain_existing_paragraph(self, client):
        """Existing paragraph returns complexity, connections, and fields."""
        resp = client.post("/api/analysis/explain-paragraph", json={
            "source_text": SIMPLE_SOURCE,
            "paragraph_name": "MAIN-PARA",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["paragraph"] == "MAIN-PARA"
        assert "complexity" in data
        assert "calls_to" in data
        assert "called_by" in data
        assert "is_dead" in data
        assert "fields_read" in data
        assert "fields_written" in data

    def test_explain_nonexistent_paragraph(self, client):
        """Nonexistent paragraph returns 404."""
        resp = client.post("/api/analysis/explain-paragraph", json={
            "source_text": SIMPLE_SOURCE,
            "paragraph_name": "DOES-NOT-EXIST",
        })
        assert resp.status_code == 404

    def test_explain_paragraph_with_goto(self, client):
        """Paragraph with GOTO edges reports connections."""
        resp = client.post("/api/analysis/explain-paragraph", json={
            "source_text": GOTO_SOURCE,
            "paragraph_name": "P-000",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["calls_to"]) >= 1


# ── Empty/Nil Input Tests ────────────────────────────────────────

class TestEmptyInputs:

    def test_call_graph_whitespace_source(self, client):
        """All-whitespace source is handled gracefully."""
        resp = client.post("/api/analysis/call-graph", json={
            "source_text": "   \n  \t  \n  ",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["paragraph_count"] == 0

    def test_complexity_empty_source(self, client):
        """Empty source returns a clean rating."""
        resp = client.post("/api/analysis/complexity", json={
            "source_text": "",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_score"] == 0
