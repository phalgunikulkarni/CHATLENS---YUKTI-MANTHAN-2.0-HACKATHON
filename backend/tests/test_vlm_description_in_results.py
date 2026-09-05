"""Phase 3D - VLM description exposed on search results (backend).

Feature: vlm-description-in-results (Phase 3D).

Model-free tests: they exercise the pure adapter mapping and the Pydantic
schema, plus the account-scoped VLM lookup with a fake store. No chromadb /
sentence-transformers / sqlalchemy needed.

Covers:
  - to_memory_result_dict maps a present vlm_description -> vlmDescription.
  - Absent VLM description -> vlmDescription is None (existing behavior intact).
  - MemoryResult schema carries the optional vlmDescription field.
  - _vlm_description_for is account-scoped: it reads (account_id, image_id) via
    the store, so another account's description can never be returned.
  - A store failure yields None (search never fails on VLM metadata).
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/

import ml_retrieval
from schemas import MemoryResult


def test_to_memory_result_dict_maps_vlm_description():
    row = {"image_id": "img-1", "score": 0.5, "vlm_description": "A red bicycle by the sea."}
    out = ml_retrieval.to_memory_result_dict(row)
    assert out["vlmDescription"] == "A red bicycle by the sea."


def test_to_memory_result_dict_without_vlm_description_is_none():
    row = {"image_id": "img-1", "score": 0.5}
    out = ml_retrieval.to_memory_result_dict(row)
    assert out["vlmDescription"] is None


def test_memory_result_schema_includes_optional_vlm_field():
    m = MemoryResult(id="img-1", thumbnailUrl="/api/images/img-1/file",
                     vlmDescription="A handwritten OSI diagram.")
    assert m.vlmDescription == "A handwritten OSI diagram."
    # Optional: default None keeps existing behavior.
    m2 = MemoryResult(id="img-2", thumbnailUrl="/api/images/img-2/file")
    assert m2.vlmDescription is None


class _FakeStore:
    """Account-scoped fake: only returns a record when BOTH ids match."""

    def __init__(self, account_id, image_id, description):
        self._acct = account_id
        self._img = image_id
        self._desc = description

    def get_vlm_by_image_id(self, image_id, account_id):
        if account_id == self._acct and image_id == self._img:
            return {"metadata": {"vlm_description": self._desc, "account_id": account_id,
                                 "image_id": image_id}}
        return None


def test_vlm_description_lookup_is_account_scoped(monkeypatch):
    store = _FakeStore("acct-A", "img-1", "A's private description.")
    monkeypatch.setattr(ml_retrieval, "_get_store", lambda: store)

    # Owner sees it...
    assert ml_retrieval._vlm_description_for("img-1", "acct-A") == "A's private description."
    # ...another account never does (store returns None for a non-owner id).
    assert ml_retrieval._vlm_description_for("img-1", "acct-B") is None


def test_vlm_description_lookup_never_raises(monkeypatch):
    class _Boom:
        def get_vlm_by_image_id(self, image_id, account_id):
            raise RuntimeError("store down")

    monkeypatch.setattr(ml_retrieval, "_get_store", lambda: _Boom())
    assert ml_retrieval._vlm_description_for("img-1", "acct-A") is None

    monkeypatch.setattr(ml_retrieval, "_get_store", lambda: None)
    assert ml_retrieval._vlm_description_for("img-1", "acct-A") is None