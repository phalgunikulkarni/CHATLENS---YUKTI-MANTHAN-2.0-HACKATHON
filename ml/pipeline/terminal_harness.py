"""Terminal-only test harness for ChatLens local image-library indexing.

This is a TESTING mechanism only. It wires together, without modifying, the
existing ML engine:

    Allow/Deny consent (terminal)
        -> LocalImageAccess.default_user_scope()   (derived home root; no hardcode)
        -> LibraryIndexer.index_locations(...)      (existing scanner/OCR/CLIP/text/ChromaDB)
        -> Retriever via LibraryIndexer.retrieve()  (existing retrieval, unchanged)

The ML API (LibraryIndexer / LocalImageAccess) is fully usable WITHOUT this
harness; a future frontend/backend can supply the authorized-access context
directly. Nothing here is imported by the ML engine.

Consent is a single decision:
    "Do you allow ChatLens to access your local image files?"  [1] Allow  [2] Deny
After Allow, the SYSTEM (not the user) derives the accessible user image-storage
root. The user is never asked for a folder path. OS permissions are respected:
protected subpaths are skipped by the OS during the walk, never bypassed.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the project importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _ask_consent() -> bool:
    """Ask the single Allow/Deny question. Returns True for Allow."""
    print("Do you allow ChatLens to access your local image files?")
    print("  1. Allow")
    print("  2. Deny")
    while True:
        choice = input("Enter 1 or 2: ").strip()
        if choice == "1":
            return True
        if choice == "2":
            return False
        print("Please enter 1 (Allow) or 2 (Deny).")


def _discover_counts(access, scope):
    """Discovery-only per-folder eligible-static-image counts.

    Uses LocalImageAccess.ingest_locations (scanner + static-image filtering)
    which does NOT run OCR/CLIP/embeddings/ChromaDB. Returns (per_folder, total).
    """
    per_folder = []
    total = 0
    for root in scope:
        batch = access.ingest_locations([root])
        n = batch.total_images
        total += n
        per_folder.append((root, n))
    return per_folder, total


def _index(indexer, scope, *, force: bool):
    print("\nEmbedding eligible images (existing pipeline)...")
    report = indexer.index_locations(scope, force=force)
    d = report.to_dict()
    print("-" * 60)
    print(f"New/changed processed: {d['new_or_changed']}")
    print(f"Unchanged skipped    : {d['skipped_unchanged']}")
    print(f"Visual vectors added : {d['visual_indexed']}")
    print(f"Text vectors added   : {d['text_indexed']}")
    print(f"ChromaDB stats       : {d['stats']}")
    print("-" * 60)
    return report


def _query_loop(indexer, top_k: int) -> None:
    print("\nEnter a natural-language query to search your indexed images.")
    print("(blank line or 'quit' to exit)")
    while True:
        try:
            q = input("\nquery> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not q or q.lower() in {"quit", "exit"}:
            return
        try:
            results = indexer.retrieve(q, top_k=top_k)
        except Exception as exc:  # never crash the harness on a bad query
            print(f"  retrieval error: {exc}")
            continue
        if not results:
            print("  No results.")
            continue
        for i, r in enumerate(results, 1):
            abs_path = getattr(r, "absolute_path", None) or r.file_path
            src = getattr(r, "source_root", None)
            src_name = Path(src).name if src else (r.category or "-")
            print(f"  {i}. [{r.retrieval_signal}] final={r.score:.4f}")
            print(f"       Image ID: {r.image_id}")
            print(f"       File:     {r.filename}")
            print(f"       Path:     {abs_path}")
            print(f"       Source:   {src_name}")
            if getattr(r, "reason", None):
                print(f"       Reason:   {r.reason}")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Terminal test harness: consent -> auto-index local images -> query."
    )
    parser.add_argument("--top_k", "--top-k", dest="top_k", type=int, default=10)
    parser.add_argument("--force", action="store_true",
                        help="Reprocess all discovered images (ignore change-skip).")
    parser.add_argument("--sync", action="store_true",
                        help="Run only a sync pass (same as re-indexing) then query.")
    parser.add_argument("--no-watch", action="store_true",
                        help="Do not start the automatic synchronization watcher.")
    args = parser.parse_args()

    if not _ask_consent():
        # DENY: stop immediately, scan nothing, no fallback, exit cleanly.
        print("\nAccess denied. ChatLens will not scan your local files. Exiting.")
        return 0

    # ALLOW: resolve the approved user-facing folder allowlist (Desktop/Downloads/
    # Documents/Pictures). The user is never asked for a path; the home root and
    # ~/Library/system/application data are never scan roots.
    from ml.filesystem.local_access import LocalImageAccess
    from ml.pipeline import LibraryIndexer

    access = LocalImageAccess()
    print(f"\nAccess allowed. Detected OS: {access.operating_system.value}")
    scope = access.default_user_scope()
    if not scope:
        # Treated like a permission failure: no approved, accessible folders.
        print("Local folder access is required to retrieve your images. "
              "No approved user folders (Desktop/Downloads/Documents/Pictures) "
              "could be accessed. Please allow access and try again.")
        return 1

    print("Approved image folders:")
    for root in scope:
        print(f"    {root}")

    # STEP 6: per-folder eligible static image counts (discovery only; no ML).
    per_folder, total = _discover_counts(access, scope)
    print("-" * 60)
    for root, n in per_folder:
        print(f"{Path(root).name}: {n} images")
    print(f"Total eligible images: {total}")
    print("-" * 60)

    if total == 0:
        print("No eligible static images found in the approved folders. "
              "Nothing to embed.")
        return 0

    # STEP 7: auto-continue into the EXISTING embedding/ingestion pipeline
    # (no extra confirmation). Pipeline behavior is unchanged.
    indexer = LibraryIndexer()
    _index(indexer, scope, force=args.force)

    # STEP 8: start automatic synchronization (watcher) over the SAME approved
    # scope. The watcher triggers the existing incremental indexer for new/
    # changed images; it never re-embeds the whole library. Runs concurrently
    # with the query loop; watcher errors never crash the app.
    from ml.pipeline import FolderWatcher
    from ml.filesystem.local_access import is_static_image_file

    def _on_change(roots):
        indexer.index_locations(roots)  # existing incremental (fingerprint) path

    watcher = None
    if not args.no_watch:
        watcher = FolderWatcher(
            roots=scope, on_batch=_on_change, is_eligible=is_static_image_file,
        )
        watcher.start()
        print("\nInitial indexing complete.")
        print("Automatic synchronization is now active.")
        print("Watching: " + ", ".join(Path(r).name for r in scope)
              + f"  (backend: {watcher.backend})")

    try:
        _query_loop(indexer, top_k=args.top_k)
    finally:
        if watcher is not None:
            watcher.stop()
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
