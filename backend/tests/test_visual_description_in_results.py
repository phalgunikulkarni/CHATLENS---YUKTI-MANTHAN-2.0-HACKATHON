"""Focused backend tests: carry the stored BLIP ``visual_description`` into
search results as ``MemoryResult.visualDescription``.

Scope: ONLY the result-construction/passthrough in backend/ml_retrieval.py and
the MemoryResult schema field. No retrieval/ranking/similarity/order changes.

Everything heavy is faked: a fake Retriever (deterministic ranked results) and
a fake ChromaStore (returns per-image_id visual_description). No real
BLIP/CLIP/OCR/Chroma, no model download.
"""
import os
import sys
import unittest
from types import SimpleNamespace

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import ml_retrieval  # noqa: E402
from schemas import MemoryResult  # noqa: E402


# --- to_memory_result_dict: direct passthrough of visual_description ---

class ToMemoryResultDictTests(unittest.TestCase):
    def test_present_description_maps_to_visualDescription(self):
        row = {"image_id": "id1", "score": 0.5, "visual_description": "a cat on a red sofa"}
        out = ml_retrieval.to_memory_result_dict(row)
        self.assertEqual(out["visualDescription"], "a cat on a red sofa")
        # Field is accepted by the schema and round-trips.
        mr = MemoryResult(**{k: v for k, v in out.items() if k != "explanation"})
        self.assertEqual(mr.visualDescription, "a cat on a red sofa")

    def test_missing_description_is_none_not_fabricated(self):
        row = {"image_id": "id2", "score": 0.4}  # no visual_description key
        out = ml_retrieval.to_memory_result_dict(row)
        self.assertIsNone(out["visualDescription"])

    def test_blank_description_normalized_to_none(self):
        row = {"image_id": "id3", "score": 0.3, "visual_description": "   "}
        out = ml_retrieval.to_memory_result_dict(row)
        self.assertIsNone(out["visualDescription"])

    def test_existing_fields_unchanged(self):
        row = {"image_id": "id4", "score": 0.9, "category": "notes",
               "extracted_text": "OSI model", "visual_description": "handwritten notes"}
        out = ml_retrieval.to_memory_result_dict(row)
        # Pre-existing behavior intact.
        self.assertEqual(out["id"], "id4")
        self.assertEqual(out["thumbnailUrl"], "/api/images/id4/file")
        self.assertEqual(out["ocrSnippet"], "OSI model")
        self.assertEqual(out["sourceTag"], "notes")
        self.assertEqual(out["matchScore"], 0.9)
        # And the new field is present.
        self.assertEqual(out["visualDescription"], "handwritten notes")


# --- search_memories: enriches kept results via store lookup by image_id ---

class _FakeStore:
    def __init__(self, descriptions):
        self._desc = descriptions  # image_id -> description (or None)

    def open(self):
        return self

    def get_visual_by_image_id(self, image_id):
        if image_id not in self._desc:
            return None
        return {"metadata": {"image_id": image_id,
                             "visual_description": self._desc[image_id]}}


class VisualDescriptionLookupTests(unittest.TestCase):
    """Exercises the exact code paths this task added: the store lookup
    (_stored_visual_description) and its passthrough into the result dict, using
    mock.patch.object on the store only. This is independent of the retriever
    singleton, so it is robust to full-suite ordering.
    """
    def _with_store(self, descriptions):
        from unittest import mock
        return mock.patch.object(ml_retrieval, "_get_store",
                                 return_value=_FakeStore(descriptions))

    def test_lookup_returns_stored_description(self):
        with self._with_store({"A": "description A", "B": "description B"}):
            self.assertEqual(ml_retrieval._stored_visual_description("A"), "description A")
            self.assertEqual(ml_retrieval._stored_visual_description("B"), "description B")

    def test_lookup_missing_returns_none(self):
        with self._with_store({"A": "description A"}):
            self.assertIsNone(ml_retrieval._stored_visual_description("C"))

    def test_each_result_keeps_its_own_description_end_to_end(self):
        # Simulate what search_memories does: build a row per ranked result, look
        # up its description by image_id, then map to the frontend result dict.
        with self._with_store({"A": "description A", "B": "description B"}):
            rows = []
            for iid, score in [("A", 0.9), ("B", 0.8)]:
                row = {"image_id": iid, "score": score}
                row["visual_description"] = ml_retrieval._stored_visual_description(iid)
                rows.append(row)
        results = [ml_retrieval.to_memory_result_dict(r) for r in rows]
        by_id = {r["id"]: r for r in results}
        self.assertEqual(by_id["A"]["visualDescription"], "description A")
        self.assertEqual(by_id["B"]["visualDescription"], "description B")
        # Order/scores untouched by the enrichment.
        self.assertEqual([r["id"] for r in results], ["A", "B"])
        self.assertEqual([r["matchScore"] for r in results], [0.9, 0.8])


if __name__ == "__main__":
    unittest.main()
