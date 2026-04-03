"""
Tests for the mainframe compile endpoint (POST /api/mainframe/compile).

Covers Mode A (real cobc) and Mode B (validation fallback), size limits,
empty source rejection, format options, and CRLF normalization.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from python.api.app import create_app


SAMPLE_COBOL = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. STUDENT.
       PROCEDURE DIVISION.
           DISPLAY "HELLO COBOL".
           STOP RUN.
"""

SAMPLE_COBOL_INVALID = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. STUDENT.
       PROCEDURE DIVISION.
           DISPLAY "HELLO COBOL"
"""


@pytest.fixture
def client():
    """Create a test client for the API."""
    app = create_app()
    return TestClient(app)


class TestCompileEndpoint:
    """Tests for POST /api/mainframe/compile."""

    def test_compile_valid_source(self, client):
        """Valid source returns 200 with mode and success fields."""
        resp = client.post("/api/mainframe/compile", json={
            "source_text": SAMPLE_COBOL,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "mode" in data
        assert "success" in data
        assert data["mode"] in ("compile", "validate")

    def test_compile_empty_source(self, client):
        """Empty source returns 400."""
        resp = client.post("/api/mainframe/compile", json={
            "source_text": "",
        })
        assert resp.status_code == 400
        assert "No source" in resp.json()["detail"]

    def test_compile_whitespace_only(self, client):
        """Whitespace-only source returns 400."""
        resp = client.post("/api/mainframe/compile", json={
            "source_text": "   \n\n  ",
        })
        assert resp.status_code == 400

    def test_compile_source_too_large(self, client):
        """Source exceeding 100KB returns 413."""
        big_source = "A" * 102401
        resp = client.post("/api/mainframe/compile", json={
            "source_text": big_source,
        })
        assert resp.status_code == 413
        assert "too large" in resp.json()["detail"]

    def test_compile_missing_source(self, client):
        """Missing source_text field returns 422 (Pydantic validation)."""
        resp = client.post("/api/mainframe/compile", json={})
        assert resp.status_code == 422

    def test_compile_format_fixed(self, client):
        """Fixed format is accepted."""
        resp = client.post("/api/mainframe/compile", json={
            "source_text": SAMPLE_COBOL,
            "format": "fixed",
        })
        assert resp.status_code == 200

    def test_compile_format_free(self, client):
        """Free format is accepted."""
        resp = client.post("/api/mainframe/compile", json={
            "source_text": SAMPLE_COBOL,
            "format": "free",
        })
        assert resp.status_code == 200

    def test_compile_crlf_normalization(self, client):
        """CRLF line endings are accepted and normalized."""
        crlf_source = SAMPLE_COBOL.replace("\n", "\r\n")
        resp = client.post("/api/mainframe/compile", json={
            "source_text": crlf_source,
        })
        assert resp.status_code == 200

    def test_compile_with_dialect(self, client):
        """Dialect parameter is accepted."""
        resp = client.post("/api/mainframe/compile", json={
            "source_text": SAMPLE_COBOL,
            "dialect": "cobol2014",
        })
        assert resp.status_code == 200

    def test_compile_default_values(self, client):
        """Default format and program_name work correctly."""
        resp = client.post("/api/mainframe/compile", json={
            "source_text": SAMPLE_COBOL,
        })
        data = resp.json()
        assert data["mode"] in ("compile", "validate")


class TestModeBFallback:
    """Tests for Mode B (validation-only) when cobc is not available."""

    def test_mode_b_returns_validate(self, client):
        """When cobc is missing, mode should be 'validate'."""
        with patch("python.api.routes_mainframe._COBC_PATH", None):
            resp = client.post("/api/mainframe/compile", json={
                "source_text": SAMPLE_COBOL,
            })
            data = resp.json()
            assert data["mode"] == "validate"

    def test_mode_b_valid_source_succeeds(self, client):
        """Valid source in Mode B returns success with validation field."""
        with patch("python.api.routes_mainframe._COBC_PATH", None):
            resp = client.post("/api/mainframe/compile", json={
                "source_text": SAMPLE_COBOL,
            })
            data = resp.json()
            assert data["mode"] == "validate"
            assert "validation" in data

    def test_mode_b_response_structure(self, client):
        """Mode B response has all expected fields."""
        with patch("python.api.routes_mainframe._COBC_PATH", None):
            resp = client.post("/api/mainframe/compile", json={
                "source_text": SAMPLE_COBOL,
            })
            data = resp.json()
            assert "success" in data
            assert "return_code" in data
            assert "stdout" in data
            assert "stderr" in data
            assert "mode" in data
