"""Model-level tests for the standalone BLIP VLM describer (ml/vlm_description.py).

Scope: ONLY the standalone model wrapper. No ingestion/backend/frontend.

Two tiers, matching the task's separation:
  - Lightweight UNIT tests (default): patch out the heavy BLIP load so they run
    fast with no download. They verify the wrapper's contract: valid image ->
    string, invalid/missing -> None, batch isolates failures, and the model is
    loaded once and reused (not reloaded per image).
  - Optional REAL-MODEL smoke test: runs only when CHATLENS_VLM_SMOKE=1 is set,
    because it may download Salesforce/blip-image-captioning-base on first use.
    It generates a tiny temp image (never repo data) and asserts a non-empty
    string comes back.

Standard-library unittest; no new testing dependency is added.
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.vlm_description import VLMImageDescriber, MODEL_NAME  # noqa: E402


def _write_tiny_png(path: Path) -> None:
    """Write a minimal valid RGB PNG using Pillow (real, decodable image)."""
    from PIL import Image
    Image.new("RGB", (8, 8), color=(123, 200, 50)).save(path, format="PNG")


class _FakeProcessor:
    """Stand-in for BlipProcessor: records calls, returns a trivial 'inputs'."""
    def __init__(self):
        self.calls = 0

    def __call__(self, images=None, return_tensors=None):
        self.calls += 1
        return _FakeInputs()

    def decode(self, ids, skip_special_tokens=True):
        return "a fake generated caption"


class _FakeInputs(dict):
    """A mapping (so ``**inputs`` works) whose .to(device) returns itself."""
    def to(self, device):
        return self


class _FakeModel:
    """Stand-in for BlipForConditionalGeneration: no real inference.

    Signature mirrors the real call ``model.generate(**inputs, max_new_tokens=N)``:
    keyword-only ``max_new_tokens`` plus arbitrary mapping kwargs from inputs.
    """
    def generate(self, max_new_tokens=None, **inputs):
        return [[0, 1, 2]]  # decoded by _FakeProcessor.decode


def _patched_describer():
    """A describer whose heavy load is replaced by fakes (no download).

    Simulates a single successful load and lets us count reuse via the fake
    processor's call count.
    """
    d = VLMImageDescriber()

    class _FakeTorch:
        class _NoGrad:
            def __enter__(self): return self
            def __exit__(self, *a): return False
        @staticmethod
        def inference_mode():
            return _FakeTorch._NoGrad()

    def fake_ensure_loaded():
        if d._model is not None and d._processor is not None:
            return True
        d._torch = _FakeTorch()
        d._device = "cpu"
        d._processor = _FakeProcessor()
        d._model = _FakeModel()
        d._load_count += 1
        return True

    d._ensure_loaded = fake_ensure_loaded  # type: ignore[assignment]
    return d


class VLMUnitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(__file__).resolve().parent / "_vlm_tmp"
        self._tmp.mkdir(exist_ok=True)

    def tearDown(self):
        # Clean up any temp images we created.
        for f in self._tmp.glob("*"):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            self._tmp.rmdir()
        except OSError:
            pass

    def test_valid_image_returns_string(self):
        d = _patched_describer()
        img = self._tmp / "valid.png"
        _write_tiny_png(img)
        out = d.describe_one(img)
        self.assertIsInstance(out, str)
        self.assertTrue(out)  # non-empty

    def test_missing_file_returns_none(self):
        d = _patched_describer()
        out = d.describe_one(self._tmp / "does_not_exist.png")
        self.assertIsNone(out)

    def test_invalid_image_returns_none(self):
        d = _patched_describer()
        bad = self._tmp / "not_an_image.png"
        bad.write_bytes(b"this is not a valid image")
        out = d.describe_one(bad)
        self.assertIsNone(out)

    def test_batch_isolates_failures(self):
        d = _patched_describer()
        good1 = self._tmp / "g1.png"; _write_tiny_png(good1)
        good2 = self._tmp / "g2.png"; _write_tiny_png(good2)
        missing = self._tmp / "missing.png"
        bad = self._tmp / "bad.png"; bad.write_bytes(b"nope")

        results = d.describe_many([good1, missing, bad, good2])
        self.assertEqual(len(results), 4)
        self.assertIsInstance(results[0], str)   # good1 ok
        self.assertIsNone(results[1])            # missing -> None
        self.assertIsNone(results[2])            # invalid -> None
        self.assertIsInstance(results[3], str)   # good2 still processed

    def test_model_reused_not_reloaded_per_image(self):
        d = _patched_describer()
        imgs = []
        for i in range(3):
            p = self._tmp / f"r{i}.png"; _write_tiny_png(p); imgs.append(p)
        d.describe_many(imgs)
        # Loaded exactly once despite 3 images.
        self.assertEqual(d.load_count, 1)
        # Processor was invoked once PER image (proves reuse of the same model).
        self.assertEqual(d._processor.calls, 3)


@unittest.skipUnless(
    os.environ.get("CHATLENS_VLM_SMOKE") == "1",
    "real-model smoke test disabled (set CHATLENS_VLM_SMOKE=1 to enable; may download BLIP)",
)
class VLMRealModelSmokeTest(unittest.TestCase):
    def test_real_caption(self):
        tmp = Path(__file__).resolve().parent / "_vlm_smoke"
        tmp.mkdir(exist_ok=True)
        img = tmp / "smoke.png"
        try:
            _write_tiny_png(img)
            d = VLMImageDescriber()
            out = d.describe_one(img)
            # Real model should return a non-empty caption; device should be set.
            self.assertIsInstance(out, str)
            self.assertTrue(out)
            self.assertIn(d.device, ("cpu", "cuda"))
            self.assertEqual(MODEL_NAME, "Salesforce/blip-image-captioning-base")
        finally:
            try:
                img.unlink()
                tmp.rmdir()
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
