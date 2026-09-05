"""Phase 8 - comprehensive five-agent integration test (offline, deterministic).

Verifies: exact five-agent registry, routing, per-agent execution, cross-agent
isolation (via run() spies), and a sequential integration run. No network: LLM
and the multi-provider collect() are stubbed; Taskwarrior/calendar use temp dirs
(the calendar store is local by default). Run:
    python tests/test_five_agents_integration.py
"""
from __future__ import annotations

import os, sys, tempfile, shutil, traceback

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
_TMP = tempfile.mkdtemp(prefix="p8-")
os.environ["CHATLENS_CALENDAR_DIR"] = os.path.join(_TMP, "c")
os.environ["CHATLENS_TASK_DIR"] = os.path.join(_TMP, "t")

from agents import build_default_registry, Orchestrator, AgentContext, AGENT_IDS
import memory_actions

FIVE = {"summarize", "add_calendar", "add_task", "analyze_bill", "research"}
ACCT = "acct-aaaa"


class _FakeLLM:
    model = "qwen2.5:3b"
    def __init__(self, reply): self._r = reply
    def generate(self, prompt, system=None, temperature=0.0): return self._r


def _reg():
    return build_default_registry()


# ---- Part 1: registry / routing / no reminder ----
def test_registry_has_exactly_five():
    ids = set(_reg().ids())
    assert ids == FIVE, ids
    assert AGENT_IDS == ("summarize", "add_calendar", "add_task", "analyze_bill", "research")


def test_reminder_not_registered():
    assert _reg().get("reminder") is None


def test_all_five_resolve():
    reg = _reg()
    for aid in FIVE:
        assert reg.get(aid) is not None and reg.get(aid).id == aid


def test_router_maps_action_to_agent():
    from agents.router import StaticRouter
    r = StaticRouter()
    for aid in FIVE:
        assert r.route(AgentContext(params={"agent": aid})) == aid


def test_orchestrator_executes_each_agent_guarded():
    reg = _reg(); orch = Orchestrator(reg)
    # each dispatch returns an AgentResult for the SAME agent id (never leaks/raises)
    for aid in FIVE:
        res = orch.dispatch(AgentContext(account_id=ACCT, params={}), agent_id=aid)
        assert res.agent == aid


# ---- Part 2: summarization modes ----
def _summ_agent(reg, reply):
    a = reg.get("summarize"); a._llm = _FakeLLM(reply); return a

def test_summarize_modes_and_grounding():
    reg = _reg(); orch = Orchestrator(reg)
    _summ_agent(reg, "A summary.\n- point a\n- point b")
    for mode, expect_key in [("summary", "summary"), ("key_points", "points"), ("roadmap", "steps")]:
        res = orch.dispatch(AgentContext(account_id=ACCT, params={"text": "some evidence text", "mode": mode}), agent_id="summarize")
        assert res.ok and res.data["mode"] == mode
    # grounding: evidence text is present in the prompt
    a = reg.get("summarize")
    class Cap(_FakeLLM):
        def generate(self, prompt, system=None, temperature=0.0):
            self.p = prompt; return "x"
    cap = Cap(""); a._llm = cap
    orch.dispatch(AgentContext(account_id=ACCT, params={"text": "UNIQUE_EVIDENCE_123", "mode": "summary"}), agent_id="summarize")
    assert "UNIQUE_EVIDENCE_123" in cap.p

def test_summarize_missing_evidence_controlled():
    reg = _reg(); orch = Orchestrator(reg); _summ_agent(reg, "should not be used")
    res = orch.dispatch(AgentContext(account_id=ACCT, params={"mode": "summary"}), agent_id="summarize")
    assert not res.ok and res.error == "no_input"


# ---- Part 3/4: calendar + task via services ----
def test_calendar_create_and_scope():
    from calendar_tasks.calendar_service import CalendarService
    cs = CalendarService()
    ev = cs.create_event(ACCT, "P8 event", "2026-12-01", "10:00", "11:00", "Asia/Kolkata", "", None)
    assert ev.id and cs.list_events(ACCT) and cs.list_events("acct-bbbb") == []

def test_calendar_agent_confirmation_and_invalid():
    reg = _reg(); orch = Orchestrator(reg)
    # unconfirmed -> no mutation
    r0 = orch.dispatch(AgentContext(account_id=ACCT, params={"title": "x", "date": "2026-12-02", "start_time": "10:00"}), agent_id="add_calendar")
    assert r0.ok and r0.data["confirmed"] is False
    # invalid -> controlled failure
    r1 = orch.dispatch(AgentContext(account_id=ACCT, params={"confirmed": True, "title": "", "date": "2026-13-40", "start_time": "99:99"}), agent_id="add_calendar")
    assert not r1.ok

def test_task_create_and_scope():
    if not shutil.which("task"):
        print("  (skip task: taskwarrior unavailable)"); return
    from calendar_tasks.task_service import TaskService
    ts = TaskService()
    t = ts.create_task(ACCT, "P8 task", "2026-12-01", "11:00", "medium")
    assert t.id and any(x.id == t.id for x in ts.list_tasks(ACCT)) and ts.list_tasks("acct-bbbb") == []


# ---- Part 5: finance analyze + split + no fabrication ----
SAMPLE = "Green Leaf Grocery\n2024-03-15\nApples 3.50\nMilk 2.99\nBread 1.20\nTax 0.61\nTOTAL $ 8.30\n"

def test_finance_analyze_and_splits_no_fabrication():
    reg = _reg(); orch = Orchestrator(reg)
    r = orch.dispatch(AgentContext(account_id=ACCT, params={"ocr_text": SAMPLE}), agent_id="analyze_bill")
    f = r.data["fields"]; assert r.ok and f["total"] == 8.30 and f["currency"] == "USD" and f["tax"] == 0.61
    # equal split reconciles
    re = orch.dispatch(AgentContext(account_id=ACCT, params={"ocr_text": SAMPLE, "operation": "split", "split_mode": "equal", "people": 3}), agent_id="analyze_bill")
    assert re.ok and abs(sum(s["amount"] for s in re.data["split"]["shares"]) - 8.30) < 0.01
    # item split
    ri = orch.dispatch(AgentContext(account_id=ACCT, params={"ocr_text": SAMPLE, "operation": "split", "split_mode": "items", "assignments": {"A": [0], "B": [1, 2]}}), agent_id="analyze_bill")
    assert ri.ok and len(ri.data["split"]["people"]) == 2
    # no total -> controlled failure (no fabrication)
    rf = orch.dispatch(AgentContext(account_id=ACCT, params={"ocr_text": "no total here", "operation": "split", "split_mode": "equal", "people": 2}), agent_id="analyze_bill")
    assert not rf.ok and rf.error == "missing_total"


# ---- Part 6: research grounding + no full-paper claim + provider isolation ----
def test_research_grounded_and_guardrails():
    reg = _reg(); orch = Orchestrator(reg)
    ra = reg.get("research"); ra._llm = _FakeLLM("Answer [1].\n- f1")
    ra._collect = lambda query, per_provider=5, target=5, provider_names=None: {
        "sources": [{"title": "Real Paper", "url": "https://doi.org/10/x", "provider": "OpenAlex",
                     "source_type": "scholarly", "authors": ["A"], "publication_date": "2023",
                     "year": 2023, "doi": "10/x", "identifier": None, "abstract": "abs", "snippet": None, "relevance_score": 1.0}],
        "providers_used": ["openalex", "crossref"], "providers_failed": ["pubmed"], "provider_counts": {}}
    res = orch.dispatch(AgentContext(account_id=ACCT, query="rag eval"), agent_id="research")
    assert res.ok
    assert res.data["sources"][0]["url"] == "https://doi.org/10/x"
    assert any("pubmed" in l.lower() for l in res.data["limitations"])  # provider failure isolated
    from agents import research_agent as RA
    assert "abstracts/snippets only" in RA._build_prompt("q", [{"title": "T", "abstract": "a"}]).lower()


# ---- Part 7: cross-agent isolation via run() spies ----
def test_cross_agent_isolation():
    reg = _reg(); orch = Orchestrator(reg)
    calls = {aid: 0 for aid in FIVE}
    originals = {}
    for aid in FIVE:
        ag = reg.get(aid); originals[aid] = ag.run
        def make(a_id, orig):
            def spy(ctx):
                calls[a_id] += 1
                return orig(ctx)
            return spy
        ag.run = make(aid, ag.run)
    # stub LLM/collect so summarize/research don't hit network
    reg.get("summarize")._llm = _FakeLLM("s")
    reg.get("research")._llm = _FakeLLM("r [1].\n- f")
    reg.get("research")._collect = lambda *a, **k: {"sources": [{"title": "T", "url": "https://x", "provider": "OpenAlex", "source_type": "scholarly", "authors": [], "publication_date": None, "year": None, "doi": None, "identifier": None, "abstract": "a", "snippet": None, "relevance_score": 1}], "providers_used": ["openalex"], "providers_failed": [], "provider_counts": {}}

    dispatches = {
        "summarize": {"text": "t", "mode": "summary"},
        "add_calendar": {"confirmed": True, "title": "e", "date": "2026-12-03", "start_time": "10:00"},
        "add_task": {"confirmed": True, "title": "t", "due_date": "2026-12-03", "priority": "medium"},
        "analyze_bill": {"ocr_text": SAMPLE},
        "research": {"query": "q"},
    }
    for target, params in dispatches.items():
        if target == "add_task" and not shutil.which("task"):
            continue
        for k in calls: calls[k] = 0
        orch.dispatch(AgentContext(account_id=ACCT, query=params.get("query", ""), params=params), agent_id=target)
        assert calls[target] == 1, f"{target} not invoked"
        for other in FIVE - {target}:
            assert calls[other] == 0, f"{target} leaked into {other}"


# ---- Part 8: sequential integration run (one process) ----
def test_sequential_integration_run():
    reg = _reg(); orch = Orchestrator(reg)
    reg.get("summarize")._llm = _FakeLLM("sum.\n- a\n- b")
    reg.get("research")._llm = _FakeLLM("ans [1].\n- f")
    reg.get("research")._collect = lambda *a, **k: {"sources": [{"title": "T", "url": "https://x", "provider": "arXiv", "source_type": "preprint", "authors": [], "publication_date": None, "year": None, "doi": None, "identifier": "arxiv:1", "abstract": "a", "snippet": None, "relevance_score": 1}], "providers_used": ["arxiv"], "providers_failed": [], "provider_counts": {}}
    steps = [
        ("summarize", {"text": "evidence", "mode": "summary"}),
        ("summarize", {"text": "evidence", "mode": "key_points"}),
        ("summarize", {"text": "evidence", "mode": "roadmap"}),
        ("add_calendar", {"confirmed": True, "title": "seq event", "date": "2026-12-04", "start_time": "10:00"}),
        ("add_task", {"confirmed": True, "title": "seq task", "due_date": "2026-12-04", "priority": "low"}),
        ("analyze_bill", {"ocr_text": SAMPLE}),
        ("research", {"query": "rag eval"}),
    ]
    for aid, params in steps:
        if aid == "add_task" and not shutil.which("task"):
            continue
        res = orch.dispatch(AgentContext(account_id=ACCT, query=params.get("query", ""), params=params), agent_id=aid)
        assert res.ok, f"{aid} failed: {res.error}"
        assert res.agent == aid
    # registry intact throughout
    assert set(build_default_registry().ids()) == FIVE


def _main():
    tests = [(n, o) for n, o in globals().items() if n.startswith("test_") and callable(o)]
    p = f = 0
    for name, fn in tests:
        try: fn(); p += 1; print(f"PASS {name}")
        except Exception: f += 1; print(f"FAIL {name}"); traceback.print_exc()
    print(f"\nfive_agents_integration: {p} passed, {f} failed, {len(tests)} total")
    shutil.rmtree(_TMP, ignore_errors=True)
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(_main())
