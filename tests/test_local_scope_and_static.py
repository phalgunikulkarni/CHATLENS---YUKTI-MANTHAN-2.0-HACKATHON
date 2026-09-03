"""Tests for local-image scope (allowlist roots) and static-image eligibility.

Isolated: uses only temporary directories; never touches real user images or the
real ChromaDB. Standard-library unittest (no extra deps).
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402
from ml.filesystem.local_access import (  # noqa: E402
    LocalImageAccess, is_static_image_file, STATIC_IMAGE_EXTENSIONS,
)


def _static(p: Path, fmt=None):
    Image.new("RGB", (32, 32), (200, 50, 50)).save(p, format=fmt)


def _animated_webp(p: Path):
    """Write a minimal but genuinely ANIMATED WebP via raw RIFF bytes.

    Pillow builds without webp-animation support silently write a static file,
    so we construct the container directly: VP8X with the animation flag set
    plus ANIM/ANMF chunks. This is what the detector must reject.
    """
    import struct

    def chunk(fourcc, payload):
        b = fourcc + struct.pack("<I", len(payload)) + payload
        if len(payload) % 2:
            b += b"\x00"
        return b

    vp8x = chunk(b"VP8X", bytes([0x02, 0, 0, 0]) + b"\x0f\x00\x00\x0f\x00\x00")
    anim = chunk(b"ANIM", b"\xff\xff\xff\xff\x00\x00")
    anmf = chunk(b"ANMF", b"\x00" * 24)
    body = b"WEBP" + vp8x + anim + anmf
    p.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)


def _touch(p: Path, data=b"x"):
    p.write_bytes(data)


class TestStaticEligibility(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="chatlens_elig_")
        self.d = Path(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_static_jpg_png_accepted(self):  # TEST 16
        for name, fmt in [("a.jpg", "JPEG"), ("b.jpeg", "JPEG"), ("c.png", "PNG")]:
            _static(self.d / name, fmt)
            self.assertTrue(is_static_image_file(self.d / name), name)

    def test_static_webp_accepted(self):  # TEST 15
        _static(self.d / "s.webp", "WEBP")
        self.assertTrue(is_static_image_file(self.d / "s.webp"))

    def test_animated_webp_rejected(self):  # TEST 14
        _animated_webp(self.d / "anim.webp")
        self.assertFalse(is_static_image_file(self.d / "anim.webp"))

    def test_gif_rejected(self):  # TEST 13
        _static(self.d / "g.gif", "GIF")
        self.assertFalse(is_static_image_file(self.d / "g.gif"))

    def test_non_image_formats_rejected(self):  # TEST 6-12
        for name in ["doc.pdf", "n.txt", "d.doc", "d.docx", "p.ppt", "p.pptx",
                     "x.xls", "x.xlsx", "c.csv", "v.mp4", "v.mov", "v.avi",
                     "v.mkv", "v.webm", "a.mp3", "a.wav", "z.zip"]:
            _touch(self.d / name)
            self.assertFalse(is_static_image_file(self.d / name), name)

    def test_cloud_only_or_missing_rejected(self):  # TEST 19
        self.assertFalse(is_static_image_file(self.d / "nonexistent.jpg"))

    def test_supported_extension_set(self):
        self.assertEqual(STATIC_IMAGE_EXTENSIONS,
                         frozenset({".jpg", ".jpeg", ".png", ".webp"}))


class TestScopeAndScan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="chatlens_home_")
        self.home = Path(self.tmp)
        (self.home / "Pictures" / "Vacation").mkdir(parents=True)
        (self.home / "Downloads").mkdir()
        (self.home / "Library" / "Caches").mkdir(parents=True)
        _static(self.home / "Pictures" / "top.jpg", "JPEG")
        _static(self.home / "Pictures" / "Vacation" / "beach.png", "PNG")
        _static(self.home / "Downloads" / "dl.jpg", "JPEG")
        _animated_webp(self.home / "Pictures" / "anim.webp")
        _touch(self.home / "Pictures" / "notes.pdf")
        _static(self.home / "Library" / "Caches" / "appicon.png", "PNG")
        _static(self.home / "loose.jpg", "JPEG")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _access_with_home(self):
        os.environ["HOME"] = str(self.home)
        os.environ["USERPROFILE"] = str(self.home)
        return LocalImageAccess()

    def test_scope_is_allowlist_not_home_or_library(self):  # TEST 3
        acc = self._access_with_home()
        roots = [Path(r).name for r in acc.default_user_scope()]
        self.assertIn("Pictures", roots)
        self.assertIn("Downloads", roots)
        self.assertNotIn("Library", roots)
        self.assertNotIn(self.home.name, roots)

    def test_approved_and_nested_scanned_static_only(self):  # TEST 1,2,15,16
        acc = self._access_with_home()
        batch = acc.ingest_locations(acc.default_user_scope())
        names = sorted(r.filename for r in batch.image_records)
        self.assertIn("top.jpg", names)
        self.assertIn("beach.png", names)
        self.assertIn("dl.jpg", names)

    def test_library_not_scanned(self):  # TEST 3
        acc = self._access_with_home()
        batch = acc.ingest_locations(acc.default_user_scope())
        paths = [r.file_path for r in batch.image_records]
        self.assertFalse(any("Library" in p for p in paths))
        self.assertFalse(any("appicon.png" in p for p in paths))

    def test_outside_root_ignored(self):  # TEST 5
        acc = self._access_with_home()
        batch = acc.ingest_locations(acc.default_user_scope())
        paths = [r.file_path for r in batch.image_records]
        self.assertFalse(any(p.endswith(os.sep + "loose.jpg") for p in paths))

    def test_animated_and_nonimage_skipped(self):  # TEST 6,13,14
        acc = self._access_with_home()
        batch = acc.ingest_locations(acc.default_user_scope())
        names = [r.filename for r in batch.image_records]
        self.assertNotIn("anim.webp", names)
        self.assertNotIn("notes.pdf", names)
        self.assertGreaterEqual(sum(l.animated_skipped for l in batch.locations), 1)

    def test_new_image_discovered_on_rescan(self):  # TEST 17
        acc = self._access_with_home()
        first = {r.filename for r in acc.ingest_locations(acc.default_user_scope()).image_records}
        _static(self.home / "Pictures" / "new_photo.jpg", "JPEG")
        second = {r.filename for r in acc.ingest_locations(acc.default_user_scope()).image_records}
        self.assertNotIn("new_photo.jpg", first)
        self.assertIn("new_photo.jpg", second)


if __name__ == "__main__":
    unittest.main(verbosity=2)
