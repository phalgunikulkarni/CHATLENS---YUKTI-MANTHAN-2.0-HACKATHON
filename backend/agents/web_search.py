"""Thin web-search seam using the free/open-source `ddgs` package (MIT).

No SearXNG, no Google/Bing paid APIs, no API keys. Isolated here so the Research
agent depends on a small stable function that tests can monkeypatch offline.
"""
from __future__ import annotations

from typing import Any, Dict, List


class SearchError(Exception):
    """Controlled web-search failure."""


def ddgs_text_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Run one bounded DDGS text search. Returns normalized rows:
        [{"title": str, "url": str, "snippet": str}, ...]
    Raises SearchError on any failure (import/network/backend)."""
    if not query or not str(query).strip():
        raise SearchError("empty query")
    try:
        from ddgs import DDGS
    except Exception as exc:  # noqa: BLE001
        raise SearchError(f"ddgs not available: {exc}") from exc
    try:
        rows = DDGS().text(str(query).strip(), max_results=max(1, int(max_results)))
    except Exception as exc:  # noqa: BLE001 - network/backend/ratelimit
        raise SearchError(f"web search failed: {exc}") from exc

    normalized: List[Dict[str, Any]] = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        normalized.append({
            "title": r.get("title") or "",
            "url": r.get("href") or r.get("url") or "",
            "snippet": r.get("body") or r.get("snippet") or "",
        })
    return normalized
