"""Startup restore + catch-up index tests for access_service.restore_on_startup().

Verifies (offline, using the existing fakes; NO CLIP/OCR/Chroma):
  - Persisted roots are restored and handed to the EXISTING incremental indexer.
  - restore reuses the SAME background path as grant_access (_run_initial_index
    -> _start_watcher): the watcher is started for the restored roots.
  - Only allowlist-validated roots are indexed (out-of-allowlist dropped).
  - No persisted roots -> safe no-op (no index, no watcher).
Run:
    python tests/test_startup_restore.py
"""
from __future__ import annotations

import os, sys, traceback

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import access_service as A
from fakes import FakeLibraryIndexer, FakeFolderWatcher


class _InlineThread:
    """Run the index target synchronously so tests are deterministic."""
    def __init__(self, target, args=()):
        self._target = target; self._args = args
    def start(self):
        self._target(*self._args)


def _reset(monkey_roots, allowlist=None, persisted=None, fail=False):
    """Reset access_service state + install fakes. Returns the fake indexer."""
    A._states = {}
    A._watchers = {}
    A._index_threads = {}
    A._state = {"error": None}

    persisted = persisted if persisted is not None else list(monkey_roots)
    allowlist = allowlist if allowlist is not None else list(monkey_roots)

    A._load_persisted = lambda: list(persisted)
    # _validate_roots must enforce the allowlist: only keep persisted ∩ allowlist.
    A._validate_roots = lambda paths: [p for p in paths if p in allowlist]

    indexer = FakeLibraryIndexer(should_fail=fail)
    A._indexer = indexer
    A._get_indexer = lambda: indexer

    import ml.pipeline.watcher as watcher_mod
    watcher_mod.FolderWatcher = FakeFolderWatcher  # _start_watcher imports from here

    A._spawn_index_thread = lambda acct, roots: _InlineThread(A._run_initial_index, (acct, roots))
    return indexer


def test_restore_indexes_persisted_allowed_roots_and_starts_watcher():
    roots = ["/fake/Desktop", "/fake/Downloads"]
    indexer = _reset(roots)
    A.restore_on_startup()
    # The existing incremental indexer was called exactly once with the roots.
    assert len(indexer.calls) == 1, indexer.calls
    assert indexer.calls[0]["locations"] == roots
    # Watcher started for the restore account (reused grant_access path).
    st = A.get_status(A.RESTORE_ACCOUNT_ID)
    assert st["indexing"] == "ready" and st["authorized"] is True, st
    assert A._watchers.get(A.RESTORE_ACCOUNT_ID) is not None
    assert A._watchers[A.RESTORE_ACCOUNT_ID].started is True


def test_restore_drops_out_of_allowlist_paths():
    # Persisted has a dataset path outside the four folders; allowlist excludes it.
    persisted = ["/fake/Desktop", "/Users/x/project/data/dataset1"]
    allowlist = ["/fake/Desktop", "/fake/Downloads", "/fake/Documents", "/fake/Pictures"]
    indexer = _reset(persisted, allowlist=allowlist, persisted=persisted)
    A.restore_on_startup()
    assert len(indexer.calls) == 1
    # Only the allowed root survived; dataset path never reached the indexer.
    assert indexer.calls[0]["locations"] == ["/fake/Desktop"], indexer.calls[0]
    assert "/Users/x/project/data/dataset1" not in indexer.calls[0]["locations"]


def test_restore_noop_when_nothing_persisted():
    indexer = _reset([], persisted=[])
    A.restore_on_startup()
    assert indexer.calls == []                       # no indexing
    assert A._watchers == {}                          # no watcher
    st = A.get_status(A.RESTORE_ACCOUNT_ID)
    assert st["indexing"] == "idle"                   # untouched default


def test_restore_noop_when_none_survive_allowlist():
    persisted = ["/Users/x/project/data/dataset1", "/tmp/whatever"]
    indexer = _reset(persisted, allowlist=["/fake/Desktop"], persisted=persisted)
    A.restore_on_startup()
    assert indexer.calls == []
    assert A._watchers == {}


def test_restore_uses_incremental_indexer_not_a_second_system():
    # Sanity: restore calls index_locations (the EXISTING idempotent/fingerprint
    # pipeline), never a bespoke indexing routine.
    roots = ["/fake/Pictures"]
    indexer = _reset(roots)
    A.restore_on_startup()
    assert len(indexer.calls) == 1 and indexer.calls[0]["locations"] == roots


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t(); print(f"PASS {t.__name__}"); passed += 1
        except Exception:
            print(f"FAIL {t.__name__}"); traceback.print_exc(); failed += 1
    print(f"startup_restore: {passed} passed, {failed} failed, {passed+failed} total")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if _run() else 1)
