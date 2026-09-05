"""P2S2 - Analyze Bill Agent tests (stdlib harness; pytest not required).

Deterministic tests use synthetic OCR text (params.ocr_text) and a fake OCR
extractor, so no PaddleOCR/torch loads are required. One OPTIONAL test exercises
the real OCRExtractor against a real receipt image if PaddleOCR is available; it
is skipped (non-fatal) otherwise. Run directly:
    python tests/test_analyze_bill_agent.py
"""
from __future__ import annotations

import os
import sys
import traceback

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
# Also put the project root on sys.path so `import ml.ocr...` resolves the same
# way it does at runtime (backend imports ml_retrieval, which anchors the root).
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from agents import AgentContext, AgentResult, AgentRegistry, Orchestrator, StaticRouter
from agents.analyze_bill_agent import AnalyzeBillAgent

SAMPLE = """\
Green Leaf Grocery
123 Market Street
2024-03-15
Apples        3.50
Milk 2L       2.99
Bread         1.20
Subtotal      7.69
Tax           0.61
TOTAL       $ 8.30
Thank you!
"""


class _FakeOCRRecord:
    def __init__(self, text, ok=True, error=None):
        self.extracted_text = text
        self.ok = ok
        self.error = error
        self.mean_confidence = 0.9


class _FakeExtractor:
    def __init__(self, text="", ok=True, error=None):
        self._text, self._ok, self._err = text, ok, error
        self.calls = 0
    def extract_one(self, image_id, file_path, category):
        self.calls += 1
        return _FakeOCRRecord(self._text, self._ok, self._err)


def test_valid_bill_structured_extraction():
    agent = AnalyzeBillAgent()
    res = agent.run(AgentContext(params={"ocr_text": SAMPLE}))
    assert isinstance(res, AgentResult) and res.ok, res.error
    f = res.data["fields"]
    assert f["total"] == 8.30
    assert f["currency"] == "USD"
    assert f["date"] == "2024-03-15"
    assert f["merchant"] == "Green Leaf Grocery"
    names = [i["name"] for i in f["line_items"]]
    assert "Apples" in names and "Bread" in names
    # totals/tax rows must NOT be line items (no hallucination of item rows)
    assert not any(n.lower() in ("subtotal", "tax", "total") for n in names)


def test_evidence_preserved():
    agent = AnalyzeBillAgent()
    res = agent.run(AgentContext(params={"ocr_text": SAMPLE}))
    assert res.evidence and res.evidence[0]["type"] == "ocr_text"
    assert res.evidence[0]["text"] == SAMPLE
    assert res.metadata["source"] == "params.ocr_text"


def test_no_hallucination_when_fields_absent():
    agent = AnalyzeBillAgent()
    res = agent.run(AgentContext(params={"ocr_text": "random unrelated words only"}))
    assert res.ok
    f = res.data["fields"]
    assert f["total"] is None
    assert f["date"] is None
    assert f["currency"] is None
    assert f["line_items"] == []
    assert res.data["confidence"] < 1.0
    assert any("not confidently detected" in n for n in res.data["notes"])


def test_missing_input_is_controlled_failure():
    agent = AnalyzeBillAgent()
    res = agent.run(AgentContext(params={}))
    assert not res.ok and res.error == "no_ocr_text"
    assert res.data["fields"] is None


def test_ocr_extractor_path_used_when_no_text():
    fake = _FakeExtractor(text=SAMPLE)
    agent = AnalyzeBillAgent(ocr_extractor=fake)
    res = agent.run(AgentContext(params={"file_path": "/tmp/whatever.jpg"}))
    assert res.ok and fake.calls == 1
    assert res.data["fields"]["total"] == 8.30
    assert res.metadata["source"] == "ocr.extract_one"


def test_ocr_failure_is_controlled_failure():
    fake = _FakeExtractor(text="", ok=False, error="file not found")
    agent = AnalyzeBillAgent(ocr_extractor=fake)
    res = agent.run(AgentContext(params={"file_path": "/tmp/missing.jpg"}))
    assert not res.ok
    assert "file not found" in res.message


def test_currency_inr_detected():
    agent = AnalyzeBillAgent()
    txt = "Chai Shop\n12/03/2024\nTea 20.00\nTOTAL Rs. 20.00\n"
    res = agent.run(AgentContext(params={"ocr_text": txt}))
    assert res.ok and res.data["fields"]["currency"] == "INR"
    assert res.data["fields"]["total"] == 20.00


def test_dispatch_through_orchestrator():
    reg = AgentRegistry(); reg.register(AnalyzeBillAgent())
    orch = Orchestrator(reg, StaticRouter())
    res = orch.dispatch(AgentContext(params={"ocr_text": SAMPLE}), agent_id="analyze_bill")
    assert res.ok and res.agent == "analyze_bill"


def test_optional_real_ocr_on_real_receipt():
    """OPTIONAL: reuse the real OCRExtractor on a real receipt image. Skipped
    (non-fatal) if PaddleOCR/torch is unavailable or no receipt image exists."""
    receipts_dir = os.path.join(_PROJECT_ROOT, "data", "dataset1", "Reciepts")
    if not os.path.isdir(receipts_dir):
        print("  (skip real-OCR test: no receipts dir)")
        return
    imgs = [f for f in sorted(os.listdir(receipts_dir))
            if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    if not imgs:
        print("  (skip real-OCR test: no receipt images)")
        return
    try:
        from ml.ocr.extractor import OCRExtractor  # noqa: F401
        ocr = OCRExtractor()
    except Exception as exc:  # PaddleOCR not installed / model load blocked
        print(f"  (skip real-OCR test: OCR unavailable: {type(exc).__name__})")
        return
    path = os.path.join(receipts_dir, imgs[0])
    agent = AnalyzeBillAgent(ocr_extractor=ocr)
    res = agent.run(AgentContext(params={"file_path": path, "category": "bill"}))
    assert isinstance(res, AgentResult)
    # Either it extracted text (ok) or reported a controlled failure; never raise.
    assert res.ok or res.error
    print(f"  (real-OCR ran on {imgs[0]}: ok={res.ok})")


def _main():
    tests = [(n, o) for n, o in globals().items() if n.startswith("test_") and callable(o)]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print(f"PASS {name}")
        except Exception:
            failed += 1
            print(f"FAIL {name}")
            traceback.print_exc()
    print(f"\nanalyze_bill_agent: {passed} passed, {failed} failed, {len(tests)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
