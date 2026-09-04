"""Example tests — access status/grant account scoping + async return (task 4.6).

Feature: account-scoped-chat-and-isolation (Phase D).
_Requirements: R11.3, R11.4, R11.5_

Uses FastAPI TestClient with the real access_service, but with the indexer,
watcher, scope derivation, and persistence FAKED so no CLIP/OCR/full-folder scan
runs. Two distinct accounts ("acct-aaaa", "acct-bbbb") prove no state leakage.
Also asserts the Phase A 401 gate is intact and the four-folder allowlist is
unchanged.
"""

import threading

import pytest
from fastapi.testclient import TestClient

import access_service
import main
from fakes import FakeLibraryIndexer, FakeFolderWatcher


A = "acct-aaaa"
B = "acct-bbbb"


class _InlineThread:
    def __init__(self, target, args=()):
        self._target = target
        self._args = args

    def start(self):
        self._target(*self._args)


@pytest.fixture
def access_client(monkeypatch):
    """TestClient with access_service faked for deterministic, offline runs."""
    monkeypatch.setattr(access_service, "_states", {}, raising=True)
    monkeypatch.setattr(access_service, "_watchers", {}, raising=True)
    monkeypatch.setattr(access_service, "_index_threads", {}, raising=True)

    fake_roots = ["/fake/Desktop", "/fake/Pictures"]
    monkeypatch.setattr(access_service, "_scoped_roots", lambda: list(fake_roots))
    monkeypatch.setattr(access_service, "_validate_roots", lambda paths: list(fake_roots))
    monkeypatch.setattr(access_service, "_save_persisted", lambda roots: None)

    indexer = FakeLibraryIndexer(should_fail=False)
    monkeypatch.setattr(access_service, "_indexer", indexer, raising=True)
    monkeypatch.setattr(access_service, "_get_indexer", lambda: indexer)

    import ml.pipeline.watcher as watcher_mod
    monkeypatch.setattr(watcher_mod, "FolderWatcher", FakeFolderWatcher, raising=False)

    # Inline index thread → deterministic completion within the request.
    monkeypatch.setattr(
        access_service,
        "_spawn_index_thread",
        lambda acct, roots: _InlineThread(access_service._run_initial_index, (acct, roots)),
    )

    return TestClient(main.app)


def _h(acct):
    return {"X-Account-Id": acct}


def test_status_default_idle_per_account(access_client):
    """A never-granted account reports the idle default; A/B independent."""
    resp = access_client.get("/api/access/status", headers=_h(A))
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "authorized": False,
        "indexing": "idle",
        "roots": [],
        "indexedCount": 0,
        "error": None,
    }


def test_grant_a_does_not_affect_b(access_client):
    """Granting for A moves only A to ready; B stays idle."""
    g = access_client.post("/api/access/grant", headers=_h(A))
    assert g.status_code == 200
    assert g.json()["authorized"] is True  # authorization accepted / started

    a_status = access_client.get("/api/access/status", headers=_h(A)).json()
    b_status = access_client.get("/api/access/status", headers=_h(B)).json()

    assert a_status["indexing"] == "ready"
    assert a_status["authorized"] is True
    assert a_status["roots"] == ["/fake/Desktop", "/fake/Pictures"]

    assert b_status["indexing"] == "idle"
    assert b_status["authorized"] is False
    assert b_status["roots"] == []


def test_grant_returns_before_indexing_completes(monkeypatch, access_client):
    """R11.5: grant returns immediately; it does NOT block on indexing.

    We replace the thread spawn with a real (non-inline) thread that blocks on
    an event, and assert grant returns while indexing is still 'running'.
    """
    release = threading.Event()
    started = threading.Event()

    slow_indexer = FakeLibraryIndexer(should_fail=False)
    orig_index = slow_indexer.index_locations

    def blocking_index(locations, account_id=None, force=False):
        started.set()
        release.wait(timeout=5)
        return orig_index(locations, account_id=account_id, force=force)

    slow_indexer.index_locations = blocking_index  # type: ignore[assignment]
    monkeypatch.setattr(access_service, "_indexer", slow_indexer, raising=True)
    monkeypatch.setattr(access_service, "_get_indexer", lambda: slow_indexer)

    # Use a REAL daemon thread so grant returns while indexing blocks.
    monkeypatch.setattr(
        access_service,
        "_spawn_index_thread",
        lambda acct, roots: threading.Thread(
            target=access_service._run_initial_index, args=(acct, roots), daemon=True
        ),
    )

    g = access_client.post("/api/access/grant", headers=_h(A))
    assert g.status_code == 200
    assert g.json()["authorized"] is True

    assert started.wait(timeout=5), "index thread should have started"
    # While the index is still blocked, status must be 'running' (async return).
    status = access_client.get("/api/access/status", headers=_h(A)).json()
    assert status["indexing"] == "running"
    assert status["authorized"] is False

    release.set()  # let the background index finish (cleanup)


def test_grant_and_status_reject_missing_or_invalid_header(access_client):
    """Phase A 401 gate intact on both access endpoints."""
    assert access_client.post("/api/access/grant", json={}, headers={}).status_code == 401
    assert access_client.get("/api/access/status", headers={}).status_code == 401
    bad = {"X-Account-Id": "not-an-account"}
    assert access_client.post("/api/access/grant", json={}, headers=bad).status_code == 401
    assert access_client.get("/api/access/status", headers=bad).status_code == 401


def test_four_folder_allowlist_unchanged():
    """The real scope derivation is still the four user-facing folders only."""
    from ml.filesystem.local_access import LocalImageAccess
    import os

    expected = {os.path.realpath(r) for r in (LocalImageAccess().default_user_scope() or [])}
    assert set(access_service._scoped_roots()) == expected
    # An arbitrary path outside the allowlist is rejected by validation.
    assert access_service._validate_roots(["C:\\"]) == []
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        assert access_service._validate_roots([tmp]) == []
