"""
Tests for the web console — validates static file serving and HTML structure.

Test strategy:
    Uses FastAPI's TestClient to verify that the console SPA and all its assets
    are served correctly. No headless browser needed — we validate HTTP responses,
    content types, and key HTML/JS/CSS markers.

Test groups:
    - Root redirect: / → /console/index.html
    - HTML structure: index.html loads, contains expected elements
    - CSS files: all 5 stylesheets served with correct content type
    - JS files: all 7 scripts served with correct content type
    - COBOL source: .cob files served for the viewer panel
    - API endpoints: simulation status reachable from console context
"""

import os
import pytest
from fastapi.testclient import TestClient

from python.api.app import create_app
from python.api import dependencies as deps
from python.api import routes_simulation as sim_routes
from python.bridge import COBOLBridge


@pytest.fixture
def client(tmp_path):
    """TestClient with temp data and reset state."""
    data_dir = str(tmp_path / "data")
    os.makedirs(os.path.join(data_dir, "BANK_A"), exist_ok=True)
    bridge = COBOLBridge("BANK_A", data_dir=data_dir, force_mode_b=True)
    bridge.seed_demo_data()
    bridge.close()

    original_data_dir = deps.DATA_DIR
    original_force_mode_b = deps.FORCE_MODE_B
    deps.DATA_DIR = data_dir
    deps.FORCE_MODE_B = True
    deps._bridges.clear()
    deps._coordinator = None
    deps._verifier = None
    sim_routes._engine = None
    sim_routes._thread = None
    sim_routes._event_queues.clear()

    app = create_app()
    with TestClient(app) as c:
        yield c

    deps.DATA_DIR = original_data_dir
    deps.FORCE_MODE_B = original_force_mode_b
    deps._bridges.clear()


# ── Root Redirect ────────────────────────────────────────────────

def test_root_redirects_to_console(client):
    """GET / should redirect to /console/index.html."""
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (301, 302, 307, 308), f"Expected redirect, got {resp.status_code}"
    assert "/console/" in resp.headers.get("location", "")


# ── HTML Structure ───────────────────────────────────────────────

def test_console_html_loads(client):
    """GET /console/index.html returns HTML with key structure."""
    resp = client.get("/console/index.html")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")

    html = resp.text
    # Page title
    assert "COBOL Legacy Ledger" in html
    # Nav tabs
    assert 'data-view="dashboard"' in html
    assert 'data-view="chat"' in html
    # Role selector
    assert 'id="roleSelect"' in html
    # Health dot
    assert 'id="healthDot"' in html
    # SVG graph container
    assert 'id="graphContainer"' in html
    # Event feed (outgoing + incoming + system)
    assert 'id="feedListOut"' in html
    assert 'id="feedListSystem"' in html
    # COBOL viewer
    assert 'id="cobolTerminal"' in html
    # Chat input
    assert 'id="chatInput"' in html
    # Chat prompt chips
    assert 'chat-chip' in html
    # API key input
    assert 'id="apiKeyInput"' in html
    # Model selector
    assert 'id="modelSelect"' in html
    # Cross-file analysis card
    assert 'id="crossFileCard"' in html
    # Toast container
    assert 'id="toastContainer"' in html
    # All JS scripts referenced
    assert 'js/utils.js' in html
    assert 'js/api-client.js' in html
    assert 'js/app.js' in html
    assert 'js/network-graph.js' in html
    assert 'js/cobol-viewer.js' in html
    assert 'js/dashboard.js' in html
    assert 'js/chat.js' in html


def test_console_has_simulation_controls(client):
    """HTML contains start/pause/stop buttons and stat counters."""
    resp = client.get("/console/index.html")
    html = resp.text
    assert 'id="btnStart"' in html
    assert 'id="btnPause"' in html
    assert 'id="btnStop"' in html
    assert 'id="dayCounter"' in html
    assert 'id="statCompleted"' in html
    assert 'id="statFailed"' in html
    assert 'id="statVolume"' in html


def test_console_has_cobol_file_selector(client):
    """HTML contains dropdown with all 10 COBOL source files."""
    resp = client.get("/console/index.html")
    html = resp.text
    cobol_files = [
        'SMOKETEST.cob', 'TRANSACT.cob', 'ACCOUNTS.cob', 'VALIDATE.cob',
        'SETTLE.cob', 'SIMULATE.cob', 'INTEREST.cob', 'FEES.cob',
        'RECONCILE.cob', 'REPORTS.cob',
    ]
    for f in cobol_files:
        assert f in html, f"COBOL file {f} not in file selector"


# ── CSS Files ────────────────────────────────────────────────────

CSS_FILES = [
    'variables.css', 'layout.css', 'components.css',
    'dashboard.css', 'chat.css', 'analysis.css',
]

@pytest.mark.parametrize("filename", CSS_FILES)
def test_css_file_served(client, filename):
    """Each CSS file should be served with text/css content type."""
    resp = client.get(f"/console/css/{filename}")
    assert resp.status_code == 200, f"CSS file {filename} returned {resp.status_code}"
    content_type = resp.headers.get("content-type", "")
    assert "css" in content_type or "text" in content_type


def test_css_variables_has_design_tokens(client):
    """variables.css should contain the glass morphism recipe and bank colors."""
    resp = client.get("/console/css/variables.css")
    css = resp.text
    assert "--bg-void" in css
    assert "--glass-blur" in css
    assert "--bank-a" in css
    assert "--bank-e" in css
    assert "--clearing" in css


# ── JS Files ─────────────────────────────────────────────────────

JS_FILES = [
    'utils.js', 'api-client.js', 'app.js',
    'network-graph.js', 'cobol-viewer.js',
    'dashboard.js', 'chat.js',
    'call-graph.js', 'compare-viewer.js', 'analysis.js',
]

@pytest.mark.parametrize("filename", JS_FILES)
def test_js_file_served(client, filename):
    """Each JS file should be served successfully."""
    resp = client.get(f"/console/js/{filename}")
    assert resp.status_code == 200, f"JS file {filename} returned {resp.status_code}"


def test_utils_js_has_expected_functions(client):
    """utils.js should export formatCurrency, escapeHtml, showToast."""
    resp = client.get("/console/js/utils.js")
    js = resp.text
    assert "formatCurrency" in js
    assert "escapeHtml" in js
    assert "showToast" in js
    assert "bankColor" in js


def test_network_graph_has_svg_logic(client):
    """network-graph.js should reference SVG namespace and 6 node positions."""
    resp = client.get("/console/js/network-graph.js")
    js = resp.text
    assert "http://www.w3.org/2000/svg" in js
    assert "BANK_A" in js
    assert "CLEARING" in js
    assert "animateTransaction" in js


def test_dashboard_has_sse_connection(client):
    """dashboard.js should reference EventSource/SSE for real-time streaming."""
    resp = client.get("/console/js/dashboard.js")
    js = resp.text
    assert "createSSE" in js or "EventSource" in js
    assert "simulation/events" in js


def test_cobol_viewer_has_syntax_highlighting(client):
    """cobol-viewer.js should have COBOL keyword highlighting logic."""
    resp = client.get("/console/js/cobol-viewer.js")
    js = resp.text
    assert "PERFORM" in js
    assert "COMPUTE" in js
    assert "cobol-kw" in js
    assert "cobol-cmt" in js


def test_chat_has_message_rendering(client):
    """chat.js should handle message rendering and tool call cards."""
    resp = client.get("/console/js/chat.js")
    js = resp.text
    assert "appendMessage" in js
    assert "tool-call" in js or "appendToolCall" in js
    assert "provider" in js


# ── COBOL Source Serving ─────────────────────────────────────────

def test_cobol_source_smoketest_served(client):
    """SMOKETEST.cob should be served from /cobol-source/ for the viewer."""
    resp = client.get("/cobol-source/SMOKETEST.cob")
    assert resp.status_code == 200
    content = resp.text
    assert "IDENTIFICATION DIVISION" in content
    assert "PROGRAM-ID" in content


def test_cobol_source_transact_served(client):
    """TRANSACT.cob should be served from /cobol-source/."""
    resp = client.get("/cobol-source/TRANSACT.cob")
    assert resp.status_code == 200
    assert "PROCEDURE DIVISION" in resp.text


def test_cobol_source_payroll_served(client):
    """PAYROLL.cob should be served from /cobol-source/payroll/."""
    resp = client.get("/cobol-source/payroll/PAYROLL.cob")
    assert resp.status_code == 200
    assert "IDENTIFICATION DIVISION" in resp.text or "PROGRAM-ID" in resp.text


# ── API reachable from console context ───────────────────────────

def test_simulation_status_from_console(client):
    """GET /api/simulation/status should be reachable (console polls this)."""
    resp = client.get("/api/simulation/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "running" in data
    assert "day" in data


def test_health_endpoint_from_console(client):
    """GET /api/health should be reachable (console health dot polls this)."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


# ── Favicon ──────────────────────────────────────────────────────

def test_favicon_redirect(client):
    """GET /favicon.ico should redirect to /console/favicon.svg."""
    resp = client.get("/favicon.ico", follow_redirects=False)
    assert resp.status_code in (301, 302, 307, 308), f"Expected redirect, got {resp.status_code}"
    assert "/console/favicon.svg" in resp.headers.get("location", "")


def test_favicon_svg_served(client):
    """GET /console/favicon.svg should return 200 with SVG content."""
    resp = client.get("/console/favicon.svg")
    assert resp.status_code == 200
    content_type = resp.headers.get("content-type", "")
    assert "svg" in content_type or "xml" in content_type
    assert "<svg" in resp.text
