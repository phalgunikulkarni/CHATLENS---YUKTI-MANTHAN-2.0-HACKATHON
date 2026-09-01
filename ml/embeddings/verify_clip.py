"""Verification script for the CLIP visual embedding layer (Phase 4).

Runs against the developer-supplied data/test_dataset/ with real images and:
  - reports total images processed, successes, and failures
  - verifies every successful embedding has the expected dimensionality (512)
  - verifies embeddings are L2-normalized (norm approximately 1.0)
  - verifies image_id and file_path are preserved from ingestion
  - prints a short summary

Runs fully automatically. Exits non-zero only on an unhandled failure
(e.g. model load failure, wrong dimension, non-normalized vectors, or any
image that failed to embed).
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.ingestion.scanner import scan_dataset  # noqa: E402
from ml.embeddings.clip_embedder import (  # noqa: E402
    CLIPImageEmbedder,
    CLIP_MODEL_NAME,
    EMBEDDING_DIM,
)

DATASET = "data/test_dataset"
NORM_TOLERANCE = 1e-3


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
    id_by_path = {r.file_path: r.image_id for r in scan.records}
    print(f"Model: {CLIP_MODEL_NAME}  |  expected dim: {EMBEDDING_DIM}")
    print(f"Dataset: {DATASET}  |  images to process: {scan.discovered_count}")

    before = _snapshot(root)

    embedder = CLIPImageEmbedder()
    try:
        embedder._ensure_loaded()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL  CLIP model load failed: {exc}")
        return 1
    print(f"CLIP model loaded on device: {embedder._device}")

    results = embedder.embed_many(scan.records)
    after = _snapshot(root)

    total = len(results)
    ok = [r for r in results if r.ok]
    failures = [r for r in results if not r.ok]

    checks: list[tuple[str, bool, str]] = []

    def check(name: str, passed: bool, detail: str = "") -> None:
        checks.append((name, passed, detail))

    # Dimensionality
    bad_dim = [r for r in ok if r.dim != EMBEDDING_DIM or len(r.visual_embedding or []) != EMBEDDING_DIM]
    check(f"all embeddings are {EMBEDDING_DIM}-d", not bad_dim,
          f"{len(bad_dim)} wrong-dim" if bad_dim else "")

    # Normalization (L2 norm approximately 1.0)
    bad_norm = []
    for r in ok:
        norm = math.sqrt(sum(x * x for x in r.visual_embedding))
        if abs(norm - 1.0) > NORM_TOLERANCE:
            bad_norm.append((r.image_id[:12], round(norm, 5)))
    check("all embeddings L2-normalized", not bad_norm,
          f"{len(bad_norm)} not normalized: {bad_norm[:3]}" if bad_norm else "")

    # image_id + file_path preserved from ingestion
    preserved = all(id_by_path.get(r.file_path) == r.image_id for r in results)
    check("image_id + file_path preserved", preserved)

    # No files modified
    files_unchanged = before == after
    check("no image files modified", files_unchanged)

    # No failures expected on the clean test dataset
    check("no embedding failures", not failures,
          "; ".join(f"{Path(r.file_path).name}:{r.error}" for r in failures) if failures else "")

    # Report
    print("-" * 70)
    print(f"Total images processed : {total}")
    print(f"Successful embeddings  : {len(ok)}")
    print(f"Failures               : {len(failures)}")
    print("-" * 70)
    if ok:
        sample = ok[0]
        head = [round(x, 4) for x in sample.visual_embedding[:5]]
        print(f"Sample embedding [{sample.category}] {Path(sample.file_path).name}")
        print(f"  dim={sample.dim}  first5={head}")
    # Per-category success counts
    by_cat: dict[str, int] = {}
    for r in ok:
        by_cat[r.category] = by_cat.get(r.category, 0) + 1
    print(f"Per-category successes : {dict(sorted(by_cat.items()))}")
    print("-" * 70)

    all_ok = True
    for name, passed, detail in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_ok = False
        suffix = f"  ({detail})" if detail else ""
        print(f"{status}  {name}{suffix}")
    print("-" * 70)
    if all_ok:
        print("OVERALL: SUCCESS - CLIP visual embeddings verified on the real dataset.")
        return 0
    print("OVERALL: FAILURE - one or more CLIP embedding checks failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
