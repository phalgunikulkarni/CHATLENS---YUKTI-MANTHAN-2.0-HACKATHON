"""Agent registry: maps agent id -> Agent instance."""
from __future__ import annotations

from typing import Dict, List

from .contracts import Agent, AGENT_IDS


class AgentRegistry:
    """A tiny in-memory registry of functional agents keyed by id."""

    def __init__(self) -> None:
        self._agents: Dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        if not getattr(agent, "id", ""):
            raise ValueError("Agent must define a non-empty id")
        if agent.id not in AGENT_IDS:
            raise ValueError(
                f"Unknown agent id {agent.id!r}; must be one of {AGENT_IDS}"
            )
        self._agents[agent.id] = agent

    def get(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)

    def has(self, agent_id: str) -> bool:
        return agent_id in self._agents

    def ids(self) -> List[str]:
        return list(self._agents.keys())
