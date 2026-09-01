"""ChatLens OCR package (Phase 3).

PaddleOCR-based text extraction over ingestion image records. No CLIP, no
Sentence Transformer embeddings, no ChromaDB writes, no agent/frontend/backend.
"""
from .extractor import (
    OCRResultRecord,
    OCRExtractor,
    extract_texts,
)

__all__ = [
    "OCRResultRecord",
    "OCRExtractor",
    "extract_texts",
]
