"""Selected-memory action orchestration (P2S5.1).

Connects the existing selected-memory UI actions (Summarize / Extract Key Points
/ Revision Roadmap / Related Memories) to the EXISTING agent + retrieval layer.

Deterministic capability routing (NO LLM used to decide the fixed UI actions):
  "summarize"    -> summarize agent (mode=summary)
  "key_points"   -> summarize agent (mode=key_points)
  "roadmap"      -> summarize agent (mode=roadmap)
  "related"      -> ml_retrieval.search_memories (NO new agent)
  "analyze_bill" -> analyze_bill agent (analysis + bill splitting via operation=split)
  "research"     -> research agent

Selected-memory context (image_id, filename, category, OCR/extracted_text,
file_path/absolute_path) is gathered via the EXISTING retrieval seam and passed
into the agent. No new retrieval system, no new agent, no paid API.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import ml_retrieval
from agents import build_default_registry, Orchestrator, AgentContext
from agents import retrieval_access

# One shared orchestrator/registry (agents are stateless; safe to reuse).
_REGISTRY = build_default_registry()
_ORCH = Orchestrator(_REGISTRY)

# UI action -> (agent_id, summarize mode) for the LLM-backed text actions.
_SUMMARY_MODES = {
    "summarize": "summary",
    "summary": "summary",
    "key_points": "key_points",
    "keypoints": "key_points",
    "roadmap": "roadmap",
    "revision_roadmap": "roadmap",
}


def _memory_context(image_id: str) -> Dict[str, Any]:
    """Gather selected-memory context via the EXISTING retrieval seam.

    Returns a dict with image_id, filename, category, extracted_text, and
    file/absolute path where already available. Never fabricates.
    """
    ctx: Dict[str, Any] = {"image_id": image_id}
    # OCR/extracted text via the P2S2 reuse helper (stored text; no re-OCR).
    ctx["extracted_text"] = retrieval_access.get_stored_ocr_text(image_id)
    # filename/category/paths from the visual record metadata (read-only).
    try:
        store = ml_retrieval._get_store()
        rec = store.get_visual_by_image_id(image_id) if store else None
        md = (rec or {}).get("metadata") or {}
        ctx["filename"] = md.get("filename")
        ctx["category"] = md.get("category")
        ctx["absolute_path"] = md.get("absolute_path")
        ctx["file_path"] = md.get("file_path")
        if not ctx.get("extracted_text"):
            ctx["extracted_text"] = md.get("extracted_text")
    except Exception:  # noqa: BLE001 - context gathering is best-effort
        pass
    return ctx


def _collect_text(image_ids: List[str]) -> Dict[str, Any]:
    """Concatenate OCR/extracted text across the selected memories.

    A per-memory [filename] label is only added when MORE THAN ONE memory
    contributes text, so a single-memory summary/key-points is not polluted by
    a header line.
    """
    collected: List[tuple] = []  # (image_id, filename, text)
    contexts: List[Dict[str, Any]] = []
    for iid in image_ids:
        c = _memory_context(iid)
        contexts.append(c)
        txt = (c.get("extracted_text") or "").strip()
        if txt:
            collected.append((iid, c.get("filename") or iid, txt))
    used = [iid for iid, _, _ in collected]
    if len(collected) <= 1:
        text = collected[0][2] if collected else ""
    else:
        text = "\n\n".join(f"[{fn}]\n{txt}" for _, fn, txt in collected)
    return {"text": text, "used_image_ids": used, "contexts": contexts}


def run_summary_action(account_id: str, image_ids: List[str], action: str) -> Dict[str, Any]:
    """Run a summarize/key_points/roadmap action over the selected memories.

    Returns the AgentResult dict (ok, agent, message, data, evidence, metadata).
    """
    mode = _SUMMARY_MODES.get((action or "summarize").strip().lower(), "summary")
    collected = _collect_text(image_ids)
    ctx = AgentContext(
        account_id=account_id,
        params={"text": collected["text"], "mode": mode},
    )
    result = _ORCH.dispatch(ctx, agent_id="summarize")
    payload = result.to_dict()
    # Attach which memories actually contributed text (grounding/evidence).
    payload.setdefault("metadata", {})
    payload["metadata"]["used_image_ids"] = collected["used_image_ids"]
    return payload


def run_related_memories(account_id: str, image_id: str, query: Optional[str] = None,
                         top_k: int = 5) -> Dict[str, Any]:
    """Find memories related to the selected one via EXISTING retrieval.

    Uses ml_retrieval.search_memories (NO new agent, NO new retrieval system).
    The query is the provided text, else the selected memory's OCR text/filename.
    Excludes the selected image from the results when possible.
    """
    ctx = _memory_context(image_id)
    q = (query or "").strip()
    if not q:
        q = (ctx.get("extracted_text") or "").strip() or (ctx.get("filename") or "").strip()
    # Bound the query to a compact snippet. The visual channel uses CLIP's text
    # encoder, which has a hard 77-token limit; a short leading snippet (first
    # line, capped words) stays well under it and gives a focused related query.
    q = " ".join(q.replace("\n", " ").split())     # collapse whitespace/newlines
    q = " ".join(q.split(" ")[:24])                    # ~24 words << 77 tokens
    if not q:
        return {"ok": False, "error": "no_query",
                "message": "No text available on the selected memory to find related items.",
                "results": []}
    # Fetch a few extra so removing the selected image still yields top_k.
    raw = ml_retrieval.search_memories(q, top_k=top_k + 2)
    related = [r for r in raw if r.get("image_id") != image_id][:top_k]
    return {
        "ok": True,
        "message": f"Found {len(related)} related memories.",
        "raw": related,                 # ml_retrieval dicts -> caller maps to MemoryResult
        "evidence": [{"type": "related_query", "query": q, "source_image_id": image_id}],
        "metadata": {"source_image_id": image_id, "retrieval": "ml_retrieval.search_memories"},
    }


def run_analyze_bill(account_id: str, image_ids: List[str],
                     extra_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run the Finance/Receipt agent over a selected memory (analysis or split).

    Reuses the SAME analyze_bill agent + existing OCR context gathering. When
    extra_params include operation="split" (+ split_mode/people/assignments/...),
    the agent performs bill splitting. Never invents values.

    Returns the AgentResult dict (ok, agent, message, data, evidence, metadata).
    """
    params: Dict[str, Any] = dict(extra_params or {})
    # Gather OCR text from the first selected memory (consistent with summarize).
    if image_ids:
        ctx = _memory_context(image_ids[0])
        txt = (ctx.get("extracted_text") or "").strip()
        if txt and not params.get("ocr_text"):
            params["ocr_text"] = txt
        params.setdefault("image_id", image_ids[0])
    agent_ctx = AgentContext(account_id=account_id, params=params)
    return _ORCH.dispatch(agent_ctx, agent_id="analyze_bill").to_dict()


def run_research(account_id: str, query: str, max_results: Optional[int] = None,
                 providers: Optional[List[str]] = None) -> Dict[str, Any]:
    """Run the existing Research agent for a natural-language query.

    Invokes the SAME research agent through the shared orchestrator (no new
    agent, no duplicated research logic). Passes the query + optional bounds; the
    agent owns provider selection, dedup, ranking, and grounded Qwen synthesis.

    Returns the AgentResult dict (ok, agent, message, data{research_answer,
    key_findings, sources, limitations}, evidence, metadata).
    """
    params: Dict[str, Any] = {"query": (query or "").strip()}
    if max_results is not None:
        params["max_results"] = max_results
    if providers:
        params["providers"] = providers
    agent_ctx = AgentContext(account_id=account_id, query=params["query"], params=params)
    return _ORCH.dispatch(agent_ctx, agent_id="research").to_dict()
