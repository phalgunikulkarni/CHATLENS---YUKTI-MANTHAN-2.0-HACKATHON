"""CLIP visual embedding generation for the ChatLens ML pipeline (Phase 4).

Consumes ImageRecord objects from the ingestion scanner
(ml/ingestion/scanner.py) and generates one normalized CLIP visual embedding
per valid image.

Maps to requirements.md Requirement 3 (CLIP Visual Embeddings):
  - Uses the approved OpenAI CLIP model openai/clip-vit-base-patch32 (Req: model choice).
  - Loads the model exactly once per process and reuses it (Req 3.4).
  - Produces fixed-length (512-d) vectors in the shared CLIP space (Req 3.2).
  - Rejects undecodable/empty images, reports the image_id, continues (Req 3.5 / 3.6).
  - Read-only: never modifies, moves, renames, or overwrites images (Req 2.8).

Embeddings are L2-normalized so cosine similarity == dot product later.

This module does NOT depend on OCR text, Sentence Transformers, ChromaDB,
retrieval, or any agent/frontend/backend code (Phase 4 scope).
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

warnings.filterwarnings("ignore")

# Approved model (docs/decisions.md, requirements Req 3). 512-d shared space.
CLIP_MODEL_NAME = "openai/clip-vit-base-patch32"
EMBEDDING_DIM = 512

SUPPORTED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})


@dataclass
class VisualEmbeddingRecord:
    """CLIP visual embedding for one image, keyed to its original image_id.

    ``visual_embedding`` is a list[float] of length EMBEDDING_DIM (L2-normalized),
    or None when embedding failed.
    """

    image_id: str
    file_path: str
    category: str
    visual_embedding: Optional[List[float]] = None
    dim: int = 0
    ok: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_id": self.image_id,
            "file_path": self.file_path,
            "category": self.category,
            "visual_embedding": self.visual_embedding,
            "dim": self.dim,
            "ok": self.ok,
            "error": self.error,
        }


class CLIPImageEmbedder:
    """Wraps a single, reused CLIP model + processor instance (Req 3.4)."""

    def __init__(self, model_name: str = CLIP_MODEL_NAME) -> None:
        self.model_name = model_name
        self._model = None
        self._processor = None
        self._torch = None
        self._device = None

    def _ensure_loaded(self) -> None:
        """Load CLIP model + processor exactly once (Req 3.4)."""
        if self._model is not None:
            return
        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor
        except Exception as exc:  # environment problem
            raise RuntimeError(f"CLIP dependencies unavailable: {exc}") from exc

        self._torch = torch
        # Prefer Apple MPS if present, else CPU. (No CUDA on this machine.)
        if torch.backends.mps.is_available():
            self._device = "mps"
        else:
            self._device = "cpu"

        self._model = CLIPModel.from_pretrained(self.model_name).to(self._device)
        self._model.eval()
        self._processor = CLIPProcessor.from_pretrained(self.model_name)

    def embed_one(self, image_id: str, file_path: str, category: str) -> VisualEmbeddingRecord:
        """Generate a normalized CLIP embedding for one image.

        Never raises for a single bad image; reports the error and lets the
        batch continue (Req 3.5 / 3.6).
        """
        path = Path(file_path)

        if not path.is_file():
            return VisualEmbeddingRecord(
                image_id=image_id, file_path=file_path, category=category,
                ok=False, error="file not found",
            )
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return VisualEmbeddingRecord(
                image_id=image_id, file_path=file_path, category=category,
                ok=False, error=f"unsupported format: {path.suffix}",
            )

        try:
            from PIL import Image
        except Exception as exc:  # pragma: no cover
            return VisualEmbeddingRecord(
                image_id=image_id, file_path=file_path, category=category,
                ok=False, error=f"Pillow unavailable: {exc}",
            )

        # Decode the image (read-only). Convert to RGB for CLIP.
        try:
            with Image.open(path) as im:
                im = im.convert("RGB")
                # Guard against zero-pixel images (Req 3.5).
                if im.width == 0 or im.height == 0:
                    return VisualEmbeddingRecord(
                        image_id=image_id, file_path=file_path, category=category,
                        ok=False, error="image has no pixel data",
                    )
                image = im.copy()
        except Exception as exc:
            return VisualEmbeddingRecord(
                image_id=image_id, file_path=file_path, category=category,
                ok=False, error=f"decode failed: {type(exc).__name__}: {exc}",
            )

        # Run the CLIP image encoder and L2-normalize (Req 3.1 / 3.2 / cosine-ready).
        #
        # We compute the projected image embedding via the vision tower's pooled
        # output followed by the model's visual_projection. This yields the true
        # CLIP shared-space embedding (equivalent to CLIPModel(...).image_embeds)
        # and is stable across transformers versions where get_image_features may
        # return a ModelOutput rather than a plain tensor. It uses no text input,
        # keeping the embedder independent of OCR (Req 11).
        try:
            self._ensure_loaded()
            torch = self._torch
            inputs = self._processor(images=image, return_tensors="pt").to(self._device)
            with torch.no_grad():
                vision_out = self._model.vision_model(**inputs)
                pooled = vision_out.pooler_output               # [1, hidden]
                feats = self._model.visual_projection(pooled)    # [1, 512]
                feats = feats / feats.norm(p=2, dim=-1, keepdim=True)
            vec = feats.squeeze(0).cpu().tolist()
            return VisualEmbeddingRecord(
                image_id=image_id, file_path=file_path, category=category,
                visual_embedding=vec, dim=len(vec), ok=True, error=None,
            )
        except Exception as exc:
            return VisualEmbeddingRecord(
                image_id=image_id, file_path=file_path, category=category,
                ok=False, error=f"embedding failed: {type(exc).__name__}: {exc}",
            )

    def embed_text_query(self, text: str) -> List[float]:
        """Embed a natural-language query into the SAME 512-d CLIP space as images.

        Uses the same loaded CLIP model as the image encoder, via the text tower
        followed by the model's text_projection, then L2-normalizes. This mirrors
        the image path (vision_model -> visual_projection) and is stable across
        transformers versions where get_text_features may return a ModelOutput
        rather than a plain tensor. Enables CLIP text-to-image retrieval.
        """
        if text is None or not str(text).strip():
            raise ValueError("query text must be a non-empty string")
        self._ensure_loaded()
        torch = self._torch
        inputs = self._processor(
            text=[str(text).strip()], return_tensors="pt", padding=True
        ).to(self._device)
        with torch.no_grad():
            text_out = self._model.text_model(**inputs)
            pooled = text_out.pooler_output              # [1, hidden]
            feats = self._model.text_projection(pooled)  # [1, 512] shared space
            feats = feats / feats.norm(p=2, dim=-1, keepdim=True)
        return feats.squeeze(0).cpu().tolist()

    def embed_many(self, records: Iterable[Any]) -> List[VisualEmbeddingRecord]:
        out: List[VisualEmbeddingRecord] = []
        for rec in records:
            out.append(
                self.embed_one(
                    _field(rec, "image_id"),
                    _field(rec, "file_path"),
                    _field(rec, "category"),
                )
            )
        return out


def _field(rec: Any, name: str) -> str:
    if isinstance(rec, dict):
        return str(rec.get(name, ""))
    return str(getattr(rec, name, ""))


def embed_images(records: Iterable[Any], model_name: str = CLIP_MODEL_NAME) -> List[VisualEmbeddingRecord]:
    """Convenience: build one CLIPImageEmbedder and embed all records."""
    embedder = CLIPImageEmbedder(model_name=model_name)
    return embedder.embed_many(records)


if __name__ == "__main__":
    import argparse
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from ml.ingestion.scanner import scan_dataset  # noqa: E402

    parser = argparse.ArgumentParser(description="Generate CLIP visual embeddings (read-only).")
    parser.add_argument("dataset_path", nargs="?", default="data/test_dataset")
    args = parser.parse_args()

    scan = scan_dataset(args.dataset_path)
    results = embed_images(scan.records)
    for r in results:
        status = f"dim={r.dim}" if r.ok else f"ERR({r.error})"
        print(f"[{r.category:<14}] {status:<10} {Path(r.file_path).name}")
