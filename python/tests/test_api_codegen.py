"""
Tests for codegen REST API endpoints -- parse, generate, edit, validate.

Test strategy:
    All tests use FastAPI's TestClient without any COBOL-specific data.
    The codegen endpoints are stateless — each request creates fresh parser,
    generator, editor, and validator instances. No temp directories needed.

Test groups:
    - Parse: POST /api/codegen/parse (source text, missing input)
    - Generate: POST /api/codegen/generate (copybook, unknown template)
    - Edit: POST /api/codegen/edit (add paragraph, unknown operation)
    - Validate: POST /api/codegen/validate (source text, missing input)

Fixture isolation:
    Minimal — only a TestClient fixture. Codegen endpoints have no shared state,
    so tests cannot interfere with each other.

Naming convention:
    test_{operation}_{scenario} — e.g., test_parse_source_text, test_generate_unknown_template
"""

import pytest
from fastapi.testclient import TestClient
from python.api.app import create_app


@pytest.fixture
def client():
    """FastAPI test client for codegen endpoints.

    No data directory override needed — codegen endpoints are stateless
    and don't touch the banking data layer.
    """
    app = create_app()
    with TestClient(app) as c:
        yield c


# Minimal valid COBOL source — has all required divisions for parsing.
# Intentionally short: one working-storage field and one paragraph.
SAMPLE_COBOL = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST-PROG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-STATUS PIC XX VALUE "00".
       PROCEDURE DIVISION.
       MAIN-PARAGRAPH.
           DISPLAY "HELLO".
           STOP RUN.
"""


# ── Parse ─────────────────────────────────────────────────────────
# POST /api/codegen/parse — source text or file path to AST summary.

class TestParse:
    def test_parse_source_text(self, client):
        """Parses inline COBOL source and returns program ID and paragraphs."""
        resp = client.post("/api/codegen/parse", json={"source_text": SAMPLE_COBOL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["program_id"] == "TEST-PROG"
        assert "MAIN-PARAGRAPH" in data["paragraphs"]

    def test_parse_no_input(self, client):
        """Returns 400 when neither source_text nor file_path provided."""
        resp = client.post("/api/codegen/parse", json={})
        assert resp.status_code == 400


# ── Generate ──────────────────────────────────────────────────────
# POST /api/codegen/generate — template + params to COBOL source.

class TestGenerate:
    def test_generate_copybook(self, client):
        """Generates a copybook with specified fields."""
        resp = client.post("/api/codegen/generate", json={
            "template": "copybook",
            "name": "TESTREC",
            "params": {"fields": [
                {"name": "TEST-ID", "pic": "X(10)"},
                {"name": "TEST-AMT", "pic": "S9(10)V99"},
            ]},
        })
        assert resp.status_code == 200
        assert "TEST-ID" in resp.json()["source"]

    def test_generate_unknown_template(self, client):
        """Returns 400 for unknown template name."""
        resp = client.post("/api/codegen/generate", json={
            "template": "nonexistent", "name": "FOO",
        })
        assert resp.status_code == 400


# ── Edit ──────────────────────────────────────────────────────────
# POST /api/codegen/edit — AST operation on existing source.

class TestEdit:
    def test_edit_add_paragraph(self, client):
        """Adds a new paragraph to existing source."""
        resp = client.post("/api/codegen/edit", json={
            "source_text": SAMPLE_COBOL,
            "operation": "add_paragraph",
            "params": {
                "name": "NEW-PARAGRAPH",
                "statements": ["DISPLAY \"NEW\""],
            },
        })
        assert resp.status_code == 200
        assert "NEW-PARAGRAPH" in resp.json()["source"]

    def test_edit_unknown_operation(self, client):
        """Returns 400 for unknown edit operation."""
        resp = client.post("/api/codegen/edit", json={
            "source_text": SAMPLE_COBOL,
            "operation": "delete_everything",
            "params": {},
        })
        assert resp.status_code == 400


# ── Validate ──────────────────────────────────────────────────────
# POST /api/codegen/validate — check source against project conventions.

class TestValidate:
    def test_validate_source(self, client):
        """Validates source and returns issues with counts."""
        resp = client.post("/api/codegen/validate", json={"source_text": SAMPLE_COBOL})
        assert resp.status_code == 200
        data = resp.json()
        assert "valid" in data
        assert "issues" in data
        assert isinstance(data["error_count"], int)

    def test_validate_no_input(self, client):
        """Returns 400 when neither source_text nor file_path provided."""
        resp = client.post("/api/codegen/validate", json={})
        assert resp.status_code == 400
