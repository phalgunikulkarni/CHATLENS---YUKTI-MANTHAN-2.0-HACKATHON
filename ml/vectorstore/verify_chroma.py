"""Verification for the ChromaDB indexing/storage layer (Phase 6).

Runs the pipeline over data/test_dataset/ (scan -> CLIP -> OCR -> text embed),
indexes into a persistent ChromaDB, and verifies storage/idempotency/persistence.
NO similarity search is performed; persistence is proven via direct ID lookup.

Verifies (task checklist 1-20):
  client init, persistent path created, both collections exist, 30 visual + 28
  text records, no fabricated text vectors for the 2 no-text images, metadata
  preserved (image_id/filename/file_path/category/extracted_text), visual<->text
  association by image_id, stored dims match sources, no image files modified,
  no fake vectors, idempotent re-run, stable counts, persistence across reopen,
  and retrieval-by-deterministic-ID.
"""
from __future__ import annotations

import math
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.ingestion.scanner import scan_dataset  # noqa: E402
from ml.ocr.extractor import OCRExtractor  # noqa: E402
from ml.embeddings.clip_embedder import CLIPImageEmbedder, EMBEDDING_DIM  # noqa: E402
from ml.embeddings.text_embedder import TextEmbedder, TEXT_EMBEDDING_DIM  # noqa: E402
from ml.vectorstore.chroma_store import (  # noqa: E402
    ChromaStore, VISUAL_COLLECTION, TEXT_COLLECTION, visual_id, text_id,
)

DATASET = "data/test_dataset"
# Use a dedicated verification DB dir so the check is reproducible/clean.
VERIFY_DB = str(Path(__file__).resolve().parent / "chroma_db_verify")
EXPECTED_VISUAL = 30
EXPECTED_TEXT = 28


def _snapshot(root: Path) -> dict:
    snap = {}
    for cur, _d, files in os.walk(root):
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
        print(f"FAIL  dataset not found: {DATASET}")
        return 1

    # Clean any prior verification DB for a deterministic run.
    if Path(VERIFY_DB).exists():
        shutil.rmtree(VERIFY_DB)

    checks: list[tuple[str, bool, str]] = []

    def check(name, ok, detail=""):
        checks.append((name, ok, detail))

    # Build the pipeline outputs once.
    scan = scan_dataset(DATASET)
    filenames = {r.image_id: r.filename for r in scan.records}
    print(f"Images: {scan.discovered_count}")
    print("Generating CLIP visual embeddings...")
    visual = CLIPImageEmbedder().embed_many(scan.records)
    print("Running OCR + text embeddings...")
    ocr = OCRExtractor().extract_many(scan.records)
    text = TextEmbedder().embed_ocr_results(ocr, filenames=filenames)

    src_visual_dim = {r.image_id: r.dim for r in visual if r.ok}
    src_text_dim = {r.image_id: r.dim for r in text if r.has_text}
    text_ids_with_vec = {r.image_id for r in text if r.has_text}
    no_text_ids = {r.image_id for r in text if r.ok and not r.has_text}

    before = _snapshot(root)

    # 1-4: client + collections
    store = ChromaStore(db_path=VERIFY_DB)
    try:
        store.open()
        check("1 ChromaDB client initializes", True)
    except Exception as exc:  # noqa: BLE001
        check("1 ChromaDB client initializes", False, str(exc))
        _report(checks)
        return 1
    check("2 persistent storage path created", Path(VERIFY_DB).is_dir(), VERIFY_DB)
    names = {c.name for c in store.client.list_collections()}
    check("3 visual collection exists", VISUAL_COLLECTION in names)
    check("4 text collection exists", TEXT_COLLECTION in names)

    # index
    v = store.index_visual_batch(visual, filenames=filenames)
    t = store.index_text_batch(text)

    # 5,6: counts
    check("5 all 30 visual embeddings indexed", store.visual.count() == EXPECTED_VISUAL,
          f"count={store.visual.count()}")
    check("6 28 text embeddings indexed", store.text.count() == EXPECTED_TEXT,
          f"count={store.text.count()}")

    # 7,16: the 2 no-text images have NO text record (no fabrication)
    no_text_leak = [i for i in no_text_ids if store.get_text_by_image_id(i) is not None]
    check("7/16 no fabricated text vectors for no-text images", not no_text_leak,
          f"leaked={len(no_text_leak)}")

    # 8-12: metadata preserved (sample a text record which has all fields)
    sample_id = next(iter(text_ids_with_vec))
    tr = store.get_text_by_image_id(sample_id)
    vr = store.get_visual_by_image_id(sample_id)
    md = (tr or {}).get("metadata", {}) or {}
    check("8 image_id preserved", md.get("image_id") == sample_id)
    check("9 filename preserved", bool(md.get("filename")))
    check("10 file_path preserved", bool(md.get("file_path")))
    check("11 category preserved", bool(md.get("category")))
    check("12 extracted_text preserved for text records", bool(md.get("extracted_text")))

    # 13: visual<->text association by image_id
    assoc = (vr is not None and tr is not None
             and vr["metadata"]["image_id"] == tr["metadata"]["image_id"] == sample_id)
    check("13 visual/text associated by image_id", assoc)

    # 14: stored dims match source
    dim_ok = True
    dim_detail = ""
    for iid in list(text_ids_with_vec)[:5]:
        rec = store.get_text_by_image_id(iid)
        if rec is None or len(rec["embedding"]) != src_text_dim[iid] or len(rec["embedding"]) != TEXT_EMBEDDING_DIM:
            dim_ok = False; dim_detail = f"text dim mismatch {iid[:8]}"; break
    for iid in list(src_visual_dim)[:5]:
        rec = store.get_visual_by_image_id(iid)
        if rec is None or len(rec["embedding"]) != src_visual_dim[iid] or len(rec["embedding"]) != EMBEDDING_DIM:
            dim_ok = False; dim_detail = f"visual dim mismatch {iid[:8]}"; break
    check("14 stored dims match source (512 visual / 384 text)", dim_ok, dim_detail)

    # 20: retrieve by deterministic ID
    direct = store.visual.get(ids=[visual_id(sample_id)])
    check("20 record retrievable by deterministic ID", bool(direct.get("ids")))

    # 17,18: idempotent re-run -> counts unchanged
    store.index_visual_batch(visual, filenames=filenames)
    store.index_text_batch(text)
    check("17/18 re-index does not duplicate (counts stable)",
          store.visual.count() == EXPECTED_VISUAL and store.text.count() == EXPECTED_TEXT,
          f"v={store.visual.count()} t={store.text.count()}")

    # 19: persistence across reopen (new client on same path)
    store2 = ChromaStore(db_path=VERIFY_DB).open()
    persisted = (store2.visual.count() == EXPECTED_VISUAL
                 and store2.text.count() == EXPECTED_TEXT
                 and store2.get_visual_by_image_id(sample_id) is not None)
    check("19 data persists after reopen", persisted,
          f"v={store2.visual.count()} t={store2.text.count()}")

    after = _snapshot(root)
    # 15: no image files modified
    check("15 no image files modified", before == after)

    _report(checks)
    all_ok = all(ok for _n, ok, _d in checks)
    print(f"\nStats: visual={store.visual.count()}  text={store.text.count()}  "
          f"no_text_images={len(no_text_ids)}")
    print(f"Verification DB: {VERIFY_DB}")
    if all_ok:
        print("OVERALL: SUCCESS - ChromaDB indexing verified on the real dataset.")
        return 0
    print("OVERALL: FAILURE - one or more indexing checks failed.")
    return 1


def _report(checks):
    print("-" * 72)
    for name, ok, det in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}{('  (' + det + ')') if det else ''}")
    print("-" * 72)


if __name__ == "__main__":
    sys.exit(main())
