"""Phase 3C — VLM description embeddings integrated into hybrid retrieval.

Feature: vlm-description-retrieval (Phase 3C).

These tests exercise Retriever.search_hybrid's fusion with a THIRD (VLM) channel
using in-memory fake Chroma collections and a stubbed text embedder, so no CLIP/
MiniLM model is loaded and behavior is deterministic. They verify:

  - A VLM-only semantic match can surface an image.
  - Existing visual/OCR results still work when VLM has no matches.
  - VLM retrieval failure does not break search.
  - An empty VLM collection does not break search.
  - Account A cannot retrieve account B's VLM records (isolation via where=).
  - Duplicate image candidates are merged (one fused row per image_id).
  - Hybrid still returns at most top_k results.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from ml.retrieval.retriever import Retriever, SIGNAL_HYBRID


class FakeCollection:
    """Minimal stand-in for a Chroma collection.

    Records: list of (record_id, embedding, metadata). query() returns rows
    ordered by a caller-provided rank and, crucially, ONLY rows whose metadata
    account_id matches the `where` filter (so account isolation is testable).
    Distances are synthesized from a per-record 'sim' in metadata so we can
    control ordering deterministically without real vectors.
    """

    def __init__(self, rows):
        # rows: list of dicts each with image_id, account_id, sim, and optional
        # extracted_text / file_path / filename / category.
        self._rows = rows

    def count(self):
        return len(self._rows)

    def query(self, query_embeddings, n_results, include, where):
        acct = (where or {}).get("account_id")
        matched = [r for r in self._rows if r.get("account_id") == acct]
        # Higher sim first; distance = 1 - sim (cosine).
        matched.sort(key=lambda r: r["sim"], reverse=True)
        matched = matched[:n_results]
        metadatas = [
            {
                "image_id": r["image_id"],
                "account_id": r["account_id"],
                "filename": r.get("filename", r["image_id"] + ".jpg"),
                "file_path": r.get("file_path", "/data/" + r["image_id"] + ".jpg"),
                "category": r.get("category", "test"),
                "extracted_text": r.get("extracted_text"),
            }
            for r in matched
        ]
        distances = [1.0 - float(r["sim"]) for r in matched]
        return {"ids": [[r["image_id"] for r in matched]],
                "metadatas": [metadatas], "distances": [distances]}


class FakeStore:
    def __init__(self, visual_rows, text_rows, vlm_rows, vlm_raises=False):
        self.visual = FakeCollection(visual_rows)
        self.text = FakeCollection(text_rows)
        if vlm_raises:
            self.vlm = _RaisingCollection()
        else:
            self.vlm = FakeCollection(vlm_rows)

    def open(self):
        return self


class _RaisingCollection:
    def count(self):
        return 5  # non-empty so search proceeds to query(), which then fails

    def query(self, *a, **k):
        raise RuntimeError("VLM collection unavailable")


class FakeTextEmbedder:
    """Stub: returns a constant vector; the fake collections ignore it."""

    def _encode(self, text):
        return [0.0, 0.0, 0.0]


def _retriever(store):
    r = Retriever(store=store)
    r._text = FakeTextEmbedder()   # stub OCR/text + VLM query embedding
    # Also stub the visual query embedding so no CLIP model loads.
    r._embed_visual_query = lambda q: [0.0] * 4  # type: ignore[assignment]
    return r


def test_vlm_only_semantic_match_surfaces_image():
    # Visual + OCR have no rows for this account; only VLM matches.
    store = FakeStore(
        visual_rows=[],
        text_rows=[],
        vlm_rows=[{"image_id": "img-vlm", "account_id": "A", "sim": 0.9}],
    )
    r = _retriever(store)
    results = r.search_hybrid("a red bicycle on a beach", account_id="A", top_k=10)
    ids = [x.image_id for x in results]
    assert "img-vlm" in ids
    hit = next(x for x in results if x.image_id == "img-vlm")
    assert hit.retrieval_signal == SIGNAL_HYBRID
    assert hit.modality == "vlm"
    assert hit.vlm_score is not None and hit.vlm_score > 0


def test_existing_visual_ocr_still_work_with_no_vlm_matches():
    store = FakeStore(
        visual_rows=[{"image_id": "img-a", "account_id": "A", "sim": 0.8},
                     {"image_id": "img-b", "account_id": "A", "sim": 0.6}],
        text_rows=[{"image_id": "img-a", "account_id": "A", "sim": 0.7,
                    "extracted_text": "hello"}],
        vlm_rows=[],  # empty VLM collection
    )
    r = _retriever(store)
    results = r.search_hybrid("hello", account_id="A", top_k=10)
    ids = [x.image_id for x in results]
    assert "img-a" in ids and "img-b" in ids
    # No VLM evidence recorded on these rows.
    assert all(x.vlm_score is None for x in results)


def test_vlm_failure_does_not_break_search():
    store = FakeStore(
        visual_rows=[{"image_id": "img-a", "account_id": "A", "sim": 0.8}],
        text_rows=[],
        vlm_rows=[],
        vlm_raises=True,   # VLM query() raises
    )
    r = _retriever(store)
    results = r.search_hybrid("anything", account_id="A", top_k=10)
    assert [x.image_id for x in results] == ["img-a"]


def test_empty_vlm_collection_does_not_break_search():
    store = FakeStore(
        visual_rows=[{"image_id": "img-a", "account_id": "A", "sim": 0.8}],
        text_rows=[],
        vlm_rows=[],  # count()==0 -> VLM returns []
    )
    r = _retriever(store)
    results = r.search_hybrid("anything", account_id="A", top_k=10)
    assert [x.image_id for x in results] == ["img-a"]


def test_account_isolation_vlm():
    # img-b belongs to account B only; account A must never retrieve it.
    store = FakeStore(
        visual_rows=[],
        text_rows=[],
        vlm_rows=[{"image_id": "img-b", "account_id": "B", "sim": 0.95}],
    )
    r = _retriever(store)
    results = r.search_hybrid("secret", account_id="A", top_k=10)
    assert results == []


def test_duplicate_candidate_merged_across_channels():
    # img-a appears in visual, text, AND vlm -> exactly ONE fused row.
    store = FakeStore(
        visual_rows=[{"image_id": "img-a", "account_id": "A", "sim": 0.8}],
        text_rows=[{"image_id": "img-a", "account_id": "A", "sim": 0.7,
                    "extracted_text": "notes"}],
        vlm_rows=[{"image_id": "img-a", "account_id": "A", "sim": 0.9}],
    )
    r = _retriever(store)
    results = r.search_hybrid("notes", account_id="A", top_k=10)
    ids = [x.image_id for x in results]
    assert ids.count("img-a") == 1
    hit = results[0]
    assert hit.modality == "both"  # visual + ocr present (existing labels preserved)
    assert hit.vlm_score is not None  # VLM evidence merged onto the same row


def test_hybrid_returns_at_most_top_k():
    vlm_rows = [{"image_id": f"img-{i}", "account_id": "A", "sim": 0.5 + i * 0.01}
                for i in range(25)]
    store = FakeStore(visual_rows=[], text_rows=[], vlm_rows=vlm_rows)
    r = _retriever(store)
    results = r.search_hybrid("many", account_id="A", top_k=10)
    assert len(results) <= 10