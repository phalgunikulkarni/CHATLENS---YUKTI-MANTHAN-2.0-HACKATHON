"""ChatLens embeddings package.

Phase 4 — CLIP visual embeddings (openai/clip-vit-base-patch32) via Hugging
Face Transformers + PyTorch.
Phase 5 — Sentence Transformer text embeddings
(sentence-transformers/all-MiniLM-L6-v2).

Not in these phases: ChromaDB writes, retrieval/ranking, agent/frontend/backend.
"""
from .clip_embedder import (
    VisualEmbeddingRecord,
    CLIPImageEmbedder,
    embed_images,
    CLIP_MODEL_NAME,
    EMBEDDING_DIM,
)
from .text_embedder import (
    TextEmbeddingRecord,
    TextEmbedder,
    embed_texts,
    TEXT_MODEL_NAME,
    TEXT_EMBEDDING_DIM,
)

__all__ = [
    # Visual (Phase 4)
    "VisualEmbeddingRecord",
    "CLIPImageEmbedder",
    "embed_images",
    "CLIP_MODEL_NAME",
    "EMBEDDING_DIM",
    # Text (Phase 5)
    "TextEmbeddingRecord",
    "TextEmbedder",
    "embed_texts",
    "TEXT_MODEL_NAME",
    "TEXT_EMBEDDING_DIM",
]
