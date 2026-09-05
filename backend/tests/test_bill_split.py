"""Bill-splitting tests for the Finance/Receipt (analyze_bill) agent.

Covers equal/item splits, rounding+reconciliation, shared items, tax handling,
missing/invalid data (controlled, non-fabricating), currency preservation, and
that existing plain analysis is unchanged. Offline (no OCR/LLM). Run:
    python tests/test_bill_split.py
"""
from __future__ import annotations

import os, sys, traceback

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from agents.analyze_bill_agent import AnalyzeBillAgent
from agents.contracts import AgentContext, AgentResult

A = AnalyzeBillAgent()
SAMPLE = ("Green Leaf Grocery\n2024-03-15\nApples 3.50\nMilk 2.99\nBread 1.20\n"
          "Tax 0.61\nTOTAL $ 8.30\n")
INR = "Chai Shop\n12/03/2024\nTea 20.00\nSamosa 10.00\nTOTAL Rs. 30.00\n"


def _split(**params):
    p = {"ocr_text": SAMPLE, "operation": "split"}
    p.update(params)
    return A.run(AgentContext(params=p))


def test_equal_split_basic():
    r = _split(split_mode="equal", people=2)
    assert r.ok and r.data["split"]["mode"] == "equal"
    shares = [p["amount"] for p in r.data["split"]["shares"]]
    assert shares == [4.15, 4.15]


def test_equal_split_2_person_reconciles():
    r = _split(split_mode="equal", people=2)
    assert abs(sum(p["amount"] for p in r.data["split"]["shares"]) - 8.30) < 0.01


def test_equal_split_3_person_rounding_reconciles():
    r = _split(split_mode="equal", people=3)
    shares = [p["amount"] for p in r.data["split"]["shares"]]
    # 8.30/3 = 2.7666...; reconciles exactly to 8.30 (last absorbs residual)
    assert abs(sum(shares) - 8.30) < 0.01
    assert r.data["split"]["rounding"]["reconciles_to_total"] is True
    assert "rule" in r.data["split"]["rounding"]


def test_item_split_valid_items():
    r = _split(split_mode="items", assignments={"A": [0], "B": [1, 2]})
    assert r.ok
    people = {p["person"]: p for p in r.data["split"]["people"]}
    assert people["A"]["items_subtotal"] == 3.50
    assert people["B"]["items_subtotal"] == 4.19
    # tax (0.61) allocated proportionally; totals reconcile to 8.30
    assert abs(sum(p["amount"] for p in r.data["split"]["people"]) - 8.30) < 0.01


def test_item_split_shared_item():
    r = _split(split_mode="items", assignments={"A": [1], "B": [2]}, shared_items=[0])
    assert r.ok
    people = {p["person"]: p for p in r.data["split"]["people"]}
    # Apples (3.50) shared equally -> +1.75 each
    assert abs(people["A"]["items_subtotal"] - (2.99 + 1.75)) < 0.01
    assert abs(people["B"]["items_subtotal"] - (1.20 + 1.75)) < 0.01
    assert abs(sum(p["amount"] for p in r.data["split"]["people"]) - 8.30) < 0.01


def test_missing_total_equal_controlled():
    r = A.run(AgentContext(params={"ocr_text": "random words, no total",
                                   "operation": "split", "split_mode": "equal", "people": 2}))
    assert not r.ok and r.error == "missing_total"
    assert r.data["split"] is None  # nothing fabricated


def test_invalid_people_controlled():
    assert _split(split_mode="equal", people=0).error == "invalid_people"
    assert _split(split_mode="equal", people="abc").error == "invalid_people"
    assert _split(split_mode="equal").error == "invalid_people"  # missing


def test_item_split_no_items_controlled():
    r = A.run(AgentContext(params={"ocr_text": "Shop\nTOTAL $10.00",
                                   "operation": "split", "split_mode": "items",
                                   "assignments": {"A": [0]}}))
    assert not r.ok and r.error == "missing_items"


def test_item_split_invalid_index_controlled():
    r = _split(split_mode="items", assignments={"A": [99]})
    assert not r.ok and r.error == "invalid_item_index"


def test_currency_preserved_in_split():
    r = A.run(AgentContext(params={"ocr_text": INR, "operation": "split",
                                   "split_mode": "equal", "people": 2}))
    assert r.ok and r.data["split"]["currency"] == "INR"
    assert abs(sum(p["amount"] for p in r.data["split"]["shares"]) - 30.00) < 0.01


def test_tax_field_detected_and_preserved():
    r = A.run(AgentContext(params={"ocr_text": SAMPLE}))
    assert r.data["fields"]["tax"] == 0.61
    # existing fields preserved
    for k in ("merchant", "date", "total", "currency", "line_items"):
        assert k in r.data["fields"]


def test_no_fabrication_tax_absent():
    # No tax line -> tax stays None; split still works and does not invent tax.
    txt = "Cafe\n2024-01-01\nCoffee 4.00\nTOTAL $4.00\n"
    r = A.run(AgentContext(params={"ocr_text": txt}))
    assert r.data["fields"]["tax"] is None
    rs = A.run(AgentContext(params={"ocr_text": txt, "operation": "split", "split_mode": "equal", "people": 2}))
    assert rs.ok and abs(sum(p["amount"] for p in rs.data["split"]["shares"]) - 4.00) < 0.01


def test_default_analysis_unchanged():
    # No operation -> original analysis shape (no "split" key), still structured.
    r = A.run(AgentContext(params={"ocr_text": SAMPLE}))
    assert isinstance(r, AgentResult) and r.ok
    assert "split" not in r.data
    assert set(r.data.keys()) == {"fields", "confidence", "notes"}


def _main():
    tests = [(n, o) for n, o in globals().items() if n.startswith("test_") and callable(o)]
    p = f = 0
    for name, fn in tests:
        try: fn(); p += 1; print(f"PASS {name}")
        except Exception: f += 1; print(f"FAIL {name}"); traceback.print_exc()
    print(f"\nbill_split: {p} passed, {f} failed, {len(tests)} total")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(_main())
