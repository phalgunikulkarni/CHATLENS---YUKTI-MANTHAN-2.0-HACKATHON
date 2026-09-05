"""Analyze Bill Agent (functional agent id="analyze_bill").

Deterministic, rule-based extraction of common receipt fields from OCR text.
No LLM, no Ollama, no new OCR engine — it REUSES the project's existing OCR
(ml/ocr/extractor.OCRExtractor) and image resolution (ml_retrieval).

OCR text source priority (first that yields text wins):
  1. params["ocr_text"]                        (caller already has OCR text)
  2. stored extracted_text for params["image_id"] (already indexed; no re-OCR)
  3. run existing OCRExtractor on a resolved on-disk path
     (params["image_id"] -> resolve_image_path, or params["file_path"])

Never hallucinates: undetected fields are returned as null with a note. Raw OCR
text is preserved as evidence. Never raises to the orchestrator.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .contracts import Agent, AgentContext, AgentResult
from . import retrieval_access

# --- extraction patterns (conservative, deterministic) ----------------------

_CURRENCY_SYMBOLS = {
    "$": "USD", "US$": "USD", "USD": "USD",
    "₹": "INR", "RS": "INR", "RS.": "INR", "INR": "INR",
    "€": "EUR", "EUR": "EUR",
    "£": "GBP", "GBP": "GBP",
    "¥": "JPY", "JPY": "JPY",
}

_AMOUNT = r"(\d{1,3}(?:[,\d]{0,12})(?:\.\d{1,2})?)"
_TOTAL_LINE = re.compile(
    r"(?im)^\s*(grand\s*total|total\s*amount|amount\s*due|balance\s*due|total)\b[^0-9]*"
    + _AMOUNT,
)
_CURRENCY_TOKEN = re.compile(
    r"(?i)(US\$|RS\.?|INR|USD|EUR|GBP|JPY|[$₹€£¥])",
)
# Common date formats: 2024-01-31, 31/01/2024, 01-31-24, Jan 31, 2024, 31 Jan 2024
_DATE_PATTERNS = [
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
    re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b"),
    re.compile(r"(?i)\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\b"),
    re.compile(r"(?i)\b([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})\b"),
]
# A line item: some text followed by a trailing price on the same line.
_LINE_ITEM = re.compile(
    r"(?m)^\s*(?P<name>[A-Za-z][A-Za-z0-9 .,'&/\-]{1,40}?)\s+"
    r"(?:[$₹€£¥]|US\$|RS\.?)?\s*(?P<price>\d{1,4}(?:\.\d{2}))\s*$",
)
_TOTAL_WORDS = re.compile(r"(?i)\b(total|subtotal|tax|balance|amount|due|change|cash|card)\b")


def _num(s: str) -> Optional[float]:
    try:
        return float(s.replace(",", ""))
    except Exception:
        return None


def _detect_currency(text: str) -> Optional[str]:
    m = _CURRENCY_TOKEN.search(text or "")
    if not m:
        return None
    tok = m.group(1).upper().rstrip(".")
    return _CURRENCY_SYMBOLS.get(tok) or _CURRENCY_SYMBOLS.get(m.group(1))


def _detect_total(text: str) -> Tuple[Optional[float], Optional[str]]:
    """Return (total, evidence_line) using the last matching total-like line."""
    matches = list(_TOTAL_LINE.finditer(text or ""))
    if not matches:
        return None, None
    m = matches[-1]  # totals usually appear near the bottom
    return _num(m.group(2)), m.group(0).strip()


def _detect_date(text: str) -> Optional[str]:
    for pat in _DATE_PATTERNS:
        m = pat.search(text or "")
        if m:
            return m.group(1)
    return None


def _detect_merchant(text: str) -> Optional[str]:
    """Heuristic: first non-empty, mostly-alphabetic line near the top."""
    for line in (text or "").splitlines():
        s = line.strip()
        if len(s) < 3:
            continue
        letters = sum(c.isalpha() for c in s)
        if letters >= max(3, int(len(s) * 0.5)) and not _TOTAL_WORDS.search(s):
            return s
    return None


def _detect_line_items(text: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for m in _LINE_ITEM.finditer(text or ""):
        name = m.group("name").strip()
        if _TOTAL_WORDS.search(name):  # skip totals/tax summary rows
            continue
        price = _num(m.group("price"))
        if price is None:
            continue
        items.append({"name": name, "price": price})
    return items


class AnalyzeBillAgent(Agent):
    id = "analyze_bill"
    description = "Rule-based extraction of receipt/bill fields from existing OCR text."

    def __init__(self, ocr_extractor=None) -> None:
        # Injectable for tests; default lazily builds the existing OCRExtractor.
        self._ocr = ocr_extractor

    # -- OCR text acquisition (reuse only) ------------------------------------

    def _get_ocr_text(self, params: Dict[str, Any]) -> Tuple[Optional[str], str]:
        """Return (ocr_text, source_label). None text if unavailable."""
        direct = params.get("ocr_text")
        if isinstance(direct, str) and direct.strip():
            return direct, "params.ocr_text"

        image_id = params.get("image_id")
        if image_id:
            stored = retrieval_access.get_stored_ocr_text(image_id)
            if stored and stored.strip():
                return stored, "stored.extracted_text"

        # Resolve a path and run the EXISTING OCR extractor.
        file_path = params.get("file_path")
        if image_id and not file_path:
            file_path = retrieval_access.resolve_image_path(image_id)
        if file_path:
            rec = self._run_ocr(image_id or "", file_path, params.get("category") or "bill")
            if rec is not None and getattr(rec, "ok", False) and (rec.extracted_text or "").strip():
                return rec.extracted_text, "ocr.extract_one"
            if rec is not None and not getattr(rec, "ok", True):
                return None, f"ocr_error:{rec.error}"
        return None, "no_source"

    def _run_ocr(self, image_id: str, file_path: str, category: str):
        try:
            if self._ocr is None:
                from ml.ocr.extractor import OCRExtractor  # reuse existing engine
                self._ocr = OCRExtractor()
            return self._ocr.extract_one(image_id, file_path, category)
        except Exception:  # noqa: BLE001 - OCR failures must not crash the agent
            return None

    # -- entry point ----------------------------------------------------------

    def run(self, context: AgentContext) -> AgentResult:
        params = context.params or {}
        ocr_text, source = self._get_ocr_text(params)

        if not ocr_text:
            note = "No OCR text available for the given input."
            if source.startswith("ocr_error:"):
                note = f"OCR failed: {source.split(':', 1)[1]}"
            elif source == "no_source":
                note = ("No usable input. Provide params.ocr_text, or an image_id/"
                        "file_path for an indexed image.")
            return AgentResult.failure(
                self.id, error="no_ocr_text", message=note,
                data={"fields": None}, metadata={"source": source},
            )

        total, total_evidence = _detect_total(ocr_text)
        currency = _detect_currency(ocr_text)
        date = _detect_date(ocr_text)
        merchant = _detect_merchant(ocr_text)
        line_items = _detect_line_items(ocr_text)

        notes: List[str] = []
        if merchant is None:
            notes.append("merchant not confidently detected")
        if date is None:
            notes.append("date not confidently detected")
        if total is None:
            notes.append("total not confidently detected")
        if currency is None:
            notes.append("currency not confidently detected")
        if not line_items:
            notes.append("no line items confidently extracted")

        # Coarse confidence: fraction of core fields detected (no fabrication).
        core = [merchant, date, total, currency]
        confidence = round(sum(1 for f in core if f is not None) / len(core), 2)

        fields = {
            "merchant": merchant,
            "date": date,
            "total": total,
            "currency": currency,
            "line_items": line_items,
        }
        evidence = [{
            "type": "ocr_text",
            "source": source,
            "image_id": params.get("image_id"),
            "text": ocr_text,
            "total_line": total_evidence,
        }]

        return AgentResult.success(
            self.id,
            message="Bill analyzed (rule-based; undetected fields left null).",
            data={"fields": fields, "confidence": confidence, "notes": notes},
            evidence=evidence,
            metadata={"source": source, "extractor": "rule_based_v1"},
        )
