"""Verification script for the ChatLens image dataset scanner (Phase 2).

Runs the scanner against a USER-PROVIDED dataset folder and checks, without
assuming any particular dataset shape:
  - the scanner discovers exactly the supported image files actually present
    (recursively, mirroring scanner.py's rules),
  - hidden/system files (e.g. .DS_Store) and hidden files are not in records,
  - categories are derived from the immediate parent folder,
  - every record has image_id, file_path, filename, and category,
  - only supported image extensions are included,
  - image ids are unique and stable across repeated scans,
  - scanning does not modify files (pre/post size+mtime snapshot),
  - a missing/invalid dataset path raises NotADirectoryError.

Usage:
    .venv/bin/python ml/ingestion/verify_scanner.py <dataset_path>

Read-only: this script does not write to, move, or modify any dataset file.
Exits non-zero if any check fails.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Make the scanner importable whether run as a module or a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.ingestion.scanner import SUPPORTED_EXTENSIONS, scan_dataset  # noqa: E402


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


def _expected_supported_images(root: Path) -> set[str]:
    """Independently enumerate the supported images the scanner should discover.

    Mirrors scanner.py's rules so the check is dynamic (no hardcoded counts):
      - recurse into subdirectories,
      - skip hidden directories and hidden files (names starting with "."),
      - match SUPPORTED_EXTENSIONS case-insensitively.
    Returns a set of file-path strings (as produced by Path(cur) / name).
    """
    expected: set[str] = set()
    for cur, dirnames, filenames in os.walk(root):
        # Prune hidden/system directories, matching the scanner.
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if name.startswith("."):
                continue
            if Path(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            expected.add(str(Path(cur) / name))
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the ChatLens image scanner against a user-provided dataset."
    )
    parser.add_argument("dataset_path", help="Path to the dataset directory to verify.")
    args = parser.parse_args()

    checks: list[tuple[str, bool, str]] = []

    def check(name: str, passed: bool, detail: str = "") -> None:
        checks.append((name, passed, detail))

    root = Path(args.dataset_path)
    if not root.is_dir():
        print(f"FAIL  dataset directory not found: {args.dataset_path}")
        return 1

    before = _snapshot(root)
    result = scan_dataset(args.dataset_path)
    after = _snapshot(root)

    # 1. The scanner discovers exactly the supported images actually present.
    #    Dynamic: compare against an independent walk instead of a fixed count.
    expected_paths = _expected_supported_images(root)
    discovered_paths = {r.file_path for r in result.records}
    missing = expected_paths - discovered_paths
    extra = discovered_paths - expected_paths
    check(
        "discovers all supported images present",
        not missing and not extra,
        f"missing={len(missing)} extra={len(extra)}",
    )
    # Sanity: discovered_count matches the number of records.
    check(
        "discovered_count matches records",
        result.discovered_count == len(result.records),
        f"count={result.discovered_count} records={len(result.records)}",
    )

    # 2. Hidden/system files are not in records.
    ds_in_records = [r for r in result.records if r.filename == ".DS_Store"]
    check(".DS_Store not in records", not ds_in_records, f"{len(ds_in_records)} leaked")

    # 3. No record has a hidden filename.
    hidden = [r for r in result.records if r.filename.startswith(".")]
    check("no hidden files in records", not hidden, f"{len(hidden)} hidden")

    # 4. Categories derived from the immediate parent folder (dynamic).
    #    Every record has a category equal to its parent folder name, and the
    #    reported counts are consistent with the discovered records.
    missing_category = [r for r in result.records if not r.category]
    check("every record has a category", not missing_category,
          f"{len(missing_category)} missing")

    wrong_category = [
        r for r in result.records
        if r.category != Path(r.file_path).parent.name
    ]
    check("category equals immediate parent folder", not wrong_category,
          f"{len(wrong_category)} mismatched")

    derived_counts: dict[str, int] = {}
    for r in result.records:
        derived_counts[r.category] = derived_counts.get(r.category, 0) + 1
    check("category counts consistent with records",
          result.category_counts() == dict(sorted(derived_counts.items())),
          f"{result.category_counts()} vs {dict(sorted(derived_counts.items()))}")

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
    result2 = scan_dataset(args.dataset_path)
    ids2 = {r.file_path: r.image_id for r in result2.records}
    stable = all(ids2.get(r.file_path) == r.image_id for r in result.records)
    check("image ids stable across runs", stable)

    # 9. No files modified (size + mtime unchanged, no additions/deletions).
    check("no files modified", before == after,
          "snapshot differs" if before != after else "")

    # 10. Missing-directory error path (dataset-independent, guaranteed-nonexistent).
    raised = False
    missing_dir = root / "__does_not_exist__"
    try:
        scan_dataset(str(missing_dir))
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
        print(f"OVERALL: SUCCESS - scanner verified against '{result.dataset_path}' "
              f"({result.discovered_count} images, "
              f"{len(result.category_counts())} categories).")
        return 0
    print("OVERALL: FAILURE - one or more scanner checks failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
