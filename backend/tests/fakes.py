"""In-memory fakes for the ml/ layer (Phase B test harness).

These fakes let chat/endpoint tests run with NO torch / CLIP / OCR import. They
are deliberately tiny and deterministic.

- FakeChromaStore: an in-memory dict store honoring `where={"account_id": ...}`
  and account-qualified record ids (`visual_<account>_<image_id>` /
  `text_<account>_<image_id>`), matching the design's Chroma strategy.
- FakeRetriever: returns a deterministic ranked list of result objects.
- FakeLibraryIndexer / FakeFolderWatcher: record calls and can simulate
  success / failure / batch, without doing any real work.

They are not wired into any production module by default; tests opt in via
monkeypatch. Nothing here imports torch/CLIP/OCR.
"""

from types import SimpleNamespace
from typing import Any, Dict, List, Optional


def visual_id(account_id: str, image_id: str) -> str:
    return f"visual_{account_id}_{image_id}"


def text_id(account_id: str, image_id: str) -> str:
    return f"text_{account_id}_{image_id}"


class FakeChromaStore:
    """Minimal in-memory Chroma-like store honoring account_id filtering."""

    def __init__(self) -> None:
        # record_id -> {"metadata": {...}, "document": str, "embedding": [...]}
        self._visual: Dict[str, Dict[str, Any]] = {}
        self._text: Dict[str, Dict[str, Any]] = {}

    def upsert_visual(self, image_id: str, metadata: Dict[str, Any], extra_metadata: Optional[Dict[str, Any]] = None):
        md = dict(metadata or {})
        if extra_metadata:
            md.update(extra_metadata)
        account_id = md.get("account_id", "")
        self._visual[visual_id(account_id, image_id)] = {"metadata": md}

    def upsert_text(self, image_id: str, metadata: Dict[str, Any], extra_metadata: Optional[Dict[str, Any]] = None):
        md = dict(metadata or {})
        if extra_metadata:
            md.update(extra_metadata)
        account_id = md.get("account_id", "")
        self._text[text_id(account_id, image_id)] = {"metadata": md}

    @staticmethod
    def _matches(md: Dict[str, Any], where: Optional[Dict[str, Any]]) -> bool:
        if not where:
            return True
        return all(md.get(k) == v for k, v in where.items())

    def query_visual(self, where: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return [rec for rec in self._visual.values() if self._matches(rec["metadata"], where)]

    def get_visual_by_image_id(self, image_id: str, account_id: str) -> Optional[Dict[str, Any]]:
        return self._visual.get(visual_id(account_id, image_id))

    def get_text_by_image_id(self, image_id: str, account_id: str) -> Optional[Dict[str, Any]]:
        return self._text.get(text_id(account_id, image_id))


class FakeRetriever:
    """Deterministic ranked results. `search` returns SimpleNamespace rows in
    the shape ml_retrieval.search_memories expects (image_id, score, filename,
    modality, visual_score, text_score, reason, ...)."""

    def __init__(self, rows: Optional[List[Dict[str, Any]]] = None) -> None:
        self._rows = rows or []

    def set_rows(self, rows: List[Dict[str, Any]]) -> None:
        self._rows = rows

    def search(self, query: str, top_k: int = 5, account_id: Optional[str] = None):
        out = []
        for r in self._rows[:top_k]:
            out.append(SimpleNamespace(**r))
        return out


class FakeLibraryIndexer:
    """Records index calls; can simulate success/failure."""

    def __init__(self, should_fail: bool = False) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.should_fail = should_fail

    def index_locations(self, locations, account_id=None, force=False):
        self.calls.append({"locations": list(locations), "account_id": account_id, "force": force})
        if self.should_fail:
            raise RuntimeError("simulated indexing failure")
        return SimpleNamespace(indexed=len(list(locations)), account_id=account_id)


class FakeFolderWatcher:
    """Records start/stop and can push a simulated batch to on_batch."""

    def __init__(self, roots=None, on_batch=None, **kwargs) -> None:
        self.roots = list(roots or [])
        self.on_batch = on_batch
        self.started = False
        self.stopped = False
        self.batches: List[Any] = []

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def simulate_batch(self, changed):
        self.batches.append(changed)
        if self.on_batch:
            self.on_batch(changed)


def make_result_rows(image_ids, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Build deterministic search-result dict rows for FakeRetriever.

    Shape mirrors what ml_retrieval.search_memories reads off retriever rows.
    """
    rows = []
    for i, iid in enumerate(image_ids):
        rows.append(
            {
                "image_id": iid,
                "score": 1.0 - (i * 0.1),
                "filename": f"{iid}.png",
                "category": "note",
                "extracted_text": f"text for {iid}",
                "absolute_path": f"/fake/root/{iid}.png",
                "file_path": f"/fake/root/{iid}.png",
                "modality": "both",
                "reason": f"matched {iid}",
                "visual_score": 0.5,
                "text_score": 0.4,
                "retrieval_signal": "hybrid",
                "account_id": account_id,
            }
        )
    return rows
