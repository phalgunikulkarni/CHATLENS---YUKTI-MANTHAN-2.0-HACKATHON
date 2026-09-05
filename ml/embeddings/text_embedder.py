"""Sentence Transformer text embedding for the ChatLens ML pipeline (Phase 5).

Consumes OCR results produced by ml/ocr/extractor.py (OCRResultRecord) and
generates one semantic text embedding per image using the approved model
sentence-transformers/all-MiniLM-L6-v2.

Maps to requirements.md Requirement 6 (semantic text similarity) and the
Text_Embedder glossary role.

Scope (Phase 5 only):
  - Load the Sentence Transformer model once and reuse it for the batch.
  - Embed the OCR extracted_text for each image.
  - Preserve association to the original image (image_id, file_path, filename,
    category, extracted_text).
  - Handle empty/missing OCR text gracefully (no fabricated text/vectors).

NOT in this phase: ChromaDB writes, retrieval/ranking/hybrid search, agent,
frontend/backend, summarization, roadmap, calendar. Read-only w.r.t. images.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

warnings.filterwarnings("ignore")

# Approved text embedding model (docs/decisions.md). 384-dim output.
TEXT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
TEXT_EMBEDDING_DIM = 384


@dataclass
class TextEmbeddingRecord:
    """Semantic text embedding for one image, keyed to its original image_id.

    ``text_embedding`` is a list[float] of length TEXT_EMBEDDING_DIM when the
    image had usable OCR text, or None when there was no usable text. When it is
    None, ``has_text`` is False and no vector is fabricated.
    """

    image_id: str
    file_path: str
    category: str
    extracted_text: str
    text_embedding: Optional[List[float]] = None
    filename: Optional[str] = None
    dim: int = 0
    has_text: bool = False
    ok: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_id": self.image_id,
            "file_path": self.file_path,
            "filename": self.filename,
            "category": self.category,
            "extracted_text": self.extracted_text,
            "text_embedding": self.text_embedding,
            "dim": self.dim,
            "has_text": self.has_text,
            "ok": self.ok,
            "error": self.error,
        }


class TextEmbedder:
    """Wraps a single, reused SentenceTransformer instance (loaded once)."""

    def __init__(self, model_name: str = TEXT_MODEL_NAME) -> None:
        self.model_name = model_name
        self._model = None
        self._load_count = 0  # for verification: proves single load

    def _ensure_loaded(self):
        """Load the SentenceTransformer model exactly once and reuse it."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except Exception as exc:
                raise RuntimeError(
                    f"sentence-transformers unavailable: {exc}"
                ) from exc
            self._model = SentenceTransformer(self.model_name)
            self._load_count += 1
        return self._model

    @property
    def load_count(self) -> int:
        return self._load_count

    def _encode(self, text: str) -> List[float]:
        """Encode one non-empty text into a normalized 384-d vector."""
        model = self._ensure_loaded()
        # normalize_embeddings=True => unit vectors, cosine-ready and consistent
        # with the CLIP layer's normalized embeddings.
        vec = model.encode(
            text,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return [float(x) for x in vec.tolist()]

    def embed_text(self, text: str) -> Optional[List[float]]:
        """Embed one non-empty text using the existing MiniLM pipeline."""
        if not text or not text.strip():
            return None
        return self._encode(text.strip())

    def embed_ocr_result(self, ocr_rec: Any, filename: Optional[str] = None) -> TextEmbeddingRecord:
        """Generate a text embedding for a single OCR result record.

        Accepts an OCRResultRecord (from ml/ocr) or a dict with the same fields.
        Never raises for a single bad item; reports the error and continues.
        """
        image_id = _field(ocr_rec, "image_id")
        file_path = _field(ocr_rec, "file_path")
        category = _field(ocr_rec, "category")
        extracted_text = _field(ocr_rec, "extracted_text")
        if filename is None:
            # OCRResultRecord has no filename; derive from path as a convenience.
            filename = Path(file_path).name if file_path else None

        text = (extracted_text or "").strip()

        # Empty / no usable OCR text -> no embedding, handled gracefully.
        if not text:
            return TextEmbeddingRecord(
                image_id=image_id, file_path=file_path, category=category,
                extracted_text=extracted_text or "", filename=filename,
                text_embedding=None, dim=0, has_text=False, ok=True, error=None,
            )

        try:
            vec = self._encode(text)
            return TextEmbeddingRecord(
                image_id=image_id, file_path=file_path, category=category,
                extracted_text=extracted_text, filename=filename,
                text_embedding=vec, dim=len(vec), has_text=True, ok=True, error=None,
            )
        except Exception as exc:
            return TextEmbeddingRecord(
                image_id=image_id, file_path=file_path, category=category,
                extracted_text=extracted_text or "", filename=filename,
                text_embedding=None, dim=0, has_text=False, ok=False,
                error=f"{type(exc).__name__}: {exc}",
            )

    def embed_ocr_results(
        self,
        ocr_records: Iterable[Any],
        filenames: Optional[Dict[str, str]] = None,
    ) -> List[TextEmbeddingRecord]:
        """Embed a batch of OCR results. Model is loaded once for the whole batch.

        Args:
            ocr_records: iterable of OCRResultRecord (or dicts).
            filenames: optional map image_id -> filename to enrich records.
        """
        self._ensure_loaded()  # single load up front, reused across the batch
        out: List[TextEmbeddingRecord] = []
        for rec in ocr_records:
            fname = None
            if filenames:
                fname = filenames.get(_field(rec, "image_id"))
            out.append(self.embed_ocr_result(rec, filename=fname))
        return out


def _field(rec: Any, name: str) -> str:
    if isinstance(rec, dict):
        return str(rec.get(name, "") or "")
    return str(getattr(rec, name, "") or "")


def embed_texts(
    ocr_records: Iterable[Any],
    model_name: str = TEXT_MODEL_NAME,
    filenames: Optional[Dict[str, str]] = None,
) -> List[TextEmbeddingRecord]:
    """Convenience: build one TextEmbedder and embed all OCR results."""
    embedder = TextEmbedder(model_name=model_name)
    return embedder.embed_ocr_results(ocr_records, filenames=filenames)


if __name__ == "__main__":
    import argparse
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from ml.ingestion.scanner import scan_dataset  # noqa: E402
    from ml.ocr.extractor import OCRExtractor  # noqa: E402

    parser = argparse.ArgumentParser(
        description="Generate Sentence Transformer text embeddings from OCR output."
    )
    parser.add_argument("dataset_path", nargs="?", default="data/test_dataset")
    args = parser.parse_args()

    scan = scan_dataset(args.dataset_path)
    filenames = {r.image_id: r.filename for r in scan.records}
    ocr = OCRExtractor().extract_many(scan.records)
    results = embed_texts(ocr, filenames=filenames)
    for r in results:
        status = f"dim={r.dim}" if r.has_text else ("no-text" if r.ok else f"ERR({r.error})")
        print(f"[{r.category:<14}] {status:<10} {r.filename}")
