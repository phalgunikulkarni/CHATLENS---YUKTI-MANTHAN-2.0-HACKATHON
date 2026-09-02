"""Retrieval/search layer for the ChatLens ML pipeline (Phase 7).

Sits ON TOP of the completed pipeline (ingestion, OCR, CLIP, text embeddings,
ChromaDB indexing). Reuses existing components through their public interfaces:

  - CLIPImageEmbedder      (ml/embeddings/clip_embedder.py) for visual queries
  - TextEmbedder           (ml/embeddings/text_embedder.py) for text queries
  - ChromaStore            (ml/vectorstore/chroma_store.py) for the collections

Operations:
  - search_visual(image_path | embedding, top_k)  -> visual similarity
  - search_text(query_text, top_k)                -> semantic OCR/text similarity
  - search(query, top_k, signal=...)              -> unified dispatch

Maps to requirements.md Requirement 6 (basic semantic image search) and the
Search_Module glossary role. This layer implements the individual retrieval
operations only; it does NOT fuse visual + text scores into a hybrid ranking.

SCORE SEMANTICS
---------------
The ChromaDB collections use cosine space, so ChromaDB returns a *distance*
(lower = more similar). All stored embeddings are unit-normalized, so:

    cosine_distance = 1 - cosine_similarity

The exposed ``RankedResult.score`` is a SIMILARITY in [0.0, 1.0] where HIGHER
IS BETTER, computed as ``max(0.0, 1.0 - distance)``. Results are returned in
descending score order (most relevant first). The raw distance is also kept in
``raw_distance`` for traceability.

Read-only: never inserts/updates/deletes ChromaDB records or modifies images.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

# Retrieval signals (project Retrieval_Signal terminology).
SIGNAL_VISUAL = "visual"
SIGNAL_SEMANTIC_OCR = "semantic_ocr"


@dataclass
class RankedResult:
    """One retrieval result, traceable to the original image via image_id."""

    image_id: str
    file_path: str
    filename: Optional[str]
    category: Optional[str]
    score: float                 # similarity in [0,1], higher is better
    retrieval_signal: str        # SIGNAL_VISUAL | SIGNAL_SEMANTIC_OCR
    raw_distance: float          # ChromaDB cosine distance (lower is better)
    extracted_text: Optional[str] = None  # preserved for text results

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_id": self.image_id,
            "file_path": self.file_path,
            "filename": self.filename,
            "category": self.category,
            "score": self.score,
            "retrieval_signal": self.retrieval_signal,
            "raw_distance": self.raw_distance,
            "extracted_text": self.extracted_text,
        }


def _similarity_from_distance(distance: float) -> float:
    """Convert cosine distance (lower better) to similarity in [0,1] (higher better)."""
    sim = 1.0 - float(distance)
    if sim < 0.0:
        sim = 0.0
    if sim > 1.0:
        sim = 1.0
    return round(sim, 6)


class Retriever:
    """Similarity search over the existing ChromaDB collections."""

    def __init__(self, store: Optional[Any] = None) -> None:
        # Reuse the existing ChromaStore abstraction.
        if store is None:
            from ml.vectorstore.chroma_store import ChromaStore
            store = ChromaStore()
        self.store = store
        self._clip = None   # lazy, reused
        self._text = None   # lazy, reused

    # -- lazy, reused embedders (existing implementations) --------------------

    def _clip_embedder(self):
        if self._clip is None:
            from ml.embeddings.clip_embedder import CLIPImageEmbedder
            self._clip = CLIPImageEmbedder()
        return self._clip

    def _text_embedder(self):
        if self._text is None:
            from ml.embeddings.text_embedder import TextEmbedder
            self._text = TextEmbedder()
        return self._text

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _valid_top_k(top_k: int) -> int:
        if not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be an integer >= 1")
        return top_k

    def _query_collection(
        self, collection, query_embedding: Sequence[float], top_k: int, signal: str,
    ) -> List[RankedResult]:
        count = collection.count()
        if count == 0:
            return []  # empty collection -> no results (no fabrication)
        n = min(top_k, count)  # top_k larger than available handled gracefully
        res = collection.query(
            query_embeddings=[list(query_embedding)],
            n_results=n,
            include=["metadatas", "distances"],
        )
        ids = (res.get("ids") or [[]])[0]
        metadatas = (res.get("metadatas") or [[]])[0]
        distances = (res.get("distances") or [[]])[0]

        results: List[RankedResult] = []
        for md, dist in zip(metadatas, distances):
            md = md or {}
            results.append(
                RankedResult(
                    image_id=md.get("image_id", ""),
                    file_path=md.get("file_path", ""),
                    filename=md.get("filename"),
                    category=md.get("category"),
                    score=_similarity_from_distance(dist),
                    retrieval_signal=signal,
                    raw_distance=round(float(dist), 6),
                    extracted_text=md.get("extracted_text"),
                )
            )
        # ChromaDB already returns nearest-first; sort defensively by score desc.
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    # -- public retrieval operations ------------------------------------------

    def search_visual(
        self,
        query: Union[str, Path, Sequence[float]],
        top_k: int = 5,
    ) -> List[RankedResult]:
        """Visual similarity search against chatlens_visual_embeddings.

        ``query`` may be:
          - an image path (str/Path pointing to an existing image file), whose
            CLIP image embedding is generated via the existing CLIPImageEmbedder;
          - a natural-language text query (any other str/Path), which is embedded
            into the SAME 512-d CLIP space via CLIP's text encoder, enabling
            text-to-image retrieval;
          - a precomputed CLIP embedding (sequence of floats).
        """
        top_k = self._valid_top_k(top_k)

        if isinstance(query, (str, Path)):
            path = Path(query)
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                # Image query -> CLIP image embedding (unchanged behavior).
                rec = self._clip_embedder().embed_one(
                    image_id="__query__", file_path=str(path), category="__query__"
                )
                if not rec.ok or rec.visual_embedding is None:
                    raise ValueError(f"failed to embed query image: {rec.error}")
                embedding = rec.visual_embedding
            else:
                # Natural-language query -> CLIP text embedding (same 512-d space).
                embedding = self._clip_embedder().embed_text_query(str(query))
        else:
            embedding = list(query)
            if not embedding:
                raise ValueError("empty visual query embedding")

        return self._query_collection(
            self.store.visual, embedding, top_k, SIGNAL_VISUAL
        )

    def search_text(self, query_text: str, top_k: int = 5) -> List[RankedResult]:
        """Semantic OCR/text search against chatlens_text_embeddings."""
        top_k = self._valid_top_k(top_k)
        if query_text is None or not str(query_text).strip():
            raise ValueError("query text must be a non-empty string")

        vec = self._text_embedder()._encode(str(query_text).strip())
        return self._query_collection(
            self.store.text, vec, top_k, SIGNAL_SEMANTIC_OCR
        )

    def search(
        self,
        query: Union[str, Path, Sequence[float]],
        top_k: int = 5,
        signal: Optional[str] = None,
    ) -> List[RankedResult]:
        """Unified interface. Dispatches to visual or text retrieval.

        Dispatch rules:
          - signal explicitly SIGNAL_VISUAL      -> search_visual
          - signal explicitly SIGNAL_SEMANTIC_OCR-> search_text
          - otherwise inferred from query type:
              * an existing image file path       -> visual
              * a sequence of floats               -> visual
              * a natural-language string          -> semantic_ocr
        """
        if signal == SIGNAL_VISUAL:
            return self.search_visual(query, top_k=top_k)
        if signal == SIGNAL_SEMANTIC_OCR:
            if not isinstance(query, (str, Path)):
                raise ValueError("semantic_ocr search requires a text query")
            return self.search_text(str(query), top_k=top_k)

        # Inference
        if isinstance(query, (str, Path)):
            p = Path(query)
            if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                return self.search_visual(p, top_k=top_k)
            return self.search_text(str(query), top_k=top_k)
        return self.search_visual(query, top_k=top_k)


if __name__ == "__main__":
    import argparse
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    parser = argparse.ArgumentParser(description="Query the ChatLens ChromaDB index (read-only).")
    parser.add_argument("query", help="text query, or an image path for visual search")
    parser.add_argument("--top_k", type=int, default=5)
    parser.add_argument("--signal", choices=[SIGNAL_VISUAL, SIGNAL_SEMANTIC_OCR], default=None)
    args = parser.parse_args()

    r = Retriever()
    results = r.search(args.query, top_k=args.top_k, signal=args.signal)
    if not results:
        print("No results.")
    for i, res in enumerate(results, 1):
        print(f"{i}. [{res.retrieval_signal}] score={res.score:.4f} "
              f"[{res.category}] {res.filename}")
