"""Summarize Agent (functional agent id="summarize").

Produces a concise summary of provided text using the LOCAL Qwen model
(LocalLLMClient -> Ollama -> qwen2.5:3b). Source text is preserved as evidence;
prompts are deterministic and instruct the model not to add facts. LLM failures
become controlled AgentResult failures. No paid/cloud LLM is used.

Supports three explicit modes (params["mode"], default "summary"):
  - "summary":     a concise 2-4 sentence summary (default; unchanged behavior)
  - "key_points":  a short bulleted list of key points (data["points"])
  - "roadmap":     an ordered revision roadmap (data["steps"])

Input text (via AgentContext), first non-empty wins:
  params["text"]            explicit text to summarize (e.g. selected OCR text)
  context.conversation      list of {role/author?, content/text?} turns
  context.query             fallback single string
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .contracts import Agent, AgentContext, AgentResult
from .llm_client import LocalLLMClient, LLMError

_VALID_MODES = ("summary", "key_points", "roadmap")

_SYSTEM = (
    "You are a concise assistant. Use ONLY the information present in the "
    "provided text. Do not add facts, opinions, or details that are not stated. "
    "If the text is too short, say so briefly rather than inventing content."
)


def _conversation_to_text(conversation: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for turn in conversation or []:
        if not isinstance(turn, dict):
            continue
        role = turn.get("role") or turn.get("author") or ""
        content = turn.get("content") or turn.get("text") or ""
        if not content:
            continue
        lines.append(f"{role}: {content}".strip(": ").strip())
    return "\n".join(lines)


def _prompt_for(mode: str, text: str) -> str:
    if mode == "key_points":
        return (
            "Extract the key points from the text below as a short bulleted list "
            "(one point per line, starting with '- '). Use only what is stated.\n\n"
            f"TEXT:\n{text}\n\nKEY POINTS:"
        )
    if mode == "roadmap":
        return (
            "Turn the text below into an ordered revision roadmap: a numbered list "
            "of concise study/revision steps (one per line, starting with '1.', "
            "'2.', ...). Use only what is stated.\n\n"
            f"TEXT:\n{text}\n\nROADMAP:"
        )
    return (
        "Summarize the following text in 2-4 concise sentences. "
        "Use only what is stated below.\n\n"
        f"TEXT:\n{text}\n\nSUMMARY:"
    )


def _parse_points(raw: str) -> List[str]:
    points: List[str] = []
    for line in (raw or "").splitlines():
        s = line.strip()
        if not s:
            continue
        s = re.sub(r"^[-*\u2022]\s*", "", s)          # bullet markers
        s = re.sub(r"^\d+[.)]\s*", "", s)               # numbered markers
        if s:
            points.append(s)
    return points


class SummarizeAgent(Agent):
    id = "summarize"
    description = "Summarize / extract key points / build a revision roadmap using the local Qwen model."

    def __init__(self, llm: Optional[LocalLLMClient] = None) -> None:
        self._llm = llm  # injectable for tests

    def _client(self) -> LocalLLMClient:
        if self._llm is None:
            self._llm = LocalLLMClient()
        return self._llm

    def _source_text(self, context: AgentContext) -> str:
        params = context.params or {}
        explicit = params.get("text")
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip()
        convo = _conversation_to_text(context.conversation)
        if convo.strip():
            return convo
        if context.query and context.query.strip():
            return context.query.strip()
        return ""

    def run(self, context: AgentContext) -> AgentResult:
        params = context.params or {}
        mode = (params.get("mode") or "summary").strip().lower()
        if mode not in _VALID_MODES:
            mode = "summary"

        text = self._source_text(context)
        if not text:
            # No OCR/text available: do NOT fabricate image contents.
            return AgentResult.failure(
                self.id, error="no_input",
                message="No text could be extracted from the selected memory, so it "
                        "cannot be summarized. (No content was invented.)",
                data={"summary": None, "points": [], "steps": [], "mode": mode},
                metadata={"mode": mode},
            )

        prompt = _prompt_for(mode, text)
        try:
            out = self._client().generate(prompt, system=_SYSTEM, temperature=0.0)
        except LLMError as exc:
            return AgentResult.failure(
                self.id, error=f"llm_error: {exc}",
                message="The local model was unavailable or failed.",
                data={"summary": None, "points": [], "steps": [], "mode": mode},
                metadata={"mode": mode},
            )

        data: Dict[str, Any] = {"mode": mode, "source_chars": len(text)}
        if mode == "key_points":
            points = _parse_points(out)
            data.update({"summary": out, "points": points, "steps": []})
            msg = "Key points extracted."
        elif mode == "roadmap":
            steps = _parse_points(out)
            data.update({"summary": out, "points": [], "steps": steps})
            msg = "Revision roadmap generated."
        else:
            data.update({"summary": out, "points": [], "steps": []})
            msg = "Summary generated."

        return AgentResult.success(
            self.id, message=msg, data=data,
            evidence=[{"type": "source_text", "text": text}],
            metadata={"model": self._client().model, "extractor": "local_llm", "mode": mode},
        )
