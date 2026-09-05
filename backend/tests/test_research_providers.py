"""Research provider + pipeline + multi-provider agent tests (offline, mocked).

Covers normalization (OpenAlex/Crossref/arXiv/PubMed), aggregation, dedup,
provider-failure isolation, metadata preservation, ranking/target behavior,
no-fabrication, Qwen grounding, and controlled insufficient-evidence.
No live network (requests is monkeypatched). Run:
    python tests/test_research_providers.py
"""
from __future__ import annotations

import os, sys, traceback

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import agents.research_providers as P
import agents.research_pipeline as PL
from agents.research_agent import ResearchAgent
from agents.contracts import AgentContext


# ---- fake requests responses -------------------------------------------------
class _Resp:
    def __init__(self, status=200, json_data=None, text=""):
        self.status_code = status
        self._json = json_data or {}
        self.text = text
    def json(self):
        return self._json


class _FakeLLM:
    model = "qwen2.5:3b"
    def __init__(self, reply="Synthesized answer [1][2].\n- finding one\n- finding two"):
        self._reply = reply; self.last_prompt = None
    def generate(self, prompt, system=None, temperature=0.0):
        self.last_prompt = prompt; return self._reply


def _install(monkey_get):
    P.requests.get = monkey_get  # type: ignore


# ---- individual provider normalization --------------------------------------
def test_openalex_normalization():
    def fake_get(url, params=None, headers=None, timeout=None):
        return _Resp(json_data={"results": [{
            "display_name": "Deep Learning", "publication_year": 2015,
            "publication_date": "2015-05-27", "doi": "https://doi.org/10.1/x",
            "id": "https://openalex.org/W1", "primary_location": {"landing_page_url": "https://ex.org/dl"},
            "authors": [], "authorships": [{"author": {"display_name": "Y. LeCun"}}],
            "abstract_inverted_index": {"Deep": [0], "nets": [1]},
        }]})
    _install(fake_get)
    out = P.fetch_openalex("deep learning", 5)
    assert len(out) == 1
    s = out[0]
    assert s["provider"] == "OpenAlex" and s["source_type"] == "scholarly"
    assert s["title"] == "Deep Learning" and s["year"] == 2015
    assert s["doi"] == "10.1/x" and s["authors"] == ["Y. LeCun"]
    assert s["abstract"] == "Deep nets"


def test_crossref_normalization():
    def fake_get(url, params=None, headers=None, timeout=None):
        return _Resp(json_data={"message": {"items": [{
            "title": ["Attention Is All You Need"], "DOI": "10.5/attn",
            "URL": "https://doi.org/10.5/attn", "container-title": ["NeurIPS"],
            "author": [{"given": "A", "family": "Vaswani"}],
            "issued": {"date-parts": [[2017, 6, 12]]}, "abstract": "<p>Transformers.</p>",
        }]}})
    _install(fake_get)
    out = P.fetch_crossref("transformers", 5)
    s = out[0]
    assert s["provider"] == "Crossref" and s["doi"] == "10.5/attn"
    assert s["title"] == "Attention Is All You Need" and s["year"] == 2017
    assert s["authors"] == ["A Vaswani"] and s["abstract"] == "Transformers."


def test_arxiv_normalization():
    xml = """<feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>BERT</title><summary>Pretraining.</summary>
      <published>2018-10-11T00:00:00Z</published>
      <id>http://arxiv.org/abs/1810.04805</id>
      <author><name>J. Devlin</name></author></entry></feed>"""
    def fake_get(url, params=None, headers=None, timeout=None):
        return _Resp(text=xml)
    _install(fake_get)
    out = P.fetch_arxiv("bert", 5)
    s = out[0]
    assert s["provider"] == "arXiv" and s["source_type"] == "preprint"
    assert s["title"] == "BERT" and s["year"] == 2018
    assert s["url"] == "http://arxiv.org/abs/1810.04805" and s["authors"] == ["J. Devlin"]


def test_pubmed_normalization():
    calls = {"n": 0}
    def fake_get(url, params=None, headers=None, timeout=None):
        calls["n"] += 1
        if "esearch" in url:
            return _Resp(json_data={"esearchresult": {"idlist": ["12345"]}})
        return _Resp(json_data={"result": {"12345": {
            "title": "Aspirin study", "pubdate": "2020 Jan", "source": "NEJM",
            "authors": [{"name": "Smith J"}], "elocationid": "doi: 10.9/asp"}}})
    _install(fake_get)
    out = P.fetch_pubmed("aspirin", 5)
    s = out[0]
    assert s["provider"] == "PubMed" and s["identifier"] == "PMID:12345"
    assert s["url"] == "https://pubmed.ncbi.nlm.nih.gov/12345/"
    assert s["year"] == 2020 and s["authors"] == ["Smith J"] and s["doi"] == "10.9/asp"


# ---- pipeline: aggregation / dedup / ranking / failure isolation -------------
def _src(**kw):
    base = dict(title=None, url=None, provider="X", source_type="web", authors=[],
                publication_date=None, year=None, doi=None, identifier=None,
                abstract=None, snippet=None, relevance_score=None)
    base.update(kw); return base


def test_multi_provider_aggregation_and_selection():
    def openalex(q, n): return [_src(title="A", provider="OpenAlex", source_type="scholarly", doi="10/a")]
    def crossref(q, n): return [_src(title="B", provider="Crossref", source_type="scholarly", doi="10/b")]
    def ddgs(q, n): return [_src(title="C", provider="DDGS", source_type="web", url="https://c")]
    res = PL.collect("general question", providers={"openalex": openalex, "crossref": crossref, "ddgs": ddgs},
                     provider_names=["openalex", "crossref", "ddgs"])
    titles = {s["title"] for s in res["sources"]}
    assert titles == {"A", "B", "C"}
    assert set(res["providers_used"]) == {"openalex", "crossref", "ddgs"}


def test_deduplication_by_doi_and_title():
    def p1(q, n): return [_src(title="Same Paper", provider="OpenAlex", source_type="scholarly", doi="10/dup", year=2020)]
    def p2(q, n): return [_src(title="same  paper", provider="Crossref", source_type="scholarly", doi="10/dup", authors=["X Y"])]
    res = PL.collect("q", providers={"openalex": p1, "crossref": p2},
                     provider_names=["openalex", "crossref"])
    assert len(res["sources"]) == 1
    kept = res["sources"][0]
    # merge fills missing metadata from the duplicate without overwriting
    assert kept["year"] == 2020 and kept["authors"] == ["X Y"]


def test_provider_failure_isolation():
    def good(q, n): return [_src(title="Good", provider="OpenAlex", source_type="scholarly", doi="10/g")]
    def boom(q, n): raise RuntimeError("network down")
    res = PL.collect("q", providers={"openalex": good, "crossref": boom},
                     provider_names=["openalex", "crossref"])
    assert [s["title"] for s in res["sources"]] == ["Good"]
    assert res["providers_failed"] == ["crossref"] and "openalex" in res["providers_used"]


def test_ranking_prefers_scholarly_and_relevance():
    def prov(q, n):
        return [
            _src(title="unrelated web page", provider="DDGS", source_type="web", url="https://w"),
            _src(title="quantum computing survey", provider="OpenAlex", source_type="scholarly",
                 doi="10/q", abstract="quantum computing methods"),
        ]
    res = PL.collect("quantum computing", providers={"openalex": prov}, provider_names=["openalex"])
    assert res["sources"][0]["provider"] == "OpenAlex"  # scholarly + relevant ranked first


def test_topic_aware_selection():
    assert "pubmed" in PL.select_providers("cancer treatment in patients")
    assert "arxiv" in PL.select_providers("deep learning transformer models")
    assert "openalex" in PL.select_providers("history of the roman empire")


# ---- agent-level (multi-provider path) --------------------------------------
def _collect_stub(sources):
    def _c(query, per_provider=5, target=5, provider_names=None):
        return {"sources": sources, "providers_used": ["openalex", "crossref"],
                "providers_failed": [], "provider_counts": {"openalex": len(sources)}}
    return _c


def test_agent_metadata_preservation_and_urls():
    sources = [_src(title="P1", provider="OpenAlex", source_type="scholarly",
                    url="https://doi.org/10/p1", doi="10/p1", authors=["A B"], year=2021,
                    abstract="abs one"),
               _src(title="P2", provider="arXiv", source_type="preprint",
                    url="http://arxiv.org/abs/2101.1", identifier="arxiv:2101.1", abstract="abs two")]
    agent = ResearchAgent(llm=_FakeLLM(), collect_fn=_collect_stub(sources))
    res = agent.run(AgentContext(query="what is X"))
    assert res.ok
    assert res.data["research_answer"].startswith("Synthesized answer")
    assert res.data["key_findings"] == ["finding one", "finding two"]
    got = res.data["sources"]
    assert [s["url"] for s in got] == ["https://doi.org/10/p1", "http://arxiv.org/abs/2101.1"]
    assert got[0]["doi"] == "10/p1" and got[0]["authors"] == ["A B"]
    assert res.metadata["search"] == "multi_provider"


def test_agent_no_fabricated_urls_or_metadata():
    # A source with missing metadata must keep nulls (never invented).
    sources = [_src(title="Bare", provider="Crossref", source_type="scholarly")]
    agent = ResearchAgent(llm=_FakeLLM(), collect_fn=_collect_stub(sources))
    res = agent.run(AgentContext(query="q"))
    s = res.data["sources"][0]
    assert s["url"] is None and s["doi"] is None and s["authors"] == [] and s["abstract"] is None


def test_agent_qwen_receives_grounded_evidence():
    sources = [_src(title="Grounding Paper", provider="OpenAlex", source_type="scholarly",
                    doi="10/g", abstract="specific abstract text")]
    llm = _FakeLLM()
    agent = ResearchAgent(llm=llm, collect_fn=_collect_stub(sources))
    agent.run(AgentContext(query="q"))
    # prompt must contain the real evidence + no-fabrication framing
    assert "Grounding Paper" in llm.last_prompt
    assert "specific abstract text" in llm.last_prompt
    assert "abstracts/snippets only" in llm.last_prompt.lower() or "abstract" in llm.last_prompt.lower()


def test_agent_insufficient_evidence_controlled():
    def _empty(query, per_provider=5, target=5, provider_names=None):
        return {"sources": [], "providers_used": ["openalex"], "providers_failed": ["crossref"],
                "provider_counts": {}}
    agent = ResearchAgent(llm=_FakeLLM(), collect_fn=_empty)
    res = agent.run(AgentContext(query="obscure nonsense query"))
    assert not res.ok and res.error == "no_evidence"
    assert res.data["research_answer"] is None
    assert any("could be retrieved" in l for l in res.data["limitations"])


def test_agent_fewer_sources_limitation():
    sources = [_src(title="Only one", provider="OpenAlex", source_type="scholarly", doi="10/1")]
    agent = ResearchAgent(llm=_FakeLLM(), collect_fn=_collect_stub(sources))
    res = agent.run(AgentContext(query="q"))
    assert res.ok and any("credible source" in l for l in res.data["limitations"])


def _main():
    tests = [(n, o) for n, o in globals().items() if n.startswith("test_") and callable(o)]
    p = f = 0
    for name, fn in tests:
        try: fn(); p += 1; print(f"PASS {name}")
        except Exception: f += 1; print(f"FAIL {name}"); traceback.print_exc()
    print(f"\nresearch_providers: {p} passed, {f} failed, {len(tests)} total")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(_main())
