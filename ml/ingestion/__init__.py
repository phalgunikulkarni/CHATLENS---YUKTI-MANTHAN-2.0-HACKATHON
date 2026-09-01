"""ChatLens ML ingestion package.

Phase 2 — image dataset scanning only. No OCR, no embeddings, no vector store.
"""
from .scanner import (
    ImageRecord,
    ScanResult,
    SUPPORTED_EXTENSIONS,
    scan_dataset,
)

__all__ = [
    "ImageRecord",
    "ScanResult",
    "SUPPORTED_EXTENSIONS",
    "scan_dataset",
]
