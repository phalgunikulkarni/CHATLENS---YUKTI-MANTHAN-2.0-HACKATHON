"""Verification script for the ChatLens OCR layer (Phase 3).

Scans the developer-supplied test dataset, runs PaddleOCR over every image,
and reports:
  - total images processed
  - images with detected text
  - images with no detected text
  - processing failures
  - a short preview of extracted text for several images across categories
  - confirmation that no image files were modified

Runs fully automatically (no per-image manual input). Exits non-zero only if
the pipeline itself fails (e.g. the OCR model cannot initialize) or if any
image raises an unhandled error. Images with no text are a normal outcome,
not a failure.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.ingestion.scanner import scan_dataset  # noqa: E402
from ml.ocr.extractor import OCRExtractor  # noqa: E402

DATASET = "data/test_dataset"


def _snapshot(root: Path) -> dict[str, tuple[int, float]]:
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
    root = Path(DATASET)
    if not root.is_dir():
        print(f"FAIL  dataset directory not found: {DATASET}")
        return 1

    scan = scan_dataset(DATASET)
    print(f"Dataset: {DATASET}  |  images to process: {scan.discovered_count}")
    print("Loading PaddleOCR model once (reused for all images)...")

    before = _snapshot(root)

    extractor = OCRExtractor()
    # Trigger model load up front so an init failure is reported clearly (Req 4.4).
    try:
        extractor._get_engine()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL  PaddleOCR model initialization failed: {exc}")
        return 1

    results = extractor.extract_many(scan.records)
    after = _snapshot(root)

    total = len(results)
    with_text = [r for r in results if r.ok and r.has_text]
    no_text = [r for r in results if r.ok and not r.has_text]
    failures = [r for r in results if not r.ok]

    print("-" * 70)
    print(f"Total images processed : {total}")
    print(f"Images with text       : {len(with_text)}")
    print(f"Images with no text    : {len(no_text)}")
    print(f"Processing failures    : {len(failures)}")
    print("-" * 70)

    # Preview one image per category (prefer one that has text).
    print("Sample extracted text (one per category):")
    by_cat: dict[str, list] = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)
    for category in sorted(by_cat):
        recs = by_cat[category]
        chosen = next((r for r in recs if r.ok and r.has_text), recs[0])
        text = chosen.extracted_text.strip()
        if chosen.ok and text:
            preview = text[:100] + ("..." if len(text) > 100 else "")
            print(f"  [{category:<14}] ({chosen.mean_confidence:.2f}) {preview!r}")
        elif chosen.ok:
            print(f"  [{category:<14}] <no readable text detected>")
        else:
            print(f"  [{category:<14}] ERROR: {chosen.error}")

    print("-" * 70)
    if failures:
        print("Failure details:")
        for r in failures:
            print(f"  {r.image_id[:12]} {Path(r.file_path).name}: {r.error}")
        print("-" * 70)

    files_unchanged = before == after
    print(f"No image files modified : {'YES' if files_unchanged else 'NO'}")
    print("-" * 70)

    # Success = pipeline ran, no unhandled failures, files untouched.
    if not files_unchanged:
        print("OVERALL: FAILURE - dataset files changed during OCR.")
        return 1
    if failures:
        print("OVERALL: FAILURE - one or more images failed to process.")
        return 1
    print("OVERALL: SUCCESS - OCR ran over the full dataset without failures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
