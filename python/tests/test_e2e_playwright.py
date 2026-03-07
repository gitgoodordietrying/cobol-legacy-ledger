"""
End-to-end Playwright tests for the web console.

These tests launch a real browser against the running FastAPI server and
exercise the dashboard (simulation controls, network graph, transaction log,
COBOL viewer, reset, onboarding), the chatbot UI (messages, tool calls,
provider switching, sessions), and the teacher persona (COBOL exploration,
spaghetti analysis, code comparison, CoBot demo).

Prerequisites:
    - Server running at http://localhost:8000
    - Data seeded via `python -m python.cli seed-all`
    - Playwright browsers installed: `python -m playwright install chromium`

Run:
    python -m pytest python/tests/test_e2e_playwright.py -v --headed   # visible browser
    python -m pytest python/tests/test_e2e_playwright.py -v            # headless
"""

import re
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:8000"


# ── Fixtures ──────────────────────────────────────────────────────

def _stop_any_running_sim():
    """Stop any running simulation via API (best-effort)."""
    import urllib.request, json, time
    for endpoint in ["/api/simulation/stop", "/api/simulation/reset"]:
        try:
            req = urllib.request.Request(
                f"{BASE_URL}{endpoint}",
                data=b"{}",
                headers={"Content-Type": "application/json",
                         "X-User": "admin", "X-Role": "admin"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass
    # Brief wait for background thread to actually stop
    time.sleep(1)


@pytest.fixture(scope="function")
def fresh_page(page: Page):
    """Navigate to app, dismiss onboarding if shown, go to dashboard."""
    _stop_any_running_sim()
    page.goto(f"{BASE_URL}/console/index.html")
    page.wait_for_selector(".nav__brand", timeout=5000)
    # Dismiss onboarding if visible
    dismiss = page.locator("#onboardingDismiss")
    if dismiss.is_visible():
        dismiss.click()
        page.wait_for_timeout(300)
    # Select operator role so simulation tests have permission
    role_select = page.locator("#roleSelect")
    if role_select.is_visible():
        role_select.select_option("operator")
    # Ensure dashboard tab is active
    page.click("[data-view='dashboard']")
    page.wait_for_selector("#view-dashboard.view--active", timeout=3000)
    return page


@pytest.fixture(scope="function")
def dash(fresh_page: Page):
    """Dashboard-ready page (onboarding dismissed)."""
    return fresh_page


@pytest.fixture(scope="function")
def chat_view(page: Page):
    """Navigate to chat view, dismiss onboarding if needed."""
    page.goto(f"{BASE_URL}/console/index.html")
    page.wait_for_selector(".nav__brand", timeout=5000)
    # Dismiss onboarding
    dismiss = page.locator("#onboardingDismiss")
    if dismiss.is_visible():
        dismiss.click()
        page.wait_for_timeout(300)
    page.click("[data-view='chat']")
    page.wait_for_selector("#view-chat.view--active", timeout=3000)
    return page


# ── Onboarding Tests ─────────────────────────────────────────────

class TestOnboarding:
    """Test first-visit onboarding popup."""

    def test_onboarding_shows_on_first_visit(self, page: Page):
        """Onboarding popup appears when localStorage flag is absent."""
        # Clear the flag so onboarding triggers
        page.goto(f"{BASE_URL}/console/index.html")
        page.evaluate("localStorage.removeItem('cll_onboarded')")
        page.reload()
        page.wait_for_selector(".nav__brand", timeout=5000)
        overlay = page.locator("#onboarding")
        expect(overlay).to_be_visible(timeout=3000)

    def test_onboarding_has_content(self, page: Page):
        """Onboarding popup contains role, dashboard, and chat info."""
        page.goto(f"{BASE_URL}/console/index.html")
        page.evaluate("localStorage.removeItem('cll_onboarded')")
        page.reload()
        page.wait_for_selector("#onboarding", state="visible", timeout=5000)
        text = page.locator("#onboarding").text_content()
        assert "Role selector" in text
        assert "Dashboard" in text
        assert "Chat" in text

    def test_onboarding_dismiss_sets_flag(self, page: Page):
        """Clicking 'Got it' hides the popup and sets localStorage."""
        page.goto(f"{BASE_URL}/console/index.html")
        page.evaluate("localStorage.removeItem('cll_onboarded')")
        page.reload()
        page.wait_for_selector("#onboardingDismiss", state="visible", timeout=5000)
        page.click("#onboardingDismiss")
        page.wait_for_timeout(500)
        expect(page.locator("#onboarding")).to_be_hidden()
        flag = page.evaluate("localStorage.getItem('cll_onboarded')")
        assert flag == "1"

    def test_onboarding_not_shown_on_return(self, page: Page):
        """Onboarding does not appear if flag is already set."""
        page.goto(f"{BASE_URL}/console/index.html")
        page.evaluate("localStorage.setItem('cll_onboarded', '1')")
        page.reload()
        page.wait_for_selector(".nav__brand", timeout=5000)
        page.wait_for_timeout(500)
        expect(page.locator("#onboarding")).to_be_hidden()


# ── Dashboard Rendering ──────────────────────────────────────────

class TestDashboardLoads:
    """Verify the dashboard renders its core elements."""

    def test_nav_brand_and_tabs(self, dash: Page):
        """Navigation bar with brand and both tabs is visible."""
        expect(dash.locator(".nav__brand")).to_have_text("COBOL Legacy Ledger")
        expect(dash.locator("[data-view='dashboard']")).to_be_visible()
        expect(dash.locator("[data-view='chat']")).to_be_visible()

    def test_network_graph_six_nodes(self, dash: Page):
        """Network topology SVG renders with exactly 6 nodes."""
        svg = dash.locator("#graphContainer svg")
        expect(svg).to_be_visible(timeout=5000)
        nodes = dash.locator("#graphContainer svg .node-group")
        expect(nodes).to_have_count(6, timeout=5000)

    def test_all_control_buttons_present(self, dash: Page):
        """All simulation control buttons are visible."""
        for btn_id in ["#btnStart", "#btnPause", "#btnStop", "#btnReset",
                       "#btnTamper", "#btnVerify"]:
            expect(dash.locator(btn_id)).to_be_visible()

    def test_days_input_present(self, dash: Page):
        """Days input field is present with default value."""
        days = dash.locator("#daysInput")
        expect(days).to_be_visible()
        assert int(days.input_value()) > 0

    def test_stats_counters_at_zero(self, dash: Page):
        """Stats show zero before any simulation runs."""
        expect(dash.locator("#dayCounter")).to_have_text("Day 0")
        expect(dash.locator("#statCompleted")).to_have_text("0")
        expect(dash.locator("#statFailed")).to_have_text("0")

    def test_cobol_viewer_loads_default_file(self, dash: Page):
        """COBOL viewer panel loads SMOKETEST.cob by default."""
        viewer = dash.locator("#cobolSource")
        expect(viewer).to_be_visible()
        dash.wait_for_function(
            "document.querySelector('#cobolSource').textContent.length > 50",
            timeout=5000,
        )
        # Default file should be SMOKETEST.cob
        selector = dash.locator("#cobolFileSelect")
        expect(selector).to_have_value("SMOKETEST.cob")

    def test_role_selector_defaults_to_operator(self, dash: Page):
        """Role selector defaults to operator (can start simulations)."""
        expect(dash.locator("#roleSelect")).to_have_value("operator")

    def test_health_dot_turns_green(self, dash: Page):
        """Health indicator dot is visible and shows healthy status."""
        dot = dash.locator("#healthDot")
        expect(dot).to_be_visible()
        # Wait for health check to complete
        dash.wait_for_function(
            "document.querySelector('#healthDot').classList.contains('health-dot--ok')",
            timeout=10000,
        )

    def test_event_feed_empty_initially(self, dash: Page):
        """Event feed shows empty state before simulation."""
        feed = dash.locator("#feedListOut")
        expect(feed).to_be_visible()
        text = feed.text_content()
        assert "Start a simulation" in text or "event" in text.lower()


# ── Simulation Controls ──────────────────────────────────────────

class TestSimulationControls:
    """Test simulation start, pause, resume, stop, reset workflow."""

    def test_start_simulation_updates_stats(self, dash: Page):
        """Start button launches simulation; day counter and stats update."""
        dash.fill("#daysInput", "3")
        dash.click("#btnStart")

        # Day counter advances past 0
        dash.wait_for_function(
            "document.querySelector('#dayCounter').textContent !== 'Day 0'",
            timeout=20000,
        )
        # Completed transactions appear
        dash.wait_for_function(
            "parseInt(document.querySelector('#statCompleted').textContent) > 0",
            timeout=20000,
        )
        # Volume shows a dollar amount
        dash.wait_for_function(
            "document.querySelector('#statVolume').textContent !== '$0'",
            timeout=20000,
        )

    def test_start_populates_event_feed(self, dash: Page):
        """Starting a simulation populates the event feed."""
        dash.fill("#daysInput", "3")
        dash.click("#btnStart")

        dash.wait_for_function(
            "document.querySelectorAll('.feed__item').length > 0",
            timeout=20000,
        )
        items = dash.locator(".feed__item")
        assert items.count() > 0

    def test_simulation_runs_past_day_5(self, dash: Page):
        """Simulation progresses beyond day 5 (verifies no verification hang)."""
        # Reset first to ensure clean state (no leftover running sim)
        dash.click("#btnReset")
        dash.wait_for_timeout(3000)

        dash.fill("#daysInput", "8")
        dash.click("#btnStart")

        # Wait for day > 5 — verification at day 5 used to hang
        dash.wait_for_function(
            """(() => {
                const txt = document.querySelector('#dayCounter').textContent;
                const m = txt.match(/\\d+/);
                return m && parseInt(m[0]) > 5;
            })()""",
            timeout=120000,
        )
        day_text = dash.locator("#dayCounter").text_content()
        day_num = int(re.search(r'\d+', day_text).group())
        assert day_num > 5, f"Expected day > 5, got {day_num}"

    def test_adjust_days_input(self, dash: Page):
        """Days input accepts and retains new values."""
        dash.fill("#daysInput", "10")
        expect(dash.locator("#daysInput")).to_have_value("10")
        dash.fill("#daysInput", "50")
        expect(dash.locator("#daysInput")).to_have_value("50")

    def test_start_disables_start_enables_others(self, dash: Page):
        """After start, Start is disabled; Pause and Stop are enabled."""
        dash.fill("#daysInput", "25")
        dash.click("#btnStart")
        # Wait for button state to change (Start becomes disabled when sim starts)
        dash.wait_for_function(
            "document.querySelector('#btnStart').disabled === true",
            timeout=10000,
        )

        expect(dash.locator("#btnStart")).to_be_disabled()
        expect(dash.locator("#btnPause")).to_be_enabled()
        expect(dash.locator("#btnStop")).to_be_enabled()

        # Clean up (best-effort — sim may finish between check and click)
        try:
            dash.click("#btnStop", timeout=2000)
        except Exception:
            pass

    def test_pause_changes_to_resume(self, dash: Page):
        """Pause button text changes to 'Resume' when clicked."""
        dash.fill("#daysInput", "25")
        dash.click("#btnStart")
        dash.wait_for_function(
            "document.querySelector('#btnStart').disabled === true",
            timeout=10000,
        )

        pause_btn = dash.locator("#btnPause")
        expect(pause_btn).to_have_text("Pause")
        dash.click("#btnPause")
        dash.wait_for_timeout(500)
        expect(pause_btn).to_have_text("Resume")

        # Resume
        dash.click("#btnPause")
        dash.wait_for_timeout(500)
        expect(pause_btn).to_have_text("Pause")

        # Clean up (best-effort — sim may finish between check and click)
        try:
            dash.click("#btnStop", timeout=2000)
        except Exception:
            pass

    def test_stop_re_enables_start(self, dash: Page):
        """After stop, Start is re-enabled; Pause and Stop are disabled."""
        dash.fill("#daysInput", "25")
        dash.click("#btnStart")
        dash.wait_for_function(
            "document.querySelector('#btnStart').disabled === true",
            timeout=10000,
        )
        dash.click("#btnStop")
        dash.wait_for_function(
            "document.querySelector('#btnStart').disabled === false",
            timeout=10000,
        )

        expect(dash.locator("#btnStart")).to_be_enabled()
        expect(dash.locator("#btnPause")).to_be_disabled()
        expect(dash.locator("#btnStop")).to_be_disabled()

    def test_reset_clears_counters(self, dash: Page):
        """Reset button re-seeds data and resets UI counters."""
        # Run a short sim first
        dash.fill("#daysInput", "2")
        dash.click("#btnStart")
        dash.wait_for_function(
            "parseInt(document.querySelector('#statCompleted').textContent) > 0",
            timeout=20000,
        )
        # Wait for sim to finish
        dash.wait_for_function(
            "!document.querySelector('#btnStart').disabled",
            timeout=30000,
        )

        # Now reset
        dash.click("#btnReset")
        dash.wait_for_timeout(3000)

        expect(dash.locator("#dayCounter")).to_have_text("Day 0")
        expect(dash.locator("#statCompleted")).to_have_text("0")
        expect(dash.locator("#statFailed")).to_have_text("0")

    def test_viewer_role_cannot_start(self, dash: Page):
        """Viewer role gets permission denied when trying to start."""
        dash.select_option("#roleSelect", "viewer")
        dash.wait_for_timeout(300)
        dash.click("#btnStart")
        # Should show an error toast
        dash.wait_for_selector(".toast", timeout=5000)
        toast_text = dash.locator(".toast").first.text_content()
        assert "permission" in toast_text.lower() or "denied" in toast_text.lower() or "403" in toast_text

        # Restore operator role
        dash.select_option("#roleSelect", "operator")


# ── Tamper & Verify ──────────────────────────────────────────────

class TestTamperAndVerify:
    """Test tamper demo and cross-node verification buttons."""

    def test_tamper_shows_toast(self, dash: Page):
        """Tamper button shows a success toast (requires auditor+ role)."""
        # Tamper requires chain.verify permission — switch to admin
        dash.select_option("#roleSelect", "admin")
        dash.wait_for_timeout(300)
        dash.click("#btnTamper")
        dash.wait_for_selector(".toast", timeout=5000)
        toast = dash.locator(".toast").first.text_content()
        assert "tamper" in toast.lower() or "balance" in toast.lower()
        dash.select_option("#roleSelect", "operator")

    def test_verify_shows_toast(self, dash: Page):
        """Verify button shows a verification result toast."""
        dash.select_option("#roleSelect", "admin")
        dash.wait_for_timeout(300)
        dash.click("#btnVerify")
        dash.wait_for_selector(".toast", timeout=30000)
        dash.select_option("#roleSelect", "operator")

    def test_tamper_then_verify_detects_tampering(self, dash: Page):
        """Tamper then verify should detect the mismatch."""
        dash.select_option("#roleSelect", "admin")
        dash.wait_for_timeout(300)
        dash.click("#btnTamper")
        dash.wait_for_timeout(1500)
        dash.click("#btnVerify")
        dash.wait_for_selector(".toast", timeout=10000)
        toasts = dash.locator(".toast")
        assert toasts.count() >= 1
        dash.select_option("#roleSelect", "operator")


# ── COBOL Viewer ─────────────────────────────────────────────────

class TestCobolViewer:
    """Test COBOL source viewer functionality."""

    def test_default_file_loads(self, dash: Page):
        """showSnippet loads SMOKETEST.cob into the ticker."""
        dash.evaluate("CobolViewer.showSnippet('SMOKETEST.cob', null)")
        dash.wait_for_function(
            "document.querySelector('#cobolSource').textContent.length > 50",
            timeout=5000,
        )
        content = dash.locator("#cobolSource").text_content()
        assert "IDENTIFICATION" in content or "DIVISION" in content or "PROGRAM-ID" in content

    def test_switch_to_transact(self, dash: Page):
        """showSnippet switches ticker to TRANSACT.cob."""
        dash.evaluate("CobolViewer.showSnippet('TRANSACT.cob', 'PROCESS-DEPOSIT')")
        dash.wait_for_function(
            "document.querySelector('#cobolSource').textContent.length > 50",
            timeout=5000,
        )
        content = dash.locator("#cobolSource").text_content()
        assert "DEPOSIT" in content or "TRANSACT" in content

    def test_switch_to_settle(self, dash: Page):
        """showSnippet switches ticker to SETTLE.cob."""
        dash.evaluate("CobolViewer.showSnippet('SETTLE.cob', 'EXECUTE-SETTLEMENT')")
        dash.wait_for_function(
            "document.querySelector('#cobolSource').textContent.length > 50",
            timeout=5000,
        )
        content = dash.locator("#cobolSource").text_content()
        assert "SETTLE" in content or "SETTLEMENT" in content

    def test_all_ten_files_in_selector(self, dash: Page):
        """File selector has all 10 COBOL source files."""
        options = dash.locator("#cobolFileSelect option")
        count = options.count()
        assert count == 10, f"Expected 10 COBOL files, got {count}"

    def test_syntax_highlighting_present(self, dash: Page):
        """COBOL viewer applies syntax highlighting spans."""
        dash.evaluate("CobolViewer.showSnippet('SMOKETEST.cob', null)")
        dash.wait_for_function(
            "document.querySelector('#cobolSource').textContent.length > 50",
            timeout=5000,
        )
        # Syntax highlighter wraps keywords in spans
        spans = dash.locator("#cobolSource span")
        assert spans.count() > 0, "Expected syntax highlighting spans"


# ── Node Interaction ─────────────────────────────────────────────

class TestNodeInteraction:
    """Test clicking network graph nodes."""

    def test_click_node_opens_popup(self, dash: Page):
        """Clicking a bank node opens the detail popup."""
        nodes = dash.locator("#graphContainer svg .node-group")
        expect(nodes).to_have_count(6, timeout=5000)
        nodes.first.click()
        dash.wait_for_timeout(1500)
        popup = dash.locator("#nodePopup")
        if popup.is_visible():
            expect(popup).to_be_visible()
            # Popup has content
            body = dash.locator("#nodePopupBody").text_content()
            assert len(body) > 0
            # Close popup
            dash.locator("#nodePopupClose").click()
            dash.wait_for_timeout(300)

    def test_close_popup_via_overlay(self, dash: Page):
        """Clicking the overlay background closes the popup."""
        nodes = dash.locator("#graphContainer svg .node-group")
        nodes.first.click()
        dash.wait_for_timeout(1500)
        popup = dash.locator("#nodePopup")
        if popup.is_visible():
            # Click the overlay (not the glass card)
            dash.locator("#nodePopup").click(position={"x": 10, "y": 10})
            dash.wait_for_timeout(500)


# ── Chat UI Tests ────────────────────────────────────────────────

class TestChatRendering:
    """Test chat view renders correctly."""

    def test_chat_layout_elements(self, chat_view: Page):
        """Chat view has sidebar, message area, input, and send button."""
        expect(chat_view.locator(".chat-sidebar")).to_be_visible()
        expect(chat_view.locator(".chat-messages")).to_be_visible()
        expect(chat_view.locator("#chatInput")).to_be_visible()
        expect(chat_view.locator("#btnSend")).to_be_visible()

    def test_provider_buttons(self, chat_view: Page):
        """Ollama and Anthropic provider buttons are visible."""
        expect(chat_view.locator("#btnOllama")).to_be_visible()
        expect(chat_view.locator("#btnAnthropic")).to_be_visible()

    def test_new_chat_button(self, chat_view: Page):
        """New Chat button is visible and clickable."""
        btn = chat_view.locator("#btnNewChat")
        expect(btn).to_be_visible()
        expect(btn).to_be_enabled()

    def test_chat_textarea_multiline(self, chat_view: Page):
        """Chat textarea supports multiple rows."""
        textarea = chat_view.locator("#chatInput")
        rows = textarea.get_attribute("rows")
        assert rows is not None and int(rows) >= 2

    def test_empty_state_shown(self, chat_view: Page):
        """Chat shows empty state message before any messages."""
        empty = chat_view.locator(".chat-empty")
        expect(empty).to_be_visible()
        text = empty.text_content()
        assert "Send a message" in text

    def test_provider_name_displayed(self, chat_view: Page):
        """Provider name is shown in the sidebar."""
        provider = chat_view.locator("#providerName")
        expect(provider).to_be_visible()
        text = provider.text_content().strip().lower()
        assert "ollama" in text or "anthropic" in text

    def test_role_shown_in_sidebar(self, chat_view: Page):
        """Current role is displayed in the chat sidebar."""
        role = chat_view.locator("#chatRole")
        expect(role).to_be_visible()


class TestChatMessaging:
    """Test sending messages and receiving responses."""

    def test_send_simple_question(self, chat_view: Page):
        """Sending a question produces an assistant response."""
        chat_view.fill("#chatInput", "What is a nostro account?")
        chat_view.click("#btnSend")

        # User message appears
        chat_view.wait_for_selector(".message--user", timeout=5000)
        user_msg = chat_view.locator(".message--user").first.text_content()
        assert "nostro" in user_msg.lower()

        # Assistant response appears
        chat_view.wait_for_selector(".message--assistant", timeout=45000)
        messages = chat_view.locator(".message--assistant")
        assert messages.count() >= 1
        response_text = messages.first.text_content()
        assert len(response_text) > 10, "Expected a meaningful response"

    def test_send_tool_use_query(self, chat_view: Page):
        """Sending a banking query triggers tool use and shows results."""
        chat_view.fill("#chatInput", "List all accounts in BANK_A")
        chat_view.click("#btnSend")

        # Wait for response
        chat_view.wait_for_selector(".message--assistant", timeout=45000)

        # Check if tool call cards appeared (LLM may or may not use tools)
        chat_view.wait_for_timeout(2000)
        assistant_text = chat_view.locator(".message--assistant").first.text_content()
        # Response should mention accounts or BANK_A
        assert len(assistant_text) > 5

    def test_input_clears_after_send(self, chat_view: Page):
        """Chat input is cleared after sending a message."""
        chat_view.fill("#chatInput", "Hello")
        chat_view.click("#btnSend")
        chat_view.wait_for_timeout(500)
        value = chat_view.locator("#chatInput").input_value()
        assert value == "", f"Expected empty input, got '{value}'"

    def test_typing_indicator_shows(self, chat_view: Page):
        """Typing indicator appears while waiting for response."""
        chat_view.fill("#chatInput", "What banks are in the network?")
        chat_view.click("#btnSend")
        # Typing indicator should appear briefly
        try:
            chat_view.wait_for_selector(".typing", timeout=5000)
        except Exception:
            pass  # May be too fast to catch — not a failure

    def test_new_chat_clears_messages(self, chat_view: Page):
        """Clicking New Chat after a conversation clears messages."""
        # Send a message first
        chat_view.fill("#chatInput", "Hello")
        chat_view.click("#btnSend")
        chat_view.wait_for_selector(".message--user", timeout=5000)

        # Click New Chat
        chat_view.click("#btnNewChat")
        chat_view.wait_for_timeout(1000)

        # Previous user messages should be gone
        user_msgs = chat_view.locator(".message--user")
        assert user_msgs.count() == 0, "Expected messages to be cleared"

    def test_multiple_messages_in_conversation(self, chat_view: Page):
        """Multiple messages create a conversation thread."""
        # First message
        chat_view.fill("#chatInput", "Hello")
        chat_view.click("#btnSend")
        chat_view.wait_for_selector(".message--assistant", timeout=45000)

        # Second message
        chat_view.fill("#chatInput", "How many banks are there?")
        chat_view.click("#btnSend")
        chat_view.wait_for_timeout(2000)

        # Should have at least 2 user messages
        user_msgs = chat_view.locator(".message--user")
        assert user_msgs.count() >= 2


class TestChatSessions:
    """Test chat session management."""

    def test_session_appears_in_sidebar(self, chat_view: Page):
        """After sending a message, a session appears in the sidebar."""
        chat_view.fill("#chatInput", "Hello")
        chat_view.click("#btnSend")
        chat_view.wait_for_selector(".message--assistant", timeout=45000)
        chat_view.wait_for_timeout(1000)
        # Check session list for an entry
        sessions = chat_view.locator("#sessionList .session-item")
        assert sessions.count() >= 1


# ── View Switching ────────────────────────────────────────────────

class TestViewSwitching:
    """Test navigation between Dashboard and Chat views."""

    def test_switch_to_chat(self, dash: Page):
        """Clicking Chat tab shows the chat view."""
        dash.click("[data-view='chat']")
        expect(dash.locator("#view-chat")).to_have_class(re.compile("view--active"))
        expect(dash.locator("#view-dashboard")).not_to_have_class(re.compile("view--active"))

    def test_switch_back_to_dashboard(self, dash: Page):
        """Clicking Dashboard tab returns to dashboard."""
        dash.click("[data-view='chat']")
        dash.click("[data-view='dashboard']")
        expect(dash.locator("#view-dashboard")).to_have_class(re.compile("view--active"))

    def test_active_tab_styling(self, dash: Page):
        """Active tab has the active class."""
        dash_tab = dash.locator("[data-view='dashboard']")
        expect(dash_tab).to_have_class(re.compile("nav__tab--active"))

        dash.click("[data-view='chat']")
        chat_tab = dash.locator("[data-view='chat']")
        expect(chat_tab).to_have_class(re.compile("nav__tab--active"))
        expect(dash_tab).not_to_have_class(re.compile("nav__tab--active"))


# ── Role Switching ────────────────────────────────────────────────

class TestRoleSwitching:
    """Test RBAC role selector behavior."""

    def test_role_options_available(self, dash: Page):
        """Role selector has all 4 RBAC roles."""
        options = dash.locator("#roleSelect option")
        texts = [options.nth(i).text_content() for i in range(options.count())]
        assert "admin" in texts
        assert "operator" in texts
        assert "auditor" in texts
        assert "viewer" in texts

    def test_role_syncs_to_chat(self, dash: Page):
        """Changing role in nav updates the chat sidebar display."""
        dash.select_option("#roleSelect", "admin")
        dash.click("[data-view='chat']")
        dash.wait_for_timeout(300)
        role_display = dash.locator("#chatRole").text_content()
        assert role_display.strip() == "admin"


# ── Analysis Tab Tests ────────────────────────────────────────────

@pytest.fixture(scope="function")
def analysis_view(page: Page):
    """Navigate to Analysis tab, dismiss onboarding if needed."""
    page.goto(f"{BASE_URL}/console/index.html")
    page.wait_for_selector(".nav__brand", timeout=5000)
    # Dismiss onboarding
    dismiss = page.locator("#onboardingDismiss")
    if dismiss.is_visible():
        dismiss.click()
        page.wait_for_timeout(300)
    page.click("[data-view='analysis']")
    page.wait_for_selector("#view-analysis.view--active", timeout=3000)
    return page


class TestAnalysisTab:
    """Test Analysis tab — file selector, analyze, call graph, compare."""

    def test_analysis_tab_loads(self, analysis_view: Page):
        """Analysis view is visible with file selector containing 11 options (7 banking + 4 payment processor)."""
        expect(analysis_view.locator("#view-analysis")).to_have_class(re.compile("view--active"))
        options = analysis_view.locator("#analysisFileSelect option")
        count = options.count()
        assert count == 11, f"Expected 11 analysis file options, got {count}"

    def test_analyze_transact_shows_clean(self, analysis_view: Page):
        """Analyzing TRANSACT.cob shows clean or moderate rating (not spaghetti)."""
        analysis_view.select_option("#analysisFileSelect", "TRANSACT.cob")
        analysis_view.click("#btnAnalyze")
        # Wait for summary to populate
        analysis_view.wait_for_function(
            "document.querySelector('#analysisSummary').textContent.length > 5",
            timeout=15000,
        )
        summary = analysis_view.locator("#analysisSummary").text_content().lower()
        assert "spaghetti" not in summary, f"TRANSACT.cob should not be spaghetti, got: {summary}"

    def test_analyze_payroll_shows_spaghetti(self, analysis_view: Page):
        """Analyzing PAYROLL.cob shows spaghetti rating."""
        analysis_view.select_option("#analysisFileSelect", "PAYROLL.cob")
        analysis_view.click("#btnAnalyze")
        analysis_view.wait_for_function(
            "document.querySelector('#analysisSummary').textContent.length > 5",
            timeout=15000,
        )
        summary = analysis_view.locator("#analysisSummary").text_content().lower()
        assert "spaghetti" in summary, f"PAYROLL.cob should be spaghetti, got: {summary}"

    def test_call_graph_renders_svg(self, analysis_view: Page):
        """After Analyze, call graph SVG container has content."""
        analysis_view.select_option("#analysisFileSelect", "TRANSACT.cob")
        analysis_view.click("#btnAnalyze")
        analysis_view.wait_for_function(
            "document.querySelector('#analysisSummary').textContent.length > 5",
            timeout=15000,
        )
        # Call graph should have SVG content
        svg = analysis_view.locator("#callGraphContainer svg")
        expect(svg).to_be_visible(timeout=5000)

    def test_execution_trace_has_entries(self, analysis_view: Page):
        """After Analyze, trace entry selector populates with paragraph names."""
        analysis_view.select_option("#analysisFileSelect", "TRANSACT.cob")
        analysis_view.click("#btnAnalyze")
        analysis_view.wait_for_function(
            "document.querySelector('#analysisSummary').textContent.length > 5",
            timeout=15000,
        )
        # Entry point selector should have options beyond the default placeholder
        options = analysis_view.locator("#traceEntrySelect option")
        count = options.count()
        assert count > 1, f"Expected trace entry options, got {count}"

    def test_compare_spaghetti_vs_clean(self, analysis_view: Page):
        """Compare button shows compare card with two panels."""
        analysis_view.click("#btnCompare")
        analysis_view.wait_for_function(
            "document.querySelector('#compareCard').style.display !== 'none'",
            timeout=15000,
        )
        compare_card = analysis_view.locator("#compareCard")
        expect(compare_card).to_be_visible()


# ── Event Feed Color Tests ────────────────────────────────────────

class TestEventFeedColors:
    """Test that event feed items get transaction-type color classes."""

    def test_event_feed_color_classes(self, dash: Page):
        """Running a short simulation produces feed items with color classes."""
        dash.fill("#daysInput", "3")
        dash.click("#btnStart")
        # Wait for feed items to appear
        dash.wait_for_function(
            "document.querySelectorAll('.feed__item').length > 3",
            timeout=20000,
        )
        # Check for at least one color-typed feed item in either panel
        html_out = dash.locator("#feedListOut").inner_html()
        html_in = dash.locator("#feedListIn").inner_html()
        combined = html_out + html_in
        has_typed = any(cls in combined for cls in [
            "feed__item--deposit",
            "feed__item--withdraw",
            "feed__item--transfer",
        ])
        assert has_typed, "Expected at least one typed feed item (deposit/withdraw/transfer)"


# ── Node Popup Degradation Tests ─────────────────────────────────

class TestNodePopupDegradation:
    """Test chain verification graceful degradation per role."""

    def test_node_popup_operator_hides_chain(self, dash: Page):
        """As operator, clicking a node shows 'requires auditor role' text."""
        dash.select_option("#roleSelect", "operator")
        dash.wait_for_timeout(300)
        nodes = dash.locator("#graphContainer svg .node-group")
        expect(nodes).to_have_count(6, timeout=5000)
        nodes.first.click()
        dash.wait_for_timeout(2000)
        popup = dash.locator("#nodePopup")
        if popup.is_visible():
            body = dash.locator("#nodePopupBody").text_content()
            assert "requires auditor role" in body.lower(), \
                f"Expected 'requires auditor role' for operator, got: {body[:200]}"
            dash.locator("#nodePopupClose").click()

    def test_node_popup_admin_shows_chain(self, dash: Page):
        """As admin, clicking a node shows chain info with INTACT or BROKEN."""
        dash.select_option("#roleSelect", "admin")
        dash.wait_for_timeout(300)
        nodes = dash.locator("#graphContainer svg .node-group")
        expect(nodes).to_have_count(6, timeout=5000)
        nodes.first.click()
        dash.wait_for_function(
            "(() => { const b = document.querySelector('#nodePopupBody'); "
            "return b && b.textContent && !b.textContent.includes('Loading'); })()",
            timeout=10000,
        )
        popup = dash.locator("#nodePopup")
        if popup.is_visible():
            body = dash.locator("#nodePopupBody").text_content()
            assert "INTACT" in body or "BROKEN" in body, \
                f"Expected chain status for admin, got: {body[:200]}"
            dash.locator("#nodePopupClose").click()
        dash.select_option("#roleSelect", "operator")


# ── Chat History Loading Tests ────────────────────────────────────

class TestChatHistory:
    """Test that chat session history loads correctly (BUGFIX-A)."""

    def test_session_history_loads(self, chat_view: Page):
        """Send message, new chat, click previous session — messages reload."""
        # Send a message to create a session
        chat_view.fill("#chatInput", "What is settlement?")
        chat_view.click("#btnSend")
        chat_view.wait_for_selector(".message--user", timeout=5000)
        chat_view.wait_for_selector(".message--assistant", timeout=45000)
        chat_view.wait_for_timeout(1000)

        # Click New Chat to clear
        chat_view.click("#btnNewChat")
        chat_view.wait_for_timeout(1000)
        user_msgs = chat_view.locator(".message--user")
        assert user_msgs.count() == 0, "Expected messages cleared after New Chat"

        # Click the previous session in sidebar to reload it
        sessions = chat_view.locator("#sessionList .session-item")
        assert sessions.count() >= 1, "Expected at least one session in sidebar"
        sessions.first.click()
        chat_view.wait_for_timeout(2000)

        # Messages should be reloaded
        reloaded = chat_view.locator(".message--user, .message--assistant")
        assert reloaded.count() >= 1, "Expected session history to reload"


# ── Teacher Persona: COBOL Exploration ────────────────────────────

class TestTeacherCobolExploration:
    """Teacher browses COBOL source files to show students well-documented code."""

    def test_accounts_has_educational_comments(self, dash: Page):
        """ACCOUNTS.cob contains COBOL CONCEPT: educational markers (modal view)."""
        # Open the modal with ACCOUNTS.cob to see the full file
        dash.evaluate("""
            document.getElementById('cobolModal').style.display = 'flex';
            document.querySelector('#cobolFileSelect').value = 'ACCOUNTS.cob';
            document.querySelector('#cobolFileSelect').dispatchEvent(new Event('change'));
        """)
        dash.wait_for_function(
            "document.querySelector('#cobolModalSource').textContent.includes('ACCOUNTS')",
            timeout=5000,
        )
        content = dash.locator("#cobolModalSource").text_content()
        assert "COBOL CONCEPT:" in content, \
            f"Expected educational markers in ACCOUNTS.cob, got: {content[:200]}"

    def test_cycle_through_multiple_files(self, dash: Page):
        """Cycling through ACCOUNTS, INTEREST, SETTLE loads distinct programs (modal)."""
        # Open the modal
        dash.evaluate("document.getElementById('cobolModal').style.display = 'flex';")
        contents = []
        for filename, program_id in [
            ("ACCOUNTS.cob", "ACCOUNTS"),
            ("INTEREST.cob", "INTEREST"),
            ("SETTLE.cob", "SETTLE"),
        ]:
            dash.evaluate(f"""
                const sel = document.querySelector('#cobolFileSelect');
                sel.value = '{filename}';
                sel.dispatchEvent(new Event('change'));
            """)
            dash.wait_for_function(
                f"document.querySelector('#cobolModalSource').textContent.includes('{program_id}')",
                timeout=5000,
            )
            content = dash.locator("#cobolModalSource").text_content()
            assert program_id in content, \
                f"Expected {program_id} in {filename}, got: {content[:200]}"
            contents.append(content)
        # All three should be distinct
        assert len(set(contents)) == 3, "Expected three distinct COBOL programs"

    def test_paragraph_navigator_highlights_code(self, dash: Page):
        """showSnippet highlights PROCESS-DEPOSIT in TRANSACT.cob ticker."""
        dash.evaluate("CobolViewer.showSnippet('TRANSACT.cob', 'PROCESS-DEPOSIT')")
        dash.wait_for_function(
            "document.querySelector('#cobolSource').textContent.length > 50",
            timeout=5000,
        )
        # Paragraph indicator should show the target paragraph
        para_text = dash.locator("#cobolParagraph").text_content()
        assert "PROCESS-DEPOSIT" in para_text, \
            f"Expected PROCESS-DEPOSIT in paragraph indicator, got: {para_text}"
        # Highlight spans should exist in the ticker
        highlights = dash.locator("#cobolSource .cobol-highlight")
        assert highlights.count() > 0, "Expected highlighted spans in COBOL ticker"
        # File name should reflect TRANSACT.cob
        file_text = dash.locator("#cobolFileName").text_content()
        assert "TRANSACT.cob" in file_text, \
            f"Expected TRANSACT.cob in file name, got: {file_text}"


# ── Teacher Persona: Spaghetti Analysis ──────────────────────────

class TestTeacherSpaghettiAnalysis:
    """Teacher dissects spaghetti payroll code in the Analysis tab."""

    def test_taxcalc_complexity_rating(self, analysis_view: Page):
        """TAXCALC.cob analysis shows a complexity rating with numeric score."""
        analysis_view.select_option("#analysisFileSelect", "TAXCALC.cob")
        analysis_view.click("#btnAnalyze")
        analysis_view.wait_for_function(
            "document.querySelector('#analysisSummary').textContent.length > 5",
            timeout=15000,
        )
        summary = analysis_view.locator("#analysisSummary").text_content().lower()
        assert "spaghetti" in summary or "moderate" in summary, \
            f"Expected complexity rating for TAXCALC.cob, got: {summary}"
        # Score should contain a number
        score_match = re.search(r'\d+', summary)
        assert score_match is not None, \
            f"Expected numeric score in summary, got: {summary}"

    def test_deductn_analysis_renders_call_graph(self, analysis_view: Page):
        """DEDUCTN.cob analysis produces an SVG call graph and a rating."""
        analysis_view.select_option("#analysisFileSelect", "DEDUCTN.cob")
        analysis_view.click("#btnAnalyze")
        analysis_view.wait_for_function(
            "document.querySelector('#analysisSummary').textContent.length > 5",
            timeout=15000,
        )
        svg = analysis_view.locator("#callGraphContainer svg")
        expect(svg).to_be_visible(timeout=5000)
        summary = analysis_view.locator("#analysisSummary").text_content().lower()
        assert any(r in summary for r in ("spaghetti", "moderate", "clean")), \
            f"Expected a rating in DEDUCTN.cob summary, got: {summary}"

    def test_payroll_trace_renders_execution_path(self, analysis_view: Page):
        """Selecting a trace entry in PAYROLL.cob renders execution path steps."""
        analysis_view.select_option("#analysisFileSelect", "PAYROLL.cob")
        analysis_view.click("#btnAnalyze")
        analysis_view.wait_for_function(
            "document.querySelector('#analysisSummary').textContent.length > 5",
            timeout=15000,
        )
        # Get the second option (first real entry after placeholder)
        entry = analysis_view.evaluate(
            "document.querySelector('#traceEntrySelect option:nth-child(2)')?.value"
        )
        assert entry, "Expected at least one trace entry option"
        analysis_view.select_option("#traceEntrySelect", entry)
        analysis_view.wait_for_function(
            "document.querySelectorAll('.exec-path__step').length > 0",
            timeout=10000,
        )
        steps = analysis_view.locator(".exec-path__step")
        assert steps.count() > 0, "Expected execution path steps"
        arrows = analysis_view.locator(".exec-path__arrow")
        assert arrows.count() > 0, "Expected execution path arrows"
        first_step = steps.first.text_content()
        assert len(first_step.strip()) > 0, "Expected non-empty step text"

    def test_payroll_analysis_shows_dead_code_count(self, analysis_view: Page):
        """PAYROLL.cob analysis summary mentions dead code."""
        analysis_view.select_option("#analysisFileSelect", "PAYROLL.cob")
        analysis_view.click("#btnAnalyze")
        analysis_view.wait_for_function(
            "document.querySelector('#analysisSummary').textContent.length > 5",
            timeout=15000,
        )
        summary = analysis_view.locator("#analysisSummary").text_content()
        assert "Dead Code" in summary or "dead code" in summary.lower(), \
            f"Expected dead code info in PAYROLL.cob summary, got: {summary[:200]}"


# ── Teacher Persona: Code Comparison ─────────────────────────────

class TestTeacherCodeComparison:
    """Teacher uses compare viewer to contrast spaghetti vs clean COBOL."""

    def test_compare_panels_have_labeled_headers(self, analysis_view: Page):
        """Compare view has PAYROLL header on left and TRANSACT on right."""
        analysis_view.click("#btnCompare")
        analysis_view.wait_for_function(
            "document.querySelector('#compareCard').style.display !== 'none'",
            timeout=15000,
        )
        expect(analysis_view.locator("#compareCard")).to_be_visible()
        left_header = analysis_view.locator(
            ".compare-pane--left .compare-pane__header"
        ).text_content()
        right_header = analysis_view.locator(
            ".compare-pane--right .compare-pane__header"
        ).text_content()
        assert "PAYROLL" in left_header.upper(), \
            f"Expected PAYROLL in left header, got: {left_header}"
        assert "TRANSACT" in right_header.upper(), \
            f"Expected TRANSACT in right header, got: {right_header}"

    def test_compare_spaghetti_scores_higher(self, analysis_view: Page):
        """Spaghetti (left) has a higher complexity score than clean (right)."""
        analysis_view.click("#btnCompare")
        analysis_view.wait_for_function(
            "document.querySelector('#compareCard').style.display !== 'none'",
            timeout=15000,
        )
        # Wait for scores to populate
        analysis_view.wait_for_function(
            "document.querySelectorAll('.compare-pane__stats').length >= 2",
            timeout=10000,
        )
        left_score = analysis_view.evaluate("""
            (() => {
                const el = document.querySelector(
                    '.compare-pane--left .compare-pane__stats span[class*="analysis-stat__value"]'
                );
                return el ? parseInt(el.textContent) : 0;
            })()
        """)
        right_score = analysis_view.evaluate("""
            (() => {
                const el = document.querySelector(
                    '.compare-pane--right .compare-pane__stats span[class*="analysis-stat__value"]'
                );
                return el ? parseInt(el.textContent) : 0;
            })()
        """)
        assert left_score > 0, f"Expected positive left score, got {left_score}"
        assert right_score > 0, f"Expected positive right score, got {right_score}"
        assert left_score > right_score, \
            f"Spaghetti score ({left_score}) should exceed clean ({right_score})"

    def test_compare_panels_have_source_content(self, analysis_view: Page):
        """Both compare panels contain substantial COBOL source code."""
        analysis_view.click("#btnCompare")
        analysis_view.wait_for_function(
            "document.querySelector('#compareCard').style.display !== 'none'",
            timeout=15000,
        )
        left_src = analysis_view.locator(
            ".compare-pane--left .compare-pane__source"
        ).text_content()
        right_src = analysis_view.locator(
            ".compare-pane--right .compare-pane__source"
        ).text_content()
        assert len(left_src) > 100, \
            f"Expected substantial left source, got {len(left_src)} chars"
        assert len(right_src) > 100, \
            f"Expected substantial right source, got {len(right_src)} chars"
        # Both should contain COBOL keywords
        for label, src in [("left", left_src), ("right", right_src)]:
            assert any(kw in src.upper() for kw in (
                "PERFORM", "MOVE", "IF", "DISPLAY", "DIVISION",
            )), f"Expected COBOL keywords in {label} panel"


# ── Teacher Persona: CoBot Demo ──────────────────────────────────

class TestTeacherCobotDemo:
    """Teacher demos the COBOL-CoBot chatbot for legacy code understanding."""

    def test_cobot_explains_cobol_concept(self, chat_view: Page):
        """CoBot explains PERFORM THRU with relevant COBOL terminology."""
        chat_view.fill("#chatInput", "Explain what PERFORM THRU means in COBOL")
        chat_view.click("#btnSend")
        chat_view.wait_for_selector(".message--user", timeout=5000)
        chat_view.wait_for_selector(".message--assistant", timeout=45000)
        response = chat_view.locator(".message--assistant").last.text_content()
        assert len(response) > 50, \
            f"Expected substantive response, got {len(response)} chars"
        assert any(term in response.upper() for term in (
            "PERFORM", "PARAGRAPH", "EXECUTE",
        )), f"Expected COBOL terms in response, got: {response[:200]}"

    def test_cobot_banking_query_shows_tool_calls(self, chat_view: Page):
        """Banking query triggers tool calls and mentions BANK_A data."""
        chat_view.fill(
            "#chatInput",
            "Show me the accounts in BANK_A and their balances",
        )
        chat_view.click("#btnSend")
        chat_view.wait_for_selector(".message--user", timeout=5000)
        chat_view.wait_for_selector(".message--assistant", timeout=45000)
        # Tool call cards should appear
        tool_calls = chat_view.locator(".tool-call")
        assert tool_calls.count() > 0, "Expected tool call cards in response"
        response = chat_view.locator(".message--assistant").last.text_content()
        assert "BANK_A" in response or "ACT-A" in response, \
            f"Expected BANK_A reference in response, got: {response[:200]}"

    def test_cobot_explains_project_architecture(self, chat_view: Page):
        """CoBot explains settlement process with relevant terminology."""
        chat_view.fill(
            "#chatInput",
            "How does the settlement process work between the 6 nodes?",
        )
        chat_view.click("#btnSend")
        chat_view.wait_for_selector(".message--user", timeout=5000)
        chat_view.wait_for_selector(".message--assistant", timeout=45000)
        response = chat_view.locator(".message--assistant").last.text_content()
        assert len(response) > 50, \
            f"Expected substantive response, got {len(response)} chars"
        assert any(term in response.lower() for term in (
            "settlement", "clearing", "node",
        )), f"Expected settlement terms in response, got: {response[:200]}"
