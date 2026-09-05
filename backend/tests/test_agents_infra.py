"""Phase 2 Step 1 - shared agent infrastructure tests (no functional agents).

Uses a MockAgent to prove: registration, routing, execution, structured result,
controlled failure, and that the existing retrieval seam is still callable.
No torch/CLIP/OCR loads (retrieval is monkeypatched).
"""
from __future__ import annotations

from agents import (
    Agent, AgentContext, AgentResult, AgentError,
    AgentRegistry, Orchestrator, StaticRouter, AGENT_IDS,
)


class MockAgent(Agent):
    id = "summarize"  # reuse a valid functional id for the harness
    description = "test mock"

    def run(self, context: AgentContext) -> AgentResult:
        return AgentResult.success(
            self.id, message=f"echo:{context.query}",
            data={"query": context.query, "n_memories": len(context.memories)},
            evidence=[{"image_id": m.get("image_id")} for m in context.memories],
        )


class FailingAgent(Agent):
    id = "research"
    description = "always fails"

    def run(self, context: AgentContext) -> AgentResult:
        raise AgentError("boom")


def test_a_register():
    reg = AgentRegistry()
    reg.register(MockAgent())
    assert reg.has("summarize") and reg.get("summarize") is not None


def test_register_rejects_unknown_id():
    class Bad(Agent):
        id = "not_a_real_agent"
        def run(self, c): return AgentResult.success(self.id)
    reg = AgentRegistry()
    try:
        reg.register(Bad())
        assert False, "should reject unknown id"
    except ValueError:
        pass


def test_b_c_d_route_execute_structured_result():
    reg = AgentRegistry(); reg.register(MockAgent())
    orch = Orchestrator(reg, StaticRouter(default_agent="summarize"))
    ctx = AgentContext(query="hello", memories=[{"image_id": "img1"}])
    res = orch.dispatch(ctx)  # B: routed via StaticRouter; C: executed
    assert isinstance(res, AgentResult)                # D: structured
    assert res.ok and res.agent == "summarize"
    assert res.message == "echo:hello"
    assert res.data["n_memories"] == 1
    assert res.evidence == [{"image_id": "img1"}]
    assert res.to_dict()["ok"] is True


def test_route_via_params_agent():
    reg = AgentRegistry(); reg.register(MockAgent())
    orch = Orchestrator(reg, StaticRouter())
    ctx = AgentContext(query="x", params={"agent": "summarize"})
    assert orch.dispatch(ctx).ok


def test_no_route_is_controlled_failure():
    orch = Orchestrator(AgentRegistry(), StaticRouter())
    res = orch.dispatch(AgentContext(query="x"))
    assert not res.ok and res.error == "no_route"


def test_unknown_agent_is_controlled_failure():
    orch = Orchestrator(AgentRegistry(), StaticRouter(default_agent="summarize"))
    res = orch.dispatch(AgentContext(query="x"))  # routed to summarize but none registered
    assert not res.ok and res.error == "unknown_agent"


def test_e_agent_failure_is_controlled():
    reg = AgentRegistry(); reg.register(FailingAgent())
    orch = Orchestrator(reg)
    res = orch.dispatch(AgentContext(query="x"), agent_id="research")
    assert not res.ok
    assert "boom" in (res.error or "")
    assert res.agent == "research"  # failure never raised out of the orchestrator


def test_f_retrieval_seam_reused(monkeypatch):
    # The agent retrieval helper must delegate to ml_retrieval.search_memories.
    import ml_retrieval
    monkeypatch.setattr(ml_retrieval, "search_memories",
                        lambda q, top_k=5: [{"image_id": "abc", "q": q, "k": top_k}])
    from agents.retrieval_access import search_memories
    rows = search_memories("penguins", top_k=3)
    assert rows == [{"image_id": "abc", "q": "penguins", "k": 3}]


def test_agent_ids_are_the_six_functional_agents():
    assert AGENT_IDS == (
        "summarize", "add_calendar", "add_task", "reminder", "analyze_bill", "research",
    )
