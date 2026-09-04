"""Property 13 — server-derived, scope-limited roots.

Feature: account-scoped-chat-and-isolation (Phase D, task 4.7).

**Property 13: Server-derived, scope-limited roots**
**Validates: Requirements R11.2, R11.8, R11.9, R15.5, R15.6**

For all grant requests, the authorized roots are derived server-side from
Scoped_Roots (Desktop/Downloads/Documents/Pictures under the OS home) and any
candidate resolving outside that allowlist is rejected, regardless of any
caller-supplied value.

This exercises the REAL, unchanged `_scoped_roots` / `_validate_roots`. No real
indexing runs: `_validate_roots` only intersects with the four-folder allowlist
first and then runs a readability check on that already-allowed subset — it never
triggers the recursive scanner/CLIP/OCR.
"""

import os

from hypothesis import given, settings, strategies as st

import access_service


ALLOWLIST = set(access_service._scoped_roots())  # the real four-folder scope


def test_scoped_roots_are_within_default_user_scope():
    """_scoped_roots must equal default_user_scope realpaths (allowlist source)."""
    from ml.filesystem.local_access import LocalImageAccess

    expected = {os.path.realpath(r) for r in (LocalImageAccess().default_user_scope() or [])}
    assert set(access_service._scoped_roots()) == expected


def test_grant_derives_roots_only_from_scoped_roots(monkeypatch):
    """grant_access ignores everything except server-derived scoped roots.

    We spy on _validate_roots to prove it is called with exactly _scoped_roots()
    (never any caller value), and stub the index thread so nothing runs.
    """
    seen = {}

    real_scoped = access_service._scoped_roots()
    monkeypatch.setattr(access_service, "_scoped_roots", lambda: list(real_scoped))

    def spy_validate(paths):
        seen["paths"] = list(paths)
        return list(real_scoped)  # pretend all scoped roots are readable

    monkeypatch.setattr(access_service, "_validate_roots", spy_validate)
    monkeypatch.setattr(access_service, "_save_persisted", lambda roots: None)
    # Never actually spawn/run indexing.
    monkeypatch.setattr(access_service, "_spawn_index_thread",
                        lambda acct, roots: type("_T", (), {"start": lambda self: None})())
    monkeypatch.setattr(access_service, "_states", {}, raising=True)
    monkeypatch.setattr(access_service, "_index_threads", {}, raising=True)

    access_service.grant_access("acct-cafe")
    # The ONLY thing handed to validation is the server-derived scope.
    assert seen["paths"] == list(real_scoped)


# Candidate paths that must NEVER be authorized (outside the allowlist).
out_of_scope = st.sampled_from([
    "C:\\",
    "C:\\Users",
    "C:\\Windows",
    "C:\\Users\\Public",
    os.path.expanduser("~"),
    os.path.join(os.path.expanduser("~"), "AppData"),
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # the repo/backend
    "/",
    "/etc",
    "/tmp",
    "relative/path",
    "..",
])


@settings(max_examples=150, deadline=None)
@given(bad=out_of_scope)
def test_arbitrary_caller_paths_are_rejected(bad):
    """No caller-supplied path outside Scoped_Roots ever survives validation.

    _validate_roots intersects with the allowlist FIRST, so any path that does
    not realpath-match one of the four scoped roots is dropped before any
    scanner/readability call.
    """
    result = access_service._validate_roots([bad])
    assert all(r in ALLOWLIST for r in result)
    # A path that is not one of the four scoped roots contributes nothing.
    if os.path.realpath(bad) not in ALLOWLIST:
        assert result == []


@settings(max_examples=100, deadline=None)
@given(bad=out_of_scope)
def test_mixing_bad_paths_with_scoped_roots_still_limited(bad):
    """Even mixed with the real scoped roots, only allowlisted roots survive."""
    candidates = list(access_service._scoped_roots()) + [bad]
    result = access_service._validate_roots(candidates)
    # Every surviving root is in the allowlist; the bad path never leaks in.
    assert all(r in ALLOWLIST for r in result)
    assert os.path.realpath(bad) not in result or os.path.realpath(bad) in ALLOWLIST
