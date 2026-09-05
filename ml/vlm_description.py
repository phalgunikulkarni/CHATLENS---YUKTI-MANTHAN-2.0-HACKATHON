"""Lazy factual image descriptions using the approved Transformers/PyTorch stack."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, List, Optional

MODEL_NAME = "Salesforce/blip-image-captioning-base"
_MAX_NEW_TOKENS = 40
_PROMPT = (
    "Describe only visible content in one short factual sentence. "
    "Do not infer identity, intent, dates, or hidden context. "
    "Mention text only when it is visibly readable."
)


class VLMImageDescriber:
    """Lazily loads BLIP and describes images one at a time."""

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        self.model_name = model_name
        self._processor = None
        self._model = None
        self._torch = None
        self._device = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import BlipForConditionalGeneration, BlipProcessor
        except Exception as exc:
            raise RuntimeError(f"VLM dependencies unavailable: {exc}") from exc

        self._torch = torch
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._processor = BlipProcessor.from_pretrained(self.model_name)
        self._model = BlipForConditionalGeneration.from_pretrained(self.model_name).to(self._device)
        self._model.eval()

    def describe_one(self, image_id: str, file_path: str, category: str = "") -> Optional[str]:
        path = Path(file_path)
        if not path.is_file():
            return None
        try:
            from PIL import Image
            with Image.open(path) as image:
                image = image.convert("RGB")
                self._ensure_loaded()
                inputs = self._processor(images=image, text=_PROMPT, return_tensors="pt")
                inputs = {key: value.to(self._device) for key, value in inputs.items()}
                with self._torch.no_grad():
                    output = self._model.generate(**inputs, max_new_tokens=_MAX_NEW_TOKENS)
                description = self._processor.decode(output[0], skip_special_tokens=True).strip()
                return " ".join(description.split()) or None
        except Exception:
            return None

    def describe_many(self, records: Iterable[Any]) -> List[dict]:
        descriptions = []
        for record in records:
            image_id = _field(record, "image_id")
            file_path = _field(record, "file_path")
            category = _field(record, "category")
            description = self.describe_one(image_id, file_path, category)
            descriptions.append({"image_id": image_id, "description": description})
        return descriptions


def _field(record: Any, name: str) -> str:
    if isinstance(record, dict):
        return str(record.get(name, "") or "")
    return str(getattr(record, name, "") or "")
