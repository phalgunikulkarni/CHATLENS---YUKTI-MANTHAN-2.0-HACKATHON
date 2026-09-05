"""Small reusable local-LLM client (Ollama / Qwen).

Talks to a LOCAL Ollama service only. No paid API, no API key, no cloud LLM.
Configurable via environment variables with localhost/Qwen defaults:

  CHATLENS_LLM_BASE_URL   (default http://localhost:11434)
  CHATLENS_LLM_MODEL      (default qwen2.5:3b)
  CHATLENS_LLM_TIMEOUT    (seconds; default 60)

Failures (service down, model missing, timeout, bad response) are surfaced as a
LLMError so callers can convert them into a controlled AgentResult.failure. No
secrets are read or logged (Ollama is unauthenticated on localhost).
"""
from __future__ import annotations

import json
import os
from typing import Optional

import requests

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:3b"
DEFAULT_TIMEOUT = 60.0


class LLMError(Exception):
    """Controlled local-LLM failure (unavailable service / model / timeout)."""


class LocalLLMClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("CHATLENS_LLM_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.model = model or os.getenv("CHATLENS_LLM_MODEL", DEFAULT_MODEL)
        try:
            self.timeout = float(timeout if timeout is not None
                                 else os.getenv("CHATLENS_LLM_TIMEOUT", DEFAULT_TIMEOUT))
        except (TypeError, ValueError):
            self.timeout = DEFAULT_TIMEOUT

    def generate(self, prompt: str, system: Optional[str] = None,
                 temperature: float = 0.0) -> str:
        """One-shot deterministic generation via Ollama /api/generate.

        temperature defaults to 0.0 for deterministic, reproducible output.
        Raises LLMError on any failure.
        """
        if not prompt or not str(prompt).strip():
            raise LLMError("empty prompt")
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": float(temperature)},
        }
        if system:
            payload["system"] = system
        url = f"{self.base_url}/api/generate"
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
        except requests.exceptions.Timeout as exc:
            raise LLMError(f"local LLM timeout after {self.timeout}s") from exc
        except requests.exceptions.ConnectionError as exc:
            raise LLMError(f"local LLM unavailable at {self.base_url}") from exc
        except requests.exceptions.RequestException as exc:
            raise LLMError(f"local LLM request failed: {exc}") from exc

        if resp.status_code == 404:
            # Ollama returns 404 when the model is not pulled/available.
            raise LLMError(f"local model {self.model!r} not available (HTTP 404)")
        if resp.status_code >= 400:
            raise LLMError(f"local LLM error HTTP {resp.status_code}")

        try:
            data = resp.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise LLMError("local LLM returned non-JSON response") from exc

        text = (data or {}).get("response")
        if not isinstance(text, str) or not text.strip():
            raise LLMError("local LLM returned empty response")
        return text.strip()

    def is_available(self) -> bool:
        """Best-effort reachability check (used by validation, not required)."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=min(self.timeout, 5))
            return resp.status_code == 200
        except requests.exceptions.RequestException:
            return False
