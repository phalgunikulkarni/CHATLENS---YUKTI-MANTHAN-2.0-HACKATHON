"""P2S5.1 - selected-memory action orchestration tests (stdlib harness).

Covers deterministic routing of the four UI actions to the EXISTING agents /
retrieval, mode-specific summarize, controlled no-OCR behavior, and that no
seventh agent exists / Gemini is not required. LLM/retrieval are stubbed for
fast, offline determinism (a separate real check is run outside these tests).
Run: python tests/test_memory_actions.py
"""
from __future__ import annotations

import os, sys, tempfile, traceback

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
_TMP = tempfile.mkdtemp(prefix="p2s51-")
os.environ["CHATLENS_CALENDAR_DIR"] = os.path.join(_TMP, "c")
os.environ["CHATLENS_TASK_DIR"] = os.path.join(_TMP, "t")

import memory_actions
from agents import AGENT_IDS, build_default_registry


# ---- stub the summarize agent's LLM + retrieval seams for determinism ----
class _FakeLLM:
    model = "qwen2.5:3b"
    def __init__(self, reply): self._r = reply
    def generate(self, prompt, system=None, temperature=0.0): return self._r


def _install_fake_llm(reply):
    # Replace the summarize agent instance's client with a fake.
    agent = memory_actions._REGISTRY.get("summarize")
    agent._llm = _FakeLLM(reply)


def _install_ocr(text_map):
    # Patch the OCR-text lookup used by memory_actions._memory_context.
    from agents import retrieval_access
    memory_actions.retrieval_access.get_stored_ocr_text = lambda iid: text_map.get(iid)  # type: ignore
    # Avoid touching the real store for filename/paths.
    import ml_retrieval
    ml_retrieval._get_store = lambda: None  # type: ignore


def _install_search(rows):
    import ml_retrieval
    ml_retrieval.search_memories = lambda q, top_k=5: list(rows)  # type: ignore


ACCT = "acct-aaaa"


def test_A_summarize_selected_image():
    _install_ocr({"img1": "The mitochondria is the powerhouse of the cell."})
    _install_fake_llm("Cells rely on mitochondria for energy.")
    r = memory_actions.run_summary_action(ACCT, ["img1"], "summarize")
    assert r["ok"] and r["data"]["mode"] == "summary"
    assert r["data"]["summary"] == "Cells rely on mitochondria for energy."
    assert r["metadata"]["used_image_ids"] == ["img1"]


def test_B_extract_key_points():
    _install_ocr({"img1": "Layer1 physical. Layer2 data link. Layer3 network."})
    _install_fake_llm("- Physical layer\n- Data link layer\n- Network layer")
    r = memory_actions.run_summary_action(ACCT, ["img1"], "key_points")
    assert r["ok"] and r["data"]["mode"] == "key_points"
    assert r["data"]["points"] == ["Physical layer", "Data link layer", "Network layer"]


def test_C_revision_roadmap():
    _install_ocr({"img1": "OSI model with seven layers and TCP/IP mapping."})
    _install_fake_llm("1. Study OSI layers\n2. Map to TCP/IP\n3. Practice questions")
    r = memory_actions.run_summary_action(ACCT, ["img1"], "roadmap")
    assert r["ok"] and r["data"]["mode"] == "roadmap"
    assert r["data"]["steps"] == ["Study OSI layers", "Map to TCP/IP", "Practice questions"]


def test_D_related_memories_uses_retrieval_and_excludes_self():
    _install_ocr({"img1": "invoice total groceries"})
    _install_search([
        {"image_id": "img1", "extracted_text": "self"},
        {"image_id": "img2", "extracted_text": "other"},
        {"image_id": "img3", "extracted_text": "another"},
    ])
    r = memory_actions.run_related_memories(ACCT, "img1")
    assert r["ok"]
    ids = [x["image_id"] for x in r["raw"]]
    assert "img1" not in ids and "img2" in ids


def test_G_no_ocr_controlled_non_hallucinating():
    _install_ocr({})  # no text for anything
    _install_fake_llm("SHOULD NOT BE USED")
    r = memory_actions.run_summary_action(ACCT, ["ghost"], "summarize")
    assert not r["ok"] and r["error"] == "no_input"
    assert "could not be extracted" in r["message"].lower() or "no text" in r["message"].lower()
    assert r["data"]["summary"] is None  # nothing invented


def test_J_five_agents_registered_no_reminder():
    ids = set(build_default_registry().ids())
    assert ids == {"summarize", "add_calendar", "add_task", "analyze_bill", "research"}
    assert AGENT_IDS == ("summarize", "add_calendar", "add_task", "analyze_bill", "research")
    # Reminder is no longer a functional agent.
    assert build_default_registry().get("reminder") is None
    # No related-memories agent exists.
    assert build_default_registry().get("related") is None
    assert build_default_registry().get("related_memories") is None


def test_H_gemini_not_required_in_code():
    # No Gemini import/env is required anywhere in backend Python code.
    import subprocess
    root = _BACKEND_DIR
    hits = []
    for dirpath, _dirs, files in os.walk(root):
        if "__pycache__" in dirpath or "/tests" in dirpath:
            continue
        for fn in files:
            if fn.endswith(".py"):
                p = os.path.join(dirpath, fn)
                try:
                    txt = open(p, encoding="utf-8").read()
                except Exception:
                    continue
                for needle in ("google.generativeai", "GEMINI_API_KEY", "gemini-1.5"):
                    if needle in txt:
                        hits.append((p, needle))
    assert hits == [], f"Gemini references found: {hits}"


def _main():
    tests = [(n, o) for n, o in globals().items() if n.startswith("test_") and callable(o)]
    p = f = 0
    for name, fn in tests:
        try: fn(); p += 1; print(f"PASS {name}")
        except Exception: f += 1; print(f"FAIL {name}"); traceback.print_exc()
    print(f"\nmemory_actions: {p} passed, {f} failed, {len(tests)} total")
    import shutil; shutil.rmtree(_TMP, ignore_errors=True)
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(_main())
