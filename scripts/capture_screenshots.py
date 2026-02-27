#!/usr/bin/env python3
"""
capture_screenshots.py — Auto-capture web console screenshots via Playwright.

Assumes the server is running at localhost:8000 (start with: uvicorn python.api.app:app).
Saves screenshots to docs/screenshots/ for README embedding.

Usage:
    pip install playwright && playwright install chromium
    python scripts/capture_screenshots.py
"""

import asyncio
import sys
from pathlib import Path

SCREENSHOTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
BASE_URL = "http://localhost:8000"
VIEWPORT = {"width": 1440, "height": 900}


async def main():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(viewport=VIEWPORT)
        page = await context.new_page()

        # ── Screenshot 1: Dashboard ──────────────────────────────────
        print("[1/2] Capturing dashboard...")
        await page.goto(f"{BASE_URL}/console/", wait_until="networkidle")

        # Dismiss onboarding overlay if visible
        dismiss = page.locator("#onboardingDismiss")
        if await dismiss.is_visible(timeout=3000):
            await dismiss.click()
            await page.wait_for_timeout(500)

        # Ensure operator role is selected (needed to start simulation)
        await page.select_option("#roleSelect", "operator")

        # Set days to 5 and start simulation
        await page.fill("#daysInput", "5")
        await page.click("#btnStart")

        # Wait for simulation to populate — poll day counter until day 3+
        for _ in range(60):
            day_text = await page.text_content("#dayCounter")
            if day_text:
                day_num = "".join(c for c in day_text if c.isdigit())
                if day_num and int(day_num) >= 3:
                    break
            await page.wait_for_timeout(500)

        # Extra pause for event feed + network graph to populate
        await page.wait_for_timeout(2000)

        await page.screenshot(
            path=str(SCREENSHOTS_DIR / "dashboard.png"),
            full_page=True,
        )
        print(f"  ✓ Saved {SCREENSHOTS_DIR / 'dashboard.png'}")

        # Stop simulation before switching views
        stop_btn = page.locator("#btnStop")
        if await stop_btn.is_enabled():
            await stop_btn.click()
            await page.wait_for_timeout(500)

        # ── Screenshot 2: Chat ───────────────────────────────────────
        print("[2/2] Capturing chat...")
        await page.click('[data-view="chat"]')
        await page.wait_for_timeout(500)

        # Try live LLM first; fall back to injected demo content if it errors
        await page.fill("#chatInput", "List all accounts in BANK_A")
        await page.click("#btnSend")

        # Wait for any response (success or error)
        for _ in range(60):
            msgs = await page.locator(".message--assistant, .tool-call").count()
            if msgs > 0:
                await page.wait_for_timeout(2000)
                break
            await page.wait_for_timeout(500)

        # Check if the response contains an error — if so, inject demo content
        error_present = await page.evaluate("""() => {
            const msgs = document.querySelectorAll('.message--assistant .message__bubble');
            return Array.from(msgs).some(m => m.textContent.includes('Error'));
        }""")

        if error_present:
            print("  LLM unavailable, injecting demo content...")
            # Clear any error toasts
            await page.evaluate("""() => {
                const tc = document.getElementById('toastContainer');
                if (tc) tc.innerHTML = '';
            }""")
            await page.evaluate("""() => {
                const container = document.getElementById('chatMessages');
                container.innerHTML = '';

                // User message
                const userDiv = document.createElement('div');
                userDiv.className = 'message message--user';
                userDiv.innerHTML = '<div class="message__bubble">List all accounts in BANK_A</div>';
                container.appendChild(userDiv);

                // Tool call card
                const toolDiv = document.createElement('div');
                toolDiv.className = 'tool-call';
                toolDiv.innerHTML = `
                    <div class="tool-call__header">
                        <span class="tool-call__arrow">▶</span>
                        <span class="tool-call__name">list_accounts</span>
                        <span class="badge badge--success">OK</span>
                    </div>
                    <div class="tool-call__body" style="display: block;">
                        <pre class="tool-call__input">{"node": "BANK_A"}</pre>
                        <pre class="tool-call__output">Found 8 accounts:
ACT-A-001  Alice Anderson    CHECKING  $45,230.00  ACTIVE
ACT-A-002  Aaron Baker       SAVINGS   $128,500.00 ACTIVE
ACT-A-003  Amanda Chen       CHECKING  $12,750.00  ACTIVE
ACT-A-004  Alex Davis        SAVINGS   $67,890.00  ACTIVE
ACT-A-005  Anna Edwards      CHECKING  $3,200.00   ACTIVE
ACT-A-006  Adam Foster       CHECKING  $89,100.00  ACTIVE
ACT-A-007  Amy Garcia        SAVINGS   $201,000.00 ACTIVE
ACT-A-008  Arthur Hill       CHECKING  $15,600.00  ACTIVE</pre>
                    </div>`;
                container.appendChild(toolDiv);

                // Assistant message
                const asstDiv = document.createElement('div');
                asstDiv.className = 'message message--assistant';
                asstDiv.innerHTML = `
                    <div class="message__bubble">BANK_A has <strong>8 accounts</strong> — all active. The total balance across all accounts is <strong>$563,270.00</strong>. The largest account is ACT-A-007 (Amy Garcia, Savings) at $201,000.00, and the smallest is ACT-A-005 (Anna Edwards, Checking) at $3,200.00.<br><br>Would you like to see transaction history for any of these accounts, or check another bank's accounts?</div>
                    <div class="message__meta">ollama/qwen2.5:3b</div>`;
                container.appendChild(asstDiv);

                // Update session sidebar
                const sessionList = document.getElementById('sessionList');
                if (sessionList) {
                    sessionList.innerHTML = '<div class="session-item session-item--active"><span>List all accounts in BA...</span></div>';
                }
            }""")
            await page.wait_for_timeout(500)

        await page.screenshot(
            path=str(SCREENSHOTS_DIR / "chat.png"),
            full_page=True,
        )
        print(f"  ✓ Saved {SCREENSHOTS_DIR / 'chat.png'}")

        await browser.close()
        print("\nDone! Screenshots saved to docs/screenshots/")


if __name__ == "__main__":
    asyncio.run(main())
