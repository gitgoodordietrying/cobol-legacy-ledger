"""
Record a demo video of the COBOL Legacy Ledger web console.

Walks through the full story arc:
  1. Dashboard overview — 6-node network at rest
  2. Start simulation — watch transactions flow in real time
  3. Corrupt ledger — tamper with BANK_C's data
  4. Integrity check — SHA-256 catches the fraud
  5. Analysis tab — spaghetti COBOL call graph
  6. Chat tab — quick LLM interaction

Requirements:
  - Server running: python -m uvicorn python.api.app:create_app --factory --port 8000
  - Playwright installed: pip install playwright && playwright install chromium

Usage:
  python site/record-demo.py              # record video
  python site/record-demo.py --screenshots # capture stills only
"""

import argparse
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000/console/"
OUTPUT_DIR = Path(__file__).parent
SCREENSHOT_DIR = OUTPUT_DIR / "screenshots"
VIDEO_DIR = OUTPUT_DIR / "video"


def wait(seconds: float):
    """Pause for pacing — gives the viewer time to read."""
    time.sleep(seconds)


def screenshot(page, name: str):
    """Save a screenshot to the screenshots directory."""
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    page.screenshot(path=str(SCREENSHOT_DIR / f"{name}.png"), full_page=False)
    print(f"  Screenshot: {name}.png")


def dismiss_onboarding(page):
    """Close the onboarding popup if it appears."""
    dismiss = page.locator("#onboardingDismiss")
    if dismiss.is_visible(timeout=2000):
        dismiss.click()
        wait(0.5)


def run_demo(page, screenshots_only=False):
    """Execute the full demo sequence."""

    # ── Scene 1: Dashboard at rest ──────────────────────────────
    print("\n[Scene 1] Dashboard overview")
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    wait(1)
    dismiss_onboarding(page)
    wait(1)
    screenshot(page, "01-dashboard-idle")

    # ── Scene 2: Start simulation ───────────────────────────────
    print("[Scene 2] Start simulation (5 days)")
    page.fill("#daysInput", "5")
    wait(0.5)
    page.click("#btnStart")
    wait(2)
    screenshot(page, "02-simulation-running")

    # Wait for simulation to complete
    print("  Waiting for simulation to finish...")
    page.wait_for_function(
        "document.querySelector('#btnStart') && !document.querySelector('#btnStart').disabled",
        timeout=60000,
    )
    wait(1)
    screenshot(page, "03-simulation-complete")

    # ── Scene 3: Corrupt the ledger ─────────────────────────────
    print("[Scene 3] Corrupt BANK_C's ledger")
    page.click("#btnTamper")
    wait(2)
    screenshot(page, "04-tamper-done")

    # ── Scene 4: Integrity check catches it ─────────────────────
    print("[Scene 4] Integrity check — detect the fraud")
    page.click("#btnVerify")
    wait(3)
    screenshot(page, "05-integrity-breach")

    # ── Scene 5: Analysis tab — spaghetti call graph ────────────
    print("[Scene 5] Analysis tab — PAYROLL.cob spaghetti")
    page.click("[data-view='analysis']")
    wait(1)

    # Select PAYROLL.cob (spaghetti) and analyze
    page.select_option("#analysisFileSelect", "PAYROLL.cob")
    wait(0.5)
    page.click("#btnAnalyze")
    wait(3)
    screenshot(page, "06-analysis-payroll")

    # Compare spaghetti vs clean
    page.click("#btnCompare")
    wait(2)
    screenshot(page, "07-compare-viewer")

    # Close compare, show cross-file
    page.click("#btnCloseCompare")
    wait(0.5)
    page.click("#btnCrossFile")
    wait(2)
    screenshot(page, "08-cross-file")

    # ── Scene 6: Chat tab ───────────────────────────────────────
    print("[Scene 6] Chat tab")
    page.click("[data-view='chat']")
    wait(1)
    screenshot(page, "09-chat-empty")

    print("\nDemo complete!")


def main():
    parser = argparse.ArgumentParser(description="Record COBOL Legacy Ledger demo")
    parser.add_argument("--screenshots", action="store_true", help="Capture stills only (no video)")
    parser.add_argument("--headed", action="store_true", help="Show browser window")
    args = parser.parse_args()

    with sync_playwright() as p:
        launch_opts = {
            "headless": not args.headed,
        }

        if not args.screenshots:
            VIDEO_DIR.mkdir(exist_ok=True)
            browser = p.chromium.launch(**launch_opts)
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                record_video_dir=str(VIDEO_DIR),
                record_video_size={"width": 1440, "height": 900},
            )
        else:
            browser = p.chromium.launch(**launch_opts)
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
            )

        page = context.new_page()

        try:
            run_demo(page, screenshots_only=args.screenshots)
        finally:
            context.close()
            browser.close()

        if not args.screenshots:
            # Playwright saves video on context close
            videos = list(VIDEO_DIR.glob("*.webm"))
            if videos:
                latest = max(videos, key=lambda p: p.stat().st_mtime)
                target = VIDEO_DIR / "demo.webm"
                latest.rename(target)
                print(f"\nVideo saved: {target}")


if __name__ == "__main__":
    main()
