"""P2S3 - Research Agent tests (stdlib harness; offline; no internet/Ollama).

Uses a fake search function + fake LLM (both injected) so no network is needed.
Run: python tests/test_research_agent.py
"""
from __future__ import annotations

import os
import sys
import traceback

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from agents import AgentContext, AgentResult, AgentRegistry, Orchestrator, StaticRouter
from agents.research_agent import ResearchAgent
from agents.llm_client import LLMError
from agents.web_search import SearchError

FAKE_SOURCES = [
    {"title": "Python (programming language)", "url": "https://en.wikipedia.org/wiki/Python",
     "snippet": "Python is a high-level programming language."},
    {"title": "Python.org", "url": "https://www.python.org",
     "snippet": "The official home of the Python Programming Language."},
]


class _FakeLLM:
    model = "qwen2.5:3b"
    def __init__(self, reply="Python is a high-level language [1][2].", raise_error=None):
        self._reply, self._raise = reply, raise_error
        self.last_prompt = None
    def generate(self, prompt, system=None, temperature=0.0):
        self.last_prompt = prompt
        if self._raise:
            raise self._raise
        return self._reply


def _search_ok(query, max_results=5):
    return list(FAKE_SOURCES)[:max_results]

def _search_empty(query, max_results=5):
    return []

def _search_boom(query, max_results=5):
    raise SearchError("web search failed: ratelimited")


def test_research_success_structured():
    llm = _FakeLLM()
    agent = ResearchAgent(llm=llm, search_fn=_search_ok)
    res = agent.run(AgentContext(query="what is python"))
    assert isinstance(res, AgentResult) and res.ok, res.error
    assert res.data["query"] == "what is python"
    assert res.data["answer"].startswith("Python is a high-level")
    # structured sources
    srcs = res.data["sources"]
    assert len(srcs) == 2
    assert set(srcs[0].keys()) == {"title", "url", "snippet"}
    # evidence carries the web results
    assert res.evidence and res.evidence[0]["type"] == "web_result"
    assert res.metadata["search"] == "ddgs" and res.metadata["n_sources"] == 2
    # grounding: the prompt contains the source snippets
    assert "high-level programming language" in llm.last_prompt


def test_research_search_failure_is_controlled():
    agent = ResearchAgent(llm=_FakeLLM(), search_fn=_search_boom)
    res = agent.run(AgentContext(query="anything"))
    assert not res.ok and "search_error" in res.error
    assert res.data["sources"] == []


def test_research_no_results_is_controlled():
    agent = ResearchAgent(llm=_FakeLLM(), search_fn=_search_empty)
    res = agent.run(AgentContext(query="obscure"))
    assert not res.ok and res.error == "no_results"


def test_research_llm_failure_preserves_sources():
    llm = _FakeLLM(raise_error=LLMError("local model 'qwen2.5:3b' not available (HTTP 404)"))
    agent = ResearchAgent(llm=llm, search_fn=_search_ok)
    res = agent.run(AgentContext(query="what is python"))
    assert not res.ok and "llm_error" in res.error
    # sources/evidence preserved even though synthesis failed
    assert len(res.data["sources"]) == 2
    assert len(res.evidence) == 2


def test_research_no_query_is_failure():
    agent = ResearchAgent(llm=_FakeLLM(), search_fn=_search_ok)
    res = agent.run(AgentContext())
    assert not res.ok and res.error == "no_query"


def test_research_max_results_bounded():
    seen = {}
    def _search(query, max_results=5):
        seen["max"] = max_results
        return list(FAKE_SOURCES)
    agent = ResearchAgent(llm=_FakeLLM(), search_fn=_search)
    agent.run(AgentContext(query="x", params={"max_results": 999}))
    assert seen["max"] == 10  # hard-capped


def test_research_dispatch_through_orchestrator():
    reg = AgentRegistry(); reg.register(ResearchAgent(llm=_FakeLLM(), search_fn=_search_ok))
    orch = Orchestrator(reg, StaticRouter())
    res = orch.dispatch(AgentContext(query="what is python"), agent_id="research")
    assert res.ok and res.agent == "research"


def _main():
    tests = [(n, o) for n, o in globals().items() if n.startswith("test_") and callable(o)]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn(); passed += 1; print(f"PASS {name}")
        except Exception:
            failed += 1; print(f"FAIL {name}"); traceback.print_exc()
    print(f"\nresearch_agent: {passed} passed, {failed} failed, {len(tests)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
