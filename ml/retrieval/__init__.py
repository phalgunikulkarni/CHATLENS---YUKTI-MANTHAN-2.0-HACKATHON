"""ChatLens retrieval/search package (Phase 7).

Similarity search on top of the existing persistent ChromaDB collections:
  - visual similarity (CLIP)      -> chatlens_visual_embeddings
  - semantic OCR/text similarity  -> chatlens_text_embeddings

Individual retrieval operations only. No hybrid ranking / score fusion, no
agent, no frontend/backend. Read-only with respect to the index and images.
"""
from .retriever import (
    RankedResult,
    Retriever,
    SIGNAL_VISUAL,
    SIGNAL_SEMANTIC_OCR,
)

__all__ = [
    "RankedResult",
    "Retriever",
    "SIGNAL_VISUAL",
    "SIGNAL_SEMANTIC_OCR",
]
