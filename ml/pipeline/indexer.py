"""Library indexer: authorized locations -> existing pipeline -> ChromaDB.

This is the integration-facing orchestration layer. It reuses, without
modifying, the existing components:

  - LocalImageAccess   (ml/filesystem/local_access.py)  authorized locations
  - scan_dataset       (ml/ingestion/scanner.py)         image discovery
  - CLIPImageEmbedder  (ml/embeddings/clip_embedder.py)  visual embeddings
  - OCRExtractor       (ml/ocr/extractor.py)             OCR text
  - TextEmbedder       (ml/embeddings/text_embedder.py)  text embeddings
  - ChromaStore        (ml/vectorstore/chroma_store.py)  indexing/storage
  - Retriever          (ml/retrieval/retriever.py)       retrieval (unchanged)

Responsibilities (ML engine side):
  scan -> OCR -> embed -> index -> synchronize.
The frontend/integration layer owns permission UI + OS folder picker and simply
passes authorized path(s) here.

SYNCHRONIZATION / IDEMPOTENCY
-----------------------------
Every image has a stable image_id (scanner: SHA-1 of its resolved path). We also
compute a lightweight change fingerprint = "<size>:<mtime_ns>" and store it in
the visual record's metadata. On sync:
  - unchanged image (existing visual record with matching fingerprint) -> SKIP
    (no CLIP/OCR/text recompute),
  - new or changed image -> (re)process and upsert.
Upserts are keyed by deterministic ids (visual_<id> / text_<id>), so repeated
runs never create duplicates and image_ids stay stable.

No dataset names, paths, categories, filenames, or OS paths are hardcoded.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def _source_root_for(file_path: str, roots: List[str]) -> Optional[str]:
    """Return the approved root (from ``roots``) that contains ``file_path``.

    Uses realpath comparison so it is correct regardless of symlinked temp dirs
    or platform path quirks. Returns None if no approved root matches.
    """
    try:
        fp = os.path.realpath(file_path)
    except Exception:
        return None
    best = None
    for r in roots:
        try:
            ra = os.path.realpath(str(r))
        except Exception:
            continue
        if fp == ra or fp.startswith(ra + os.sep):
            # Prefer the longest matching root (most specific).
            if best is None or len(ra) > len(best):
                best = ra
    return best


def _fingerprint(file_path: str) -> str:
    """Cheap change signature for a file: size + modification time (ns)."""
    try:
        st = os.stat(file_path)
        return f"{st.st_size}:{st.st_mtime_ns}"
    except OSError:
        return ""


@dataclass
class IndexReport:
    """Summary of an index/sync run."""

    authorized_locations: int = 0
    granted_locations: int = 0
    denied_or_missing: List[str] = field(default_factory=list)
    discovered_images: int = 0
    new_or_changed: int = 0
    skipped_unchanged: int = 0
    visual_indexed: int = 0
    text_indexed: int = 0
    errors: List[str] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "authorized_locations": self.authorized_locations,
            "granted_locations": self.granted_locations,
            "denied_or_missing": self.denied_or_missing,
            "discovered_images": self.discovered_images,
            "new_or_changed": self.new_or_changed,
            "skipped_unchanged": self.skipped_unchanged,
            "visual_indexed": self.visual_indexed,
            "text_indexed": self.text_indexed,
            "errors": self.errors,
            "stats": self.stats,
        }


class LibraryIndexer:
    """Clean, stable interface the integration layer calls.

    Typical usage:
        idx = LibraryIndexer()
        report = idx.index_locations(
            ["/authorized/path/A", "/authorized/path/B"], account_id="acct-example"
        )
        results = idx.retrieve("a receipt from a restaurant", top_k=10)

    Re-calling index_locations()/sync() later picks up new/changed images only.
    """

    def __init__(self, store: Optional[Any] = None) -> None:
        # Reuse existing components; construct lazily so importing is cheap and
        # model loads happen only when indexing/retrieving actually runs.
        self._store = store
        self._clip = None
        self._ocr = None
        self._text = None
        self._retriever = None

    # -- lazy, reused singletons ---------------------------------------------

    @property
    def store(self):
        if self._store is None:
            from ml.vectorstore.chroma_store import ChromaStore
            self._store = ChromaStore()
        self._store.open()
        return self._store

    def _clip_embedder(self):
        if self._clip is None:
            from ml.embeddings.clip_embedder import CLIPImageEmbedder
            self._clip = CLIPImageEmbedder()
        return self._clip

    def _ocr_extractor(self):
        if self._ocr is None:
            from ml.ocr.extractor import OCRExtractor
            self._ocr = OCRExtractor()
        return self._ocr

    def _text_embedder(self):
        if self._text is None:
            from ml.embeddings.text_embedder import TextEmbedder
            self._text = TextEmbedder()
        return self._text

    # -- discovery via authorized locations (reuses LocalImageAccess) --------

    def _collect_records(self, locations, report: IndexReport) -> List[Any]:
        """Turn authorized locations into scanner ImageRecords (existing scanner)."""
        from ml.filesystem.local_access import LocalImageAccess, AccessResult
        access = LocalImageAccess()
        batch = access.ingest_locations(locations)
        report.authorized_locations = len(batch.locations)
        for lr in batch.locations:
            if lr.access is AccessResult.GRANTED:
                report.granted_locations += 1
            else:
                report.denied_or_missing.append(f"{lr.location} ({lr.access.value})")
        records = batch.image_records
        report.discovered_images = len(records)
        return records

    def _needs_processing(self, image_id: str, account_id: str, fingerprint: str) -> bool:
        """True if this image is new or changed since last index (idempotency)."""
        existing = self.store.get_visual_by_image_id(image_id, account_id)
        if existing is None:
            return True
        md = existing.get("metadata") or {}
        return md.get("fingerprint") != fingerprint

    # -- public API for the integration layer --------------------------------

    def index_locations(self, locations, account_id: str, force: bool = False) -> IndexReport:
        """Scan + index ONLY the given user-authorized locations.

        Args:
            locations: iterable of authorized directory paths (strings/Paths).
            force: if True, reprocess every discovered image even if unchanged.

        Returns an IndexReport. Safe to call repeatedly (idempotent sync).
        """
        report = IndexReport()
        records = self._collect_records(locations, report)
        if not records:
            report.stats = self.store.stats()
            return report

        # Decide which images actually need (re)processing.
        to_process = []
        fingerprints: Dict[str, str] = {}
        for rec in records:
            iid = getattr(rec, "image_id", None)
            fp = _fingerprint(getattr(rec, "file_path", ""))
            fingerprints[iid] = fp
            if force or self._needs_processing(iid, account_id, fp):
                to_process.append(rec)
            else:
                report.skipped_unchanged += 1
        report.new_or_changed = len(to_process)
        if not to_process:
            report.stats = self.store.stats()
            return report

        filenames = {getattr(r, "image_id", None): getattr(r, "filename", None)
                     for r in to_process}

        # Existing pipeline, unchanged: CLIP visual + OCR + text embeddings.
        visual = self._clip_embedder().embed_many(to_process)
        ocr = self._ocr_extractor().extract_many(to_process)
        text = self._text_embedder().embed_ocr_results(ocr, filenames=filenames)

        # Attach change fingerprints + filesystem provenance to the visual
        # records' stored metadata (additive; no schema change, no re-embedding).
        #   - fingerprint  : existing change-detection key
        #   - absolute_path: complete platform-native absolute path
        #   - source_root  : the approved folder the image was found under
        roots = [str(l) for l in locations]
        path_by_id = {getattr(r, "image_id", None): getattr(r, "file_path", "")
                      for r in to_process}
        extra_md = {}
        for iid in filenames:
            fpath = path_by_id.get(iid, "")
            abs_path = os.path.abspath(fpath) if fpath else ""
            src_root = _source_root_for(fpath, roots) or ""
            extra_md[iid] = {
                "fingerprint": fingerprints.get(iid, ""),
                "absolute_path": abs_path,
                "source_root": src_root,
            }

        report.visual_indexed = self.store.index_visual_batch(
            visual, account_id=account_id, filenames=filenames, extra_metadata=extra_md)
        report.text_indexed = self.store.index_text_batch(text, account_id=account_id)
        report.stats = self.store.stats()
        return report

    def sync(self, locations, account_id: str, force: bool = False) -> IndexReport:
        """Alias for index_locations(); named for the integration trigger."""
        return self.index_locations(locations, account_id=account_id, force=force)

    def retrieve(self, query, account_id: str, top_k: int = 10, signal: Optional[str] = None):
        """Delegate to the EXISTING Retriever (retrieval logic unchanged)."""
        if self._retriever is None:
            from ml.retrieval.retriever import Retriever
            self._retriever = Retriever(store=self.store)
        return self._retriever.search(query, account_id=account_id, top_k=top_k, signal=signal)


if __name__ == "__main__":
    import argparse
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    parser = argparse.ArgumentParser(
        description="Index user-authorized image location(s) into ChatLens (reuses existing pipeline)."
    )
    parser.add_argument("locations", nargs="+", help="Authorized directory path(s).")
    parser.add_argument("--account-id", required=True, help="Account identity for scoped indexing.")
    parser.add_argument("--force", action="store_true", help="Reprocess all images.")
    parser.add_argument("--query", default=None, help="Optional retrieval query after indexing.")
    parser.add_argument("--top_k", "--top-k", dest="top_k", type=int, default=10)
    args = parser.parse_args()

    idx = LibraryIndexer()
    rep = idx.index_locations(args.locations, account_id=args.account_id, force=args.force)
    import json
    print(json.dumps(rep.to_dict(), indent=2))
    if args.query:
        print("-" * 60)
        for i, r in enumerate(idx.retrieve(args.query, top_k=args.top_k), 1):
            print(f"{i}. [{r.retrieval_signal}] {r.score:.4f} [{r.category}] {r.filename}")
