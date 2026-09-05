"""Local-folder access -> indexing bridge (backend side).

This is the ONLY new backend module that imports ml.* for ingestion/indexing.
It isolates the ml dependency (native folder picker, LibraryIndexer,
FolderWatcher) behind a small, thread-safe public API consumed by main.py.

Design principles (aligned with docs/CHATLENS_MASTER.md and AGENTS.md):
  - Local folder access is an INPUT/SOURCE mechanism, not the core product.
  - Reuse the existing ml/ components EXACTLY; never duplicate scanning,
    OCR/CLIP/text-embedding, ChromaDB, or retrieval logic here.
  - Never fabricate state. Report honest authorization/indexing status.
  - Errors are handled explicitly and are non-fatal to the API layer.
"""

import os
import sys
import json
import threading
from typing import List, Dict, Any

# Put the project root (parent of backend/) on sys.path so `import ml...`
# resolves regardless of the current working directory. Mirrors ml_retrieval.py.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Persisted authorization file (server-side access state). Git-ignored.
_STORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "authorized_locations.json")


# ---------------------------------------------------------------------------
# Account-keyed state (Phase D). Thread-safe via _lock.
#
# Phase D (task 4) converts the former process-global singleton into per-account
# maps keyed by account_id, guarded by the existing _lock. The LibraryIndexer is
# stateless and remains a single shared instance (safe to share across accounts).
#
# LIMITATION (documented): the watcher is NOT yet account-aware — its on_batch
# still calls the shared indexer without account attribution (that is Task 6).
# Phase D only keys the *tracking* of watchers/threads by account so one
# account's start/stop cannot clobber another account's state. Per-account
# authorization PERSISTENCE (account-keyed authorized_locations.json) is Task 8;
# Phase D keeps per-account state in-memory and leaves the legacy global file
# read/write behavior unchanged.
# ---------------------------------------------------------------------------
_lock = threading.Lock()

# account_id -> {authorized, indexing, roots, indexedCount, error}
_states: Dict[str, Dict[str, Any]] = {}

# account_id -> FolderWatcher / threading.Thread (tracked per account so one
# account's lifecycle cannot clobber another's).
_watchers: Dict[str, Any] = {}
_index_threads: Dict[str, threading.Thread] = {}

_indexer = None             # single shared, stateless LibraryIndexer

# Legacy error sink. `_scoped_roots` / `_validate_roots` are kept byte-for-byte
# UNCHANGED per the Phase D spec; their exception paths write a diagnostic into
# `_state["error"]`. Since those two helpers are account-agnostic (they only
# derive/validate the shared four-folder allowlist), their error diagnostics are
# not account-scoped. This shared, non-account dict absorbs those writes without
# affecting any per-account state in `_states`.
_state: Dict[str, Any] = {"error": None}


def _default_state() -> Dict[str, Any]:
    """A fresh, idle per-account state dict."""
    return {
        "authorized": False,
        "indexing": "idle",     # idle | running | ready | failed
        "roots": [],            # validated absolute roots
        "indexedCount": 0,      # visual_indexed from last index (or stats)
        "error": None,
    }


def _state_for(account_id: str) -> Dict[str, Any]:
    """Get-or-create the per-account state dict. MUST be called under _lock."""
    st = _states.get(account_id)
    if st is None:
        st = _default_state()
        _states[account_id] = st
    return st


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_indexer():
    """Lazily construct the single shared LibraryIndexer.

    On import/construct failure, returns None. The indexer is stateless and safe
    to share across accounts; per-account attribution of indexing is Task 5/6.
    """
    global _indexer
    if _indexer is not None:
        return _indexer
    try:
        from ml.pipeline.indexer import LibraryIndexer
        _indexer = LibraryIndexer()
        return _indexer
    except Exception as exc:  # noqa: BLE001 - adapter must be robust
        print(f"[access] indexer unavailable: {exc!r}")
        return None


def _load_persisted() -> List[str]:
    """Read persisted roots from _STORE. Returns [] on any error."""
    try:
        with open(_STORE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        roots = data.get("roots", [])
        if isinstance(roots, list):
            return [str(r) for r in roots]
        return []
    except Exception:  # noqa: BLE001 - missing/corrupt file is non-fatal
        return []


def _save_persisted(roots: List[str]) -> None:
    """Write {"roots": roots} to _STORE. Ignore write errors (log via print)."""
    try:
        with open(_STORE, "w", encoding="utf-8") as fh:
            json.dump({"roots": roots}, fh)
    except Exception as exc:  # noqa: BLE001
        print(f"[access] failed to persist authorized locations: {exc!r}")


def _scoped_roots() -> List[str]:
    """The ONLY roots ChatLens may authorize: Desktop/Downloads/Documents/
    Pictures, resolved by the existing LocalImageAccess.default_user_scope()
    (which returns only existing, readable user-facing folders under the home
    directory, skipping missing ones). Returns realpaths."""
    try:
        from ml.filesystem.local_access import LocalImageAccess
        return [os.path.realpath(r) for r in (LocalImageAccess().default_user_scope() or [])]
    except Exception as exc:  # noqa: BLE001
        print(f"[access] scoped roots unavailable: {exc!r}")
        with _lock:
            _state["error"] = f"local access unavailable: {exc}"
        return []


def _validate_roots(paths: List[str]) -> List[str]:
    """Return only the subset of `paths` that are BOTH (a) members of the
    user-facing allowlist (default_user_scope) AND (b) OS-readable per the
    existing LocalImageAccess check.

    SECURITY / ORDER: the allowlist intersection is applied FIRST, using
    os.path.realpath on both the incoming candidates and the allowed roots.
    ingest_locations()/scan_dataset() is invoked ONLY on the already-allowed
    subset, so broad or arbitrary paths (C:\\, C:\\Users, home, AppData, the
    ChatLens repo, external drives, any other readable directory) are rejected
    BEFORE any recursive scanner call can run.
    """
    if not paths:
        return []

    # 1. Allowed roots from the existing scope helper, normalized.
    allowed = set(_scoped_roots())          # already realpath'd in _scoped_roots
    if not allowed:
        return []

    # 2. Normalize incoming candidates and INTERSECT with the allowlist FIRST.
    #    Nothing outside the allowlist proceeds to any scanner call.
    candidate_reals = []
    for p in paths:
        try:
            candidate_reals.append(os.path.realpath(p))
        except Exception:
            continue
    prefiltered = sorted(set(candidate_reals) & allowed)
    if not prefiltered:
        return []   # rejected before ingest_locations()/scan_dataset()

    # 3. ONLY NOW run the existing OS-readability validation, and only on the
    #    already-allowed subset (safe: these are the 4 user-facing roots).
    try:
        from ml.filesystem.local_access import LocalImageAccess, AccessResult
        batch = LocalImageAccess().ingest_locations(prefiltered)
        granted = set()
        for lr in batch.locations:
            if lr.access is AccessResult.GRANTED:
                try:
                    granted.add(os.path.realpath(lr.location))
                except Exception:
                    continue
    except Exception as exc:  # noqa: BLE001
        print(f"[access] validation failed: {exc!r}")
        with _lock:
            _state["error"] = f"validation failed: {exc}"
        return []

    # Final result: allowed AND granted (intersection already applied in step 2).
    return sorted(granted & set(prefiltered))


def get_status(account_id: str) -> dict:
    """Return a copy of ONLY the given account's access/indexing state.

    An account that has never granted access has no entry yet; we return a fresh
    idle default WITHOUT creating a persistent entry, so a pure status read never
    fabricates state for an unknown account.
    """
    with _lock:
        st = _states.get(account_id)
        return dict(st) if st is not None else _default_state()


# ---------------------------------------------------------------------------
# Background initial indexing (per-account)
# ---------------------------------------------------------------------------
def _run_initial_index(account_id: str, roots: List[str]) -> None:
    """Run the initial full (incremental/idempotent) index pass in background
    for a SINGLE account.

    Caller has already set that account's indexing="running". On success records
    the indexed count, flips ONLY this account's state to ready/authorized, and
    starts this account's watcher. On failure flips ONLY this account to failed
    and does NOT start its watcher. A failure here never touches any other
    account's state (R11.6).
    """
    idx = _get_indexer()
    if idx is None:
        with _lock:
            st = _state_for(account_id)
            st["indexing"] = "failed"
            st["error"] = "indexer unavailable"
            st["authorized"] = False
        return  # DO NOT start watcher when the indexer is unavailable
    try:
        report = idx.index_locations(roots, account_id=account_id)  # initial full pass (idempotent)
        # Prefer report.visual_indexed; fall back to visual count in stats.
        count = getattr(report, "visual_indexed", 0) or 0
        if not count:
            stats = getattr(report, "stats", None) or {}
            count = stats.get("visual") or stats.get("visual_count") or 0
        with _lock:
            st = _state_for(account_id)
            st["indexedCount"] = int(count)
            st["indexing"] = "ready"
            st["authorized"] = True
            st["error"] = None
        _start_watcher(account_id, roots)  # ONLY after a successful initial index
    except Exception as exc:  # noqa: BLE001
        print(f"[access] initial index failed for {account_id}: {exc!r}")
        with _lock:
            st = _state_for(account_id)
            st["indexing"] = "failed"
            st["error"] = str(exc)
            st["authorized"] = False
        # DO NOT start watcher on failure


# ---------------------------------------------------------------------------
# Watcher lifecycle (per-account tracking)
# ---------------------------------------------------------------------------
def _start_watcher(account_id: str, roots: List[str]) -> None:
    """Start a FolderWatcher for the given account's roots.

    Tracking is keyed by account_id in `_watchers` so one account's start/stop
    cannot clobber another account's watcher or state. Failure to start is
    non-fatal: this account's indexing is already ready.

    LIMITATION (Task 6): the watcher's on_batch is NOT yet account-aware — it
    calls the shared indexer without threading account_id. Making on_batch
    account-scoped is Task 6 (account-aware watcher) and is intentionally NOT
    done here.
    """
    with _lock:
        if _watchers.get(account_id) is not None:
            return  # avoid duplicate watchers for this account
    try:
        from ml.pipeline.watcher import FolderWatcher

        idx = _get_indexer()

        def on_batch(changed_roots):
            try:
                if idx is not None:
                    idx.index_locations(list(changed_roots), account_id=account_id)
            except Exception as exc:  # noqa: BLE001
                print(f"[access] watcher index failed: {exc}")

        def on_delete(paths):
            try:
                if idx is not None:
                    idx.remove_paths(paths, account_id=account_id)
            except Exception as exc:  # noqa: BLE001
                print(f"[access] watcher cleanup failed: {exc}")

        watcher = FolderWatcher(
            roots=roots,
            on_batch=on_batch,
            on_delete=on_delete,
            notify=lambda m: print(f"[access] {m}"),
        )
        watcher.start()
        with _lock:
            _watchers[account_id] = watcher
    except Exception as exc:  # noqa: BLE001 - non-fatal; indexing already ready
        print(f"[access] watcher start failed for {account_id}: {exc}")


def stop_watcher(account_id: str) -> None:
    """Stop and forget a single account's FolderWatcher if running."""
    with _lock:
        watcher = _watchers.pop(account_id, None)
    if watcher is not None:
        try:
            watcher.stop()
        except Exception as exc:  # noqa: BLE001
            print(f"[access] watcher stop failed for {account_id}: {exc}")


# ---------------------------------------------------------------------------
# Public API used by main.py
# ---------------------------------------------------------------------------
def grant_access(account_id: str) -> dict:
    """Authorize the user-facing image folders (Desktop/Downloads/Documents/
    Pictures) for a SINGLE account and start background indexing scoped to that
    account.

    Does NOT open a native picker and does NOT accept any path from the caller --
    the allowed roots are derived server-side from
    LocalImageAccess.default_user_scope() and re-validated against the allowlist
    (R11.2, R11.8, R11.9). authorized=True in the response means 'authorization
    accepted / indexing started'; the frontend polls /status for 'ready'. The
    call returns immediately without waiting for indexing (R11.5).

    Persistence: the legacy global authorized_locations.json write is preserved
    as-is (Task 8 introduces the account-keyed store). Per-account state here is
    authoritative in-memory for Phase D.
    """
    with _lock:
        st = _state_for(account_id)
        if st["indexing"] == "running":
            return dict(st)

    roots = _validate_roots(_scoped_roots())
    if not roots:
        with _lock:
            st = _state_for(account_id)
            st["error"] = "No accessible image folders (Desktop, Downloads, Documents, Pictures) were found to authorize."
        return {
            "authorized": False,
            "roots": [],
            "message": "No accessible image folders were found to authorize.",
        }

    # Preserve the existing global-file write behavior AS-IS (account-keyed
    # persistence is Task 8). This does not affect per-account in-memory state.
    _save_persisted(roots)
    with _lock:
        st = _state_for(account_id)
        st["roots"] = roots
        st["indexing"] = "running"
        st["error"] = None
        st["authorized"] = False  # becomes True once initial index succeeds

    thread = _spawn_index_thread(account_id, roots)
    with _lock:
        _index_threads[account_id] = thread
    thread.start()

    return {
        "authorized": True,  # authorization accepted / indexing started
        "roots": roots,
        "message": "Authorized your image folders. Indexing started.",
    }


def _spawn_index_thread(account_id: str, roots: List[str]) -> threading.Thread:
    """Create (but do not start) the per-account daemon index thread.

    Isolated into its own function so tests can monkeypatch it to run the index
    step inline/deterministically WITHOUT changing production async behavior.
    """
    return threading.Thread(
        target=_run_initial_index, args=(account_id, roots), daemon=True
    )


def restore_on_startup() -> None:
    """Restore persisted authorization on startup.

    Phase D LIMITATION: per-account authorization persistence is Task 8. The
    legacy authorized_locations.json holds a single UNATTRIBUTED global
    ``{"roots": [...]}`` that cannot be safely attributed to any specific
    account (R12.5 forbids fabricating an owner). Therefore Phase D restores
    NOTHING per-account here: it neither leaks the legacy global roots into a
    specific account's state nor crashes. The account-keyed loader and
    per-account watcher restart land in Task 8 (and Task 6 for account-aware
    watching). This function is intentionally a safe no-op for Phase D.
    """
    return


def shutdown() -> None:
    """Stop ALL tracked per-account watchers on server shutdown."""
    with _lock:
        account_ids = list(_watchers.keys())
    for account_id in account_ids:
        stop_watcher(account_id)
