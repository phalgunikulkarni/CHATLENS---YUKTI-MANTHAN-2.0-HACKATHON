"""Verification script for the ChatLens image dataset scanner (Phase 2).

Runs the scanner against the developer-supplied test dataset and checks:
  - the expected images are discovered,
  - hidden/system files (.DS_Store) are ignored,
  - categories are detected from the immediate parent folder,
  - image ids are stable and unique,
  - no image files are modified (verified via pre/post mtime + size snapshot).

Read-only: this script does not write to, move, or modify any dataset file.
Exits non-zero if any check fails.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the scanner importable whether run as a module or a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.ingestion.scanner import SUPPORTED_EXTENSIONS, scan_dataset  # noqa: E402

DATASET = "data/test_dataset"


def _snapshot(root: Path) -> dict[str, tuple[int, float]]:
    """Map every file path -> (size, mtime) to detect modification."""
    snap: dict[str, tuple[int, float]] = {}
    for cur, _dirs, files in os.walk(root):
        for f in files:
            p = Path(cur) / f
            try:
                st = p.stat()
                snap[str(p)] = (st.st_size, st.st_mtime)
            except OSError:
                pass
    return snap


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, passed: bool, detail: str = "") -> None:
        checks.append((name, passed, detail))

    root = Path(DATASET)
    if not root.is_dir():
        print(f"FAIL  dataset directory not found: {DATASET}")
        return 1

    before = _snapshot(root)
    result = scan_dataset(DATASET)
    after = _snapshot(root)

    # 1. Expected total discovered images.
    check(
        "30 images discovered",
        result.discovered_count == 30,
        f"got {result.discovered_count}",
    )

    # 2. Hidden files ignored: no .DS_Store in records; at least one ignored.
    ds_in_records = [r for r in result.records if r.filename == ".DS_Store"]
    ds_ignored = [p for p in result.ignored_files if p.endswith(".DS_Store")]
    check(".DS_Store not in records", not ds_in_records, f"{len(ds_in_records)} leaked")
    check(".DS_Store ignored", len(ds_ignored) >= 1, f"{len(ds_ignored)} ignored")

    # 3. No record has a hidden filename.
    hidden = [r for r in result.records if r.filename.startswith(".")]
    check("no hidden files in records", not hidden, f"{len(hidden)} hidden")

    # 4. Categories detected from folder names, with expected per-category counts.
    expected_categories = {
        "Visualimages": 5,
        "handwritten": 5,
        "lectureslides": 5,
        "memes": 5,
        "receipts": 5,
        "screenshots": 5,
    }
    actual_counts = result.category_counts()
    check(
        "categories + counts match",
        actual_counts == expected_categories,
        f"got {actual_counts}",
    )

    # 5. Every record has all four required fields populated.
    complete = all(
        r.image_id and r.file_path and r.filename and r.category
        for r in result.records
    )
    check("all records have id/path/filename/category", complete)

    # 6. Only supported extensions in records.
    bad_ext = [
        r.filename for r in result.records
        if Path(r.filename).suffix.lower() not in SUPPORTED_EXTENSIONS
    ]
    check("only supported extensions", not bad_ext, f"bad: {bad_ext}")

    # 7. Image ids are unique.
    ids = [r.image_id for r in result.records]
    check("image ids unique", len(ids) == len(set(ids)), f"{len(ids)} vs {len(set(ids))}")

    # 8. Image ids are stable across a second scan.
    result2 = scan_dataset(DATASET)
    ids2 = {r.file_path: r.image_id for r in result2.records}
    stable = all(ids2.get(r.file_path) == r.image_id for r in result.records)
    check("image ids stable across runs", stable)

    # 9. No files modified (size + mtime unchanged, no additions/deletions).
    check("no files modified", before == after,
          "snapshot differs" if before != after else "")

    # 10. Missing-directory error path.
    raised = False
    try:
        scan_dataset("data/__does_not_exist__")
    except NotADirectoryError:
        raised = True
    check("missing dir raises NotADirectoryError", raised)

    # Report
    print(f"Dataset: {result.dataset_path}")
    print(f"Discovered: {result.discovered_count} | Ignored: {result.ignored_count}")
    print(f"Categories: {result.category_counts()}")
    print("-" * 60)
    all_ok = True
    for name, passed, detail in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_ok = False
        suffix = f"  ({detail})" if detail else ""
        print(f"{status}  {name}{suffix}")
    print("-" * 60)
    if all_ok:
        print("OVERALL: SUCCESS - scanner verified against the 30-image test dataset.")
        return 0
    print("OVERALL: FAILURE - one or more scanner checks failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
