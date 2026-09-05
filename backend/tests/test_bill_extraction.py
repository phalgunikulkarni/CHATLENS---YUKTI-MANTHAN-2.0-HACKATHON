"""Focused tests for the enhanced analyze_bill extraction (rule_based_v2).

Offline (use_llm=False so no Ollama needed). Covers GST breakdown, extended
fields, no-fabrication, deterministic arithmetic reconciliation, and equal-split
rounding residual for 2/3/4 people. Run:
    python tests/test_bill_extraction.py
"""
from __future__ import annotations

import os, sys, traceback

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from agents.analyze_bill_agent import AnalyzeBillAgent
from agents.contracts import AgentContext

A = AnalyzeBillAgent()

GST = """Spice Garden Restaurant
123 MG Road, Bengaluru
Phone: 080-12345678
Invoice No: INV-2024-0345
Date: 05/03/2024   Time: 20:15
Paneer Tikka   2   250.00   500.00
Butter Naan    4    40.00   160.00
Dal Makhani    1   180.00   180.00
Subtotal       840.00
Discount        40.00
Taxable Amount 800.00
CGST 2.5%       20.00
SGST 2.5%       20.00
Service Charge  40.00
GRAND TOTAL    880.00
Payment: UPI
"""

IGST = """Acme Traders
Invoice No: 991
Date: 2024-06-01
Widget 1 100.00 100.00
Subtotal 100.00
IGST 18% 18.00
GRAND TOTAL 118.00
"""


def _f(text):
    return A.run(AgentContext(params={"ocr_text": text, "use_llm": False})).data["fields"]


def test_core_fields_extracted():
    f = _f(GST)
    assert f["merchant"] == "Spice Garden Restaurant"
    assert f["date"] == "05/03/2024"
    assert f["total"] == 880.0
    assert len(f["line_items"]) == 3
    assert f["line_items"][0]["qty"] == 2 and f["line_items"][0]["unit_price"] == 250.0


def test_gst_cgst_sgst_preserved_separately():
    f = _f(GST)
    assert f["cgst"] == 20.0 and f["sgst"] == 20.0 and f["igst"] is None
    assert f["subtotal"] == 840.0 and f["discount"] == 40.0 and f["taxable_amount"] == 800.0
    assert f["service_charge"] == 40.0


def test_igst_preserved_separately():
    f = _f(IGST)
    assert f["igst"] == 18.0 and f["cgst"] is None and f["sgst"] is None
    assert f["total"] == 118.0


def test_missing_field_not_fabricated():
    f = _f("Just some text with TOTAL 50.00 and nothing else structured")
    # total detected, but GST components genuinely absent -> stay None (no invention)
    assert f["total"] == 50.0
    assert f["cgst"] is None and f["sgst"] is None and f["igst"] is None and f["discount"] is None


def test_deterministic_arithmetic_reconciles():
    r = A.run(AgentContext(params={"ocr_text": GST, "use_llm": False}))
    a = r.data["arithmetic"]
    # 840 - 40 + (20+20) + 40 = 880 == grand total
    assert a["gst_total"] == 40.0
    assert a["computed_total"] == 880.0
    assert a["reconciles"] is True


def _shares(text, n):
    r = A.run(AgentContext(params={"ocr_text": text, "use_llm": False,
                                   "operation": "split", "split_mode": "equal", "people": n}))
    return r.data["split"]["shares"], r.data["split"]["rounding"]


def test_equal_split_2_3_4_reconcile_exactly():
    for n in (2, 3, 4):
        shares, rounding = _shares(GST, n)
        amounts = [s["amount"] for s in shares]
        assert len(amounts) == n
        # each rounded to 2dp, and the sum equals the total exactly
        assert all(abs(round(x, 2) - x) < 1e-9 for x in amounts)
        assert abs(sum(amounts) - 880.0) < 0.005, (n, amounts, sum(amounts))
        assert rounding["reconciles_to_total"] is True


def test_equal_split_rounding_residual_on_last():
    # 880 / 3 = 293.333...  -> 293.33, 293.33, 293.34 ; last absorbs residual
    shares, _ = _shares(GST, 3)
    amts = [s["amount"] for s in shares]
    assert amts[0] == 293.33 and amts[1] == 293.33 and amts[2] == 293.34
    assert abs(sum(amts) - 880.0) < 0.005


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p = f = 0
    for t in tests:
        try: t(); print(f"PASS {t.__name__}"); p += 1
        except Exception: print(f"FAIL {t.__name__}"); traceback.print_exc(); f += 1
    print(f"bill_extraction: {p} passed, {f} failed, {p+f} total")
    return f == 0


if __name__ == "__main__":
    sys.exit(0 if _run() else 1)
