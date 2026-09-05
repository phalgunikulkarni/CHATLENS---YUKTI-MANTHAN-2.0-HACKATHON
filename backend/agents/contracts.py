"""Shared agent contract: base Agent, AgentContext, AgentResult.

Lightweight, plain-Python (dataclasses + ABC). Each functional agent implements
the same tiny interface so the orchestrator can invoke them uniformly, while
each agent's domain payload stays in a free-form `data` dict (a small common
envelope with agent-specific data inside — outputs are NOT forced into one
identical shape).
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# The fixed set of functional agent identifiers (Phase 2 scope). Intent/
# Retrieval/Analysis/Verification/Explanation are internal capabilities, NOT
# entries here.
AGENT_IDS = (
    "summarize",
    "add_calendar",
    "add_task",
    "reminder",
    "analyze_bill",
    "research",
)


@dataclass
class AgentContext:
    """Minimum shared context an agent may need for one invocation.

    Does NOT own auth/account logic: `account_id` is passed through from the
    backend's existing resolve_account result; agents must not re-derive or
    bypass account scoping. `memories` holds already-retrieved results (list of
    ml_retrieval dicts) when the caller has them; otherwise an agent may request
    retrieval via the retrieval_access seam.
    """

    query: str = ""
    session_id: Optional[str] = None
    account_id: Optional[str] = None
    memories: List[Dict[str, Any]] = field(default_factory=list)
    # Free-form, agent-specific parameters (e.g. image_ids, datetime, url).
    params: Dict[str, Any] = field(default_factory=dict)
    # Optional prior conversation context, when the caller already has it.
    conversation: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentResult:
    """Common structured envelope for any agent's output.

    A small, uniform envelope (`ok`, `agent`, `message`, `error`, `metadata`)
    wrapping an agent-specific free-form `data` dict, plus optional grounded
    `evidence` (e.g. source image_ids / references). This supports the very
    different outputs of summarize / calendar / task / reminder / bill / research
    without forcing an unnatural identical payload.
    """

    agent: str
    ok: bool = True
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    @classmethod
    def success(cls, agent: str, message: str = "", **kw) -> "AgentResult":
        return cls(agent=agent, ok=True, message=message, **kw)

    @classmethod
    def failure(cls, agent: str, error: str, message: str = "", **kw) -> "AgentResult":
        return cls(agent=agent, ok=False, error=error, message=message, **kw)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent,
            "ok": self.ok,
            "message": self.message,
            "data": self.data,
            "evidence": self.evidence,
            "metadata": self.metadata,
            "error": self.error,
        }


class AgentError(Exception):
    """Raised inside an agent for a controlled, expected failure.

    The orchestrator converts any exception (including this one) into an
    AgentResult.failure(...), so an agent failure never crashes the caller.
    """


class Agent(abc.ABC):
    """Base class for the six functional agents.

    Subclasses set `id` (one of AGENT_IDS) and `description`, and implement
    `run(context) -> AgentResult`. Subclasses should raise AgentError (or return
    AgentResult.failure) on expected failures; the orchestrator guards against
    unexpected exceptions regardless.
    """

    id: str = ""
    description: str = ""

    @abc.abstractmethod
    def run(self, context: AgentContext) -> AgentResult:
        ...

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Agent id={self.id!r}>"
