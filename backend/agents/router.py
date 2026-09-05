"""Routing abstraction: decide which functional agent handles a request.

Phase 2 Step 1 provides ONLY a deterministic interface + a simple static router
for wiring/testing the architecture. The real (possibly LLM-assisted) intent
classifier is a LATER step; it will implement the same `Router` interface.
"""
from __future__ import annotations

import abc
from typing import Optional

from .contracts import AgentContext, AGENT_IDS


class Router(abc.ABC):
    """Returns an agent id (one of AGENT_IDS) for a given context, or None."""

    @abc.abstractmethod
    def route(self, context: AgentContext) -> Optional[str]:
        ...


class StaticRouter(Router):
    """Deterministic router for architecture testing (no LLM).

    Resolution order:
      1. An explicit `context.params["agent"]` id, if valid.
      2. A fixed default agent id supplied at construction (optional).
    Returns None when nothing valid is selected (orchestrator handles that).
    """

    def __init__(self, default_agent: Optional[str] = None) -> None:
        if default_agent is not None and default_agent not in AGENT_IDS:
            raise ValueError(f"default_agent must be one of {AGENT_IDS}")
        self.default_agent = default_agent

    def route(self, context: AgentContext) -> Optional[str]:
        requested = (context.params or {}).get("agent")
        if requested in AGENT_IDS:
            return requested
        return self.default_agent
