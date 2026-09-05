"""Research Agent (functional agent id="research").

Credible MULTI-SOURCE research (NOT a generic DDGS answer generator). A
provider-based pipeline queries scholarly + official sources (OpenAlex, Crossref,
arXiv, PubMed) with DDGS as a general discovery fallback, aggregates, dedups and
ranks them, then the LOCAL Qwen model synthesizes an answer grounded ONLY in the
collected evidence. No paid API; the only optional key is OPENALEX_API_KEY (read
from env, never hard-coded/logged/returned). No new agent is introduced.

Input (via AgentContext):
  context.query / params["query"]   the research question
  params["max_results"]             target source count (default 5, cap 10)
  params["providers"]               optional explicit provider name list

Output data:
  query, research_answer, key_findings, sources[normalized], limitations
  (plus legacy aliases: answer, and sources kept structured for the frontend)

Backward compatible: when a `search_fn` is injected (tests / legacy callers) the
agent uses the original single-provider DDGS path and legacy result shape.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .contracts import Agent, AgentContext, AgentResult
from .llm_client import LocalLLMClient, LLMError
from . import web_search
from . import research_pipeline

_SYSTEM = (
    "You are a careful research assistant. Use ONLY the numbered sources "
    "provided as evidence. Do NOT use outside knowledge. Do NOT invent "
    "citations, paper titles, authors, DOIs, or URLs. Distinguish abstract or "
    "snippet evidence from full-text: you have only abstracts/snippets, so do "
    "NOT claim to have read a full paper. State uncertainty plainly and never "
    "present unsupported claims as facts. If the evidence is insufficient, say so."
)


def _evidence_block(sources: List[Dict[str, Any]]) -> str:
    blocks = []
    for i, s in enumerate(sources, 1):
        lines = [f"[{i}] {s.get('title') or '(untitled)'}"]
        if s.get("provider"):
            lines.append(f"Provider: {s['provider']} ({s.get('source_type') or 'source'})")
        if s.get("authors"):
            lines.append("Authors: " + ", ".join(s["authors"][:6]))
        if s.get("year") or s.get("publication_date"):
            lines.append(f"Published: {s.get('publication_date') or s.get('year')}")
        if s.get("doi"):
            lines.append(f"DOI: {s['doi']}")
        if s.get("url"):
            lines.append(f"URL: {s['url']}")
        ev = s.get("abstract")
        kind = "ABSTRACT"
        if not ev:
            ev = s.get("snippet")
            kind = "SNIPPET"
        if ev:
            lines.append(f"{kind}: {ev}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) if blocks else "(no sources)"


def _build_prompt(query: str, sources: List[Dict[str, Any]]) -> str:
    return (
        f"QUESTION: {query}\n\n"
        f"EVIDENCE (abstracts/snippets only — you have NOT read full papers):\n"
        f"{_evidence_block(sources)}\n\n"
        "Write a concise research answer (4-8 sentences) using ONLY the evidence "
        "above, citing sources inline like [1], [2]. Then, on new lines, list 2-5 "
        "key findings each prefixed with '- '. Do not invent anything.\n\n"
        "ANSWER:"
    )


def _split_answer_and_findings(raw: str) -> Dict[str, Any]:
    """Best-effort split of the model output into answer + key findings list."""
    lines = (raw or "").splitlines()
    findings: List[str] = []
    answer_lines: List[str] = []
    for ln in lines:
        s = ln.strip()
        if s.startswith(("- ", "* ", "• ")):
            findings.append(s[2:].strip())
        elif s[:2].rstrip(".").isdigit() and s[1:2] in ".) ":
            findings.append(s[2:].strip())
        else:
            if s:
                answer_lines.append(s)
    return {"answer": " ".join(answer_lines).strip() or (raw or "").strip(),
            "key_findings": findings}


class ResearchAgent(Agent):
    id = "research"
    description = "Credible multi-source research (scholarly providers + local Qwen synthesis)."

    def __init__(self, llm: Optional[LocalLLMClient] = None, search_fn=None,
                 collect_fn=None) -> None:
        # search_fn -> legacy single-provider (DDGS) path (kept for back-compat/tests)
        # collect_fn -> injectable multi-provider aggregator (tests)
        self._llm = llm
        self._search = search_fn
        self._collect = collect_fn or research_pipeline.collect

    def _client(self) -> LocalLLMClient:
        if self._llm is None:
            self._llm = LocalLLMClient()
        return self._llm

    # -- entry point ----------------------------------------------------------

    def run(self, context: AgentContext) -> AgentResult:
        params = context.params or {}
        query = (params.get("query") or context.query or "").strip()
        if not query:
            return AgentResult.failure(
                self.id, error="no_query",
                message="Provide a research query (context.query or params.query).",
                data={"query": None, "answer": None, "research_answer": None,
                      "sources": [], "key_findings": [], "limitations": []},
            )

        try:
            max_results = int(params.get("max_results", 5))
        except (TypeError, ValueError):
            max_results = 5
        max_results = max(1, min(max_results, 10))

        if self._search is not None:
            return self._run_legacy(query, max_results)   # back-compat path
        return self._run_pipeline(query, max_results, params)

    # -- legacy single-provider (DDGS) path — unchanged shape -----------------

    def _run_legacy(self, query: str, max_results: int) -> AgentResult:
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
        prompt = (
            f"QUESTION: {query}\n\nSOURCES:\n"
            + "\n\n".join(f"[{i}] {s.get('title','')}\nURL: {s.get('url','')}\n{s.get('snippet','')}"
                          for i, s in enumerate(sources, 1))
            + "\n\nUsing only the sources above, write a concise answer. "
              "Cite sources inline like [1], [2] where relevant.\n\nANSWER:"
        )
        try:
            answer = self._client().generate(prompt, system=_SYSTEM, temperature=0.0)
        except LLMError as exc:
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

    # -- multi-provider scholarly pipeline ------------------------------------

    def _run_pipeline(self, query: str, max_results: int, params: Dict[str, Any]) -> AgentResult:
        provider_names = params.get("providers") if isinstance(params.get("providers"), list) else None
        try:
            agg = self._collect(query, per_provider=max_results, target=max_results,
                                provider_names=provider_names)
        except Exception as exc:  # noqa: BLE001 - aggregation must never crash
            return AgentResult.failure(
                self.id, error=f"aggregation_error: {type(exc).__name__}",
                message="Research providers could not be queried.",
                data={"query": query, "research_answer": None, "answer": None,
                      "sources": [], "key_findings": [], "limitations": [
                          "Provider aggregation failed."]},
            )

        sources = agg.get("sources") or []
        limitations: List[str] = []
        if agg.get("providers_failed"):
            limitations.append(
                "Some providers were unavailable: " + ", ".join(agg["providers_failed"]) + ".")
        if not sources:
            limitations.append("No reliable evidence could be retrieved for this query.")
            return AgentResult.failure(
                self.id, error="no_evidence",
                message="Reliable research evidence could not be retrieved; no answer was generated.",
                data={"query": query, "research_answer": None, "answer": None,
                      "sources": [], "key_findings": [], "limitations": limitations},
                metadata={"providers_used": agg.get("providers_used", []),
                          "providers_failed": agg.get("providers_failed", [])},
            )
        if len(sources) < 4:
            limitations.append(
                f"Only {len(sources)} credible source(s) were found; findings may be limited.")

        prompt = _build_prompt(query, sources)
        try:
            raw = self._client().generate(prompt, system=_SYSTEM, temperature=0.0)
        except LLMError as exc:
            # Preserve gathered sources/evidence even if synthesis failed.
            return AgentResult.failure(
                self.id, error=f"llm_error: {exc}",
                message="Collected sources but the local model failed to synthesize an answer.",
                data={"query": query, "research_answer": None, "answer": None,
                      "sources": sources, "key_findings": [],
                      "limitations": limitations + ["Local model synthesis failed."]},
                evidence=[{"type": "research_source", **s} for s in sources],
                metadata={"providers_used": agg.get("providers_used", [])},
            )

        parsed = _split_answer_and_findings(raw)
        evidence = [{"type": "research_source", **s} for s in sources]
        return AgentResult.success(
            self.id, message="Research synthesized from credible multi-source evidence.",
            data={
                "query": query,
                "research_answer": parsed["answer"],
                "answer": parsed["answer"],                 # legacy alias
                "key_findings": parsed["key_findings"],
                "sources": sources,                          # normalized metadata + URLs
                "limitations": limitations,
            },
            evidence=evidence,
            metadata={
                "model": self._client().model,
                "n_sources": len(sources),
                "providers_used": agg.get("providers_used", []),
                "providers_failed": agg.get("providers_failed", []),
                "provider_counts": agg.get("provider_counts", {}),
                "search": "multi_provider",
            },
        )
