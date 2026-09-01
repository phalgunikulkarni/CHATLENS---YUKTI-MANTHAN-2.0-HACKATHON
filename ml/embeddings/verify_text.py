"""Verification for the Sentence Transformer text-embedding layer (Phase 5).

Runs the real pipeline over data/test_dataset/:
    scan (ingestion) -> PaddleOCR -> Sentence Transformer text embeddings

Verifies:
  1. text model loads successfully
  2. model is loaded once and reused (load_count == 1)
  3. OCR output is consumed correctly by the text-embedding layer
  4. images with valid OCR text receive a 384-d embedding
  5. images with empty/no OCR text are handled gracefully (embedding None, ok)
  6. embedding dimensionality == 384 for all embedded images
  7-10. image_id / file_path / category / extracted_text preserved from OCR
  11. no original image files modified
  12. no fake/placeholder embeddings (None when no text; real vectors otherwise)
  13. works across all dataset categories
  14. semantic sanity check: similar OCR texts score higher than unrelated ones

Runs automatically (no per-image manual input). Exits non-zero on any failure.
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.ingestion.scanner import scan_dataset  # noqa: E402
from ml.ocr.extractor import OCRExtractor  # noqa: E402
from ml.embeddings.text_embedder import (  # noqa: E402
    TextEmbedder,
    TEXT_MODEL_NAME,
    TEXT_EMBEDDING_DIM,
)

DATASET = "data/test_dataset"
NORM_TOL = 1e-3


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


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def main() -> int:
    root = Path(DATASET)
    if not root.is_dir():
        print(f"FAIL  dataset directory not found: {DATASET}")
        return 1

    print(f"Text model: {TEXT_MODEL_NAME}  |  expected dim: {TEXT_EMBEDDING_DIM}")
    scan = scan_dataset(DATASET)
    filenames = {r.image_id: r.filename for r in scan.records}
    print(f"Dataset: {DATASET}  |  images: {scan.discovered_count}")

    before = _snapshot(root)

    print("Running PaddleOCR over dataset (reusing OCR model)...")
    ocr_results = OCRExtractor().extract_many(scan.records)

    embedder = TextEmbedder()
    try:
        embedder._ensure_loaded()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL  text model load failed: {exc}")
        return 1

    results = embedder.embed_ocr_results(ocr_results, filenames=filenames)
    after = _snapshot(root)

    ocr_by_id = {r.image_id: r for r in ocr_results}
    id_by_path = {r.file_path: r.image_id for r in scan.records}

    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))

    embedded = [r for r in results if r.has_text]
    no_text = [r for r in results if r.ok and not r.has_text]
    failures = [r for r in results if not r.ok]

    # 1 & 2: single load
    check("model loaded exactly once", embedder.load_count == 1,
          f"load_count={embedder.load_count}")

    # 4 & 6: embedded images have 384-d vectors
    bad_dim = [r for r in embedded if r.dim != TEXT_EMBEDDING_DIM
               or len(r.text_embedding or []) != TEXT_EMBEDDING_DIM]
    check(f"embedded vectors are {TEXT_EMBEDDING_DIM}-d", not bad_dim,
          f"{len(bad_dim)} wrong" if bad_dim else "")

    # 5 & 12: no-text handled gracefully, no fabricated vectors
    fabricated = [r for r in no_text if r.text_embedding is not None]
    check("no-text images have None embedding (no fabrication)", not fabricated,
          f"{len(fabricated)} fabricated" if fabricated else "")

    # 3, 7-10: association preserved from OCR
    preserved = True
    detail = ""
    for r in results:
        o = ocr_by_id.get(r.image_id)
        if o is None or r.file_path != o.file_path or r.category != o.category \
           or r.extracted_text != o.extracted_text \
           or id_by_path.get(r.file_path) != r.image_id:
            preserved = False
            detail = f"mismatch on {r.image_id[:10]}"
            break
    check("image_id/file_path/category/extracted_text preserved", preserved, detail)

    # 11: no files modified
    check("no image files modified", before == after)

    # 13: works across all categories (every category has at least one embedded)
    cats_all = {r.category for r in results}
    cats_embedded = {r.category for r in embedded}
    check("all categories produced embeddings", cats_all == cats_embedded,
          f"missing: {cats_all - cats_embedded}" if cats_all != cats_embedded else "")

    # embedded vectors are unit-normalized (real numeric vectors, not placeholders)
    bad_norm = []
    for r in embedded:
        n = math.sqrt(sum(x * x for x in r.text_embedding))
        if abs(n - 1.0) > NORM_TOL:
            bad_norm.append((r.image_id[:10], round(n, 4)))
    check("embedded vectors are unit-normalized", not bad_norm,
          str(bad_norm[:3]) if bad_norm else "")

    # 14: semantic sanity check on real OCR text (independent of dataset content)
    sanity_pass = True
    sanity_detail = ""
    try:
        a = embedder._encode("computer network OSI model notes")
        b = embedder._encode("networking layers and protocols")
        c = embedder._encode("grocery shopping receipt total amount")
        sim_related = _cos(a, b)
        sim_unrelated = _cos(a, c)
        sanity_pass = sim_related > sim_unrelated
        sanity_detail = f"related={sim_related:.3f} > unrelated={sim_unrelated:.3f}"
    except Exception as exc:  # noqa: BLE001
        sanity_pass = False
        sanity_detail = f"error: {exc}"
    check("semantic sanity (related > unrelated)", sanity_pass, sanity_detail)

    # no failures
    check("no embedding failures", not failures,
          "; ".join(f"{r.filename}:{r.error}" for r in failures) if failures else "")

    # Report
    print("-" * 72)
    print(f"Total images processed        : {len(results)}")
    print(f"Images with text embedding    : {len(embedded)}")
    print(f"Images with empty/no OCR text : {len(no_text)}")
    print(f"Failures                      : {len(failures)}")
    by_cat: dict[str, int] = {}
    for r in embedded:
        by_cat[r.category] = by_cat.get(r.category, 0) + 1
    print(f"Per-category embedded         : {dict(sorted(by_cat.items()))}")
    if embedded:
        s = embedded[0]
        print(f"Sample [{s.category}] {s.filename}: dim={s.dim} "
              f"first5={[round(x,4) for x in s.text_embedding[:5]]}")
    print("-" * 72)
    all_ok = True
    for name, ok, det in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_ok = False
        print(f"{status}  {name}{('  (' + det + ')') if det else ''}")
    print("-" * 72)
    if all_ok:
        print("OVERALL: SUCCESS - text embeddings verified on the real dataset.")
        return 0
    print("OVERALL: FAILURE - one or more text-embedding checks failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
