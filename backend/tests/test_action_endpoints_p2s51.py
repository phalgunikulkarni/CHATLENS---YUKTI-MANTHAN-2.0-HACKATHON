"""P2S5.1 - action endpoint tests via TestClient (offline; LLM/retrieval stubbed).

Verifies the /api/actions/summarize (modes), /api/actions/roadmap, and
/api/actions/related endpoints are account-scoped and return the expected
shapes. E (bill) and F (research) intents are covered by the agent-level tests
(analyze_bill/research suites); here we confirm the selected-memory HTTP wiring.
Run: python tests/test_action_endpoints_p2s51.py
"""
from __future__ import annotations

import os, sys, tempfile, traceback

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
_TMP = tempfile.mkdtemp(prefix="p2s51api-")
os.environ["CHATLENS_CALENDAR_DIR"] = os.path.join(_TMP, "c")
os.environ["CHATLENS_TASK_DIR"] = os.path.join(_TMP, "t")

from fastapi.testclient import TestClient
import main
import memory_actions
import ml_retrieval

client = TestClient(main.app)
A = {"X-Account-Id": "acct-aaaa"}


class _FakeLLM:
    model = "qwen2.5:3b"
    def __init__(self, reply): self._r = reply
    def generate(self, prompt, system=None, temperature=0.0): return self._r


def _stub(summary_reply, ocr_map, search_rows):
    memory_actions._REGISTRY.get("summarize")._llm = _FakeLLM(summary_reply)
    memory_actions.retrieval_access.get_stored_ocr_text = lambda iid: ocr_map.get(iid)  # type: ignore
    ml_retrieval._get_store = lambda: None  # type: ignore
    ml_retrieval.search_memories = lambda q, top_k=5: list(search_rows)  # type: ignore


def test_summarize_endpoint_requires_account():
    assert client.post("/api/actions/summarize", json={"sessionId": "s", "imageIds": ["x"]}).status_code == 401


def test_summarize_endpoint_summary_mode():
    _stub("A concise summary.", {"img1": "some real ocr text about networks"}, [])
    r = client.post("/api/actions/summarize", headers=A,
                    json={"sessionId": "s", "imageIds": ["img1"], "mode": "summary"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] and body["summary"] == "A concise summary."
    assert body["usedImageIds"] == ["img1"]


def test_summarize_endpoint_key_points_mode():
    _stub("- Point one\n- Point two", {"img1": "text"}, [])
    r = client.post("/api/actions/summarize", headers=A,
                    json={"sessionId": "s", "imageIds": ["img1"], "mode": "key_points"})
    body = r.json()
    assert body["ok"] and body["points"] == ["Point one", "Point two"]


def test_summarize_endpoint_no_ocr_controlled():
    _stub("UNUSED", {}, [])
    r = client.post("/api/actions/summarize", headers=A,
                    json={"sessionId": "s", "imageIds": ["ghost"], "mode": "summary"})
    body = r.json()
    # Controlled, non-hallucinating: ok=False and the summary field carries the
    # explanatory message (never invented image content).
    assert body["ok"] is False
    assert body["usedImageIds"] == []
    assert "could not" in (body["summary"] or "").lower() or "no text" in (body["summary"] or "").lower()


def test_roadmap_endpoint():
    _stub("1. Step A\n2. Step B", {"img1": "study material"}, [])
    r = client.post("/api/actions/roadmap", headers=A, json={"sessionId": "s", "imageIds": ["img1"]})
    assert r.status_code == 200, r.text
    steps = r.json()["steps"]
    assert [s["title"] for s in steps] == ["Step A", "Step B"]
    assert [s["order"] for s in steps] == [1, 2]


def test_related_endpoint_excludes_self():
    _stub("UNUSED", {"img1": "invoice groceries total"},
          [{"image_id": "img1"}, {"image_id": "img2", "filename": "b.png", "category": "note"},
           {"image_id": "img3", "filename": "c.png", "category": "note"}])
    r = client.post("/api/actions/related", headers=A, json={"sessionId": "s", "imageId": "img1"})
    assert r.status_code == 200, r.text
    ids = [it["id"] for it in r.json()]
    assert "img1" not in ids


def test_existing_search_intact():
    assert client.get("/health").json() == {"status": "ok"}
    assert client.post("/api/search", json={"query": "x"}).status_code == 401  # gated


def _main():
    tests = [(n, o) for n, o in globals().items() if n.startswith("test_") and callable(o)]
    p = f = 0
    for name, fn in tests:
        try: fn(); p += 1; print(f"PASS {name}")
        except Exception: f += 1; print(f"FAIL {name}"); traceback.print_exc()
    print(f"\naction_endpoints_p2s51: {p} passed, {f} failed, {len(tests)} total")
    import shutil; shutil.rmtree(_TMP, ignore_errors=True)
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(_main())
