"""Automatic image synchronization / filesystem watcher for ChatLens.

This is an EVENT/TRIGGER layer only. It watches the already-approved folders and,
when an eligible static image appears or changes, it calls the EXISTING indexing
pipeline for those roots. It contains no OCR/CLIP/text-embedding/ChromaDB/
retrieval logic and reuses:

  - LocalImageAccess.default_user_scope()  -> the approved watch roots
  - is_static_image_file()                 -> the existing eligibility policy
  - LibraryIndexer.index_locations()       -> existing incremental (fingerprint)
                                              indexing; only new/changed images
                                              are (re)processed, never the whole
                                              library.

Backends:
  - Preferred: `watchdog` (cross-platform: FSEvents on macOS,
    ReadDirectoryChangesW on Windows) if installed.
  - Fallback: a lightweight periodic re-scan (mtime/size snapshot) when watchdog
    is unavailable. The fallback still relies on the indexer's fingerprint logic
    so nothing is re-embedded unnecessarily.

Design points:
  - Single worker thread + queue: batched, controlled processing (never N
    parallel pipelines).
  - Debounce/coalesce duplicate events per path.
  - File-stability wait (size stable across a short interval) so partially
    written downloads are not processed early.
  - Runs concurrently with the query loop; watcher errors never crash the app.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from queue import Queue, Empty
from typing import Callable, Iterable, List, Optional, Set

# Debounce window: collect rapid repeated events for the same file before acting.
DEFAULT_DEBOUNCE_SECONDS = 1.5
# File-stability: size must be unchanged across this interval before processing.
DEFAULT_STABILITY_INTERVAL = 0.6
DEFAULT_STABILITY_RETRIES = 8
# Polling fallback interval (only used when watchdog is unavailable).
DEFAULT_POLL_INTERVAL = 5.0


def _default_eligibility(path: str) -> bool:
    """Reuse the EXISTING static-image policy (no second validation system)."""
    from ml.filesystem.local_access import is_static_image_file
    return is_static_image_file(path)


class FolderWatcher:
    """Watches approved roots and triggers the existing indexer for changes.

    Parameters
    ----------
    roots : list[str]
        Approved watch roots (must come from LocalImageAccess.default_user_scope()).
        on_batch : callable(list[str]) -> None
        Called with a list of approved roots that had eligible changes; the
        callback is expected to invoke the existing LibraryIndexer.index_locations
        on them (incremental). Provided by the harness so this layer stays free
        of ML imports.
        on_delete : callable(list[str]) -> None, optional
            Called with filesystem paths that disappeared from approved roots.
    is_eligible : callable(str) -> bool
        Eligibility predicate (defaults to the existing static-image policy).
    notify : callable(str) -> None, optional
        Lightweight user feedback sink (defaults to print).
    """

    def __init__(
        self,
        roots: Iterable[str],
        on_batch: Callable[[List[str]], None],
        on_delete: Optional[Callable[[List[str]], None]] = None,
        is_eligible: Callable[[str], bool] = _default_eligibility,
        notify: Optional[Callable[[str], None]] = None,
        debounce_seconds: float = DEFAULT_DEBOUNCE_SECONDS,
        stability_interval: float = DEFAULT_STABILITY_INTERVAL,
        stability_retries: int = DEFAULT_STABILITY_RETRIES,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        # Normalize to realpaths: macOS FSEvents reports realpath'd paths
        # (e.g. /var/... -> /private/var/...), so roots must match that form.
        self.roots = [os.path.realpath(str(Path(r))) for r in roots]
        self._on_batch = on_batch
        self._on_delete = on_delete or (lambda paths: None)
        self._is_eligible = is_eligible
        self._notify = notify or (lambda msg: print(msg))
        self.debounce_seconds = debounce_seconds
        self.stability_interval = stability_interval
        self.stability_retries = stability_retries
        self.poll_interval = poll_interval

        self._queue: "Queue[str]" = Queue()
        self._pending: Set[str] = set()
        self._pending_lock = threading.Lock()
        self._stop = threading.Event()
        self._worker: Optional[threading.Thread] = None
        self._observer = None            # watchdog observer, if used
        self._poll_thread: Optional[threading.Thread] = None
        self._snapshot: dict[str, tuple[int, float]] = {}
        self.backend = "none"

    # -- lifecycle ------------------------------------------------------------

    def start(self) -> None:
        """Begin watching. Safe no-op if there are no roots."""
        if not self.roots:
            return
        self._stop.clear()
        self._worker = threading.Thread(target=self._worker_loop, name="chatlens-sync", daemon=True)
        self._worker.start()
        if not self._start_watchdog():
            self._start_polling()

    def stop(self) -> None:
        self._stop.set()
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception:
                pass
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=5)
        if self._worker is not None:
            self._worker.join(timeout=5)

    # -- watchdog backend -----------------------------------------------------

    def _start_watchdog(self) -> bool:
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except Exception:
            return False

        watcher = self

        class _Handler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory:
                    watcher._enqueue_path(event.src_path)

            def on_modified(self, event):
                if not event.is_directory:
                    watcher._enqueue_path(event.src_path)

            def on_moved(self, event):
                dest = getattr(event, "dest_path", None)
                if dest and not event.is_directory:
                    watcher._enqueue_path(dest)

            def on_deleted(self, event):
                if not event.is_directory:
                    watcher._enqueue_deleted(event.src_path)

        try:
            self._observer = Observer()
            for root in self.roots:
                if Path(root).is_dir():
                    self._observer.schedule(_Handler(), root, recursive=True)
            self._observer.start()
            self.backend = "watchdog"
            return True
        except Exception:
            self._observer = None
            return False

    # -- polling fallback -----------------------------------------------------

    def _start_polling(self) -> None:
        self.backend = "polling"
        self._snapshot = self._scan_snapshot()  # baseline: existing files ignored
        self._poll_thread = threading.Thread(target=self._poll_loop, name="chatlens-poll", daemon=True)
        self._poll_thread.start()

    def _scan_snapshot(self) -> dict[str, tuple[int, float]]:
        snap: dict[str, tuple[int, float]] = {}
        for root in self.roots:
            for cur, dnames, fnames in os.walk(root):
                dnames[:] = [d for d in dnames if not d.startswith(".")]
                for f in fnames:
                    if f.startswith("."):
                        continue
                    p = os.path.join(cur, f)
                    try:
                        st = os.stat(p)
                        snap[p] = (st.st_size, st.st_mtime)
                    except OSError:
                        pass
        return snap

    def _poll_loop(self) -> None:
        while not self._stop.wait(self.poll_interval):
            try:
                current = self._scan_snapshot()
                deleted = set(self._snapshot) - set(current)
                if deleted:
                    self._on_delete(sorted(deleted))
                for path, sig in current.items():
                    if self._snapshot.get(path) != sig:
                        self._enqueue_path(path)
                self._snapshot = current
            except Exception:
                # Never let the poll loop crash the process.
                continue

    # -- event intake + worker ------------------------------------------------

    def _enqueue_path(self, path: str) -> None:
        """Filter to eligible images, debounce duplicates, queue for processing."""
        try:
            ext_ok = Path(path).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
            if not ext_ok:
                return  # ignore non-image events quietly (no noisy logs)
            with self._pending_lock:
                if path in self._pending:
                    return  # already queued -> coalesce duplicate events
                self._pending.add(path)
            self._queue.put(path)
        except Exception:
            return

    def _enqueue_deleted(self, path: str) -> None:
        try:
            if Path(path).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                self._on_delete([path])
        except Exception:
            return

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                path = self._queue.get(timeout=0.5)
            except Empty:
                continue
            try:
                # Debounce: let a burst of events for this file settle.
                time.sleep(self.debounce_seconds)
                # Drain any other queued paths that arrived in the meantime so we
                # can process them as one batch (controlled, not N pipelines).
                batch_paths = [path]
                while True:
                    try:
                        batch_paths.append(self._queue.get_nowait())
                    except Empty:
                        break
                self._process_batch(batch_paths)
            except Exception as exc:
                # A failure on one batch must not kill the watcher.
                try:
                    self._notify(f"[sync] error while indexing: {exc}")
                except Exception:
                    pass
            finally:
                with self._pending_lock:
                    for bp in set([path]) | set(locals().get("batch_paths", [])):
                        self._pending.discard(bp)

    def _process_batch(self, paths: List[str]) -> None:
        # Keep only files that are stable and pass the EXISTING eligibility check.
        eligible_roots: Set[str] = set()
        processed_any = False
        for p in dict.fromkeys(paths):  # dedupe, preserve order
            if not self._wait_for_stable(p):
                continue
            if not self._is_eligible(p):
                continue  # non-static / animated / unreadable -> skip silently
            root = self._root_for(p)
            if root:
                eligible_roots.add(root)
                processed_any = True
                self._notify(f"New image detected: {Path(p).name}")
        if not eligible_roots:
            return
        self._notify("Indexing...")
        # Reuse the EXISTING incremental indexer via the harness callback. It
        # fingerprints and processes ONLY new/changed images in these roots.
        self._on_batch(sorted(eligible_roots))
        if processed_any:
            self._notify("Image indexed and now searchable.")

    def _root_for(self, path: str) -> Optional[str]:
        """Return the approved root that contains ``path`` (scope boundary)."""
        rp = os.path.realpath(path)
        for root in self.roots:
            ra = os.path.realpath(root)
            if rp == ra or rp.startswith(ra + os.sep):
                return root
        return None

    def _wait_for_stable(self, path: str) -> bool:
        """Wait until the file exists, is readable, and size is stable."""
        last = -1
        stable_hits = 0
        for _ in range(self.stability_retries):
            if self._stop.is_set():
                return False
            try:
                if not os.path.isfile(path) or not os.access(path, os.R_OK):
                    return False
                size = os.path.getsize(path)
            except OSError:
                return False
            if size == last and size > 0:
                stable_hits += 1
                if stable_hits >= 1:
                    return True
            else:
                stable_hits = 0
                last = size
            time.sleep(self.stability_interval)
        # Final check: readable and non-empty.
        try:
            return os.path.isfile(path) and os.access(path, os.R_OK) and os.path.getsize(path) > 0
        except OSError:
            return False
