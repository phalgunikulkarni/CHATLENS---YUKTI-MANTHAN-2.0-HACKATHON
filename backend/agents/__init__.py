"""ChatLens agent infrastructure (Phase 2).

Minimal, framework-free shared architecture for the SIX functional agents
(Summarize, AddCalendar, AddTask, AnalyzeBill, Research). This package
contains the shared contract, structured result/context, a registry, a
deterministic orchestrator, a thin retrieval-access helper that REUSES the
existing backend/ml_retrieval.py seam, a small LOCAL-LLM client (Ollama/Qwen),
a free web-search seam (ddgs), and the five functional agents
(Summarize, AddCalendar, AddTask, AnalyzeBill, Research).

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
from .analyze_bill_agent import AnalyzeBillAgent
from .summarize_agent import SummarizeAgent
from .research_agent import ResearchAgent
from .add_calendar_agent import AddCalendarAgent
from .add_task_agent import AddTaskAgent


def build_default_registry() -> AgentRegistry:
    """Registry pre-loaded with the five functional agents.

    Exactly five: summarize, add_calendar, add_task, analyze_bill, research.
    (The Reminder agent was removed in the five-agent alignment; the shared
    APScheduler reminder_service remains for calendar-event reminders.) This
    factory gives tests and integration one place to obtain a populated registry.
    """
    reg = AgentRegistry()
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
    "AnalyzeBillAgent",
    "SummarizeAgent",
    "ResearchAgent",
    "AddCalendarAgent",
    "AddTaskAgent",
    "build_default_registry",
]
