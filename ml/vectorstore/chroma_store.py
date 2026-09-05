"""Persistent ChromaDB indexing/storage for the ChatLens ML pipeline (Phase 6).

Stores already-generated embeddings into two separate ChromaDB collections
(different embedding spaces / dimensions), keyed by a common image_id so that
future retrieval can join visual and textual results:

    chatlens_visual_embeddings : CLIP 512-d vectors + metadata (all images)
    chatlens_text_embeddings   : Sentence Transformer 384-d vectors + metadata
                                 (only images with usable OCR text)

Maps to requirements.md Requirement 5 (Vector Index Storage). Storage only:
NO similarity search, nearest-neighbor, ranking, or query embedding here.

Design points required by the task:
  - Persistent client (not in-memory). DB kept under ml/ (separate from images,
    frontend, backend, dataset). Docs specify ChromaDB but no exact path/names.
  - Deterministic record IDs: visual_<image_id> / text_<image_id> -> idempotent
    upserts; re-running does not duplicate logical records.
  - No fabricated vectors: images without a text embedding are skipped in the
    text collection but still indexed visually.
  - Metadata preserves image_id, filename, file_path, category, and (for text)
    extracted_text + has_text.

Does not modify images, OCR, CLIP, or text-embedding source code.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# Collection names (docs do not mandate specific names; use clear stable ones).
VISUAL_COLLECTION = "chatlens_visual_embeddings"
TEXT_COLLECTION = "chatlens_text_embeddings"
VLM_COLLECTION = "chatlens_vlm_description_embeddings"

# Canonical persistent DB location: <project_root>/chroma_db.
#
# Derived from the project root (two levels above ml/vectorstore/) so that
# indexing and retrieval ALWAYS open the same database regardless of the current
# working directory. This is the single source of truth for the ChromaDB path;
# both the indexer (__main__ below) and the Retriever (via ChromaStore()) use it.
#
# Note: earlier this pointed at ml/vectorstore/chroma_db while the indexing
# pipeline wrote to <project_root>/chroma_db, which caused retrieval to open an
# empty database ("No results"). Anchoring to the project root fixes that at the
# architecture level.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = str(PROJECT_ROOT / "chroma_db")


def visual_id(account_id: str, image_id: str) -> str:
    """Deterministic ChromaDB id for a visual record."""
    return f"visual_{account_id}_{image_id}"


def text_id(account_id: str, image_id: str) -> str:
    """Deterministic ChromaDB id for a text record."""
    return f"text_{account_id}_{image_id}"


def vlm_id(account_id: str, image_id: str) -> str:
    """Deterministic ChromaDB id for a VLM description record."""
    return f"vlm_{account_id}_{image_id}"


def _clean_metadata(md: Dict[str, Any]) -> Dict[str, Any]:
    """ChromaDB metadata values must be str/int/float/bool (no None)."""
    out: Dict[str, Any] = {}
    for k, v in md.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            out[k] = v
        else:
            out[k] = str(v)
    return out


class ChromaStore:
    """Opens a persistent ChromaDB client and manages the two collections."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self._client = None
        self._visual = None
        self._text = None
        self._vlm = None

    # -- client / collections -------------------------------------------------

    def open(self) -> "ChromaStore":
        """Create/open the persistent client and both collections."""
        import chromadb

        Path(self.db_path).mkdir(parents=True, exist_ok=True)
        # PersistentClient writes to disk (not in-memory).
        self._client = chromadb.PersistentClient(path=self.db_path)
        # Cosine space is the natural metric for our normalized embeddings.
        self._visual = self._client.get_or_create_collection(
            name=VISUAL_COLLECTION, metadata={"hnsw:space": "cosine"}
        )
        self._text = self._client.get_or_create_collection(
            name=TEXT_COLLECTION, metadata={"hnsw:space": "cosine"}
        )
        self._vlm = self._client.get_or_create_collection(
            name=VLM_COLLECTION, metadata={"hnsw:space": "cosine"}
        )
        return self

    @property
    def client(self):
        if self._client is None:
            self.open()
        return self._client

    @property
    def visual(self):
        if self._visual is None:
            self.open()
        return self._visual

    @property
    def text(self):
        if self._text is None:
            self.open()
        return self._text

    @property
    def vlm(self):
        if self._vlm is None:
            self.open()
        return self._vlm

    # -- indexing -------------------------------------------------------------

    def upsert_visual(self, record: Any, account_id: str, filename: Optional[str] = None,
                      extra_metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Upsert one CLIP visual embedding. Returns True if stored.

        ``extra_metadata`` (optional) merges additional scalar metadata (e.g. a
        change-detection fingerprint) without altering existing behavior.
        """
        image_id = _get(record, "image_id")
        vec = _get(record, "visual_embedding")
        ok = _get(record, "ok", True)
        if not image_id or vec is None or not ok:
            return False
        md = {
            "account_id": account_id,
            "image_id": image_id,
            "filename": filename if filename is not None else _derive_filename(record),
            "file_path": _get(record, "file_path"),
            "category": _get(record, "category"),
            "embedding_type": "visual",
            "dim": _get(record, "dim", len(vec)),
        }
        if extra_metadata:
            md.update(extra_metadata)
        metadata = _clean_metadata(md)
        self.visual.upsert(
            ids=[visual_id(account_id, image_id)],
            embeddings=[list(vec)],
            metadatas=[metadata],
        )
        return True

    def upsert_text(self, record: Any, account_id: str) -> bool:
        """Upsert one text embedding. Skips (returns False) when no usable text.

        Never fabricates a vector for images without OCR text.
        """
        image_id = _get(record, "image_id")
        vec = _get(record, "text_embedding")
        has_text = _get(record, "has_text", False)
        ok = _get(record, "ok", True)
        if not image_id or vec is None or not has_text or not ok:
            return False
        metadata = _clean_metadata({
            "account_id": account_id,
            "image_id": image_id,
            "filename": _get(record, "filename") or _derive_filename(record),
            "file_path": _get(record, "file_path"),
            "category": _get(record, "category"),
            "extracted_text": _get(record, "extracted_text"),
            "has_text": True,
            "embedding_type": "text",
            "dim": _get(record, "dim", len(vec)),
        })
        self.text.upsert(
            ids=[text_id(account_id, image_id)],
            embeddings=[list(vec)],
            metadatas=[metadata],
        )
        return True

    def index_visual_batch(self, records: Iterable[Any],
                           account_id: str,
                           filenames: Optional[Dict[str, str]] = None,
                           extra_metadata: Optional[Dict[str, Dict[str, Any]]] = None) -> int:
        count = 0
        for rec in records:
            iid = _get(rec, "image_id")
            fname = filenames.get(iid) if filenames else None
            extra = extra_metadata.get(iid) if extra_metadata else None
            if self.upsert_visual(rec, account_id=account_id, filename=fname, extra_metadata=extra):
                count += 1
        return count

    def index_text_batch(self, records: Iterable[Any], account_id: str) -> int:
        count = 0
        for rec in records:
            if self.upsert_text(rec, account_id=account_id):
                count += 1
        return count

    def upsert_vlm_description(
        self, image_id: str, account_id: str, description: str,
        embedding: List[float], metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if not image_id or not account_id or not description or not embedding:
            return False
        md = _clean_metadata({
            "account_id": account_id,
            "image_id": image_id,
            "vlm_description": description,
            "embedding_type": "vlm_description",
            **(metadata or {}),
        })
        self.vlm.upsert(
            ids=[vlm_id(account_id, image_id)],
            embeddings=[list(embedding)],
            metadatas=[md],
        )
        return True

    # -- lookup / stats (NO similarity search) --------------------------------

    def get_visual_by_image_id(self, image_id: str, account_id: str) -> Optional[Dict[str, Any]]:
        return self._get_one(self.visual, visual_id(account_id, image_id))

    def get_text_by_image_id(self, image_id: str, account_id: str) -> Optional[Dict[str, Any]]:
        return self._get_one(self.text, text_id(account_id, image_id))

    def get_vlm_by_image_id(self, image_id: str, account_id: str) -> Optional[Dict[str, Any]]:
        return self._get_one(self.vlm, vlm_id(account_id, image_id))

    def delete_visual(self, image_id: str, account_id: str) -> None:
        self.visual.delete(ids=[visual_id(account_id, image_id)])

    def delete_text(self, image_id: str, account_id: str) -> None:
        self.text.delete(ids=[text_id(account_id, image_id)])

    def delete_vlm(self, image_id: str, account_id: str) -> None:
        self.vlm.delete(ids=[vlm_id(account_id, image_id)])

    @staticmethod
    def _get_one(collection, record_id: str) -> Optional[Dict[str, Any]]:
        """Direct ID lookup (not a similarity query)."""
        res = collection.get(ids=[record_id], include=["metadatas", "embeddings"])
        ids = res.get("ids") or []
        if not ids:
            return None
        embeddings = res.get("embeddings")
        metadatas = res.get("metadatas")
        emb = embeddings[0] if embeddings is not None and len(embeddings) else None
        md = metadatas[0] if metadatas is not None and len(metadatas) else None
        return {"id": ids[0], "embedding": emb, "metadata": md}

    def stats(self) -> Dict[str, int]:
        return {
            VISUAL_COLLECTION: self.visual.count(),
            TEXT_COLLECTION: self.text.count(),
            VLM_COLLECTION: self.vlm.count(),
        }


def _get(rec: Any, name: str, default: Any = None) -> Any:
    if isinstance(rec, dict):
        return rec.get(name, default)
    return getattr(rec, name, default)


def _derive_filename(rec: Any) -> Optional[str]:
    fp = _get(rec, "file_path")
    return Path(fp).name if fp else None


if __name__ == "__main__":
    import argparse
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from ml.ingestion.scanner import scan_dataset  # noqa: E402
    from ml.ocr.extractor import OCRExtractor  # noqa: E402
    from ml.embeddings.clip_embedder import CLIPImageEmbedder  # noqa: E402
    from ml.embeddings.text_embedder import TextEmbedder  # noqa: E402

    parser = argparse.ArgumentParser(description="Index a dataset into persistent ChromaDB.")
    parser.add_argument("dataset_path", nargs="?", default="data/test_dataset")
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--account-id", required=True)
    args = parser.parse_args()

    scan = scan_dataset(args.dataset_path)
    filenames = {r.image_id: r.filename for r in scan.records}

    visual = CLIPImageEmbedder().embed_many(scan.records)
    ocr = OCRExtractor().extract_many(scan.records)
    text = TextEmbedder().embed_ocr_results(ocr, filenames=filenames)

    store = ChromaStore(db_path=args.db).open()
    v = store.index_visual_batch(visual, account_id=args.account_id, filenames=filenames)
    t = store.index_text_batch(text, account_id=args.account_id)
    print(f"Indexed visual={v}, text={t}")
    print("Collection stats:", store.stats())
