"""Property 12 — per-account access/indexing/watcher independence.

Feature: account-scoped-chat-and-isolation (Phase D, task 4.5).

**Property 12: Per-account access/indexing/watcher independence**
**Validates: Requirements R11.1, R11.4, R11.7**

For all pairs of distinct accounts, each account's Access_State (authorized,
indexing, roots, indexedCount, error) is stored and returned independently, and
one account's indexing failure never changes another account's state.

Isolation: the real LibraryIndexer / FolderWatcher and the four-folder scope
derivation are all FAKED here so NO CLIP/OCR/full-folder scan runs. The
per-account daemon thread is replaced with an inline runner so assertions are
deterministic (production async behavior is untouched).
"""

import pytest
from hypothesis import given, settings, strategies as st

import access_service
from fakes import FakeLibraryIndexer, FakeFolderWatcher


# A pair of distinct valid account ids (hex bodies keep them resolver-valid).
_hex = st.text(alphabet="0123456789abcdef", min_size=1, max_size=12)
account_ids = _hex.map(lambda h: f"acct-{h}")
distinct_pairs = st.tuples(account_ids, account_ids).filter(lambda p: p[0] != p[1])


class _InlineThread:
    """A stand-in for threading.Thread whose .start() runs the target inline,
    so the index step completes deterministically within the test."""

    def __init__(self, target, args=()):
        self._target = target
        self._args = args

    def start(self):
        self._target(*self._args)


@pytest.fixture(autouse=True)
def _reset_and_fake():
    """Install fakes once per test function and restore originals afterward.

    NOTE: we deliberately do NOT take pytest's function-scoped `monkeypatch`
    inside `@given` tests (hypothesis re-runs the body per example without
    resetting function-scoped fixtures). Instead we patch module attributes
    directly here and each example resets the maps at its own start.
    """
    import ml.pipeline.watcher as watcher_mod  # noqa: WPS433

    saved = {
        name: getattr(access_service, name)
        for name in ("_states", "_watchers", "_index_threads", "_scoped_roots",
                     "_validate_roots", "_save_persisted", "_spawn_index_thread",
                     "_indexer", "_get_indexer")
    }
    saved_watcher = getattr(watcher_mod, "FolderWatcher", None)

    access_service._states = {}
    access_service._watchers = {}
    access_service._index_threads = {}

    fake_roots = ["/fake/Desktop", "/fake/Pictures"]
    access_service._scoped_roots = lambda: list(fake_roots)
    access_service._validate_roots = lambda paths: list(fake_roots)
    access_service._save_persisted = lambda roots: None
    watcher_mod.FolderWatcher = FakeFolderWatcher
    access_service._spawn_index_thread = (
        lambda acct, roots: _InlineThread(access_service._run_initial_index, (acct, roots))
    )
    try:
        yield
    finally:
        for name, val in saved.items():
            setattr(access_service, name, val)
        watcher_mod.FolderWatcher = saved_watcher


def _use_indexer(indexer):
    """Directly install a fake indexer on the module (restored by the fixture)."""
    access_service._indexer = indexer
    access_service._get_indexer = lambda: indexer


@settings(max_examples=150, deadline=None)
@given(pair=distinct_pairs)
def test_grant_for_A_leaves_B_idle_and_independent(pair):
    """A successful grant for A changes ONLY A; B stays at the idle default."""
    a, b = pair
    access_service._states.clear()
    access_service._watchers.clear()
    access_service._index_threads.clear()
    _use_indexer(FakeLibraryIndexer(should_fail=False))

    resp = access_service.grant_access(a)
    assert resp["authorized"] is True  # authorization accepted / indexing started

    a_state = access_service.get_status(a)
    b_state = access_service.get_status(b)

    # A moved to ready with roots; B is untouched (fresh idle default).
    assert a_state["indexing"] == "ready"
    assert a_state["authorized"] is True
    assert a_state["roots"] == ["/fake/Desktop", "/fake/Pictures"]
    assert b_state == {
        "authorized": False,
        "indexing": "idle",
        "roots": [],
        "indexedCount": 0,
        "error": None,
    }
    # B has no persistent state entry created by a pure status read.
    assert b not in access_service._states


@settings(max_examples=150, deadline=None)
@given(pair=distinct_pairs)
def test_A_failure_never_touches_B(pair):
    """An indexing FAILURE for A sets only A to failed; B can still grant OK."""
    a, b = pair
    access_service._states.clear()
    access_service._watchers.clear()
    access_service._index_threads.clear()

    # A fails.
    _use_indexer(FakeLibraryIndexer(should_fail=True))
    access_service.grant_access(a)
    a_state = access_service.get_status(a)
    assert a_state["indexing"] == "failed"
    assert a_state["authorized"] is False
    assert a_state["error"]
    # No watcher for a failed account.
    assert a not in access_service._watchers

    # B independently grants and succeeds — A's failure did not leak.
    _use_indexer(FakeLibraryIndexer(should_fail=False))
    access_service.grant_access(b)
    b_state = access_service.get_status(b)
    assert b_state["indexing"] == "ready"
    assert b_state["authorized"] is True

    # A is STILL failed and unchanged by B's success.
    a_state2 = access_service.get_status(a)
    assert a_state2["indexing"] == "failed"
    assert a_state2["authorized"] is False


@settings(max_examples=150, deadline=None)
@given(pair=distinct_pairs)
def test_watchers_tracked_per_account(pair):
    """A successful grant starts a watcher tracked under that account only."""
    a, b = pair
    access_service._states.clear()
    access_service._watchers.clear()
    access_service._index_threads.clear()
    _use_indexer(FakeLibraryIndexer(should_fail=False))

    access_service.grant_access(a)
    assert a in access_service._watchers
    assert b not in access_service._watchers
    assert access_service._watchers[a].started is True

    access_service.grant_access(b)
    assert b in access_service._watchers
    # A's watcher object is a distinct instance from B's.
    assert access_service._watchers[a] is not access_service._watchers[b]

    # shutdown stops all tracked watchers and clears tracking.
    wa, wb = access_service._watchers[a], access_service._watchers[b]
    access_service.shutdown()
    assert wa.stopped is True and wb.stopped is True
    assert access_service._watchers == {}
