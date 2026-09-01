"""ChatLens vector store package (Phase 6).

Persistent ChromaDB indexing of already-generated CLIP visual embeddings and
Sentence Transformer text embeddings into two separate collections keyed by a
common image_id.

Storage only — no similarity search, ranking, or retrieval (that is Phase 7).
"""
from .chroma_store import (
    ChromaStore,
    VISUAL_COLLECTION,
    TEXT_COLLECTION,
    DEFAULT_DB_PATH,
    visual_id,
    text_id,
)

__all__ = [
    "ChromaStore",
    "VISUAL_COLLECTION",
    "TEXT_COLLECTION",
    "DEFAULT_DB_PATH",
    "visual_id",
    "text_id",
]
