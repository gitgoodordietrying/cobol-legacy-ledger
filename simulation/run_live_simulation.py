"""
Live Simulation Runner — Generates Persona Reports from Real LLM Interactions
==============================================================================

Sends real messages through the chat API to a running Ollama instance, records
every response (text, tool calls, latency), and writes detailed Markdown reports
to simulation/reports/live/.

Unlike pytest (pass/fail), this script captures the FULL conversation and
produces narrative reports that document what the LLM actually said and did.

Prerequisites:
    - Ollama running at localhost:11434 with a tool-capable model
    - FastAPI server running at localhost:8000 with seeded data

Run:
    python simulation/run_live_simulation.py

Output:
    simulation/reports/live/summary.md              — Overall results
    simulation/reports/live/marcus-live.md           — Marcus Chen's LLM session
    simulation/reports/live/sarah-live.md            — Sarah Williams's LLM session
    simulation/reports/live/dev-live.md              — Dev Patel's LLM session
    simulation/reports/live/elena-live.md            — Elena Vasquez's LLM session
"""

import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field

import httpx

BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8000")
OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
REPORT_DIR = Path("simulation/reports/live")

ADMIN = {"X-User": "admin", "X-Role": "admin"}
OPERATOR = {"X-User": "operator", "X-Role": "operator"}
VIEWER = {"X-User": "viewer", "X-Role": "viewer"}


# ── Data Classes ──────────────────────────────────────────────────

@dataclass
class Interaction:
    """A single chat message → response exchange."""
    message: str
    mode: str
    role: str
    response: str = ""
    tool_calls: list = field(default_factory=list)
    session_id: str = ""
    provider: str = ""
    model: str = ""
    latency_s: float = 0.0
    status_code: int = 0
    error: str = ""
    verdict: str = ""  # PASS / FAIL / PARTIAL


@dataclass
class PersonaReport:
    """Collected interactions for one persona."""
    name: str
    title: str
    focus: str
    interactions: list = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0


# ── Helpers ───────────────────────────────────────────────────────

def check_prerequisites() -> tuple[str, str]:
    """Verify Ollama and server are available. Returns (model, version)."""
    # Check Ollama
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        if not models:
            print("ERROR: Ollama running but no models installed.")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: Ollama not available at {OLLAMA_URL}: {e}")
        sys.exit(1)

    # Pick model
    preferred = ["qwen3:8b", "qwen3:30b-a3b", "qwen2.5:3b", "llama3.1", "mistral"]
    model = next((p for p in preferred if p in models), models[0])

    # Check server
    try:
        r = httpx.get(f"{BASE_URL}/api/health", timeout=5)
        version = r.json().get("version", "?")
    except Exception as e:
        print(f"ERROR: Server not available at {BASE_URL}: {e}")
        sys.exit(1)

    return model, version


def switch_provider(client: httpx.Client, model: str) -> dict:
    """Switch to Ollama with the given model."""
    r = client.post("/api/provider/switch", json={
        "provider": "ollama", "model": model,
    }, headers=ADMIN)
    return r.json()


def chat(client: httpx.Client, message: str, mode: str = "direct",
         headers: dict = None) -> Interaction:
    """Send a chat message and record the full response."""
    headers = headers or ADMIN
    role = headers.get("X-Role", "admin")
    ix = Interaction(message=message, mode=mode, role=role)

    t0 = time.time()
    try:
        r = client.post("/api/chat", json={
            "message": message, "mode": mode,
        }, headers=headers)
        ix.latency_s = round(time.time() - t0, 2)
        ix.status_code = r.status_code

        if r.status_code == 200:
            data = r.json()
            ix.response = data.get("response", "")
            ix.tool_calls = data.get("tool_calls", [])
            ix.session_id = data.get("session_id", "")
            ix.provider = data.get("provider", "")
            ix.model = data.get("model", "")
        else:
            ix.error = r.text[:500]
    except Exception as e:
        ix.latency_s = round(time.time() - t0, 2)
        ix.error = str(e)

    return ix


def format_tool_calls(tool_calls: list) -> str:
    """Format tool calls for markdown display."""
    if not tool_calls:
        return "_No tools invoked_"
    lines = []
    for tc in tool_calls:
        name = tc.get("tool_name", "?")
        permitted = tc.get("permitted", False)
        args = tc.get("arguments", {})
        result = tc.get("result", {})
        status = "PERMITTED" if permitted else "DENIED"
        lines.append(f"- **{name}** [{status}]")
        if args:
            lines.append(f"  - Args: `{json.dumps(args, default=str)[:200]}`")
        if isinstance(result, dict):
            # Show key structure, not full data
            keys = list(result.keys())[:8]
            lines.append(f"  - Result keys: `{keys}`")
        elif isinstance(result, str) and len(result) > 0:
            lines.append(f"  - Result: `{result[:150]}...`" if len(result) > 150
                         else f"  - Result: `{result}`")
    return "\n".join(lines)


# ── Persona Simulations ──────────────────────────────────────────

def run_marcus(client: httpx.Client) -> PersonaReport:
    """Marcus Chen — COBOL maintainer testing chatbot understanding."""
    report = PersonaReport(
        name="Marcus Chen",
        title="Senior COBOL Systems Programmer, IBM Z",
        focus="Does the chatbot actually understand COBOL and the banking system?",
    )
    report.start_time = time.time()
    print("\n  Marcus Chen — COBOL Maintainer")

    # 1. List accounts (should trigger list_accounts tool)
    print("    [1/5] Asking to list BANK_A accounts...")
    ix = chat(client, "List all accounts in BANK_A")
    ix.verdict = "PASS" if ix.tool_calls and any(
        tc["tool_name"] == "list_accounts" for tc in ix.tool_calls
    ) else "PARTIAL" if ix.response else "FAIL"
    report.interactions.append(ix)

    # 2. Verify chain integrity (should trigger verify_chain)
    print("    [2/5] Asking to verify BANK_A chain...")
    ix = chat(client, "Verify the integrity chain for BANK_A. Use the verify_chain tool.")
    ix.verdict = "PASS" if ix.tool_calls and any(
        tc["tool_name"] in ("verify_chain", "verify_all_nodes") for tc in ix.tool_calls
    ) else "PARTIAL" if ix.response else "FAIL"
    report.interactions.append(ix)

    # 3. General COBOL knowledge (should NOT need tools)
    print("    [3/5] Asking about nostro accounts...")
    ix = chat(client, "What is a nostro account in banking? Answer in 2-3 sentences.")
    ix.verdict = "PASS" if len(ix.response) > 30 else "FAIL"
    report.interactions.append(ix)

    # 4. Compare complexity (new tool!)
    print("    [4/5] Comparing PAYROLL.cob vs TRANSACT.cob complexity...")
    ix = chat(client, "Compare the complexity of PAYROLL.cob vs TRANSACT.cob using the compare_complexity tool.")
    ix.verdict = "PASS" if ix.tool_calls and any(
        tc["tool_name"] == "compare_complexity" for tc in ix.tool_calls
    ) else "PARTIAL" if ix.response else "FAIL"
    report.interactions.append(ix)

    # 5. Technical COBOL question
    print("    [5/5] Asking about ALTER statement...")
    ix = chat(client, "What is the ALTER statement in COBOL and why is it considered harmful?")
    has_keywords = any(kw in ix.response.lower() for kw in ["alter", "go to", "goto", "branch", "spaghetti"])
    ix.verdict = "PASS" if has_keywords and len(ix.response) > 50 else "PARTIAL" if ix.response else "FAIL"
    report.interactions.append(ix)

    report.end_time = time.time()
    return report


def run_sarah(client: httpx.Client) -> PersonaReport:
    """Sarah Williams — Hiring manager testing the demo experience."""
    report = PersonaReport(
        name="Sarah Williams",
        title="VP Engineering / Hiring Manager, Edward Jones",
        focus="Does this demo work end-to-end in under 5 minutes?",
    )
    report.start_time = time.time()
    print("\n  Sarah Williams — Hiring Manager")

    # 1. First impression — what can you do?
    print("    [1/5] First message: what can you do?")
    ix = chat(client, "Hello, what can you do?")
    ix.verdict = "PASS" if ix.response and ix.session_id else "FAIL"
    report.interactions.append(ix)

    # 2. Session persistence — follow-up in same session
    print("    [2/5] Follow-up: list accounts...")
    session = ix.session_id
    ix2 = chat(client, "Show me the accounts in BANK_B")
    ix2.verdict = "PASS" if ix2.response else "FAIL"
    report.interactions.append(ix2)

    # 3. Check session history exists
    print("    [3/5] Checking session history...")
    ix3 = Interaction(message="[GET /api/chat/history]", mode="api", role="admin")
    t0 = time.time()
    r = client.get(f"/api/chat/history/{session}", headers=ADMIN)
    ix3.latency_s = round(time.time() - t0, 2)
    ix3.status_code = r.status_code
    history = r.json() if r.status_code == 200 else []
    ix3.response = f"Session has {len(history)} messages"
    ix3.verdict = "PASS" if len(history) >= 2 else "FAIL"
    report.interactions.append(ix3)

    # 4. Viewer RBAC — can a limited user still chat?
    print("    [4/5] Testing viewer RBAC...")
    ix = chat(client, "What is this system?", headers=VIEWER)
    ix.verdict = "PASS" if ix.response else "FAIL"
    report.interactions.append(ix)

    # 5. Explain the system for hiring evaluation
    print("    [5/5] Asking for system explanation...")
    ix = chat(client, "Explain this COBOL Legacy Ledger system in 3 sentences. What makes it impressive?")
    relevant = any(kw in ix.response.lower() for kw in ["cobol", "bank", "settlement", "integrity", "hash"])
    ix.verdict = "PASS" if relevant and len(ix.response) > 50 else "PARTIAL" if ix.response else "FAIL"
    report.interactions.append(ix)

    report.end_time = time.time()
    return report


def run_dev(client: httpx.Client) -> PersonaReport:
    """Dev Patel — Tech journalist testing quotable output."""
    report = PersonaReport(
        name="Dev Patel",
        title="Staff Writer, TechCrunch",
        focus="Can I get quotable responses about the system for an article?",
    )
    report.start_time = time.time()
    print("\n  Dev Patel — Tech Journalist")

    # 1. Elevator pitch
    print("    [1/5] Asking for elevator pitch...")
    ix = chat(client, "Explain in 2-3 sentences what this COBOL Legacy Ledger system does and why it matters.")
    relevant = any(kw in ix.response.lower() for kw in ["cobol", "bank", "ledger", "settlement", "node"])
    ix.verdict = "PASS" if relevant and len(ix.response) > 50 else "PARTIAL" if ix.response else "FAIL"
    report.interactions.append(ix)

    # 2. Numbers for the article
    print("    [2/5] Asking for account stats...")
    ix = chat(client, "How many accounts are there across all banks? Use the list_accounts tool to check each bank.")
    ix.verdict = "PASS" if ix.tool_calls else "PARTIAL" if ix.response else "FAIL"
    report.interactions.append(ix)

    # 3. The spaghetti narrative
    print("    [3/5] Asking about spaghetti COBOL...")
    ix = chat(client, "What is the payroll spaghetti COBOL? Tell me the story of PAYROLL.cob.")
    has_story = any(kw in ix.response.lower() for kw in ["spaghetti", "payroll", "go to", "alter", "1974", "jrk", "legacy"])
    ix.verdict = "PASS" if has_story and len(ix.response) > 80 else "PARTIAL" if ix.response else "FAIL"
    report.interactions.append(ix)

    # 4. Compare for visual contrast
    print("    [4/5] Comparing spaghetti vs clean for contrast...")
    ix = chat(client, "Compare PAYROLL.cob vs TRANSACT.cob. Which is more complex and why?")
    ix.verdict = "PASS" if ix.tool_calls and any(
        tc["tool_name"] == "compare_complexity" for tc in ix.tool_calls
    ) else "PARTIAL" if ix.response else "FAIL"
    report.interactions.append(ix)

    # 5. The hook
    print("    [5/5] Asking for the headline...")
    ix = chat(client, "If you had to write a one-sentence headline about this project for a tech article, what would it be?")
    ix.verdict = "PASS" if len(ix.response) > 20 else "FAIL"
    report.interactions.append(ix)

    report.end_time = time.time()
    return report


def run_elena(client: httpx.Client) -> PersonaReport:
    """Elena Vasquez — University teacher testing classroom readiness."""
    report = PersonaReport(
        name="Dr. Elena Vasquez",
        title="Associate Professor, University of Illinois at Chicago",
        focus="Can I use this chatbot and tutor mode in my IS 447 class?",
    )
    report.start_time = time.time()
    print("\n  Dr. Elena Vasquez — University Teacher")

    # 1. Tutor mode — Socratic teaching
    print("    [1/6] Testing tutor mode with PAYROLL.cob...")
    ix = chat(client, "What does the PAYROLL.cob program do?", mode="tutor")
    ix.verdict = "PASS" if len(ix.response) > 30 else "FAIL"
    report.interactions.append(ix)

    # 2. Direct mode — same question for comparison
    print("    [2/6] Same question in direct mode...")
    ix = chat(client, "What does the PAYROLL.cob program do?", mode="direct")
    ix.verdict = "PASS" if len(ix.response) > 30 else "FAIL"
    report.interactions.append(ix)

    # 3. COBOL concept explanation for students
    print("    [3/6] Asking about COBOL divisions...")
    ix = chat(client, "Explain the four COBOL divisions to a student who only knows Python. Use analogies.", mode="tutor")
    has_divisions = any(kw in ix.response.lower() for kw in ["identification", "environment", "data", "procedure"])
    ix.verdict = "PASS" if has_divisions else "PARTIAL" if len(ix.response) > 50 else "FAIL"
    report.interactions.append(ix)

    # 4. Anti-pattern teaching
    print("    [4/6] Asking about GO TO anti-pattern...")
    ix = chat(client, "Why is GO TO considered an anti-pattern? Show me an example from the spaghetti COBOL files.", mode="tutor")
    ix.verdict = "PASS" if ix.tool_calls or (len(ix.response) > 50 and "go to" in ix.response.lower()) else "PARTIAL" if ix.response else "FAIL"
    report.interactions.append(ix)

    # 5. Compare for grading exercise
    print("    [5/6] Compare for classroom exercise...")
    ix = chat(client, "Compare PAYROLL.cob and ACCOUNTS.cob complexity. I want to use this as a grading exercise.", mode="direct")
    ix.verdict = "PASS" if ix.tool_calls and any(
        tc["tool_name"] == "compare_complexity" for tc in ix.tool_calls
    ) else "PARTIAL" if ix.response else "FAIL"
    report.interactions.append(ix)

    # 6. Operator RBAC — student role
    print("    [6/6] Testing operator role (student simulation)...")
    ix = chat(client, "List all accounts in BANK_A", headers=OPERATOR)
    ix.verdict = "PASS" if ix.response else "FAIL"
    report.interactions.append(ix)

    report.end_time = time.time()
    return report


# ── Report Generation ─────────────────────────────────────────────

def write_persona_report(report: PersonaReport, model: str) -> Path:
    """Write a detailed Markdown report for one persona."""
    total_time = round(report.end_time - report.start_time, 1)
    pass_count = sum(1 for ix in report.interactions if ix.verdict == "PASS")
    partial_count = sum(1 for ix in report.interactions if ix.verdict == "PARTIAL")
    fail_count = sum(1 for ix in report.interactions if ix.verdict == "FAIL")
    total = len(report.interactions)
    tool_invocations = sum(len(ix.tool_calls) for ix in report.interactions)
    avg_latency = round(sum(ix.latency_s for ix in report.interactions) / max(total, 1), 1)

    lines = []
    lines.append(f"# {report.name} — Live LLM Session Report")
    lines.append(f"")
    lines.append(f"**{report.title}**")
    lines.append(f"")
    lines.append(f"*Focus: {report.focus}*")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")
    lines.append(f"## Summary")
    lines.append(f"")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Model | `{model}` |")
    lines.append(f"| Total interactions | {total} |")
    lines.append(f"| PASS | {pass_count} |")
    lines.append(f"| PARTIAL | {partial_count} |")
    lines.append(f"| FAIL | {fail_count} |")
    lines.append(f"| Tool invocations | {tool_invocations} |")
    lines.append(f"| Average latency | {avg_latency}s |")
    lines.append(f"| Total session time | {total_time}s |")
    lines.append(f"| Date | {datetime.now().strftime('%Y-%m-%d %H:%M')} |")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    for i, ix in enumerate(report.interactions, 1):
        emoji = {"PASS": "PASS", "PARTIAL": "PARTIAL", "FAIL": "FAIL"}.get(ix.verdict, "?")
        lines.append(f"## Interaction {i} — [{emoji}]")
        lines.append(f"")
        lines.append(f"**User** ({ix.role}, {ix.mode} mode): {ix.message}")
        lines.append(f"")
        lines.append(f"**Latency**: {ix.latency_s}s")
        lines.append(f"")

        if ix.error:
            lines.append(f"**Error**: `{ix.error}`")
            lines.append(f"")
        else:
            lines.append(f"### Tool Calls")
            lines.append(f"")
            lines.append(format_tool_calls(ix.tool_calls))
            lines.append(f"")
            lines.append(f"### LLM Response")
            lines.append(f"")
            lines.append(f"> {ix.response[:2000]}")
            if len(ix.response) > 2000:
                lines.append(f"> ... (truncated, {len(ix.response)} chars total)")
            lines.append(f"")

        lines.append(f"---")
        lines.append(f"")

    # Write file
    slug = report.name.split()[0].lower()
    path = REPORT_DIR / f"{slug}-live.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_summary(reports: list[PersonaReport], model: str, version: str) -> Path:
    """Write the overall summary report."""
    total_interactions = sum(len(r.interactions) for r in reports)
    total_pass = sum(1 for r in reports for ix in r.interactions if ix.verdict == "PASS")
    total_partial = sum(1 for r in reports for ix in r.interactions if ix.verdict == "PARTIAL")
    total_fail = sum(1 for r in reports for ix in r.interactions if ix.verdict == "FAIL")
    total_tools = sum(len(ix.tool_calls) for r in reports for ix in r.interactions)
    total_time = round(sum(r.end_time - r.start_time for r in reports), 1)

    lines = []
    lines.append(f"# Live LLM Simulation — Summary Report")
    lines.append(f"")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")
    lines.append(f"## Environment")
    lines.append(f"")
    lines.append(f"| Setting | Value |")
    lines.append(f"|---------|-------|")
    lines.append(f"| Server | `{BASE_URL}` v{version} |")
    lines.append(f"| LLM Provider | Ollama (local) |")
    lines.append(f"| Model | `{model}` |")
    lines.append(f"| Total time | {total_time}s ({round(total_time/60, 1)} min) |")
    lines.append(f"")
    lines.append(f"## Results")
    lines.append(f"")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Personas tested | {len(reports)} |")
    lines.append(f"| Total interactions | {total_interactions} |")
    lines.append(f"| PASS | **{total_pass}** |")
    lines.append(f"| PARTIAL | {total_partial} |")
    lines.append(f"| FAIL | {total_fail} |")
    lines.append(f"| Tool invocations | {total_tools} |")
    lines.append(f"| Pass rate | {round(total_pass/max(total_interactions,1)*100)}% |")
    lines.append(f"")
    lines.append(f"## Per-Persona Breakdown")
    lines.append(f"")
    lines.append(f"| Persona | Role | Interactions | PASS | PARTIAL | FAIL | Time | Tools |")
    lines.append(f"|---------|------|-------------|------|---------|------|------|-------|")

    for r in reports:
        n = len(r.interactions)
        p = sum(1 for ix in r.interactions if ix.verdict == "PASS")
        par = sum(1 for ix in r.interactions if ix.verdict == "PARTIAL")
        f = sum(1 for ix in r.interactions if ix.verdict == "FAIL")
        t = round(r.end_time - r.start_time, 1)
        tc = sum(len(ix.tool_calls) for ix in r.interactions)
        slug = r.name.split()[0].lower()
        lines.append(f"| [{r.name}]({slug}-live.md) | {r.title.split(',')[0]} | {n} | {p} | {par} | {f} | {t}s | {tc} |")

    lines.append(f"")
    lines.append(f"## Tool Usage Across All Personas")
    lines.append(f"")

    # Aggregate tool usage
    tool_counts: dict[str, int] = {}
    for r in reports:
        for ix in r.interactions:
            for tc in ix.tool_calls:
                name = tc.get("tool_name", "?")
                tool_counts[name] = tool_counts.get(name, 0) + 1

    if tool_counts:
        lines.append(f"| Tool | Times Invoked |")
        lines.append(f"|------|--------------|")
        for name, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| `{name}` | {count} |")
    else:
        lines.append(f"_No tools were invoked across any persona._")

    lines.append(f"")
    lines.append(f"## Verdict")
    lines.append(f"")
    rate = round(total_pass / max(total_interactions, 1) * 100)
    if rate >= 80:
        lines.append(f"The LLM chatbot is **production-ready** for demo purposes. "
                      f"{total_pass}/{total_interactions} interactions passed with real Ollama inference.")
    elif rate >= 50:
        lines.append(f"The LLM chatbot is **partially functional**. "
                      f"{total_pass}/{total_interactions} interactions passed. "
                      f"Tool use and response quality need improvement.")
    else:
        lines.append(f"The LLM chatbot **needs work**. "
                      f"Only {total_pass}/{total_interactions} interactions passed. "
                      f"Review tool definitions and system prompt.")

    lines.append(f"")
    path = REPORT_DIR / "summary.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ── Main ──────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  COBOL Legacy Ledger — Live LLM Simulation")
    print("=" * 60)

    # Prerequisites
    model, version = check_prerequisites()
    print(f"\n  Server: {BASE_URL} v{version}")
    print(f"  Model:  {model}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    with httpx.Client(base_url=BASE_URL, timeout=120) as client:
        # Switch to Ollama
        switch_provider(client, model)
        print(f"  Provider switched to Ollama/{model}")

        # Run all 4 personas
        reports = []

        print("\n" + "-" * 60)
        print("  Running persona simulations...")
        print("-" * 60)

        reports.append(run_marcus(client))
        reports.append(run_sarah(client))
        reports.append(run_dev(client))
        reports.append(run_elena(client))

    # Generate reports
    print("\n" + "-" * 60)
    print("  Generating reports...")
    print("-" * 60)

    for r in reports:
        path = write_persona_report(r, model)
        p = sum(1 for ix in r.interactions if ix.verdict == "PASS")
        print(f"    {r.name}: {path} ({p}/{len(r.interactions)} PASS)")

    summary_path = write_summary(reports, model, version)
    total_pass = sum(1 for r in reports for ix in r.interactions if ix.verdict == "PASS")
    total = sum(len(r.interactions) for r in reports)
    print(f"    Summary: {summary_path}")

    print("\n" + "=" * 60)
    print(f"  DONE — {total_pass}/{total} interactions passed")
    print(f"  Reports: {REPORT_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
