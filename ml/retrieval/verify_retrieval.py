"""Verification for the retrieval/search layer (Phase 7).

Runs against the REAL dataset and the REAL persistent ChromaDB index. If the
persistent index is empty, it is built once from the real pipeline (scan ->
CLIP -> OCR -> text embed -> index) so retrieval can be exercised. Retrieval
itself is read-only.

Verifies task checklist items 1-20 plus a semantic sanity test and a visual
sanity test (query with a real dataset image; it should rank near the top).
NO record is inserted/updated/deleted by retrieval.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.ingestion.scanner import scan_dataset  # noqa: E402
from ml.vectorstore.chroma_store import (  # noqa: E402
    ChromaStore, VISUAL_COLLECTION, TEXT_COLLECTION,
)
from ml.retrieval.retriever import (  # noqa: E402
    Retriever, RankedResult, SIGNAL_VISUAL, SIGNAL_SEMANTIC_OCR,
)

DATASET = "data/test_dataset"
EXPECTED_VISUAL = 30
EXPECTED_TEXT = 28


def _ensure_index(store: ChromaStore) -> None:
    """Populate the persistent index once if it is empty (uses real pipeline)."""
    store.open()
    if store.visual.count() >= EXPECTED_VISUAL and store.text.count() >= EXPECTED_TEXT:
        print(f"Index already populated: {store.stats()}")
        return
    print("Persistent index empty/incomplete - building it once from the real pipeline...")
    from ml.ocr.extractor import OCRExtractor
    from ml.embeddings.clip_embedder import CLIPImageEmbedder
    from ml.embeddings.text_embedder import TextEmbedder

    scan = scan_dataset(DATASET)
    filenames = {r.image_id: r.filename for r in scan.records}
    visual = CLIPImageEmbedder().embed_many(scan.records)
    ocr = OCRExtractor().extract_many(scan.records)
    text = TextEmbedder().embed_ocr_results(ocr, filenames=filenames)
    store.index_visual_batch(visual, filenames=filenames)
    store.index_text_batch(text)
    print(f"Built index: {store.stats()}")


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

    checks: list[tuple[str, bool, str]] = []

    def check(name, ok, detail=""):
        checks.append((name, ok, detail))

    store = ChromaStore()
    try:
        _ensure_index(store)
        check("1 ChromaDB collections open", True)
    except Exception as exc:  # noqa: BLE001
        check("1 ChromaDB collections open", False, str(exc))
        _report(checks); return 1

    # Known valid image_ids / files from the real dataset + index.
    scan = scan_dataset(DATASET)
    valid_ids = {r.image_id for r in scan.records}
    # image_ids that actually have a text record (for check 15).
    text_ids = set()
    got = store.text.get(include=["metadatas"])
    for md in (got.get("metadatas") or []):
        if md and md.get("image_id"):
            text_ids.add(md["image_id"])
    no_text_ids = valid_ids - text_ids

    counts_before = store.stats()
    before_files = _snapshot(root)

    retr = Retriever(store=store)

    # 2 & 3: visual + text retrieval run with real embeddings
    vis = retr.search_text  # placeholder to avoid lint; replaced below
    text_results = retr.search_text("networking protocols and OSI model", top_k=5)
    check("3 text retrieval works (real ST embedding)", len(text_results) > 0,
          f"{len(text_results)} results")

    # visual query = a real dataset image
    sample_img = next(r for r in scan.records)
    visual_results = retr.search_visual(sample_img.file_path, top_k=5)
    check("2 visual retrieval works (real CLIP embedding)", len(visual_results) > 0,
          f"{len(visual_results)} results")

    # 4,5,6: result fields valid
    def fields_ok(rs: list[RankedResult]) -> bool:
        return all(r.image_id and r.file_path and (r.filename is not None)
                   and (r.category is not None) for r in rs)
    check("4-6 results have image_id/file_path/filename/category",
          fields_ok(text_results) and fields_ok(visual_results))

    # 7,8: signals map to correct collection
    check("7 visual results carry 'visual' signal",
          all(r.retrieval_signal == SIGNAL_VISUAL for r in visual_results))
    check("8 text results carry 'semantic_ocr' signal",
          all(r.retrieval_signal == SIGNAL_SEMANTIC_OCR for r in text_results))

    # 9: ranked (descending score)
    def is_ranked(rs): return all(rs[i].score >= rs[i+1].score for i in range(len(rs)-1))
    check("9 results ranked best-first", is_ranked(text_results) and is_ranked(visual_results))

    # 10: top_k respected
    k3 = retr.search_text("receipt total amount", top_k=3)
    check("10 top_k respected", len(k3) <= 3, f"{len(k3)} for top_k=3")

    # top_k larger than available -> capped, no fabrication
    big = retr.search_text("networking", top_k=1000)
    check("10b top_k > available capped to collection size", len(big) <= EXPECTED_TEXT,
          f"{len(big)} <= {EXPECTED_TEXT}")

    # 11: invalid/empty queries handled gracefully
    graceful = True
    detail = ""
    for bad in ("", "   "):
        try:
            retr.search_text(bad, top_k=3)
            graceful = False; detail = f"empty text accepted: {bad!r}"; break
        except ValueError:
            pass
    for bad_k in (0, -1):
        try:
            retr.search_text("networking", top_k=bad_k)
            graceful = False; detail = f"bad top_k accepted: {bad_k}"; break
        except ValueError:
            pass
    check("11 invalid/empty queries raise ValueError", graceful, detail)

    # 12,13: no fabricated results; ids exist in the real dataset
    all_ids_valid = all(r.image_id in valid_ids for r in text_results + visual_results)
    check("12/13 all returned image_ids exist in dataset (no fabrication)", all_ids_valid)

    # 14: retrieval signal attached
    check("14 retrieval signal attached to every result",
          all(r.retrieval_signal in (SIGNAL_VISUAL, SIGNAL_SEMANTIC_OCR)
              for r in text_results + visual_results))

    # 15: text retrieval never returns a no-text image
    text_probe = retr.search_text("a b c the and is of to", top_k=EXPECTED_TEXT)
    no_text_leak = [r for r in text_probe if r.image_id in no_text_ids]
    check("15 text retrieval excludes no-text images", not no_text_leak,
          f"leaked={len(no_text_leak)}")

    # 16: visual retrieval can surface images without OCR text
    #     (search with a no-text image; its own id should appear)
    if no_text_ids:
        nt_id = next(iter(no_text_ids))
        nt_path = next(r.file_path for r in scan.records if r.image_id == nt_id)
        nt_results = retr.search_visual(nt_path, top_k=EXPECTED_VISUAL)
        check("16 visual retrieval includes no-text images",
              any(r.image_id == nt_id for r in nt_results))
    else:
        check("16 visual retrieval includes no-text images", True, "no no-text images")

    # 17,18,19,20: no side effects
    counts_after = store.stats()
    after_files = _snapshot(root)
    check("17 no image files modified", before_files == after_files)
    check("19/20 ChromaDB counts unchanged by retrieval",
          counts_after == counts_before, f"{counts_before} -> {counts_after}")

    # --- Semantic sanity: content-related query ranks a sensible category high
    sem = retr.search_text("handwritten study notes about entropy and decision tree", top_k=5)
    sanity_sem = bool(sem) and any(r.category == "handwritten" for r in sem[:3])
    check("SANITY semantic query surfaces a relevant category",
          sanity_sem, f"top3 cats={[r.category for r in sem[:3]]}")

    # --- Visual sanity: querying with a real image ranks itself at/near the top
    q = scan.records[0]
    vres = retr.search_visual(q.file_path, top_k=3)
    self_top = bool(vres) and vres[0].image_id == q.image_id
    check("SANITY visual self-query ranks the query image first",
          self_top, f"top={vres[0].filename if vres else None} score={vres[0].score if vres else 0:.3f}")

    _report(checks)

    # Show a couple of example rankings for transparency.
    print("Example semantic search 'networking protocols and OSI model' (top 3):")
    for i, r in enumerate(retr.search_text("networking protocols and OSI model", top_k=3), 1):
        print(f"  {i}. [{r.category}] {r.filename}  score={r.score:.4f}")
    print(f"Visual self-query [{q.category}] {q.filename} (top 3):")
    for i, r in enumerate(vres, 1):
        print(f"  {i}. [{r.category}] {r.filename}  score={r.score:.4f}")

    all_ok = all(ok for _n, ok, _d in checks)
    print("\nOVERALL:", "SUCCESS - retrieval verified on the real dataset/index."
          if all_ok else "FAILURE - one or more retrieval checks failed.")
    return 0 if all_ok else 1


def _report(checks):
    print("-" * 74)
    for name, ok, det in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}{('  (' + det + ')') if det else ''}")
    print("-" * 74)


if __name__ == "__main__":
    sys.exit(main())
