from pathlib import Path
import sys
import types
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.pipeline.indexer import LibraryIndexer
from ml.vectorstore.chroma_store import ChromaStore, vlm_id


class FakeStore:
    def __init__(self):
        self.visual = {}
        self.vlm = {}
        self.deleted = []
        self.visual_indexed = 0
        self.text_indexed = 0

    def open(self):
        return self

    def get_visual_by_image_id(self, image_id, account_id):
        return self.visual.get((account_id, image_id))

    def index_visual_batch(self, records, account_id, filenames=None, extra_metadata=None):
        records = list(records)
        self.visual_indexed += len(records)
        for record in records:
            image_id = record.image_id
            self.visual[(account_id, image_id)] = {
                "metadata": {"fingerprint": (extra_metadata or {})[image_id]["fingerprint"]}
            }
        return len(records)

    def index_text_batch(self, records, account_id):
        records = list(records)
        self.text_indexed += len(records)
        return len(records)

    def delete_vlm(self, image_id, account_id):
        self.deleted.append((image_id, account_id))
        self.vlm.pop((account_id, image_id), None)

    def upsert_vlm_description(self, image_id, account_id, description, embedding, metadata=None):
        self.vlm[(account_id, image_id)] = {
            "description": description,
            "embedding": embedding,
            "metadata": metadata or {},
        }
        return True

    def stats(self):
        return {}


class FakeClip:
    def embed_many(self, records):
        return [SimpleNamespace(image_id=r.image_id, visual_embedding=[1.0], ok=True, dim=1)
                for r in records]


class FakeOcr:
    def extract_many(self, records):
        return [SimpleNamespace(image_id=r.image_id, extracted_text="", file_path=r.file_path,
                                category=r.category) for r in records]


class FakeText:
    def __init__(self):
        self.description_calls = 0

    def embed_ocr_results(self, records, filenames=None):
        return [SimpleNamespace(image_id="image-1", text_embedding=[0.2], has_text=True, ok=True)]

    def embed_text(self, description):
        self.description_calls += 1
        return [0.5, 0.5]


class FakeVlm:
    def __init__(self):
        self.calls = 0

    def describe_many(self, records):
        records = list(records)
        self.calls += len(records)
        return [{"image_id": r.image_id, "description": "A factual image description."}
                for r in records]


class FailingVlm:
    def describe_many(self, records):
        raise RuntimeError("VLM unavailable")


def _indexer(tmp_path, monkeypatch):
    path = tmp_path / "image.jpg"
    path.write_bytes(b"image")
    record = SimpleNamespace(image_id="image-1", file_path=str(path), filename=path.name, category="test")
    store = FakeStore()
    clip = FakeClip()
    ocr = FakeOcr()
    text = FakeText()
    vlm = FakeVlm()
    indexer = LibraryIndexer(store=store)
    monkeypatch.setattr(indexer, "_collect_records", lambda locations, report: [record])
    monkeypatch.setattr(indexer, "_clip_embedder", lambda: clip)
    monkeypatch.setattr(indexer, "_ocr_extractor", lambda: ocr)
    monkeypatch.setattr(indexer, "_text_embedder", lambda: text)
    monkeypatch.setattr(indexer, "_vlm_describer", lambda: vlm)
    return indexer, path, store, text, vlm, record


def test_vlm_generated_once_for_new_and_unchanged_image(tmp_path, monkeypatch):
    indexer, _path, store, text, vlm, _record = _indexer(tmp_path, monkeypatch)

    indexer.index_locations([str(tmp_path)], account_id="acct-a")
    indexer.index_locations([str(tmp_path)], account_id="acct-a")

    assert vlm.calls == 1
    assert text.description_calls == 1
    assert len(store.vlm) == 1


def test_changed_image_replaces_vlm_record(tmp_path, monkeypatch):
    indexer, path, store, _text, vlm, _record = _indexer(tmp_path, monkeypatch)

    indexer.index_locations([str(tmp_path)], account_id="acct-a")
    path.write_bytes(b"changed image")
    path.touch()
    indexer.index_locations([str(tmp_path)], account_id="acct-a")

    assert vlm.calls == 2
    assert len(store.vlm) == 1
    assert store.deleted == [("image-1", "acct-a"), ("image-1", "acct-a")]


def test_vlm_failure_does_not_block_normal_indexing(tmp_path, monkeypatch):
    indexer, _path, store, _text, _vlm, _record = _indexer(tmp_path, monkeypatch)
    monkeypatch.setattr(indexer, "_vlm_describer", lambda: FailingVlm())

    report = indexer.index_locations([str(tmp_path)], account_id="acct-a")

    assert report.visual_indexed == 1
    assert report.text_indexed == 1
    assert store.visual_indexed == 1
    assert store.text_indexed == 1
    assert store.vlm == {}


def test_vlm_load_failure_is_cached(tmp_path, monkeypatch):
    from PIL import Image
    from ml.vlm_description import VLMImageDescriber

    image = tmp_path / "image.jpg"
    Image.new("RGB", (2, 2), "white").save(image)
    calls = {"processor": 0}

    class FailingProcessor:
        @classmethod
        def from_pretrained(cls, _name):
            calls["processor"] += 1
            raise RuntimeError("model unavailable")

    fake_transformers = types.SimpleNamespace(
        BlipProcessor=FailingProcessor,
        BlipForConditionalGeneration=FailingProcessor,
    )
    fake_torch = types.SimpleNamespace(
        cuda=types.SimpleNamespace(is_available=lambda: False),
    )
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    describer = VLMImageDescriber()
    assert describer.describe_one("image-1", str(image)) is None
    assert describer.describe_one("image-1", str(image)) is None
    assert calls["processor"] == 1


def test_vlm_record_id_and_read_are_account_scoped():
    class Collection:
        def __init__(self):
            self.records = {}

        def get(self, ids, include):
            record = self.records.get(ids[0])
            if record is None:
                return {"ids": [], "metadatas": [], "embeddings": []}
            return {"ids": [ids[0]], "metadatas": [record], "embeddings": [[0.1]]}

    store = ChromaStore(db_path="unused")
    store._vlm = Collection()
    store._vlm.records[vlm_id("acct-a", "image-1")] = {
        "account_id": "acct-a", "image_id": "image-1", "vlm_description": "A description"
    }

    assert store.get_vlm_by_image_id("image-1", "acct-a") is not None
    assert store.get_vlm_by_image_id("image-1", "acct-b") is None