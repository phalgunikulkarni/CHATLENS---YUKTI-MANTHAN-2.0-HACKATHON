"""ChatLens ML pipeline orchestration.

Ties together the EXISTING components (local access -> scanner -> OCR -> CLIP ->
text embeddings -> ChromaDB) behind one clean, integration-friendly interface.
Owns orchestration + synchronization only; it does not reimplement any of them.
"""
from .indexer import LibraryIndexer, IndexReport
from .watcher import FolderWatcher

__all__ = ["LibraryIndexer", "IndexReport", "FolderWatcher"]
