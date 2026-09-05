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

Also supports a bill-splitting operation (params["operation"]="split") on the
SAME agent (no new agent): equal split (params["people"]) or item-based split
(params["assignments"], optional params["shared_items"]/["tip"]). Splits reuse
the detected total/tax/items; missing/invalid data -> controlled failure; no
values are invented. Amounts reconcile to the detected total when known.
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
_TAX_LINE = re.compile(
    r"(?im)^\s*(gst|vat|tax|service\s*charge|service\s*tax)\b[^0-9]*"
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


def _detect_tax(text: str) -> Tuple[Optional[float], Optional[str]]:
    """Return (tax, evidence_line) from a reliably-labeled tax/GST/VAT/service line.

    Conservative: only a clearly tax-labeled line counts. Never inferred from
    the total. Returns (None, None) when no such line exists.
    """
    matches = list(_TAX_LINE.finditer(text or ""))
    if not matches:
        return None, None
    m = matches[-1]
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


def _round2(x: float) -> float:
    return round(x + 1e-9, 2)


def _reconcile(amounts: List[float], target: Optional[float]) -> Tuple[List[float], Dict[str, Any]]:
    """Round amounts to 2dp; push any residual (vs target) onto the last share so
    the allocation reconciles to the detected total when a total is known.

    Returns (adjusted_amounts, rounding_info). Rounding rule: round half up to
    2 decimals; the final person absorbs the leftover cents.
    """
    rounded = [_round2(a) for a in amounts]
    info: Dict[str, Any] = {"rule": "round half to 2 decimals; last share absorbs residual"}
    if target is not None and rounded:
        residual = _round2(target - sum(rounded))
        if abs(residual) >= 0.01:
            rounded[-1] = _round2(rounded[-1] + residual)
            info["residual_applied_to_last"] = residual
    info["sum"] = _round2(sum(rounded))
    info["reconciles_to_total"] = (target is None) or abs(info["sum"] - target) < 0.01
    return rounded, info


def _equal_split(total: float, n: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    base = total / n
    shares = [base] * n
    adjusted, rounding = _reconcile(shares, total)
    people = [{"person": f"Person {i+1}", "amount": adjusted[i]} for i in range(n)]
    return people, rounding


def _item_split(items: List[Dict[str, Any]], assignments: Dict[str, List[int]],
                shared: List[int], tax: Optional[float], tip: Optional[float],
                total: Optional[float]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Allocate items by index to named people; `shared` items split equally
    across ALL named people. Tax/tip (if given) allocated proportionally to each
    person's item subtotal. Never invents prices/tax/tip.
    """
    names = list(assignments.keys())
    n = len(names)
    subtotals = {name: 0.0 for name in names}

    # assigned items
    for name, idxs in assignments.items():
        for i in idxs:
            subtotals[name] += float(items[i]["price"])
    # shared items split equally
    for i in shared:
        share = float(items[i]["price"]) / n
        for name in names:
            subtotals[name] += share

    items_subtotal = sum(subtotals.values())
    # proportional allocation of tax + tip over item subtotals (only if provided)
    extra = (tax or 0.0) + (tip or 0.0)
    per_person: List[float] = []
    for name in names:
        prop = (subtotals[name] / items_subtotal) if items_subtotal > 0 else (1.0 / n)
        per_person.append(subtotals[name] + extra * prop)

    # reconcile to total when known, else to items_subtotal + extra
    target = total if total is not None else _round2(items_subtotal + extra)
    adjusted, rounding = _reconcile(per_person, target)
    people = [{
        "person": names[i],
        "items_subtotal": _round2(subtotals[names[i]]),
        "amount": adjusted[i],
    } for i in range(n)]
    return people, rounding


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
        tax, tax_evidence = _detect_tax(ocr_text)
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

        # `tax` is additive: existing fields are preserved unchanged; tax is only
        # populated when a clearly-labeled tax/GST/VAT/service line is present.
        fields = {
            "merchant": merchant,
            "date": date,
            "total": total,
            "currency": currency,
            "tax": tax,
            "line_items": line_items,
        }
        evidence = [{
            "type": "ocr_text",
            "source": source,
            "image_id": params.get("image_id"),
            "text": ocr_text,
            "total_line": total_evidence,
            "tax_line": tax_evidence,
        }]

        # -- bill-splitting operation (opt-in; default is plain analysis) ------
        operation = (params.get("operation") or "analyze").strip().lower()
        if operation == "split":
            return self._split(params, fields, evidence, source)

        return AgentResult.success(
            self.id,
            message="Bill analyzed (rule-based; undetected fields left null).",
            data={"fields": fields, "confidence": confidence, "notes": notes},
            evidence=evidence,
            metadata={"source": source, "extractor": "rule_based_v1"},
        )

    # -- bill splitting -------------------------------------------------------

    def _split(self, params: Dict[str, Any], fields: Dict[str, Any],
               evidence: List[Dict[str, Any]], source: str) -> AgentResult:
        """Split the analyzed bill. Mode via params["split_mode"]:
          - "equal" (default): total / people
          - "items": allocate detected line items to named people (+ shared)

        Never invents total/tax/tip/prices. Missing data -> controlled failure
        that explains what is missing. Amounts reconcile to the detected total
        when a total is known; the rounding rule is documented in the result.
        """
        split_mode = (params.get("split_mode") or "equal").strip().lower()
        total = fields.get("total")
        tax = fields.get("tax")
        items = fields.get("line_items") or []
        # tip is only used if explicitly supplied and numeric (never inferred).
        tip = params.get("tip")
        tip = float(tip) if isinstance(tip, (int, float)) else None

        meta = {"source": source, "extractor": "rule_based_v1",
                "operation": "split", "split_mode": split_mode}

        if split_mode == "equal":
            people = params.get("people")
            try:
                n = int(people)
            except (TypeError, ValueError):
                return AgentResult.failure(
                    self.id, error="invalid_people",
                    message="Provide params.people as a positive integer for an equal split.",
                    data={"fields": fields, "split": None}, metadata=meta, evidence=evidence,
                )
            if n < 1:
                return AgentResult.failure(
                    self.id, error="invalid_people",
                    message="Number of people must be at least 1.",
                    data={"fields": fields, "split": None}, metadata=meta, evidence=evidence,
                )
            if total is None:
                return AgentResult.failure(
                    self.id, error="missing_total",
                    message="No bill total was confidently detected, so an equal split "
                            "cannot be computed. (No total was invented.)",
                    data={"fields": fields, "split": None}, metadata=meta, evidence=evidence,
                )
            shares, rounding = _equal_split(float(total), n)
            return AgentResult.success(
                self.id, message=f"Bill split equally among {n}.",
                data={"fields": fields, "split": {
                    "mode": "equal", "people_count": n, "currency": fields.get("currency"),
                    "total": total, "shares": shares, "rounding": rounding,
                }},
                evidence=evidence, metadata=meta,
            )

        if split_mode == "items":
            assignments = params.get("assignments")
            if not isinstance(assignments, dict) or not assignments:
                return AgentResult.failure(
                    self.id, error="missing_assignments",
                    message="Provide params.assignments as {person: [item_index, ...]} "
                            "for an item-based split.",
                    data={"fields": fields, "split": None}, metadata=meta, evidence=evidence,
                )
            if not items:
                return AgentResult.failure(
                    self.id, error="missing_items",
                    message="No line items with prices were confidently extracted, so an "
                            "item-based split is not possible. (No prices were invented.)",
                    data={"fields": fields, "split": None}, metadata=meta, evidence=evidence,
                )
            shared = params.get("shared_items") or []
            # Validate all indices reference real detected items with prices.
            n_items = len(items)
            all_idx: List[int] = []
            norm_assign: Dict[str, List[int]] = {}
            try:
                for person, idxs in assignments.items():
                    norm_assign[str(person)] = [int(i) for i in idxs]
                    all_idx += norm_assign[str(person)]
                shared = [int(i) for i in shared]
                all_idx += shared
            except (TypeError, ValueError):
                return AgentResult.failure(
                    self.id, error="invalid_assignments",
                    message="Item indices must be integers.",
                    data={"fields": fields, "split": None}, metadata=meta, evidence=evidence,
                )
            for i in all_idx:
                if i < 0 or i >= n_items or items[i].get("price") is None:
                    return AgentResult.failure(
                        self.id, error="invalid_item_index",
                        message=f"Item index {i} is out of range or has no reliable price.",
                        data={"fields": fields, "split": None}, metadata=meta, evidence=evidence,
                    )
            people, rounding = _item_split(items, norm_assign, shared, tax, tip, total)
            return AgentResult.success(
                self.id, message="Bill split by items.",
                data={"fields": fields, "split": {
                    "mode": "items", "currency": fields.get("currency"),
                    "total": total, "tax": tax, "tip": tip,
                    "people": people, "shared_item_indices": shared, "rounding": rounding,
                }},
                evidence=evidence, metadata=meta,
            )

        return AgentResult.failure(
            self.id, error="invalid_split_mode",
            message="split_mode must be 'equal' or 'items'.",
            data={"fields": fields, "split": None}, metadata=meta, evidence=evidence,
        )
