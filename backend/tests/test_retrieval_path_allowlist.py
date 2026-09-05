"""Positive path-allowlist tests for the retrieval/serving layer (ml_retrieval).

ChatLens may only surface images whose RESOLVED filesystem path is inside one of
the four user folders (Desktop/Downloads/Documents/Pictures), derived from
Path.home(). Enforcement is by resolved/canonical path prefix ONLY — never by
folder name. These tests exercise the boundary helper directly (offline; no
Chroma/model needed). Run:
    python tests/test_retrieval_path_allowlist.py
"""
from __future__ import annotations

import os, sys, traceback
from pathlib import Path

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import ml_retrieval as m

HOME = Path.home()


def test_allowed_roots_are_the_four_user_folders():
    roots = set(m._allowed_roots())
    expected = {os.path.realpath(str(HOME / n)) for n in ("Desktop", "Downloads", "Documents", "Pictures")}
    assert roots == expected, (roots, expected)


def test_paths_inside_allowed_folders_are_allowed():
    for name in ("Desktop", "Downloads", "Documents", "Pictures"):
        assert m._path_in_allowlist(str(HOME / name / "image.jpg")) is True
    # nested paths too
    assert m._path_in_allowlist(str(HOME / "Downloads" / "a" / "b" / "c.png")) is True


def test_paths_outside_allowed_folders_are_rejected():
    assert m._path_in_allowlist(str(HOME / "project" / "data" / "image.jpg")) is False
    assert m._path_in_allowlist(str(HOME / "project" / "data" / "dataset1" / "image.jpg")) is False
    assert m._path_in_allowlist(str(HOME / "assets" / "image.jpg")) is False
    assert m._path_in_allowlist(str(HOME / "anything-else" / "image.jpg")) is False


def test_boundary_is_path_based_not_name_prefix():
    # "Desktopics" must NOT be treated as inside "Desktop".
    assert m._path_in_allowlist(str(HOME / "Desktopics" / "x.jpg")) is False
    # A sibling that merely starts with an allowed name string.
    assert m._path_in_allowlist(str(HOME / "Documents_backup" / "x.jpg")) is False


def test_project_relative_dataset_path_is_rejected():
    # Legacy records store project-root-relative dataset paths; must be rejected.
    assert m._path_in_allowlist("Data/dataset1/Reciepts/IMG.jpg") is False
    assert m._path_in_allowlist("data/dataset1/x.png") is False


def test_missing_path_is_not_allowed():
    assert m._path_in_allowlist(None) is False
    assert m._path_in_allowlist("") is False
    assert m._record_allowed({}) is False
    assert m._record_allowed({"absolute_path": str(HOME / "Desktop" / "ok.jpg")}) is True
    assert m._record_allowed({"file_path": "data/dataset1/x.jpg"}) is False


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t(); print(f"PASS {t.__name__}"); passed += 1
        except Exception:
            print(f"FAIL {t.__name__}"); traceback.print_exc(); failed += 1
    print(f"retrieval_path_allowlist: {passed} passed, {failed} failed, {passed+failed} total")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if _run() else 1)
