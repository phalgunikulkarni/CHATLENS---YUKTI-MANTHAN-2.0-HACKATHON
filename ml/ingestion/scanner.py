"""Image dataset scanner for the ChatLens ML ingestion pipeline (Phase 2).

Scope (Phase 2 only):
  - Recursively scan a developer-supplied dataset directory.
  - Recognize common image formats: .jpg, .jpeg, .png, .webp.
  - Produce a structured record per image: image_id, file_path, filename, category.
  - Category is the name of the immediate parent folder.
  - Ignore hidden/system files (e.g. .DS_Store) and hidden directories.

Explicitly NOT in this module (later phases):
  - No OCR (PaddleOCR).
  - No CLIP visual embeddings.
  - No Sentence Transformer text embeddings.
  - No ChromaDB writes.
  - No frontend/backend/agent code.

The scanner is read-only: it never modifies, moves, renames, or writes to any
scanned image file. It maps to requirements.md Requirement 2 (Local Image
Ingestion).
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List

# Supported image extensions (matched case-insensitively). Requirement 2.2.
SUPPORTED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})


@dataclass(frozen=True)
class ImageRecord:
    """A structured record for one discovered image.

    Only genuinely existing metadata is stored (Requirement 2.7): no fabricated
    timestamps or personal history.
    """

    image_id: str
    file_path: str
    filename: str
    category: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class ScanResult:
    """Outcome of a dataset scan."""

    dataset_path: str
    records: List[ImageRecord] = field(default_factory=list)
    ignored_files: List[str] = field(default_factory=list)

    @property
    def discovered_count(self) -> int:
        return len(self.records)

    @property
    def ignored_count(self) -> int:
        return len(self.ignored_files)

    def category_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for rec in self.records:
            counts[rec.category] = counts.get(rec.category, 0) + 1
        return dict(sorted(counts.items()))


def _is_hidden(name: str) -> bool:
    """A file or directory is hidden if its name starts with a dot."""
    return name.startswith(".")


def _stable_image_id(file_path: Path) -> str:
    """Deterministic id derived from the image's path (Requirement 2.6).

    Uses the POSIX-style relative-agnostic absolute path so the same file always
    yields the same id. SHA-1 hex digest keeps ids short and filesystem-safe.
    """
    normalized = file_path.resolve().as_posix()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def scan_dataset(dataset_path: str | os.PathLike[str]) -> ScanResult:
    """Recursively scan ``dataset_path`` for supported images.

    Args:
        dataset_path: Path to a developer-supplied dataset directory.

    Returns:
        ScanResult with one ImageRecord per discovered image plus the list of
        ignored (hidden/system or unsupported) files.

    Raises:
        NotADirectoryError: if the path does not exist or is not a directory
            (Requirement 2.9).
    """
    root = Path(dataset_path)
    if not root.exists() or not root.is_dir():
        raise NotADirectoryError(
            f"Dataset directory is missing or unreadable: {dataset_path}"
        )

    result = ScanResult(dataset_path=str(root))

    # os.walk lets us prune hidden directories in-place and stay read-only.
    for current_dir, dirnames, filenames in os.walk(root):
        # Skip descending into hidden/system directories.
        dirnames[:] = [d for d in dirnames if not _is_hidden(d)]

        for filename in sorted(filenames):
            file_path = Path(current_dir) / filename

            # Ignore hidden/system files such as .DS_Store (Requirement 2.3).
            if _is_hidden(filename):
                result.ignored_files.append(str(file_path))
                continue

            # Match supported extensions case-insensitively (Requirement 2.2).
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                result.ignored_files.append(str(file_path))
                continue

            # Category = immediate parent folder name (Requirement 2.5).
            category = file_path.parent.name

            result.records.append(
                ImageRecord(
                    image_id=_stable_image_id(file_path),
                    file_path=str(file_path),
                    filename=filename,
                    category=category,
                )
            )

    # Stable ordering for reproducible output.
    result.records.sort(key=lambda r: (r.category, r.filename))
    result.ignored_files.sort()
    return result


# Default dataset location for this phase's test dataset.
DEFAULT_DATASET_PATH = "data/test_dataset"


def _print_report(result: ScanResult) -> None:
    print(f"Scanned dataset: {result.dataset_path}")
    print(f"Discovered images: {result.discovered_count}")
    print(f"Ignored files:     {result.ignored_count}")
    print("Category counts:")
    for category, count in result.category_counts().items():
        print(f"  {category:<20} {count}")
    print("-" * 60)
    for rec in result.records:
        print(f"[{rec.category:<14}] {rec.filename:<45} id={rec.image_id[:12]}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Scan a ChatLens image dataset (read-only, no OCR/embeddings)."
    )
    parser.add_argument(
        "dataset_path",
        nargs="?",
        default=DEFAULT_DATASET_PATH,
        help=f"Path to dataset directory (default: {DEFAULT_DATASET_PATH})",
    )
    args = parser.parse_args()
    _print_report(scan_dataset(args.dataset_path))
