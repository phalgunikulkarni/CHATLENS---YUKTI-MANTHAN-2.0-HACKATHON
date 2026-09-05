"""Standalone BLIP visual-description (VLM) component for ChatLens.

Purpose (and ONLY purpose): given a local image, produce a concise
natural-language description/caption of what the image looks like, using the
BLIP image-captioning model via Hugging Face Transformers.

This is INDEPENDENT of CLIP. CLIP does image -> visual embedding -> retrieval;
BLIP does image -> natural-language description. This module never imports or
touches the CLIP implementation, OCR, retrieval, or any backend/frontend code.

Model:
    Salesforce/blip-image-captioning-base
Classes:
    transformers.BlipProcessor
    transformers.BlipForConditionalGeneration

Design:
  - The processor and model are loaded LAZILY on first use and then REUSED for
    every subsequent image (loaded once per process, not per image).
  - Device is auto-selected (CUDA if available, else CPU). The current
    environment is CPU-only and must work correctly.
  - Inference runs under torch.inference_mode() (no gradients).
  - Failures are isolated: describe_one() returns None for a missing/invalid/
    unreadable image or an inference failure, and NEVER raises to the caller or
    fabricates a description. describe_many() isolates per-image failures so one
    bad image does not stop the batch.

Model caching: this module does NOT hard-code any cache path and does NOT
manually download files. Hugging Face's normal caching applies; the first real
inference may trigger an automatic download if the model is not already cached.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Union

# The approved BLIP captioning model. Loaded through Hugging Face's normal
# caching (no project-specific cache path).
MODEL_NAME = "Salesforce/blip-image-captioning-base"

# Keep generated captions reasonably concise.
_MAX_NEW_TOKENS = 30

PathLike = Union[str, Path]


class VLMImageDescriber:
    """Lazily loads BLIP once and describes images one at a time or in batches.

    Independent of CLIP: this class only performs image captioning and shares no
    state with the visual-embedding pipeline.
    """

    def __init__(self, model_name: str = MODEL_NAME, max_new_tokens: int = _MAX_NEW_TOKENS) -> None:
        self.model_name = model_name
        self.max_new_tokens = max_new_tokens
        self._processor = None
        self._model = None
        self._torch = None
        self._device: Optional[str] = None
        self._load_count = 0  # for tests: proves the model is loaded once, reused

    # -- lazy, reused load ----------------------------------------------------

    def _ensure_loaded(self) -> bool:
        """Load BLIP processor + model exactly once; reuse thereafter.

        Returns True when the model is ready, False if loading failed (so the
        caller degrades to returning None rather than crashing).
        """
        if self._model is not None and self._processor is not None:
            return True
        try:
            import torch
            from transformers import BlipForConditionalGeneration, BlipProcessor
        except Exception as exc:  # noqa: BLE001 - missing/broken deps must not crash callers
            print(f"[vlm_description] transformers/torch unavailable: {exc!r}")
            return False
        try:
            self._torch = torch
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._processor = BlipProcessor.from_pretrained(self.model_name)
            self._model = BlipForConditionalGeneration.from_pretrained(
                self.model_name
            ).to(self._device)
            self._model.eval()
            self._load_count += 1
            return True
        except Exception as exc:  # noqa: BLE001 - download/load failure is non-fatal
            print(f"[vlm_description] model load failed: {exc!r}")
            self._processor = None
            self._model = None
            return False

    @property
    def device(self) -> Optional[str]:
        """The device the model is loaded on ('cpu'/'cuda'); None until loaded."""
        return self._device

    @property
    def load_count(self) -> int:
        """How many times the underlying model was loaded (should be <= 1)."""
        return self._load_count

    # -- public API -----------------------------------------------------------

    def describe_one(self, image_path: PathLike) -> Optional[str]:
        """Return a concise natural-language description of one image, or None.

        Returns None (never raises, never fabricates) when the file is missing,
        is not a readable/decodable image, or inference fails.
        """
        # Validate the path cheaply before loading heavy models.
        try:
            p = Path(image_path)
            if not p.is_file():
                return None
        except Exception:  # noqa: BLE001
            return None

        if not self._ensure_loaded():
            return None

        # Open + convert the image safely with Pillow.
        try:
            from PIL import Image
        except Exception as exc:  # noqa: BLE001
            print(f"[vlm_description] Pillow unavailable: {exc!r}")
            return None
        try:
            with Image.open(p) as im:
                image = im.convert("RGB")
        except Exception as exc:  # noqa: BLE001 - invalid/unreadable image
            print(f"[vlm_description] cannot open image {p}: {exc!r}")
            return None

        # Run BLIP captioning under no-grad; isolate any inference failure.
        try:
            torch = self._torch
            inputs = self._processor(images=image, return_tensors="pt").to(self._device)
            with torch.inference_mode():
                output_ids = self._model.generate(
                    **inputs, max_new_tokens=self.max_new_tokens
                )
            text = self._processor.decode(output_ids[0], skip_special_tokens=True)
            text = (text or "").strip()
            return text or None
        except Exception as exc:  # noqa: BLE001 - inference failure is non-fatal
            print(f"[vlm_description] inference failed for {p}: {exc!r}")
            return None

    def describe_many(self, image_paths: Iterable[PathLike]) -> List[Optional[str]]:
        """Describe a batch of images, isolating per-image failures.

        Returns a list aligned with the input order; each entry is the image's
        description or None. A failure on one image never stops the others.
        """
        results: List[Optional[str]] = []
        for path in image_paths:
            try:
                results.append(self.describe_one(path))
            except Exception as exc:  # noqa: BLE001 - defensive; describe_one already guards
                print(f"[vlm_description] unexpected error for {path}: {exc!r}")
                results.append(None)
        return results
