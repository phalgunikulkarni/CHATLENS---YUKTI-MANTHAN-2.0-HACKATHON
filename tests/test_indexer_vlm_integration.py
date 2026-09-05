"""Focused ingestion-integration tests for the additive BLIP (VLM) step in
ml/pipeline/indexer.py::LibraryIndexer.index_locations.

Scope: ONLY the ingestion integration. Verifies that BLIP runs as an additive
step whose output (``visual_description``) is persisted against the correct
image_id via the EXISTING visual-metadata path, that BLIP failures are isolated
(CLIP/OCR/text indexing still succeeds), that multiple images get their own
descriptions, and that existing indexing behavior/order is intact.

Everything heavy is faked: no real BLIP/CLIP/OCR/Chroma, no model download. We
inject fakes into a real LibraryIndexer instance by replacing its lazy
component accessors and its `store`, exercising the REAL index_locations logic.

Standard-library unittest; no new testing dependency.
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.pipeline.indexer import LibraryIndexer  # noqa: E402


# --- Fakes for the existing pipeline components (behavior unchanged) ---

def _record(image_id, file_path, filename, category="cat"):
    return SimpleNamespace(
        image_id=image_id, file_path=file_path, filename=filename, category=category
    )


class _FakeClip:
    """Returns a visual record per input (mirrors CLIPImageEmbedder.embed_many)."""
    def __init__(self):
        self.calls = 0

    def embed_many(self, records):
        self.calls += 1
        out = []
        for r in records:
            out.append(SimpleNamespace(
                image_id=r.image_id, file_path=r.file_path, category=r.category,
                visual_embedding=[0.1, 0.2, 0.3], dim=3, ok=True,
            ))
        return out


class _FakeOcr:
    def __init__(self):
        self.calls = 0

    def extract_many(self, records):
        self.calls += 1
        return [SimpleNamespace(image_id=r.image_id, file_path=r.file_path,
                                category=r.category, extracted_text="") for r in records]


class _FakeText:
    def __init__(self):
        self.calls = 0

    def embed_ocr_results(self, ocr, filenames=None):
        self.calls += 1
        return list(ocr)  # text records (no usable text -> skipped by store)


class _FakeVlm:
    """Fake BLIP describer. ``fail_for`` = set of image_ids that raise."""
    def __init__(self, mapping=None, fail_for=None):
        self.mapping = mapping or {}
        self.fail_for = fail_for or set()
        self.calls = []

    def describe_one(self, file_path):
        self.calls.append(file_path)
        # Map by filename tail so tests can key on the path they passed.
        for iid, (path, desc) in self.mapping.items():
            if path == file_path:
                if iid in self.fail_for:
                    raise RuntimeError("simulated BLIP failure")
                return desc
        return None


class _FakeStore:
    """Captures what index_visual_batch/index_text_batch receive.

    get_visual_by_image_id returns None so every image 'needs processing'
    (exercises the full path). Records the extra_metadata per image_id so tests
    can assert visual_description persistence keyed by image_id.
    """
    def __init__(self):
        self.visual_extra = {}   # image_id -> extra_metadata dict
        self.visual_count = 0
        self.text_count = 0
        self.open_calls = 0

    def open(self):
        self.open_calls += 1
        return self

    def get_visual_by_image_id(self, image_id):
        return None

    def index_visual_batch(self, records, filenames=None, extra_metadata=None):
        recs = list(records)
        for r in recs:
            iid = getattr(r, "image_id", None)
            if extra_metadata and iid in extra_metadata:
                self.visual_extra[iid] = dict(extra_metadata[iid])
        self.visual_count += len(recs)
        return len(recs)

    def index_text_batch(self, records):
        recs = list(records)
        self.text_count += len(recs)
        return len(recs)

    def stats(self):
        return {"visual": self.visual_count, "text": self.text_count}


def _make_indexer(records, vlm, store):
    """Build a LibraryIndexer with all heavy components faked, exercising the
    REAL index_locations orchestration."""
    idx = LibraryIndexer(store=store)
    idx._clip = _FakeClip()
    idx._ocr = _FakeOcr()
    idx._text = _FakeText()
    idx._vlm = vlm
    # Fake discovery: return our records regardless of the given locations.
    idx._collect_records = lambda locations, report: (
        setattr(report, "discovered_images", len(records)) or list(records)
    )
    # Deterministic fingerprint so no real os.stat is needed.
    import ml.pipeline.indexer as indexer_mod
    indexer_mod._fingerprint = lambda p: "fp"
    indexer_mod._source_root_for = lambda fp, roots: (roots[0] if roots else "")
    return idx


class IndexerVlmIntegrationTests(unittest.TestCase):
    def test_A_description_stored_against_image_id(self):
        recs = [_record("id1", "/x/a.png", "a.png")]
        vlm = _FakeVlm(mapping={"id1": ("/x/a.png", "a red diagram on white paper")})
        store = _FakeStore()
        idx = _make_indexer(recs, vlm, store)

        report = idx.index_locations(["/x"])

        self.assertEqual(store.visual_extra["id1"].get("visual_description"),
                         "a red diagram on white paper")
        # Existing metadata still present (additive, not replacing).
        self.assertIn("fingerprint", store.visual_extra["id1"])
        self.assertIn("absolute_path", store.visual_extra["id1"])
        self.assertEqual(report.visual_indexed, 1)

    def test_B_blip_failure_does_not_block_clip_ocr_text(self):
        recs = [_record("id1", "/x/a.png", "a.png")]
        vlm = _FakeVlm(mapping={"id1": ("/x/a.png", "desc")}, fail_for={"id1"})
        store = _FakeStore()
        idx = _make_indexer(recs, vlm, store)

        report = idx.index_locations(["/x"])

        # CLIP/OCR/text still ran and indexed despite BLIP raising.
        self.assertEqual(idx._clip.calls, 1)
        self.assertEqual(idx._ocr.calls, 1)
        self.assertEqual(idx._text.calls, 1)
        self.assertEqual(report.visual_indexed, 1)
        # No visual_description persisted for the failed image.
        self.assertNotIn("visual_description", store.visual_extra.get("id1", {}))

    def test_C_multiple_images_get_own_descriptions(self):
        recs = [
            _record("id1", "/x/a.png", "a.png"),
            _record("id2", "/x/b.png", "b.png"),
            _record("id3", "/x/c.png", "c.png"),
        ]
        vlm = _FakeVlm(mapping={
            "id1": ("/x/a.png", "desc one"),
            "id2": ("/x/b.png", "desc two"),
            "id3": ("/x/c.png", "desc three"),
        }, fail_for={"id2"})  # middle one fails -> isolation
        store = _FakeStore()
        idx = _make_indexer(recs, vlm, store)

        idx.index_locations(["/x"])

        self.assertEqual(store.visual_extra["id1"]["visual_description"], "desc one")
        self.assertNotIn("visual_description", store.visual_extra["id2"])  # failed
        self.assertEqual(store.visual_extra["id3"]["visual_description"], "desc three")
        self.assertEqual(store.visual_count, 3)  # all 3 still visually indexed

    def test_D_existing_behavior_intact_and_reuse(self):
        recs = [
            _record("id1", "/x/a.png", "a.png"),
            _record("id2", "/x/b.png", "b.png"),
        ]
        vlm = _FakeVlm(mapping={
            "id1": ("/x/a.png", "d1"),
            "id2": ("/x/b.png", "d2"),
        })
        store = _FakeStore()
        idx = _make_indexer(recs, vlm, store)

        report = idx.index_locations(["/x"])

        # Existing counts/behavior intact.
        self.assertEqual(report.visual_indexed, 2)
        self.assertEqual(report.text_indexed, 2)
        # One reused describer for the whole batch: describe_one called per image
        # on the SAME fake instance (no reload/reconstruct per image).
        self.assertEqual(len(vlm.calls), 2)
        self.assertEqual(idx._vlm, vlm)  # same instance used throughout

    def test_E_idempotency_preserved_no_processing_when_unchanged(self):
        # Store reports the image already exists with a matching fingerprint ->
        # index_locations must skip it (no CLIP/OCR/text/BLIP), preserving the
        # existing incremental behavior. BLIP must not run for skipped images.
        recs = [_record("id1", "/x/a.png", "a.png")]
        vlm = _FakeVlm(mapping={"id1": ("/x/a.png", "desc")})
        store = _FakeStore()

        class _ExistingStore(_FakeStore):
            def get_visual_by_image_id(self, image_id):
                return {"metadata": {"fingerprint": "fp"}}  # matches faked _fingerprint

        store = _ExistingStore()
        idx = _make_indexer(recs, vlm, store)

        report = idx.index_locations(["/x"])

        self.assertEqual(report.skipped_unchanged, 1)
        self.assertEqual(report.new_or_changed, 0)
        self.assertEqual(len(vlm.calls), 0)   # BLIP NOT run for unchanged image
        self.assertEqual(store.visual_count, 0)


if __name__ == "__main__":
    unittest.main()
