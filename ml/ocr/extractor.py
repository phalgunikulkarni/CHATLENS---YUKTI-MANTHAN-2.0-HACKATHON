"""PaddleOCR text extraction for the ChatLens ML pipeline (Phase 3).

Consumes the ImageRecord objects produced by the ingestion scanner
(ml/ingestion/scanner.py) and produces a structured OCR result per image.

Maps to requirements.md Requirement 4 (OCR Text Extraction):
  - Uses the already-approved PaddleOCR dependency.
  - Loads the PaddleOCR model once per process and reuses it (Req 4.3).
  - Returns an empty string for images with no detectable text (Req 4.2).
  - On failure for one image, reports the image_id + error and continues (Req 4.7).
  - Read-only: never modifies, moves, or writes to any scanned image file (Req 2.8).

Explicitly NOT in this module (later phases):
  - No CLIP visual embeddings.
  - No Sentence Transformer text embeddings.
  - No ChromaDB writes.
  - No agent / frontend / backend code.

Installed API: PaddleOCR 3.x. `predict(path)` returns a list of dict-like
OCRResult objects, each exposing `rec_texts` (list[str]) and `rec_scores`
(list[float]).
"""
from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# Quiet the very chatty PaddleOCR/Paddle logs for a clean pipeline run.
os.environ.setdefault("GLOG_minloglevel", "3")
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "False")
warnings.filterwarnings("ignore")

# Confidence below this is treated as noise and dropped from extracted_text.
DEFAULT_MIN_CONFIDENCE = 0.5

# Formats PaddleOCR reliably decodes here (Req 4.1 / 4.5).
SUPPORTED_OCR_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})


@dataclass
class OCRResultRecord:
    """Structured OCR output for one image, keyed to its original image_id.

    Only genuinely produced data is stored (no fabricated metadata).
    """

    image_id: str
    file_path: str
    category: str
    extracted_text: str
    # Diagnostics (not required fields, useful for verification/explainability later)
    token_count: int = 0
    mean_confidence: float = 0.0
    ok: bool = True
    error: Optional[str] = None

    @property
    def has_text(self) -> bool:
        return bool(self.extracted_text.strip())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OCRExtractor:
    """Wraps a single, reused PaddleOCR engine instance (Req 4.3)."""

    def __init__(
        self,
        lang: str = "en",
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> None:
        self.lang = lang
        self.min_confidence = min_confidence
        self._engine = None  # lazy-loaded once

    def _get_engine(self):
        """Load the PaddleOCR model exactly once and reuse it (Req 4.3 / 4.4)."""
        if self._engine is None:
            try:
                from paddleocr import PaddleOCR
            except Exception as exc:  # import failure => model init failure (Req 4.4)
                raise RuntimeError(f"PaddleOCR import failed: {exc}") from exc
            try:
                self._engine = PaddleOCR(
                    lang=self.lang,
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                )
            except Exception as exc:  # Req 4.4: model initialization failed
                raise RuntimeError(f"PaddleOCR model initialization failed: {exc}") from exc
        return self._engine

    def _parse_prediction(self, prediction: Any) -> tuple[str, int, float]:
        """Turn a PaddleOCR 3.x prediction into (text, token_count, mean_conf)."""
        texts: List[str] = []
        scores: List[float] = []

        # 3.x: prediction is a list of dict-like OCRResult objects.
        results: Iterable[Any] = prediction or []
        for res in results:
            rec_texts = None
            rec_scores = None
            try:
                rec_texts = res["rec_texts"]
                rec_scores = res.get("rec_scores", []) if hasattr(res, "get") else res["rec_scores"]
            except Exception:
                # Fall back to attribute access if not dict-like.
                rec_texts = getattr(res, "rec_texts", None)
                rec_scores = getattr(res, "rec_scores", None)

            if not rec_texts:
                continue
            rec_scores = rec_scores or [1.0] * len(rec_texts)
            for t, s in zip(rec_texts, rec_scores):
                if t is None:
                    continue
                if float(s) < self.min_confidence:
                    continue
                cleaned = str(t).strip()
                if cleaned:
                    texts.append(cleaned)
                    scores.append(float(s))

        extracted = " ".join(texts)
        mean_conf = round(sum(scores) / len(scores), 4) if scores else 0.0
        return extracted, len(texts), mean_conf

    def extract_one(self, image_id: str, file_path: str, category: str) -> OCRResultRecord:
        """Run OCR on a single image. Never raises for per-image failures (Req 4.7)."""
        path = Path(file_path)

        # Unsupported / missing file -> record an error, keep pipeline alive (Req 4.5 / 4.7).
        if not path.is_file():
            return OCRResultRecord(
                image_id=image_id, file_path=file_path, category=category,
                extracted_text="", ok=False, error="file not found",
            )
        if path.suffix.lower() not in SUPPORTED_OCR_EXTENSIONS:
            return OCRResultRecord(
                image_id=image_id, file_path=file_path, category=category,
                extracted_text="", ok=False,
                error=f"unsupported format: {path.suffix}",
            )

        try:
            engine = self._get_engine()
            prediction = engine.predict(str(path))
            text, tokens, mean_conf = self._parse_prediction(prediction)
            # No detectable text -> empty string, still a success (Req 4.2).
            return OCRResultRecord(
                image_id=image_id, file_path=file_path, category=category,
                extracted_text=text, token_count=tokens,
                mean_confidence=mean_conf, ok=True, error=None,
            )
        except Exception as exc:  # per-image failure (Req 4.7)
            return OCRResultRecord(
                image_id=image_id, file_path=file_path, category=category,
                extracted_text="", ok=False, error=f"{type(exc).__name__}: {exc}",
            )

    def extract_many(self, records: Iterable[Any]) -> List[OCRResultRecord]:
        """Run OCR over ingestion ImageRecords (or dicts with the same fields)."""
        out: List[OCRResultRecord] = []
        for rec in records:
            image_id = _field(rec, "image_id")
            file_path = _field(rec, "file_path")
            category = _field(rec, "category")
            out.append(self.extract_one(image_id, file_path, category))
        return out


def _field(rec: Any, name: str) -> str:
    """Read a field from either a dataclass/object or a dict."""
    if isinstance(rec, dict):
        return str(rec.get(name, ""))
    return str(getattr(rec, name, ""))


def extract_texts(
    records: Iterable[Any],
    lang: str = "en",
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> List[OCRResultRecord]:
    """Convenience: build one OCRExtractor and run it over the given records."""
    extractor = OCRExtractor(lang=lang, min_confidence=min_confidence)
    return extractor.extract_many(records)


if __name__ == "__main__":
    import argparse
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from ml.ingestion.scanner import scan_dataset  # noqa: E402

    parser = argparse.ArgumentParser(
        description="Run PaddleOCR over a scanned dataset (read-only)."
    )
    parser.add_argument("dataset_path", nargs="?", default="data/test_dataset")
    args = parser.parse_args()

    scan = scan_dataset(args.dataset_path)
    results = extract_texts(scan.records)
    for r in results:
        preview = (r.extracted_text[:70] + "...") if len(r.extracted_text) > 70 else r.extracted_text
        status = "ok" if r.ok else f"ERR({r.error})"
        print(f"[{r.category:<14}] {status:<6} '{preview}'")
