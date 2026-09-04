"""
Thin adapter between the backend /api layer and the canonical ml/ retrieval
engine (Chroma-based).

This is the ONLY backend module that imports ml.*. It isolates the ml
dependency so the rest of the backend never touches Chroma / retriever
internals directly.

Design principles:
- Never fabricate results or signals. If the canonical retriever is
  unavailable (missing ml deps, empty Chroma, etc.), return empty results.
- Grounded evidence only: explanations must come from a real retrieval,
  never invented.
"""

import os
import sys
from typing import List, Optional

# Put the project root (parent of backend/) on sys.path so `import ml...`
# resolves regardless of the current working directory. Done at import time.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# Supported image extensions we are willing to serve to the browser.
_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _within(child_real: str, root: str) -> bool:
    """True if ``child_real`` (already a realpath) is inside ``root``.

    Uses realpath + prefix checks to prevent path traversal / symlink escapes.
    """
    try:
        root_real = os.path.realpath(root)
    except Exception:  # noqa: BLE001
        return False
    if not root_real:
        return False
    return child_real == root_real or child_real.startswith(root_real + os.sep)


# Module-level singleton Retriever instance. Lazily constructed on first use.
_RETRIEVER = None
_RETRIEVER_FAILED = False


def _get_retriever():
    """
    Lazily construct a single Retriever instance.

    Catches import/construction errors (ml deps missing, empty/unavailable
    Chroma, etc.). On failure, logs and returns None; callers must treat a
    None retriever as "no results available".
    """
    global _RETRIEVER, _RETRIEVER_FAILED

    if _RETRIEVER is not None:
        return _RETRIEVER
    if _RETRIEVER_FAILED:
        return None

    try:
        from ml.retrieval.retriever import Retriever

        _RETRIEVER = Retriever()
        return _RETRIEVER
    except Exception as exc:  # noqa: BLE001 - intentionally broad; adapter must be robust
        print(f"[ml_retrieval] Retriever unavailable: {exc!r}")
        _RETRIEVER_FAILED = True
        return None


def _get_store():
    """
    Lazily obtain the canonical ChromaStore by REUSING the retriever's store.

    Does not construct any new ml objects beyond what the retriever already
    holds. Ensures the store's client/collections are opened (idempotent).
    On failure, logs and returns None; callers must treat None as
    "store unavailable".
    """
    r = _get_retriever()
    if r is None:
        return None
    try:
        store = getattr(r, "store", None)
        if store is not None:
            store.open()  # ensure client/collections ready; ChromaStore.open() is idempotent
        return store
    except Exception as exc:  # noqa: BLE001 - adapter must be robust
        print(f"[ml_retrieval] store unavailable: {exc!r}")
        return None


def resolve_image_path(image_id: str) -> Optional[str]:
    """On-disk path for an indexed image_id, or None. READ-ONLY; safe.

    The path is taken from Chroma metadata we indexed (never client input),
    validated to exist, be a supported image, and be contained within its
    authorized source_root (or, if no source_root, exactly its own indexed
    absolute path). Uses realpath + prefix checks to block traversal/symlink
    escapes.
    """
    if not image_id or not str(image_id).strip():
        return None
    store = _get_store()
    if store is None:
        return None
    try:
        rec = store.get_visual_by_image_id(image_id)
    except Exception as exc:  # noqa: BLE001
        print(f"[ml_retrieval] lookup failed: {exc!r}")
        return None
    if not rec:
        return None
    md = rec.get("metadata") or {}
    raw_path = md.get("absolute_path") or md.get("file_path")
    if not raw_path:
        return None
    try:
        real = os.path.realpath(raw_path)
        if not os.path.isfile(real):
            return None
        if os.path.splitext(real)[1].lower() not in _ALLOWED_EXT:
            return None
        source_root = md.get("source_root")
        if source_root:
            if not _within(real, source_root):
                return None
        else:
            # No provenance root recorded: only serve the exact indexed path.
            indexed_real = os.path.realpath(raw_path)
            if real != indexed_real:
                return None
        return real
    except Exception:  # noqa: BLE001
        return None


def list_memories(limit: int = 200) -> List[dict]:
    """List indexed memories from the canonical Chroma visual collection.

    Returns [] if unavailable/empty. Never fabricates.
    """
    store = _get_store()
    if store is None:
        return []
    try:
        col = store.visual
        n = col.count()
        if not n:
            return []
        got = col.get(include=["metadatas"], limit=min(limit, n))
        metadatas = (got or {}).get("metadatas") or []
    except Exception as exc:  # noqa: BLE001
        print(f"[ml_retrieval] list_memories failed: {exc!r}")
        return []
    out: List[dict] = []
    for md in metadatas:
        md = md or {}
        iid = md.get("image_id")
        if not iid:
            continue
        out.append(
            {
                "image_id": iid,
                "score": None,  # library listing is not a ranked search
                "filename": md.get("filename"),
                "category": md.get("category"),
                "extracted_text": md.get("extracted_text"),
                "absolute_path": md.get("absolute_path"),
                "file_path": md.get("file_path"),
                "modality": None,
                "reason": None,
                "visual_score": None,
                "text_score": None,
                "retrieval_signal": None,
            }
        )
    return out


# Max distinct results the product surfaces (fewer is valid).
DEFAULT_MAX_RESULTS = 5
# Candidate pool multiplier: fetch more than we return so that removing
# duplicates does not shrink the distinct set below the requested cap. The
# retriever's own ranking/order is preserved; we only pick the first occurrence
# of each canonical identity.
_CANDIDATE_MULTIPLIER = 4
_MIN_CANDIDATE_POOL = 20


def _identity_key(r: dict) -> Optional[str]:
    """Canonical image identity for dedup: the ML `image_id` (path-hash),
    falling back to the realpath of the stored absolute/file path. NEVER the
    displayed filename alone (different files can share a filename)."""
    iid = r.get("image_id")
    if iid:
        return f"id:{iid}"
    path = r.get("absolute_path") or r.get("file_path")
    if path:
        try:
            return f"path:{os.path.realpath(path)}"
        except Exception:  # noqa: BLE001
            return f"path:{path}"
    return None


def search_memories(query: str, top_k: int = DEFAULT_MAX_RESULTS) -> List[dict]:
    """
    Run a query against the canonical ml/ retriever and return up to `top_k`
    DISTINCT results (default 5) as plain dicts, deduplicated by canonical image
    identity (image_id / stored path), preserving the retriever's ranking.

    - Returns [] for a blank/whitespace query.
    - On ANY exception (ml deps missing, empty Chroma, etc.) logs via print and
      returns []. NEVER fabricates results.
    - Fewer than `top_k` results is valid when there are not enough distinct
      matches. Scores and ranking are never modified.
    """
    if not query or not query.strip():
        return []

    retriever = _get_retriever()
    if retriever is None:
        return []

    # Fetch a generous candidate pool so post-dedup we can still fill up to
    # top_k distinct images. The retriever's ranking/order is preserved.
    pool = max(top_k * _CANDIDATE_MULTIPLIER, _MIN_CANDIDATE_POOL)
    try:
        ranked = retriever.search(query, top_k=pool)
    except Exception as exc:  # noqa: BLE001 - adapter must never raise to the API layer
        print(f"[ml_retrieval] search failed: {exc!r}")
        return []

    results: List[dict] = []
    seen: set = set()
    for r in ranked or []:
        row = {
            "image_id": getattr(r, "image_id", None),
            "score": getattr(r, "score", None),
            "filename": getattr(r, "filename", None),
            "category": getattr(r, "category", None),
            "extracted_text": getattr(r, "extracted_text", None),
            "absolute_path": getattr(r, "absolute_path", None),
            "file_path": getattr(r, "file_path", None),
            "modality": getattr(r, "modality", None),
            "reason": getattr(r, "reason", None),
            "visual_score": getattr(r, "visual_score", None),
            "text_score": getattr(r, "text_score", None),
            "retrieval_signal": getattr(r, "retrieval_signal", None),
        }
        key = _identity_key(row)
        # Drop exact duplicate identities (same underlying image), keeping the
        # first (highest-ranked) occurrence. Rows with no resolvable identity
        # are kept as-is (cannot be proven duplicate; never fabricate a merge).
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        results.append(row)
        if len(results) >= top_k:
            break
    return results


def explanation_signals_for(image_id: str, query: Optional[str] = None) -> List[dict]:
    """
    Return grounded explanation signals for a given image id.

    Real evidence only. The canonical retriever produces evidence per query
    (not per stored image id in isolation), and we do not have the originating
    query available in this call. Since we cannot ground signals in a real
    retrieval here, we return [] rather than fabricate anything.
    """
    # Grounded-only: without the originating query we cannot produce real
    # retrieval evidence for this image, so we return nothing instead of
    # inventing signals.
    return []


def _signal_type_and_icon(modality: Optional[str]) -> tuple:
    """Map a retriever modality to a frontend explanation (type, icon)."""
    if modality == "ocr":
        return "ocr", "text"
    if modality == "visual":
        return "visual", "eye"
    return "semantic", "sparkles"


def _similarity_percent(modality, visual_score, text_score) -> Optional[int]:
    """Truthful 0-100 similarity from the REAL per-channel cosine similarities
    (each already in [0,1] from the retriever). NOT derived from the unbounded
    fused ranking score. Modality-aware:
      - visual  -> visual_score
      - ocr     -> text_score
      - both    -> max(visual_score, text_score)  (strongest real signal; stays in [0,1])
    Returns None when no real similarity signal is available (never fabricate)."""
    vs = visual_score if isinstance(visual_score, (int, float)) else None
    ts = text_score if isinstance(text_score, (int, float)) else None
    chosen = None
    if modality == "visual":
        chosen = vs
    elif modality == "ocr":
        chosen = ts
    else:  # "both"/hybrid or unknown -> use the strongest available real similarity
        cands = [x for x in (vs, ts) if x is not None]
        chosen = max(cands) if cands else None
    if chosen is None:
        # Fall back to whichever single channel is present (still real, bounded).
        chosen = vs if vs is not None else ts
    if chosen is None:
        return None
    # Clamp to [0,1] defensively (retriever already clamps), then to 0-100 int.
    c = max(0.0, min(1.0, float(chosen)))
    return int(round(c * 100))


def to_memory_result_dict(r: dict) -> dict:
    """
    Map an adapter search dict (from search_memories) to the frontend-canonical
    MemoryResult field names. Returns a plain dict; main.py constructs the
    Pydantic models.
    """
    # Browser-usable backend URL keyed by our canonical image_id. Do NOT emit
    # raw filesystem paths (e.g. C:\...) to the browser. When there is no
    # image_id we cannot serve the file, so both URLs are empty/None.
    image_id = r.get("image_id")
    if image_id:
        served_url = f"/api/images/{image_id}/file"
    else:
        served_url = ""
    thumbnail_url = served_url
    full_url = served_url if image_id else None

    extracted_text = r.get("extracted_text")
    score = r.get("score")

    # metadata: build ONLY from present values; stringify numbers; omit missing.
    metadata: dict = {}
    modality = r.get("modality")
    retrieval_signal = r.get("retrieval_signal")
    visual_score = r.get("visual_score")
    text_score = r.get("text_score")
    if modality is not None:
        metadata["modality"] = str(modality)
    if retrieval_signal is not None:
        metadata["retrieval_signal"] = str(retrieval_signal)
    if visual_score is not None:
        metadata["visual_score"] = str(visual_score)
    if text_score is not None:
        metadata["text_score"] = str(text_score)

    # explanation: grounded in real retrieval evidence (comes from the
    # retriever's reason). Only include when reason is non-empty.
    reason = r.get("reason")
    explanation = None
    if reason:
        exp_type, exp_icon = _signal_type_and_icon(modality)
        explanation = [
            {
                "type": exp_type,
                "label": reason,
                "icon": exp_icon,
                "strength": float(score) if score is not None else None,
            }
        ]

    return {
        "id": r.get("image_id"),
        "thumbnailUrl": thumbnail_url,
        "fullUrl": full_url,
        "ocrSnippet": extracted_text or None,
        "matchScore": float(score) if score is not None else None,
        "similarity": _similarity_percent(modality, visual_score, text_score),
        "sourceTag": r.get("category") or None,
        "capturedAt": None,  # retriever has no reliable capture time; do NOT fabricate
        "metadata": metadata or None,
        "explanation": explanation,
    }
