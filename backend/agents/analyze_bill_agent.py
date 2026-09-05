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
# Totals: match anywhere on the line (not only line-start) so noisy OCR that
# puts "TOTAL" mid-line is still read. Prefer the most specific labels.
_TOTAL_LINE = re.compile(
    r"(?i)(grand\s*total|net\s*payable|amount\s*payable|total\s*amount|amount\s*due|balance\s*due|\btotal\b)[^0-9\n]{0,20}"
    + _AMOUNT,
)
_SUBTOTAL_LINE = re.compile(r"(?i)(sub[\s-]*total|sub\s*tot)[^0-9\n]{0,20}" + _AMOUNT)
_DISCOUNT_LINE = re.compile(r"(?i)(discount|less|savings?)[^0-9\n]{0,20}" + _AMOUNT)
_TAXABLE_LINE = re.compile(r"(?i)(taxable\s*(?:amount|value|amt))[^0-9\n]{0,20}" + _AMOUNT)
_CGST_LINE = re.compile(r"(?i)(\bC\s*GST\b)(?:[^0-9\n]*?\d{1,2}(?:\.\d+)?\s*%)?[^0-9\n]{0,12}" + _AMOUNT)
_SGST_LINE = re.compile(r"(?i)(\bS\s*GST\b)(?:[^0-9\n]*?\d{1,2}(?:\.\d+)?\s*%)?[^0-9\n]{0,12}" + _AMOUNT)
_IGST_LINE = re.compile(r"(?i)(\bI\s*GST\b)(?:[^0-9\n]*?\d{1,2}(?:\.\d+)?\s*%)?[^0-9\n]{0,12}" + _AMOUNT)
# Generic tax (GST/VAT/TAX/service tax) but NOT a CGST/SGST/IGST-specific line.
_TAX_LINE = re.compile(
    r"(?i)(?<![CSI])\b(gst|vat|tax|service\s*tax)\b(?:[^0-9\n]*?\d{1,2}(?:\.\d+)?\s*%)?[^0-9\n]{0,12}" + _AMOUNT,
)
_SERVICE_LINE = re.compile(r"(?i)(service\s*charge|svc\s*charge)[^0-9\n]{0,20}" + _AMOUNT)
_OTHER_CHARGE_LINE = re.compile(
    r"(?i)(packaging|packing|convenience|delivery|handling|container)\s*(?:charges?|fee)?[^0-9\n]{0,20}" + _AMOUNT)
_ROUNDING_LINE = re.compile(r"(?i)(round(?:ing)?(?:\s*off)?|round\s*adj)[^0-9\n]{0,20}(-?\d+(?:\.\d{1,2})?)")
_INVOICE_LINE = re.compile(r"(?i)(?:invoice|bill|receipt|memo|order)\s*(?:no\.?|number|#|:)\s*([A-Za-z0-9\-/]{1,24})")
_PHONE_LINE = re.compile(r"(?<!\d)(\+?\d[\d\s\-]{7,13}\d)(?!\d)")
_TIME_LINE = re.compile(r"\b([0-2]?\d:[0-5]\d(?::[0-5]\d)?\s*(?:[AaPp][Mm])?)\b")
_PAYMENT_LINE = re.compile(r"(?i)\b(cash|card|credit|debit|upi|paytm|gpay|google\s*pay|phonepe|net\s*banking|wallet)\b")

_CURRENCY_TOKEN = re.compile(
    r"(?i)(US\$|RS\.?|INR|USD|EUR|GBP|JPY|[$₹€£¥])",
)
# Common date formats incl. dot separators (05-03.2026), ISO, and month names.
_DATE_PATTERNS = [
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
    re.compile(r"\b(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})\b"),
    re.compile(r"(?i)\b(\d{1,2}\s+[A-Za-z]{3,9}\.?,?\s+\d{2,4})\b"),
    re.compile(r"(?i)\b([A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{2,4})\b"),
]
# A line item with an optional trailing quantity/price. Two shapes:
#  (a) "Name  qty  rate  amount"  (rate & amount)
#  (b) "Name  price"              (single trailing price)
_LINE_ITEM = re.compile(
    r"(?m)^\s*(?P<name>[A-Za-z][A-Za-z0-9 .,'&/()\-]{1,40}?)\s+"
    r"(?:[$₹€£¥]|US\$|RS\.?)?\s*(?P<price>\d{1,5}(?:\.\d{1,2})?)\s*$",
)
_LINE_ITEM_QTY = re.compile(
    r"(?m)^\s*(?P<name>[A-Za-z][A-Za-z0-9 .,'&/()\-]{1,40}?)\s+"
    r"(?P<qty>\d{1,3})\s+(?:[$₹€£¥]|RS\.?)?\s*(?P<unit>\d{1,5}(?:\.\d{1,2})?)\s+"
    r"(?:[$₹€£¥]|RS\.?)?\s*(?P<amount>\d{1,6}(?:\.\d{1,2})?)\s*$",
)
_TOTAL_WORDS = re.compile(r"(?i)(total|subtotal|sub\s*total|\btax|gst|vat|balance|amount|due|change|\bcash\b|\bcard\b|discount|taxable|service|round|invoice|gstin|\bdate\b|payment)")


def _num(s: Optional[str]) -> Optional[float]:
    if s is None:
        return None
    try:
        return float(str(s).replace(",", ""))
    except Exception:
        return None


def _detect_currency(text: str) -> Optional[str]:
    m = _CURRENCY_TOKEN.search(text or "")
    if not m:
        return None
    tok = m.group(1).upper().rstrip(".")
    return _CURRENCY_SYMBOLS.get(tok) or _CURRENCY_SYMBOLS.get(m.group(1))


def _last_amount(pat: re.Pattern, text: str, grp: int = 2) -> Tuple[Optional[float], Optional[str]]:
    """Return (amount, evidence_line) from the LAST match of ``pat`` (totals/
    summary values usually appear near the bottom). Never fabricates."""
    matches = list(pat.finditer(text or ""))
    if not matches:
        return None, None
    m = matches[-1]
    try:
        raw = m.group(grp)
    except Exception:
        return None, None
    return _num(raw), m.group(0).strip()


def _detect_total(text: str) -> Tuple[Optional[float], Optional[str]]:
    return _last_amount(_TOTAL_LINE, text, grp=2)


def _detect_tax(text: str) -> Tuple[Optional[float], Optional[str]]:
    """Generic tax total from a clearly-labeled GST/VAT/TAX/service-tax line.
    Never inferred from the total. Excludes CGST/SGST/IGST-specific lines."""
    return _last_amount(_TAX_LINE, text, grp=2)


def _detect_date(text: str) -> Optional[str]:
    for pat in _DATE_PATTERNS:
        m = pat.search(text or "")
        if m:
            return m.group(1)
    return None


def _detect_time(text: str) -> Optional[str]:
    m = _TIME_LINE.search(text or "")
    return m.group(1).strip() if m else None


def _detect_invoice(text: str) -> Optional[str]:
    m = _INVOICE_LINE.search(text or "")
    return m.group(1).strip() if m else None


def _detect_phone(text: str) -> Optional[str]:
    m = _PHONE_LINE.search(text or "")
    if not m:
        return None
    digits = re.sub(r"\D", "", m.group(1))
    return m.group(1).strip() if 8 <= len(digits) <= 14 else None


def _detect_payment(text: str) -> Optional[str]:
    m = _PAYMENT_LINE.search(text or "")
    return m.group(1).strip().title() if m else None


def _detect_merchant(text: str) -> Optional[str]:
    """Heuristic: first non-empty, mostly-alphabetic line near the top that is
    not a totals/labels line and not a bare number/date."""
    for line in (text or "").splitlines()[:8]:
        s = line.strip()
        if len(s) < 3:
            continue
        if _TOTAL_WORDS.search(s):
            continue
        letters = sum(c.isalpha() for c in s)
        digits = sum(c.isdigit() for c in s)
        if letters >= max(3, int(len(s) * 0.5)) and digits <= letters:
            return s
    return None


def _detect_line_items(text: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    seen_lines: set = set()
    # First pass: qty/unit/amount rows (richer).
    for m in _LINE_ITEM_QTY.finditer(text or ""):
        name = m.group("name").strip()
        if _TOTAL_WORDS.search(name):
            continue
        qty = _num(m.group("qty"))
        unit = _num(m.group("unit"))
        amount = _num(m.group("amount"))
        if amount is None:
            continue
        seen_lines.add(m.group(0).strip())
        items.append({"name": name, "price": amount, "qty": qty,
                      "unit_price": unit, "amount": amount})
    # Second pass: simple "name price" rows not already captured.
    for m in _LINE_ITEM.finditer(text or ""):
        line = m.group(0).strip()
        if line in seen_lines:
            continue
        name = m.group("name").strip()
        if _TOTAL_WORDS.search(name):
            continue
        price = _num(m.group("price"))
        if price is None:
            continue
        items.append({"name": name, "price": price, "qty": None,
                      "unit_price": None, "amount": price})
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


# --- optional local-LLM (Qwen) grounded enrichment --------------------------

# Fields the LLM is allowed to fill (never overrides deterministic values, and
# only with strings/numbers that literally appear in the OCR text).
_LLM_STR_FIELDS = ("merchant", "date", "time", "invoice_no", "phone", "payment_method")
_LLM_NUM_FIELDS = ("total", "subtotal", "discount", "taxable_amount", "tax",
                   "cgst", "sgst", "igst", "service_charge", "other_charges")

_LLM_SYSTEM = (
    "You extract fields from receipt OCR text. Use ONLY values that literally "
    "appear in the text. Never guess, never compute, never invent. If a field "
    "is not present, use null. Return ONLY strict JSON, no prose."
)


def _digits_only(v: Any) -> str:
    return re.sub(r"[^0-9]", "", str(v))


def _value_grounded_in_text(value: Any, text: str, numeric: bool) -> bool:
    """A value is accepted only if it is evidenced in the OCR text."""
    if value is None:
        return False
    t = text or ""
    if numeric:
        # the number's digits must appear in the text (ignoring separators)
        d = _digits_only(value)
        return len(d) >= 1 and d in _digits_only(t)
    sval = str(value).strip()
    if len(sval) < 2:
        return False
    # case-insensitive substring OR all significant tokens present
    low = t.lower()
    if sval.lower() in low:
        return True
    toks = [w for w in re.split(r"\s+", sval.lower()) if len(w) > 2]
    return bool(toks) and all(w in low for w in toks)


def _llm_enrich(fields: Dict[str, Any], ocr_text: str) -> bool:
    """Fill ONLY null fields using the local Qwen model, grounded in OCR text.

    Returns True if the LLM ran and contributed at least one grounded value.
    Silent no-op (returns False) when the local LLM is unavailable/offline or
    returns anything unusable. Never overrides existing values; never invents.
    """
    from .llm_client import LocalLLMClient, LLMError
    client = LocalLLMClient()
    prompt = (
        "Extract these receipt fields as JSON with exactly these keys: "
        "merchant, date, time, invoice_no, phone, payment_method, total, subtotal, "
        "discount, taxable_amount, tax, cgst, sgst, igst, service_charge, other_charges. "
        "Strings for text fields, numbers for money fields, null if absent. "
        "Use ONLY what appears in the text.\n\nOCR TEXT:\n" + (ocr_text or "") + "\n\nJSON:"
    )
    try:
        raw = client.generate(prompt, system=_LLM_SYSTEM, temperature=0.0)
    except LLMError:
        return False
    except Exception:  # noqa: BLE001
        return False

    # Extract the first JSON object from the response.
    import json as _json
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return False
    try:
        parsed = _json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return False
    if not isinstance(parsed, dict):
        return False

    contributed = False
    for k in _LLM_STR_FIELDS:
        if fields.get(k) is None and isinstance(parsed.get(k), (str,)):
            cand = parsed[k].strip()
            if cand and _value_grounded_in_text(cand, ocr_text, numeric=False):
                fields[k] = cand
                contributed = True
    for k in _LLM_NUM_FIELDS:
        if fields.get(k) is None and isinstance(parsed.get(k), (int, float)):
            cand = float(parsed[k])
            if _value_grounded_in_text(cand, ocr_text, numeric=True):
                fields[k] = cand
                contributed = True
    return contributed


# --- deterministic arithmetic validation (NO LLM math) ----------------------

def _validate_arithmetic(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Cross-check the receipt's money fields deterministically.

    - line_items_sum: sum of item amounts (when items exist).
    - gst_total: cgst + sgst + igst + generic tax (only the components present).
    - computed_total: subtotal - discount + taxes + charges + rounding, computed
      ONLY when the needed inputs are present.
    - reconciles: whether computed_total matches the detected grand total (2dp).
    Never fabricates: any field whose inputs are missing is left as None.
    """
    def g(k):
        v = fields.get(k)
        return float(v) if isinstance(v, (int, float)) else None

    out: Dict[str, Any] = {}
    items = fields.get("line_items") or []
    amounts = [float(it.get("amount") if it.get("amount") is not None else it.get("price"))
               for it in items if (it.get("amount") is not None or it.get("price") is not None)]
    out["line_items_sum"] = _round2(sum(amounts)) if amounts else None

    gst_parts = [g("cgst"), g("sgst"), g("igst"), g("tax")]
    gst_present = [x for x in gst_parts if x is not None]
    out["gst_total"] = _round2(sum(gst_present)) if gst_present else None

    subtotal = g("subtotal")
    base = subtotal if subtotal is not None else out["line_items_sum"]
    if base is not None:
        computed = base
        d = g("discount")
        if d is not None:
            computed -= d
        for extra in (out["gst_total"], g("service_charge"), g("other_charges"), g("rounding_adjustment")):
            if extra is not None:
                computed += extra
        out["computed_total"] = _round2(computed)
    else:
        out["computed_total"] = None

    total = g("total")
    if out["computed_total"] is not None and total is not None:
        out["reconciles"] = abs(out["computed_total"] - total) < 0.01
    else:
        out["reconciles"] = None
    return out


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

        # Additional evidence-only fields (all nullable; never fabricated).
        subtotal, _ = _last_amount(_SUBTOTAL_LINE, ocr_text)
        discount, _ = _last_amount(_DISCOUNT_LINE, ocr_text)
        taxable_amount, _ = _last_amount(_TAXABLE_LINE, ocr_text)
        cgst, _ = _last_amount(_CGST_LINE, ocr_text)
        sgst, _ = _last_amount(_SGST_LINE, ocr_text)
        igst, _ = _last_amount(_IGST_LINE, ocr_text)
        service_charge, _ = _last_amount(_SERVICE_LINE, ocr_text)
        other_charges, _ = _last_amount(_OTHER_CHARGE_LINE, ocr_text)
        rounding_adjustment, _ = _last_amount(_ROUNDING_LINE, ocr_text)
        invoice_no = _detect_invoice(ocr_text)
        time_ = _detect_time(ocr_text)
        phone = _detect_phone(ocr_text)
        payment_method = _detect_payment(ocr_text)

        # `tax` is additive: existing fields are preserved unchanged; tax is only
        # populated when a clearly-labeled tax/GST/VAT/service line is present.
        fields = {
            "merchant": merchant,
            "date": date,
            "total": total,
            "currency": currency,
            "tax": tax,
            "line_items": line_items,
            # extended, evidence-only fields (nullable; omitted-from-UI when null)
            "invoice_no": invoice_no,
            "time": time_,
            "phone": phone,
            "subtotal": subtotal,
            "discount": discount,
            "taxable_amount": taxable_amount,
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "service_charge": service_charge,
            "other_charges": other_charges,
            "rounding_adjustment": rounding_adjustment,
            "payment_method": payment_method,
        }

        # OPTIONAL local-LLM (Qwen) structured enrichment. It may ONLY fill fields
        # the deterministic pass left null, and ONLY with values that literally
        # appear in the OCR text (grounded; no arithmetic; no fabrication). If the
        # LLM is unavailable/offline it is a silent no-op. Deterministic values
        # are never overridden.
        llm_used = False
        if params.get("use_llm", True):
            try:
                llm_used = _llm_enrich(fields, ocr_text)
            except Exception:  # noqa: BLE001 - enrichment is best-effort
                llm_used = False

        # Deterministic arithmetic validation/derivation (NO LLM math). Only
        # derives a value when its inputs are all present; never invents.
        arithmetic = _validate_arithmetic(fields)

        notes: List[str] = []
        if fields.get("merchant") is None:
            notes.append("merchant not confidently detected")
        if fields.get("date") is None:
            notes.append("date not confidently detected")
        if fields.get("total") is None:
            notes.append("total not confidently detected")
        if fields.get("currency") is None:
            notes.append("currency not confidently detected")
        if not fields.get("line_items"):
            notes.append("no line items confidently extracted")

        # Coarse confidence: fraction of core fields detected (no fabrication).
        core = [fields.get("merchant"), fields.get("date"), fields.get("total"), fields.get("currency")]
        confidence = round(sum(1 for f in core if f is not None) / len(core), 2)

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
            message="Bill analyzed (rule-based + optional local-LLM enrichment; undetected fields left null).",
            data={"fields": fields, "confidence": confidence, "notes": notes,
                  "arithmetic": arithmetic},
            evidence=evidence,
            metadata={"source": source, "extractor": "rule_based_v2",
                      "llm_enriched": bool(llm_used)},
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
