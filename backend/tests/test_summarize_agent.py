"""P2S3 - Summarize Agent tests (stdlib harness; offline; no Ollama needed).

Uses a fake LLM client (injected) so no network/model is required. Run:
    python tests/test_summarize_agent.py
"""
from __future__ import annotations

import os
import sys
import traceback

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from agents import AgentContext, AgentResult, AgentRegistry, Orchestrator, StaticRouter
from agents.summarize_agent import SummarizeAgent
from agents.llm_client import LLMError


class _FakeLLM:
    model = "qwen2.5:3b"
    def __init__(self, reply="This is a concise summary.", raise_error=None):
        self._reply, self._raise = reply, raise_error
        self.last_prompt = None
        self.last_system = None
    def generate(self, prompt, system=None, temperature=0.0):
        self.last_prompt, self.last_system = prompt, system
        if self._raise:
            raise self._raise
        return self._reply


def test_summarize_success_structured():
    llm = _FakeLLM(reply="Cats are great pets that need care.")
    agent = SummarizeAgent(llm=llm)
    res = agent.run(AgentContext(params={"text": "Long text about cats and their care needs..."}))
    assert isinstance(res, AgentResult) and res.ok, res.error
    assert res.data["summary"] == "Cats are great pets that need care."
    assert res.metadata["model"] == "qwen2.5:3b"
    # deterministic prompt: temperature 0 and source preserved as evidence
    assert res.evidence and res.evidence[0]["type"] == "source_text"
    assert "cats" in res.evidence[0]["text"].lower()


def test_summarize_uses_conversation():
    llm = _FakeLLM(reply="Summary of the chat.")
    agent = SummarizeAgent(llm=llm)
    ctx = AgentContext(conversation=[
        {"role": "user", "content": "What is the weather?"},
        {"role": "assistant", "content": "It is sunny today."},
    ])
    res = agent.run(ctx)
    assert res.ok
    assert "user: What is the weather?" in llm.last_prompt
    assert "assistant: It is sunny today." in llm.last_prompt


def test_summarize_llm_failure_is_controlled():
    llm = _FakeLLM(raise_error=LLMError("local LLM unavailable at http://localhost:11434"))
    agent = SummarizeAgent(llm=llm)
    res = agent.run(AgentContext(params={"text": "something"}))
    assert not res.ok
    assert "llm_error" in res.error
    assert res.data["summary"] is None


def test_summarize_no_input_is_failure():
    agent = SummarizeAgent(llm=_FakeLLM())
    res = agent.run(AgentContext())
    assert not res.ok and res.error == "no_input"


def test_summarize_dispatch_through_orchestrator():
    reg = AgentRegistry(); reg.register(SummarizeAgent(llm=_FakeLLM(reply="ok")))
    orch = Orchestrator(reg, StaticRouter())
    res = orch.dispatch(AgentContext(query="text to summarize"), agent_id="summarize")
    assert res.ok and res.agent == "summarize"


def _main():
    tests = [(n, o) for n, o in globals().items() if n.startswith("test_") and callable(o)]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn(); passed += 1; print(f"PASS {name}")
        except Exception:
            failed += 1; print(f"FAIL {name}"); traceback.print_exc()
    print(f"\nsummarize_agent: {passed} passed, {failed} failed, {len(tests)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
