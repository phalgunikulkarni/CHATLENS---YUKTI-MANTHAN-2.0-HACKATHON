"""Thin retrieval seam for agents.

REUSES the existing backend/ml_retrieval.py `search_memories` — it does NOT
duplicate or modify retrieval. This indirection exists only so agents depend on
a stable, testable function (which tests can monkeypatch) instead of importing
ml_retrieval internals directly.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def search_memories(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Call the existing retrieval seam. Returns [] on blank query / any failure
    (delegated behavior of ml_retrieval.search_memories; never fabricates)."""
    import ml_retrieval  # local import: keep agent import cheap, reuse the seam
    return ml_retrieval.search_memories(query, top_k=top_k)


def resolve_image_path(image_id: str) -> Optional[str]:
    """Reuse ml_retrieval.resolve_image_path (validated on-disk path or None)."""
    import ml_retrieval
    return ml_retrieval.resolve_image_path(image_id)


def get_stored_ocr_text(image_id: str) -> Optional[str]:
    """Return already-indexed OCR text for an image_id, if any (no re-OCR).

    Reuses the existing text collection metadata (`extracted_text`) via the
    store the backend already opened. Returns None on any failure — callers then
    fall back to running the existing OCRExtractor on a resolved path.
    """
    if not image_id or not str(image_id).strip():
        return None
    try:
        import ml_retrieval
        store = ml_retrieval._get_store()  # reuse the same store instance
        if store is None:
            return None
        rec = store.get_text_by_image_id(image_id)
    except Exception:  # noqa: BLE001 - retrieval is best-effort here
        return None
    if not rec:
        return None
    md = rec.get("metadata") or {}
    text = md.get("extracted_text")
    return text if text else None
