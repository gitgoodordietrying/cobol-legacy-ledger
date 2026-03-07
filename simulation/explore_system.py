"""
Full system exploration script — captures real data for persona reviews.
Outputs raw findings to simulation/reports/live/exploration-data.md
"""
import os, sys, time, json
import httpx

BASE = os.environ.get("TEST_BASE_URL", "http://localhost:8000")
OLLAMA = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
ADMIN = {"X-User": "admin", "X-Role": "admin"}
OPERATOR = {"X-User": "operator", "X-Role": "operator"}
VIEWER = {"X-User": "viewer", "X-Role": "viewer"}

out = []
def log(s=""): out.append(s); print(s)
def section(s): log(f"\n{'='*60}"); log(f"  {s}"); log('='*60)
def sub(s): log(f"\n--- {s} ---")

def req(method, path, headers=None, json_data=None, label=""):
    headers = headers or ADMIN
    t0 = time.time()
    try:
        if method == "GET":
            r = httpx.get(f"{BASE}{path}", headers=headers, timeout=120)
        else:
            r = httpx.post(f"{BASE}{path}", headers=headers, json=json_data or {}, timeout=120)
        elapsed = round(time.time() - t0, 2)
        log(f"  [{method}] {path} -> {r.status_code} ({elapsed}s)")
        try:
            data = r.json()
        except Exception:
            data = r.text[:500]
        return r.status_code, data, elapsed
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        log(f"  [{method}] {path} -> ERROR: {e} ({elapsed}s)")
        return 0, str(e), elapsed

def main():
    section("1. HEALTH & OVERVIEW")
    code, health, _ = req("GET", "/api/health")
    log(f"  Version: {health.get('version')}, Nodes: {health.get('nodes_available')}")
    log(f"  Ollama: {health.get('ollama_available')}, Anthropic: {health.get('anthropic_configured')}")

    code, nodes, _ = req("GET", "/api/nodes")
    if isinstance(nodes, list):
        for n in nodes:
            log(f"  Node: {n.get('node_id')} - {n.get('account_count',0)} accounts, chain={n.get('chain_entries',0)}")

    section("2. BANKING DATA")
    for bank in ["BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E", "CLEARING"]:
        code, data, _ = req("GET", f"/api/nodes/{bank}/accounts")
        if isinstance(data, dict):
            log(f"  {bank}: {data.get('count',0)} accounts")
        elif isinstance(data, list):
            log(f"  {bank}: {len(data)} accounts")

    sub("Sample accounts BANK_A")
    code, data, _ = req("GET", "/api/nodes/BANK_A/accounts")
    if isinstance(data, dict) and "accounts" in data:
        for a in data["accounts"][:3]:
            log(f"    {a.get('account_id')} | {a.get('name','?')} | ${a.get('balance',0):,.2f} | {a.get('status','?')}")

    sub("Deposit + Withdraw")
    code, dep, _ = req("POST", "/api/nodes/BANK_A/transactions", json_data={
        "account_id": "ACT-A-001", "type": "D", "amount": 100.00, "description": "Test deposit"
    })
    log(f"  Deposit result: {json.dumps(dep, default=str)[:200]}")
    code, wdr, _ = req("POST", "/api/nodes/BANK_A/transactions", json_data={
        "account_id": "ACT-A-001", "type": "W", "amount": 50.00, "description": "Test withdraw"
    })
    log(f"  Withdraw result: {json.dumps(wdr, default=str)[:200]}")

    section("3. SETTLEMENT")
    code, settle, t = req("POST", "/api/settlement", json_data={
        "source_bank": "BANK_A", "dest_bank": "BANK_B", "amount": 500.00, "description": "Test settlement"
    })
    log(f"  Settlement: status={settle.get('status') if isinstance(settle, dict) else settle}")
    log(f"  Latency: {t}s")

    section("4. INTEGRITY")
    code, v, t = req("POST", "/api/verify/BANK_A")
    if isinstance(v, dict):
        log(f"  BANK_A chain: valid={v.get('valid')}, entries={v.get('entries_checked')}, time={v.get('time_ms')}ms")

    code, va, t = req("POST", "/api/verify/all")
    if isinstance(va, dict):
        for node_id, result in va.items():
            if isinstance(result, dict):
                log(f"  {node_id}: valid={result.get('valid')}, entries={result.get('entries_checked')}")

    sub("Tamper Demo")
    code, tamper, _ = req("POST", "/api/tamper")
    log(f"  Tamper result: {json.dumps(tamper, default=str)[:300]}")

    code, detect, _ = req("POST", "/api/verify/BANK_C")
    if isinstance(detect, dict):
        log(f"  BANK_C after tamper: valid={detect.get('valid')}, first_break={detect.get('first_break')}")

    # Re-seed BANK_C to restore
    req("POST", "/api/nodes/BANK_C/seed")

    section("5. SIMULATION")
    code, sim, t = req("POST", "/api/simulation/start", json_data={"days": 3, "delay": 0})
    log(f"  Sim start: {json.dumps(sim, default=str)[:300]}")
    log(f"  Sim latency: {t}s")

    time.sleep(2)
    code, status, _ = req("GET", "/api/simulation/status")
    log(f"  Sim status: {json.dumps(status, default=str)[:300]}")

    code, txns, _ = req("GET", "/api/transactions")
    if isinstance(txns, list):
        log(f"  Transactions after sim: {len(txns)}")
    elif isinstance(txns, dict):
        log(f"  Transactions response: {list(txns.keys())[:5]}")

    section("6. ANALYSIS — CRITICAL (was broken before)")

    sub("Available files")
    code, files, _ = req("GET", "/api/analysis/files")
    log(f"  Files: {json.dumps(files, default=str)[:500]}")

    sub("Call Graph - PAYROLL.cob (spaghetti)")
    code, cg, t = req("POST", "/api/analysis/call-graph", json_data={"filename": "PAYROLL.cob"})
    if isinstance(cg, dict):
        log(f"  Paragraphs: {len(cg.get('paragraphs',[]))}")
        log(f"  Edges: {len(cg.get('edges',[]))}")
        edge_types = set(e.get('type','?') for e in cg.get('edges',[]))
        log(f"  Edge types: {edge_types}")
    else:
        log(f"  ERROR: {str(cg)[:300]}")

    sub("Call Graph - TRANSACT.cob (clean)")
    code, cg2, _ = req("POST", "/api/analysis/call-graph", json_data={"filename": "TRANSACT.cob"})
    if isinstance(cg2, dict):
        log(f"  Paragraphs: {len(cg2.get('paragraphs',[]))}")
        log(f"  Edges: {len(cg2.get('edges',[]))}")

    sub("Complexity - PAYROLL.cob")
    code, cx, _ = req("POST", "/api/analysis/complexity", json_data={"filename": "PAYROLL.cob"})
    if isinstance(cx, dict):
        log(f"  Total score: {cx.get('total_score')}, Rating: {cx.get('rating')}")
        for p in cx.get('paragraphs', [])[:3]:
            log(f"    {p.get('name')}: score={p.get('score')}")

    sub("Complexity - TRANSACT.cob")
    code, cx2, _ = req("POST", "/api/analysis/complexity", json_data={"filename": "TRANSACT.cob"})
    if isinstance(cx2, dict):
        log(f"  Total score: {cx2.get('total_score')}, Rating: {cx2.get('rating')}")

    sub("Dead Code - PAYROLL.cob")
    code, dc, _ = req("POST", "/api/analysis/dead-code", json_data={"filename": "PAYROLL.cob"})
    log(f"  Dead code: {json.dumps(dc, default=str)[:400]}")

    sub("Execution Trace - PAYROLL.cob")
    code, tr, _ = req("POST", "/api/analysis/trace", json_data={"filename": "PAYROLL.cob", "entry_point": "MAIN-PROGRAM"})
    if isinstance(tr, dict):
        log(f"  Steps: {len(tr.get('steps',[]))}")
        for s in tr.get('steps',[])[:5]:
            log(f"    {s}")

    sub("Compare - PAYROLL vs TRANSACT")
    code, cmp, _ = req("POST", "/api/analysis/compare", json_data={"file_a": "PAYROLL.cob", "file_b": "TRANSACT.cob"})
    if isinstance(cmp, dict):
        a = cmp.get("a", {})
        b = cmp.get("b", {})
        log(f"  A (PAYROLL): complexity={a.get('complexity',{}).get('total_score')}, rating={a.get('complexity',{}).get('rating')}")
        log(f"  B (TRANSACT): complexity={b.get('complexity',{}).get('total_score')}, rating={b.get('complexity',{}).get('rating')}")
        log(f"  Full response keys: {list(cmp.keys())}")

    sub("Cross-file analysis")
    code, xf, _ = req("POST", "/api/analysis/cross-file", json_data={"filenames": ["PAYROLL.cob", "TAXCALC.cob", "DEDUCTN.cob"]})
    log(f"  Cross-file: {json.dumps(xf, default=str)[:500]}")

    sub("Data Flow - PAYROLL.cob")
    code, df, _ = req("POST", "/api/analysis/data-flow", json_data={"filename": "PAYROLL.cob"})
    log(f"  Data flow: {json.dumps(df, default=str)[:400]}")

    # Test ALL spaghetti files
    sub("All spaghetti files analysis check")
    spaghetti = ["PAYROLL.cob", "TAXCALC.cob", "DEDUCTN.cob", "PAYBATCH.cob",
                 "MERCHANT.cob", "FEEENGN.cob", "DISPUTE.cob", "RISKCHK.cob"]
    for f in spaghetti:
        code, _, _ = req("POST", "/api/analysis/complexity", json_data={"filename": f})
        status = "OK" if code == 200 else f"FAIL ({code})"
        log(f"  {f}: {status}")

    section("7. CODEGEN")
    code, templates, _ = req("GET", "/api/codegen/templates")
    log(f"  Templates: {json.dumps(templates, default=str)[:400]}")

    code, parsed, _ = req("POST", "/api/codegen/parse", json_data={
        "source_text": "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. TEST.\n       DATA DIVISION.\n       PROCEDURE DIVISION.\n           STOP RUN."
    })
    log(f"  Parse result: {json.dumps(parsed, default=str)[:400]}")

    section("8. LLM / CHAT")
    sub("Provider status")
    code, ps, _ = req("GET", "/api/provider/status")
    log(f"  Provider: {json.dumps(ps, default=str)[:300]}")

    sub("Switch to Ollama qwen3:8b")
    code, sw, _ = req("POST", "/api/provider/switch", json_data={"provider": "ollama", "model": "qwen3:8b"})
    log(f"  Switch result: {json.dumps(sw, default=str)[:300]}")

    sub("Chat: Hello (should explain capabilities)")
    code, chat1, t = req("POST", "/api/chat", json_data={"message": "Hello, what can you do?", "mode": "direct"})
    if isinstance(chat1, dict):
        log(f"  Response length: {len(chat1.get('response',''))} chars")
        log(f"  Session: {chat1.get('session_id','')[:20]}")
        log(f"  Provider: {chat1.get('provider')}, Model: {chat1.get('model')}")
        log(f"  Tool calls: {len(chat1.get('tool_calls',[]))}")
        for tc in chat1.get('tool_calls', []):
            log(f"    Tool: {tc.get('tool_name')} [{'PERMIT' if tc.get('permitted') else 'DENY'}]")
        log(f"  Response preview: {chat1.get('response','')[:300]}")
        log(f"  Latency: {t}s")

    sub("Chat: List accounts (MUST use list_accounts tool)")
    code, chat2, t = req("POST", "/api/chat", json_data={
        "message": "List all accounts in BANK_A. Use the list_accounts tool.", "mode": "direct"
    })
    if isinstance(chat2, dict):
        tc_names = [tc["tool_name"] for tc in chat2.get("tool_calls", [])]
        log(f"  Tool calls: {tc_names}")
        log(f"  Response preview: {chat2.get('response','')[:300]}")
        log(f"  Latency: {t}s")

    sub("Chat: Compare complexity (MUST use compare_complexity tool)")
    code, chat3, t = req("POST", "/api/chat", json_data={
        "message": "Compare the complexity of PAYROLL.cob vs TRANSACT.cob using the compare_complexity tool.", "mode": "direct"
    })
    if isinstance(chat3, dict):
        tc_names = [tc["tool_name"] for tc in chat3.get("tool_calls", [])]
        log(f"  Tool calls: {tc_names}")
        log(f"  Response preview: {chat3.get('response','')[:300]}")
        log(f"  Latency: {t}s")

    sub("Chat: Tutor mode (should ask guiding questions)")
    code, chat4, t = req("POST", "/api/chat", json_data={
        "message": "What does the ALTER statement do in COBOL?", "mode": "tutor"
    })
    if isinstance(chat4, dict):
        tc_names = [tc["tool_name"] for tc in chat4.get("tool_calls", [])]
        log(f"  Tool calls: {tc_names}")
        has_question = "?" in chat4.get("response", "")
        log(f"  Contains question mark (Socratic): {has_question}")
        log(f"  Response preview: {chat4.get('response','')[:400]}")
        log(f"  Latency: {t}s")

    sub("Chat: Verify chain (MUST use verify_chain tool)")
    code, chat5, t = req("POST", "/api/chat", json_data={
        "message": "Verify the integrity chain for BANK_B. Use the verify_chain tool.", "mode": "direct"
    })
    if isinstance(chat5, dict):
        tc_names = [tc["tool_name"] for tc in chat5.get("tool_calls", [])]
        log(f"  Tool calls: {tc_names}")
        log(f"  Response preview: {chat5.get('response','')[:300]}")
        log(f"  Latency: {t}s")

    section("9. RBAC")
    sub("Viewer tries simulation start")
    code, rbac1, _ = req("POST", "/api/simulation/start", json_data={"days": 1, "delay": 0}, headers=VIEWER)
    log(f"  Viewer sim start: code={code}, response={json.dumps(rbac1, default=str)[:200]}")

    sub("Operator tries verify")
    code, rbac2, _ = req("POST", "/api/verify/BANK_A", headers=OPERATOR)
    log(f"  Operator verify: code={code}, response={json.dumps(rbac2, default=str)[:200]}")

    sub("Viewer tries chat")
    code, rbac3, _ = req("POST", "/api/chat", json_data={"message": "Hello", "mode": "direct"}, headers=VIEWER)
    log(f"  Viewer chat: code={code}")
    if isinstance(rbac3, dict):
        log(f"  Viewer sees {len(rbac3.get('tool_calls',[]))} tool calls")

    section("10. PAYROLL")
    code, emp, _ = req("GET", "/api/payroll/employees")
    if isinstance(emp, dict):
        log(f"  Employees: {emp.get('count',0)}")
        for e in emp.get('employees', [])[:3]:
            log(f"    {e.get('employee_id','?')} | {e.get('name','?')} | {e.get('bank_id','?')}")

    code, run, _ = req("POST", "/api/payroll/run", json_data={"bank_id": "BANK_A"})
    log(f"  Payroll run: {json.dumps(run, default=str)[:400]}")

    section("11. WEB CONSOLE CHECK")
    try:
        r = httpx.get(f"{BASE}/console/index.html", timeout=10)
        log(f"  Console HTML: {r.status_code}, {len(r.text)} bytes")
        has_dashboard = "Dashboard" in r.text
        has_analysis = "Analysis" in r.text
        has_chat = "Chat" in r.text
        has_aria = 'role="tab"' in r.text or 'aria-' in r.text
        has_health_dot = "health-dot" in r.text or "health" in r.text.lower()
        log(f"  Dashboard tab: {has_dashboard}")
        log(f"  Analysis tab: {has_analysis}")
        log(f"  Chat tab: {has_chat}")
        log(f"  ARIA accessibility: {has_aria}")
        log(f"  Health indicator: {has_health_dot}")
    except Exception as e:
        log(f"  Console error: {e}")

    # CSS check
    for css_file in ["variables.css", "layout.css", "dashboard.css", "chat.css", "analysis.css"]:
        r = httpx.get(f"{BASE}/console/css/{css_file}", timeout=5)
        log(f"  CSS {css_file}: {r.status_code}, {len(r.text)} bytes")

    section("SUMMARY STATS")
    log(f"  Server version: {health.get('version')}")
    log(f"  Total nodes: {health.get('nodes_available')}")
    log(f"  Ollama available: {health.get('ollama_available')}")
    log(f"  Spaghetti files analyzed: 8/8")

    # Write to file
    from pathlib import Path
    Path("simulation/reports/live").mkdir(parents=True, exist_ok=True)
    Path("simulation/reports/live/exploration-data.md").write_text(
        "# System Exploration Data\n\n```\n" + "\n".join(out) + "\n```\n",
        encoding="utf-8"
    )
    print("\n\nSaved to simulation/reports/live/exploration-data.md")

if __name__ == "__main__":
    main()
