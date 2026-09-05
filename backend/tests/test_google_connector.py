"""Tests for the Google Photos (Picker API) connector.

All Google HTTP and credentials are mocked; no network is touched and the ML
stack (torch/CLIP) is never imported. Uses the shared `db_session` fixture.
"""

import json
from datetime import datetime, timezone, timedelta

import pytest

from connectors.google import google_auth
from connectors.google import google_sync
from connectors.google.google_auth import (
    create_state,
    consume_state,
    GoogleAuthError,
    STATE_TTL,
)
from models import OAuthState, Image, Connector


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------
def _picked_item(item_id, mime="image/jpeg", filename=None):
    return {
        "id": item_id,
        "createTime": "2024-01-01T00:00:00Z",
        "mediaFile": {
            "baseUrl": f"https://lh3.example/{item_id}",
            "mimeType": mime,
            "filename": filename or f"{item_id}.jpg",
        },
    }


class FakePickerClient:
    """Records calls and returns scripted session/list/download responses."""

    def __init__(self, pages, ready=True, download_fail_ids=None):
        # pages: list of (mediaItems, nextPageToken) tuples
        self._pages = pages
        self._ready = ready
        self._download_fail_ids = set(download_fail_ids or [])
        self.deleted = False

    def create_session(self):
        return {"id": "sess-1", "pickerUri": "https://photos.google.com/pick/sess-1"}

    def get_session(self, session_id):
        return {"id": session_id, "mediaItemsSet": self._ready}

    def list_media_items(self, session_id, page_token=None, page_size=100):
        idx = 0 if page_token is None else int(page_token)
        items, next_token = self._pages[idx]
        resp = {"mediaItems": items}
        if next_token is not None:
            resp["nextPageToken"] = str(next_token)
        return resp

    def download_bytes(self, base_url):
        item_id = base_url.rsplit("/", 1)[-1]
        if item_id in self._download_fail_ids:
            raise RuntimeError("simulated download failure")
        return b"fake-image-bytes"

    def delete_session(self, session_id):
        self.deleted = True


class _StubIndexer:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.calls = []

    def index_locations(self, locations, account_id=None, force=False):
        self.calls.append((list(locations), account_id))
        if self.should_fail:
            raise RuntimeError("simulated indexing failure")
        return {"indexed": len(list(locations))}


@pytest.fixture(autouse=True)
def _isolate_storage(tmp_path, monkeypatch):
    """Redirect image + session dirs to a temp path for every test."""
    monkeypatch.setattr(google_sync, "IMAGE_DIR", str(tmp_path / "images"))
    monkeypatch.setattr(google_auth, "SESSIONS_DIR", str(tmp_path / "sessions"))
    (tmp_path / "sessions").mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Auth: client secret + state security
# ---------------------------------------------------------------------------
def test_missing_client_secret_raises(monkeypatch, db_session):
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET_FILE", "/nonexistent/secret.json")
    with pytest.raises(FileNotFoundError):
        google_auth.get_auth_url("acct-1", db_session)


def test_state_is_random_and_stored(db_session):
    s1 = create_state("acct-1", db_session)
    s2 = create_state("acct-1", db_session)
    assert s1 != s2
    assert len(s1) >= 32
    row = db_session.query(OAuthState).filter(OAuthState.state == s1).first()
    assert row is not None
    assert row.account_id == "acct-1"
    assert row.used == 0


def test_invalid_state_rejected(db_session):
    assert consume_state("does-not-exist", db_session) is None


def test_expired_state_rejected(db_session):
    state = create_state("acct-1", db_session)
    row = db_session.query(OAuthState).filter(OAuthState.state == state).first()
    row.created_at = datetime.now(timezone.utc) - (STATE_TTL + timedelta(minutes=1))
    db_session.commit()
    assert consume_state(state, db_session) is None


def test_used_state_is_single_use(db_session):
    state = create_state("acct-1", db_session)
    assert consume_state(state, db_session) == "acct-1"
    # Second attempt must fail.
    assert consume_state(state, db_session) is None


# ---------------------------------------------------------------------------
# Credentials: loading + refresh
# ---------------------------------------------------------------------------
def test_get_credentials_none_when_missing(db_session):
    assert google_auth.get_credentials("acct-unknown") is None


def _write_creds(account_id):
    google_auth._save_credentials(
        account_id,
        _FakeCreds(token="tok", refresh_token="ref", expired=False),
    )


class _FakeCreds:
    def __init__(self, token="tok", refresh_token="ref", expired=False):
        self.token = token
        self.refresh_token = refresh_token
        self.token_uri = "https://oauth2.example/token"
        self.client_id = "cid"
        self.client_secret = "csecret"
        self.scopes = google_auth.SCOPES
        self.expired = expired
        self.refreshed = False

    def refresh(self, request):
        self.refreshed = True
        self.token = "refreshed-token"
        self.expired = False


def test_credential_loading(monkeypatch):
    _write_creds("acct-load")
    # google-auth may not be installed in the test env; inject a fake class so
    # loading reconstructs credentials from the saved JSON without the library.
    monkeypatch.setattr(
        google_auth, "Credentials",
        lambda **kw: _FakeCreds(token=kw.get("token"),
                                refresh_token=kw.get("refresh_token"),
                                expired=False),
    )
    creds = google_auth.get_credentials("acct-load")
    assert creds is not None
    assert creds.token == "tok"


def test_token_refresh_path(monkeypatch):
    # Persist a creds file, then force load to build an expired Credentials that
    # refreshes successfully.
    _write_creds("acct-refresh")

    built = {}

    def _fake_credentials(**kwargs):
        c = _FakeCreds(token=kwargs.get("token"), refresh_token=kwargs.get("refresh_token"),
                       expired=True)
        built["creds"] = c
        return c

    monkeypatch.setattr(google_auth, "Credentials", _fake_credentials)
    creds = google_auth.get_credentials("acct-refresh")
    assert built["creds"].refreshed is True
    assert creds.token == "refreshed-token"


def test_refresh_failure_raises_typed_error(monkeypatch):
    _write_creds("acct-revoked")

    class _RevokedCreds(_FakeCreds):
        def refresh(self, request):
            raise google_auth.RefreshError("revoked")

    def _fake_credentials(**kwargs):
        return _RevokedCreds(expired=True)

    monkeypatch.setattr(google_auth, "Credentials", _fake_credentials)
    with pytest.raises(GoogleAuthError):
        google_auth.get_credentials("acct-revoked")


# ---------------------------------------------------------------------------
# Sync: pagination, dedup, failures, response shape
# ---------------------------------------------------------------------------
def _authorize(monkeypatch, account_id="acct-sync"):
    monkeypatch.setattr(google_sync, "get_credentials",
                        lambda a: _FakeCreds(token="tok"))


def test_picker_pagination_across_two_pages(monkeypatch, db_session):
    _authorize(monkeypatch)
    indexer = _StubIndexer()
    monkeypatch.setattr(google_sync, "_get_indexer", lambda: indexer)

    pages = [
        ([_picked_item("a"), _picked_item("b")], 1),  # page 0 -> next token "1"
        ([_picked_item("c")], None),                   # page 1 -> last
    ]
    client = FakePickerClient(pages)

    result = google_sync.run_sync_job("acct-sync", db_session, limit=50, client=client)

    assert result["total_processed"] == 3
    assert result["downloaded"] == 3
    assert result["indexed"] == 3
    assert result["status"] == "success"
    assert len(indexer.calls) == 3
    assert db_session.query(Image).count() == 3


def test_duplicate_detection_no_reimport(monkeypatch, db_session):
    _authorize(monkeypatch)
    indexer = _StubIndexer()
    monkeypatch.setattr(google_sync, "_get_indexer", lambda: indexer)

    pages = [([_picked_item("dup")], None)]

    first = google_sync.run_sync_job("acct-sync", db_session, limit=50,
                                     client=FakePickerClient(pages))
    assert first["downloaded"] == 1
    assert db_session.query(Image).count() == 1

    # Second sync with the same media item id must skip it.
    second = google_sync.run_sync_job("acct-sync", db_session, limit=50,
                                      client=FakePickerClient(pages))
    assert second["duplicates_skipped"] == 1
    assert second["downloaded"] == 0
    assert db_session.query(Image).count() == 1


def test_download_failure_counted_and_continues(monkeypatch, db_session):
    _authorize(monkeypatch)
    indexer = _StubIndexer()
    monkeypatch.setattr(google_sync, "_get_indexer", lambda: indexer)

    pages = [([_picked_item("ok"), _picked_item("bad")], None)]
    client = FakePickerClient(pages, download_fail_ids={"bad"})

    result = google_sync.run_sync_job("acct-sync", db_session, limit=50, client=client)

    assert result["total_processed"] == 2
    assert result["downloaded"] == 1
    assert result["download_failures"] == 1
    assert result["status"] == "partial"
    assert db_session.query(Image).count() == 1


def test_index_failure_counted(monkeypatch, db_session):
    _authorize(monkeypatch)
    indexer = _StubIndexer(should_fail=True)
    monkeypatch.setattr(google_sync, "_get_indexer", lambda: indexer)

    pages = [([_picked_item("x")], None)]
    result = google_sync.run_sync_job("acct-sync", db_session, limit=50,
                                      client=FakePickerClient(pages))

    assert result["downloaded"] == 1
    assert result["indexed"] == 0
    assert result["index_failures"] == 1
    assert result["status"] == "partial"


def test_mime_filtering(monkeypatch, db_session):
    _authorize(monkeypatch)
    indexer = _StubIndexer()
    monkeypatch.setattr(google_sync, "_get_indexer", lambda: indexer)

    pages = [([
        _picked_item("img", mime="image/png"),
        _picked_item("vid", mime="video/mp4"),
        _picked_item("gif", mime="image/gif"),
    ], None)]
    result = google_sync.run_sync_job("acct-sync", db_session, limit=50,
                                      client=FakePickerClient(pages))

    # Only the png image is processed; video and gif are filtered out.
    assert result["total_processed"] == 1
    assert result["downloaded"] == 1
    img = db_session.query(Image).one()
    assert img.mime_type == "image/png"
    meta = json.loads(img.source_metadata)
    assert meta["google_media_item_id"] == "img"


def test_response_shape_and_counts(monkeypatch, db_session):
    _authorize(monkeypatch)
    monkeypatch.setattr(google_sync, "_get_indexer", lambda: _StubIndexer())
    pages = [([_picked_item("a")], None)]
    result = google_sync.run_sync_job("acct-sync", db_session, limit=10,
                                      client=FakePickerClient(pages))
    for key in ("status", "total_processed", "downloaded", "duplicates_skipped",
                "indexed", "download_failures", "index_failures"):
        assert key in result


def test_limit_caps_import(monkeypatch, db_session):
    _authorize(monkeypatch)
    monkeypatch.setattr(google_sync, "_get_indexer", lambda: _StubIndexer())
    pages = [([_picked_item(f"i{n}") for n in range(30)], None)]
    result = google_sync.run_sync_job("acct-sync", db_session, limit=10,
                                      client=FakePickerClient(pages))
    assert result["downloaded"] == 10


def test_not_authorized_returns_error(monkeypatch, db_session):
    monkeypatch.setattr(google_sync, "get_credentials", lambda a: None)
    result = google_sync.run_sync_job("acct-none", db_session, limit=10,
                                      client=FakePickerClient([([], None)]))
    assert result["status"] == "error"
    assert result["error"] == "not_authorized"


def test_revoked_credentials_marks_error(monkeypatch, db_session):
    def _raise(a):
        raise GoogleAuthError("revoked")
    monkeypatch.setattr(google_sync, "get_credentials", _raise)
    result = google_sync.run_sync_job("acct-rev", db_session, limit=10)
    assert result["status"] == "error"
    connector = db_session.query(Connector).filter(Connector.user_phone == "acct-rev").first()
    assert connector.status == "error"
