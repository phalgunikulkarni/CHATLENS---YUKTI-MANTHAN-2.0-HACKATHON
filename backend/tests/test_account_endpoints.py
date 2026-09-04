"""Backend tests — resolver + endpoint gating (Task 1.9).

Feature: account-scoped-chat-and-isolation (Phase A).

Covers:
- `resolve_account` directly for valid / missing / malformed headers.
- FastAPI TestClient: the seven user-owned endpoints return 401 with a
  missing/malformed `X-Account-Id`; `/health` works with no header; a valid
  `acct-<hex>` header is accepted (resolves as that account, incl. A and B).

To avoid importing torch/CLIP, tests assert the 401 gate (which runs BEFORE the
endpoint body via the dependency) and, for the accepted path, monkeypatch the
specific service functions to no-ops so no heavy model is loaded.
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import account
import main
from account import resolve_account


# --- resolve_account direct tests ------------------------------------------

@pytest.mark.parametrize("value", ["acct-1a2b", "acct-deadbeef", "acct-0", "acct-abcdef0123456789"])
def test_resolve_account_accepts_valid(value):
    assert resolve_account(value) == value


@pytest.mark.parametrize(
    "value",
    [
        None,            # missing header
        "",              # empty
        "acct-",         # no hex body
        "acct-XYZ",      # non-hex
        "acct-1A2B",     # uppercase hex not allowed by ^acct-[0-9a-f]+$
        "user-1a2b",     # wrong prefix
        "1a2b",          # no prefix
        " acct-1a2b",    # leading space
        "acct-1a2b ",    # trailing space
    ],
)
def test_resolve_account_rejects_invalid(value):
    with pytest.raises(HTTPException) as exc:
        resolve_account(value)
    assert exc.value.status_code == 401


# --- TestClient endpoint gating --------------------------------------------

client = TestClient(main.app)

# (method, path) for each of the seven user-owned endpoints.
USER_OWNED = [
    ("post", "/api/search"),
    ("post", "/api/refine"),
    ("get", "/api/library"),
    ("get", "/api/images/abc123/file"),
    ("get", "/api/images/abc123/status"),
    ("post", "/api/access/grant"),
    ("get", "/api/access/status"),
]


def _call(method, path, headers=None):
    if method == "post":
        # Send an empty JSON body; the 401 gate fires before body validation
        # for missing/invalid identity, so the body shape does not matter here.
        return client.post(path, json={}, headers=headers or {})
    return client.get(path, headers=headers or {})


@pytest.mark.parametrize("method,path", USER_OWNED)
def test_user_owned_reject_missing_header(method, path):
    resp = _call(method, path, headers={})
    assert resp.status_code == 401


@pytest.mark.parametrize("method,path", USER_OWNED)
def test_user_owned_reject_malformed_header(method, path):
    resp = _call(method, path, headers={"X-Account-Id": "not-an-account"})
    assert resp.status_code == 401


def test_health_open_without_header():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_valid_header_accepted_resolves_account(monkeypatch):
    """A valid acct-<hex> header passes the gate and the endpoint body runs.

    We monkeypatch `access_service.get_status` so no indexer/model loads, and
    capture that the endpoint executed (i.e. was not 401-gated) for Account A
    and Account B distinctly.
    """
    seen = {}

    def fake_get_status(*args, **kwargs):
        seen["called"] = True
        return {"authorized": False, "indexing": "idle", "roots": [], "indexedCount": 0, "error": None}

    monkeypatch.setattr(main.access_service, "get_status", fake_get_status)

    for acct in ("acct-aaaa", "acct-bbbb"):
        seen.clear()
        resp = client.get("/api/access/status", headers={"X-Account-Id": acct})
        assert resp.status_code == 200, resp.text
        assert seen.get("called") is True


def test_account_a_and_b_resolve_independently():
    """Direct resolver check that A resolves as A and B resolves as B."""
    assert resolve_account("acct-aaaa") == "acct-aaaa"
    assert resolve_account("acct-bbbb") == "acct-bbbb"
    assert account.ACCOUNT_RE.match("acct-aaaa")
    assert account.ACCOUNT_RE.match("acct-bbbb")
