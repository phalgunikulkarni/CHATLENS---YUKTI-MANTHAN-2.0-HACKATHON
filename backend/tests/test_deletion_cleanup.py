from pathlib import Path
import sys
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.pipeline.indexer import LibraryIndexer
from ml.ingestion.scanner import stable_image_id
from ml.vectorstore.chroma_store import ChromaStore, text_id, visual_id


class _Store:
    def __init__(self):
        self.visual_deleted = []
        self.text_deleted = []
        self.visual_records = set()
        self.text_records = set()

    def open(self):
        return self

    def delete_visual(self, image_id, account_id):
        self.visual_deleted.append((image_id, account_id))
        self.visual_records.discard((image_id, account_id))

    def delete_text(self, image_id, account_id):
        self.text_deleted.append((image_id, account_id))
        self.text_records.discard((image_id, account_id))


def test_deleted_path_removes_visual_and_text_for_only_owner(tmp_path):
    path = tmp_path / "note.jpg"
    path.write_bytes(b"test")
    store = _Store()
    image_id = stable_image_id(path)
    store.visual_records.add((image_id, "acct-a"))
    store.text_records.add((image_id, "acct-a"))
    store.visual_records.add((image_id, "acct-b"))
    store.text_records.add((image_id, "acct-b"))
    indexer = LibraryIndexer(store=store)

    path.unlink()
    assert indexer.remove_paths([str(path)], account_id="acct-a") == 1
    assert store.visual_deleted == [(image_id, "acct-a")]
    assert store.text_deleted == [(image_id, "acct-a")]
    assert (image_id, "acct-a") not in store.visual_records
    assert (image_id, "acct-a") not in store.text_records
    assert (image_id, "acct-b") in store.visual_records
    assert (image_id, "acct-b") in store.text_records


def test_already_missing_path_does_not_crash_cleanup(tmp_path):
    store = _Store()
    indexer = LibraryIndexer(store=store)
    missing = Path(tmp_path) / "missing.png"
    assert indexer.remove_paths([str(missing)], account_id="acct-a") == 1


def test_chroma_delete_ids_are_account_scoped():
    store = ChromaStore(db_path="unused")
    store._visual = Mock()
    store._text = Mock()

    store.delete_visual("img-1", "acct-a")
    store.delete_text("img-1", "acct-a")

    store._visual.delete.assert_called_once_with(ids=[visual_id("acct-a", "img-1")])
    store._text.delete.assert_called_once_with(ids=[text_id("acct-a", "img-1")])
    assert visual_id("acct-b", "img-1") != visual_id("acct-a", "img-1")
    assert text_id("acct-b", "img-1") != text_id("acct-a", "img-1")