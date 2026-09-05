"""Tests for the automatic synchronization watcher (event/trigger layer).

Uses temporary directories and a MOCK on_batch callback (no real OCR/CLIP/
ChromaDB). Verifies detection, eligibility reuse, debounce, stability, batching,
and that watcher errors don't crash. Standard-library unittest.
"""
from __future__ import annotations

import struct
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402
from ml.pipeline.watcher import FolderWatcher  # noqa: E402
from ml.filesystem.local_access import is_static_image_file  # noqa: E402


def _static(p: Path, fmt=None):
    Image.new("RGB", (32, 32), (10, 20, 30)).save(p, format=fmt)


def _animated_webp(p: Path):
    def chunk(fourcc, payload):
        b = fourcc + struct.pack("<I", len(payload)) + payload
        return b + (b"\x00" if len(payload) % 2 else b"")
    body = (b"WEBP"
            + chunk(b"VP8X", bytes([0x02, 0, 0, 0]) + b"\x0f\x00\x00\x0f\x00\x00")
            + chunk(b"ANIM", b"\xff\xff\xff\xff\x00\x00")
            + chunk(b"ANMF", b"\x00" * 24))
    p.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)


class _Collector:
    """Mock on_batch: records the roots it was asked to (re)index."""
    def __init__(self):
        self.calls = []
        self.deleted = []
        self.paths_seen = []
        self.lock = threading.Lock()

    def __call__(self, roots):
        with self.lock:
            self.calls.append(list(roots))

    def on_delete(self, paths):
        with self.lock:
            self.deleted.extend(paths)


class WatcherTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="chatlens_watch_"))
        (self.tmp / "Pictures" / "nested").mkdir(parents=True)
        (self.tmp / "Downloads").mkdir()
        self.roots = [str(self.tmp / "Pictures"), str(self.tmp / "Downloads")]
        self.collector = _Collector()
        # Short timings for fast tests.
        self.w = FolderWatcher(
            roots=self.roots, on_batch=self.collector,
            on_delete=self.collector.on_delete,
            is_eligible=is_static_image_file,
            notify=lambda m: None,
            debounce_seconds=0.3, stability_interval=0.1,
            stability_retries=6, poll_interval=0.5,
        )
        self.w.start()
        time.sleep(0.4)  # let backend spin up

    def tearDown(self):
        self.w.stop()
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _wait_for_calls(self, timeout=6.0):
        end = time.time() + timeout
        while time.time() < end:
            if self.collector.calls:
                return True
            time.sleep(0.1)
        return False

    def test_new_jpg_triggers(self):
        _static(self.tmp / "Pictures" / "a.jpg", "JPEG")
        self.assertTrue(self._wait_for_calls(), "new jpg should trigger indexing")

    def test_new_png_and_nested(self):
        _static(self.tmp / "Pictures" / "nested" / "n.png", "PNG")
        self.assertTrue(self._wait_for_calls(), "nested png should be detected")

    def test_deleted_image_triggers_cleanup_callback(self):
        path = self.tmp / "Pictures" / "removed.jpg"
        _static(path, "JPEG")
        self.assertTrue(self._wait_for_calls(), "image should be indexed before deletion")
        self.collector.deleted.clear()
        path.unlink()
        end = time.time() + 6.0
        while time.time() < end and str(path) not in self.collector.deleted:
            time.sleep(0.1)
        self.assertIn(str(path), self.collector.deleted)

    def test_already_deleted_path_is_safe(self):
        missing = self.tmp / "Pictures" / "already-gone.jpg"
        self.w._enqueue_deleted(str(missing))
        self.assertEqual(self.collector.deleted, [str(missing)])

    def test_static_webp_triggers(self):
        _static(self.tmp / "Downloads" / "s.webp", "WEBP")
        self.assertTrue(self._wait_for_calls(), "static webp should trigger")

    def test_animated_webp_does_not_trigger(self):
        _animated_webp(self.tmp / "Downloads" / "anim.webp")
        self.assertFalse(self._wait_for_calls(timeout=3.0),
                         "animated webp must NOT trigger indexing")

    def test_non_image_does_not_trigger(self):
        for name in ("doc.pdf", "n.txt", "v.mp4", "a.mp3", "d.docx"):
            (self.tmp / "Downloads" / name).write_bytes(b"x")
        self.assertFalse(self._wait_for_calls(timeout=3.0),
                         "non-image files must NOT trigger indexing")

    def test_duplicate_events_coalesced(self):
        p = self.tmp / "Pictures" / "dup.jpg"
        _static(p, "JPEG")
        for _ in range(4):  # simulate repeated MODIFY
            with open(p, "ab") as fh:
                fh.flush()
            time.sleep(0.05)
        self.assertTrue(self._wait_for_calls())
        time.sleep(1.0)
        # A single logical file should not explode into many index calls.
        self.assertLessEqual(len(self.collector.calls), 2,
                             f"duplicate events should coalesce, got {len(self.collector.calls)}")

    def test_multiple_new_files_batched(self):
        for i in range(6):
            _static(self.tmp / "Downloads" / f"m{i}.jpg", "JPEG")
        self.assertTrue(self._wait_for_calls())
        time.sleep(1.0)
        # Should not spawn one call per file.
        self.assertLess(len(self.collector.calls), 6)

    def test_callback_error_does_not_crash(self):
        # Drive the worker deterministically (avoid a 2nd live FSEvents observer
        # on overlapping paths, which is racy). Enqueue a real file directly.
        boom = _Collector()
        raised = threading.Event()
        def raising(roots):
            boom.calls.append(roots)
            raised.set()
            raise RuntimeError("boom")
        w2 = FolderWatcher(roots=self.roots, on_batch=raising,
                           is_eligible=is_static_image_file, notify=lambda m: None,
                           debounce_seconds=0.1, stability_interval=0.05)
        # Start only the worker thread; feed it a path directly.
        w2._stop.clear()
        import threading as _t
        w2._worker = _t.Thread(target=w2._worker_loop, daemon=True); w2._worker.start()
        try:
            f = self.tmp / "Pictures" / "err.jpg"
            _static(f, "JPEG")
            w2._enqueue_path(str(f))
            self.assertTrue(raised.wait(timeout=5), "callback should have been invoked")
            # Worker must survive the exception and process a second file.
            boom.calls.clear(); raised.clear()
            f2 = self.tmp / "Pictures" / "again.jpg"
            _static(f2, "JPEG")
            w2._enqueue_path(str(f2))
            self.assertTrue(raised.wait(timeout=5),
                            "worker should survive an exception and keep processing")
        finally:
            w2.stop()


class WatcherNoRootsTest(unittest.TestCase):
    def test_no_roots_is_safe_noop(self):
        called = []
        w = FolderWatcher(roots=[], on_batch=lambda r: called.append(r),
                          notify=lambda m: None)
        w.start()  # should be a no-op
        w.stop()
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
