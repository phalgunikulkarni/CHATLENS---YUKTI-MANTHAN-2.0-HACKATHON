"""P3S1 - /api/actions/research endpoint tests (offline; agent LLM+pipeline stubbed).

Covers: account gating, missing query, success shape (answer/findings/sources/
limitations/providers), provider partial failure surfaced, and no-evidence ->
controlled 422 (no answer generated). No live network. Run:
    python tests/test_research_endpoint.py
"""
from __future__ import annotations

import os, sys, tempfile, traceback

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
_TMP = tempfile.mkdtemp(prefix="p3s1-")
os.environ["CHATLENS_CALENDAR_DIR"] = os.path.join(_TMP, "c")
os.environ["CHATLENS_TASK_DIR"] = os.path.join(_TMP, "t")

from fastapi.testclient import TestClient
import main
import memory_actions

client = TestClient(main.app)
A = {"X-Account-Id": "acct-aaaa"}


class _FakeLLM:
    model = "qwen2.5:3b"
    def generate(self, prompt, system=None, temperature=0.0):
        return "Synthesized answer [1].\n- finding one\n- finding two"


def _stub_pipeline(sources, used, failed):
    ra = memory_actions._REGISTRY.get("research")
    ra._llm = _FakeLLM()
    def _collect(query, per_provider=5, target=5, provider_names=None):
        return {"sources": sources, "providers_used": used,
                "providers_failed": failed, "provider_counts": {}}
    ra._collect = _collect


def _src(**kw):
    base = dict(title=None, url=None, provider="OpenAlex", source_type="scholarly",
                authors=[], publication_date=None, year=None, doi=None, identifier=None,
                abstract=None, snippet=None, relevance_score=None)
    base.update(kw); return base


def test_requires_account():
    assert client.post("/api/actions/research", json={"query": "x"}).status_code == 401


def test_missing_query_400():
    assert client.post("/api/actions/research", headers=A, json={"query": "   "}).status_code == 400


def test_success_shape_and_source_urls():
    _stub_pipeline(
        [_src(title="P1", url="https://doi.org/10/p1", doi="10/p1", authors=["A B"],
              year=2021, abstract="abstract text", provider="OpenAlex"),
         _src(title="P2", url="http://arxiv.org/abs/2101.1", provider="arXiv",
              source_type="preprint", identifier="arxiv:2101.1", abstract="preprint")],
        used=["openalex", "arxiv"], failed=[])
    r = client.post("/api/actions/research", headers=A, json={"query": "what is X", "maxResults": 5})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["research_answer"].startswith("Synthesized answer")
    assert d["key_findings"] == ["finding one", "finding two"]
    urls = [s["url"] for s in d["sources"]]
    assert urls == ["https://doi.org/10/p1", "http://arxiv.org/abs/2101.1"]
    assert d["sources"][0]["doi"] == "10/p1" and d["sources"][0]["authors"] == ["A B"]
    assert r.json()["metadata"]["providers_used"] == ["openalex", "arxiv"]


def test_provider_partial_failure_surfaced():
    _stub_pipeline([_src(title="Only", url="https://x", doi="10/x")],
                   used=["openalex"], failed=["pubmed"])
    r = client.post("/api/actions/research", headers=A, json={"query": "q"})
    assert r.status_code == 200
    lim = r.json()["data"]["limitations"]
    assert any("pubmed" in l.lower() for l in lim)


def test_no_evidence_controlled_422_no_answer():
    ra = memory_actions._REGISTRY.get("research")
    ra._llm = _FakeLLM()
    ra._collect = lambda query, per_provider=5, target=5, provider_names=None: {
        "sources": [], "providers_used": ["openalex"], "providers_failed": [], "provider_counts": {}}
    r = client.post("/api/actions/research", headers=A, json={"query": "obscure"})
    assert r.status_code == 422
    # detail carries the safe explanation; no answer generated
    assert "evidence" in (r.json().get("detail") or "").lower()


def _main():
    tests = [(n, o) for n, o in globals().items() if n.startswith("test_") and callable(o)]
    p = f = 0
    for name, fn in tests:
        try: fn(); p += 1; print(f"PASS {name}")
        except Exception: f += 1; print(f"FAIL {name}"); traceback.print_exc()
    print(f"\nresearch_endpoint: {p} passed, {f} failed, {len(tests)} total")
    import shutil; shutil.rmtree(_TMP, ignore_errors=True)
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(_main())
