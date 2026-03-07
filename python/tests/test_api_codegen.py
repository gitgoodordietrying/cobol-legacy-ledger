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


# ── Path Traversal Protection ──────────────────────────────────────
# Verify that file_path inputs are restricted to COBOL source dirs.

class TestPathTraversal:
    """Path traversal prevention in parse and validate endpoints."""

    def test_parse_path_traversal_relative(self, client):
        """Relative path traversal (../) is rejected with 403."""
        resp = client.post("/api/codegen/parse", json={
            "file_path": "../../../../etc/passwd",
        })
        assert resp.status_code == 403

    def test_parse_path_traversal_absolute(self, client):
        """Absolute path outside project is rejected with 403."""
        resp = client.post("/api/codegen/parse", json={
            "file_path": "/etc/passwd",
        })
        assert resp.status_code == 403

    def test_validate_path_traversal_relative(self, client):
        """Validate endpoint also blocks path traversal."""
        resp = client.post("/api/codegen/validate", json={
            "file_path": "../../../etc/shadow",
        })
        assert resp.status_code == 403

    def test_validate_path_traversal_absolute(self, client):
        """Validate endpoint blocks absolute paths outside project."""
        resp = client.post("/api/codegen/validate", json={
            "file_path": "/tmp/malicious.cob",
        })
        assert resp.status_code == 403

    def test_parse_valid_cobol_file(self, client):
        """Valid COBOL file path in allowed directory succeeds."""
        resp = client.post("/api/codegen/parse", json={
            "file_path": "COBOL-BANKING/src/SMOKETEST.cob",
        })
        # 200 if file exists, 404 if not — but never 403
        assert resp.status_code in (200, 404)

    def test_parse_path_traversal_within_project(self, client):
        """Path that traverses within project but escapes COBOL dirs is blocked."""
        resp = client.post("/api/codegen/parse", json={
            "file_path": "COBOL-BANKING/src/../../python/api/app.py",
        })
        assert resp.status_code == 403


# ── Generate Templates ──────────────────────────────────────────
# POST /api/codegen/generate — test additional template types.

class TestGenerateTemplates:

    def test_generate_crud_program(self, client):
        """Generates a CRUD program from template."""
        resp = client.post("/api/codegen/generate", json={
            "template": "crud",
            "name": "CUSTMGMT",
            "params": {
                "record_copybook": "CUSTREC",
                "record_name": "CUSTOMER-RECORD",
                "file_name": "CUSTOMERS",
                "id_field": "CUST-ID",
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "source" in data
        assert data["line_count"] > 0

    def test_generate_report_program(self, client):
        """Generates a report program from template."""
        resp = client.post("/api/codegen/generate", json={
            "template": "report",
            "name": "CUSTRPT",
            "params": {
                "input_files": [{"logical_name": "CUSTFILE", "physical_name": "CUSTOMERS.DAT"}],
                "report_types": ["STATEMENT"],
            },
        })
        assert resp.status_code == 200
        assert resp.json()["line_count"] > 0

    def test_generate_batch_program(self, client):
        """Generates a batch processing program from template."""
        resp = client.post("/api/codegen/generate", json={
            "template": "batch",
            "name": "CUSTBATCH",
            "params": {
                "input_file": "CUSTOMERS",
                "input_copybook": "CUSTREC",
                "record_name": "CUSTOMER-RECORD",
            },
        })
        assert resp.status_code == 200
        assert resp.json()["line_count"] > 0

    def test_generate_crud_missing_params(self, client):
        """CRUD template with missing required params returns 400."""
        resp = client.post("/api/codegen/generate", json={
            "template": "crud",
            "name": "BROKEN",
            "params": {},
        })
        assert resp.status_code == 400


# ── Edit Error Paths ────────────────────────────────────────────
# POST /api/codegen/edit — test invalid params for valid operations.

class TestEditErrorPaths:

    def test_edit_add_field_missing_params(self, client):
        """Add field with missing required params returns 400."""
        resp = client.post("/api/codegen/edit", json={
            "source_text": SAMPLE_COBOL,
            "operation": "add_field",
            "params": {},
        })
        assert resp.status_code == 400

    def test_edit_rename_paragraph(self, client):
        """Rename paragraph operation works with valid params."""
        resp = client.post("/api/codegen/edit", json={
            "source_text": SAMPLE_COBOL,
            "operation": "rename_paragraph",
            "params": {"old_name": "MAIN-PARAGRAPH", "new_name": "ENTRY-POINT"},
        })
        assert resp.status_code == 200
        assert "ENTRY-POINT" in resp.json()["source"]
