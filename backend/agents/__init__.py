"""ChatLens agent infrastructure (Phase 2).

Minimal, framework-free shared architecture for the SIX functional agents
(Summarize, AddCalendar, AddTask, Reminder, AnalyzeBill, Research). This package
contains the shared contract, structured result/context, a registry, a
deterministic orchestrator, a thin retrieval-access helper that REUSES the
existing backend/ml_retrieval.py seam, a small LOCAL-LLM client (Ollama/Qwen),
a free web-search seam (ddgs), and the functional agents implemented so far
(P2S2: Reminder, AnalyzeBill; P2S3: Summarize, Research).

No paid/cloud LLM, no API keys, and no large agent framework
(LangChain/LlamaIndex/etc.) live here.
"""
from .contracts import (
    Agent,
    AgentContext,
    AgentResult,
    AgentError,
    AGENT_IDS,
)
from .registry import AgentRegistry
from .orchestrator import Orchestrator
from .router import Router, StaticRouter
from .retrieval_access import search_memories

# Functional agents implemented so far.
from .reminder_agent import ReminderAgent
from .analyze_bill_agent import AnalyzeBillAgent
from .summarize_agent import SummarizeAgent
from .research_agent import ResearchAgent
from .add_calendar_agent import AddCalendarAgent
from .add_task_agent import AddTaskAgent


def build_default_registry() -> AgentRegistry:
    """Registry pre-loaded with the currently-implemented functional agents.

    Implemented: Reminder, AnalyzeBill (P2S2), Summarize, Research (P2S3). The
    remaining two (add_calendar, add_task) are registered in later steps.
    Backend/frontend wiring is out of scope here (P2S5). This factory gives
    tests and future integration one place to obtain a populated registry.
    """
    reg = AgentRegistry()
    reg.register(ReminderAgent())
    reg.register(AnalyzeBillAgent())
    reg.register(SummarizeAgent())
    reg.register(ResearchAgent())
    reg.register(AddCalendarAgent())
    reg.register(AddTaskAgent())
    return reg


__all__ = [
    "Agent",
    "AgentContext",
    "AgentResult",
    "AgentError",
    "AGENT_IDS",
    "AgentRegistry",
    "Orchestrator",
    "Router",
    "StaticRouter",
    "search_memories",
    "ReminderAgent",
    "AnalyzeBillAgent",
    "SummarizeAgent",
    "ResearchAgent",
    "AddCalendarAgent",
    "AddTaskAgent",
    "build_default_registry",
]
