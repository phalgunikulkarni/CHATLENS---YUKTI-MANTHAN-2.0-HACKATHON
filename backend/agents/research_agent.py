"""Research Agent (functional agent id="research").

Free/local research: DDGS text search (bounded) -> structured sources -> local
Qwen synthesis grounded ONLY in the retrieved snippets. No SearXNG, no paid
search/LLM APIs, no API keys.

Input (via AgentContext):
  context.query            the research question (preferred), or
  params["query"]          explicit query
  params["max_results"]    optional bound (default 5, hard-capped at 10)

Output data:
  query, answer, sources [{title,url,snippet}], evidence
Failures (search or LLM) -> controlled AgentResult.failure.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .contracts import Agent, AgentContext, AgentResult
from .llm_client import LocalLLMClient, LLMError
from . import web_search

_SYSTEM = (
    "You are a careful research assistant. Answer the question using ONLY the "
    "numbered sources provided. Do not use outside knowledge and do not invent "
    "facts. If the sources do not contain the answer, say so plainly. Keep the "
    "answer concise (3-6 sentences)."
)


def _build_prompt(query: str, sources: List[Dict[str, Any]]) -> str:
    blocks = []
    for i, s in enumerate(sources, 1):
        snippet = (s.get("snippet") or "").strip()
        title = (s.get("title") or "").strip()
        url = (s.get("url") or "").strip()
        blocks.append(f"[{i}] {title}\nURL: {url}\n{snippet}")
    joined = "\n\n".join(blocks) if blocks else "(no sources)"
    return (
        f"QUESTION: {query}\n\n"
        f"SOURCES:\n{joined}\n\n"
        "Using only the sources above, write a concise answer. "
        "Cite sources inline like [1], [2] where relevant.\n\nANSWER:"
    )


class ResearchAgent(Agent):
    id = "research"
    description = "Answer a question from bounded web search results, synthesized by the local Qwen model."

    def __init__(self, llm: Optional[LocalLLMClient] = None, search_fn=None) -> None:
        # Injectable LLM + search function for offline unit tests.
        self._llm = llm
        self._search = search_fn or web_search.ddgs_text_search

    def _client(self) -> LocalLLMClient:
        if self._llm is None:
            self._llm = LocalLLMClient()
        return self._llm

    def run(self, context: AgentContext) -> AgentResult:
        params = context.params or {}
        query = (params.get("query") or context.query or "").strip()
        if not query:
            return AgentResult.failure(
                self.id, error="no_query",
                message="Provide a research query (context.query or params.query).",
                data={"query": None, "answer": None, "sources": []},
            )

        try:
            max_results = int(params.get("max_results", 5))
        except (TypeError, ValueError):
            max_results = 5
        max_results = max(1, min(max_results, 10))  # bounded

        # 1) Web search (free ddgs).
        try:
            sources = self._search(query, max_results=max_results)
        except web_search.SearchError as exc:
            return AgentResult.failure(
                self.id, error=f"search_error: {exc}",
                message="Web search failed or is unavailable.",
                data={"query": query, "answer": None, "sources": []},
            )

        if not sources:
            return AgentResult.failure(
                self.id, error="no_results",
                message="No web results were found for this query.",
                data={"query": query, "answer": None, "sources": []},
            )

        # 2) Local LLM synthesis grounded in the snippets.
        prompt = _build_prompt(query, sources)
        try:
            answer = self._client().generate(prompt, system=_SYSTEM, temperature=0.0)
        except LLMError as exc:
            # Search succeeded but synthesis failed: return a controlled failure
            # that still preserves the sources/evidence we did gather.
            return AgentResult.failure(
                self.id, error=f"llm_error: {exc}",
                message="Found sources but the local model failed to synthesize an answer.",
                data={"query": query, "answer": None, "sources": sources},
                evidence=[{"type": "web_result", **s} for s in sources],
            )

        evidence = [{"type": "web_result", **s} for s in sources]
        return AgentResult.success(
            self.id, message="Research answer synthesized from web sources.",
            data={"query": query, "answer": answer, "sources": sources},
            evidence=evidence,
            metadata={"model": self._client().model, "n_sources": len(sources),
                      "search": "ddgs"},
        )
