"""Minimal agent orchestrator: route -> invoke -> structured result.

Keeps routing (Router) separate from execution (Agent). Guards every agent call
so a failure becomes a controlled AgentResult.failure(...) rather than an
exception escaping to the backend. No autonomous planning; a single optional
multi-agent `run_sequence` is provided for genuinely sequential workflows.
"""
from __future__ import annotations

from typing import List, Optional

from .contracts import Agent, AgentContext, AgentResult
from .registry import AgentRegistry
from .router import Router


class Orchestrator:
    def __init__(self, registry: AgentRegistry, router: Optional[Router] = None) -> None:
        self.registry = registry
        self.router = router

    def _invoke(self, agent: Agent, context: AgentContext) -> AgentResult:
        try:
            result = agent.run(context)
            if not isinstance(result, AgentResult):
                return AgentResult.failure(
                    agent.id, error="agent returned non-AgentResult",
                    message="Internal agent contract violation.",
                )
            return result
        except Exception as exc:  # noqa: BLE001 - orchestrator must never leak agent errors
            return AgentResult.failure(
                agent.id, error=f"{type(exc).__name__}: {exc}",
                message="The agent failed to complete the request.",
            )

    def dispatch(self, context: AgentContext, agent_id: Optional[str] = None) -> AgentResult:
        """Route (if agent_id not given) then execute one agent."""
        selected = agent_id
        if selected is None and self.router is not None:
            selected = self.router.route(context)
        if not selected:
            return AgentResult.failure(
                agent="orchestrator", error="no_route",
                message="Could not determine which agent should handle this request.",
            )
        agent = self.registry.get(selected)
        if agent is None:
            return AgentResult.failure(
                agent="orchestrator", error="unknown_agent",
                message=f"No agent registered for id {selected!r}.",
            )
        return self._invoke(agent, context)

    def run_sequence(self, context: AgentContext, agent_ids: List[str]) -> List[AgentResult]:
        """Run several agents in order (each guarded). For genuinely multi-step
        workflows only; not an autonomous planner."""
        return [self.dispatch(context, agent_id=aid) for aid in agent_ids]
