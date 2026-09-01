"""Verify the ML/retrieval slice dependencies import successfully.

Scope: CLIP (transformers), PaddleOCR, Sentence Transformers, ChromaDB,
OpenCV, Pillow. Emits one pass/fail line per package and exits non-zero if
any import fails (requirements.md Req 1.5 / 1.6).
"""
import importlib
import sys

# (label, module, attribute to touch for a real load)
CHECKS = [
    ("OpenAI CLIP (transformers)", "transformers", "CLIPModel"),
    ("PaddleOCR", "paddleocr", "PaddleOCR"),
    ("Sentence Transformers", "sentence_transformers", "SentenceTransformer"),
    ("ChromaDB", "chromadb", "PersistentClient"),
    ("OpenCV", "cv2", "__version__"),
    ("Pillow", "PIL", "__version__"),
]


def main() -> int:
    all_ok = True
    for label, module, attr in CHECKS:
        try:
            mod = importlib.import_module(module)
            getattr(mod, attr)
            ver = getattr(mod, "__version__", "n/a")
            print(f"PASS  {label:<32} ({module} {ver})")
        except Exception as exc:  # noqa: BLE001 - report any failure
            all_ok = False
            print(f"FAIL  {label:<32} {module}: {type(exc).__name__}: {exc}")

    print("-" * 60)
    if all_ok:
        print("OVERALL: SUCCESS - all 6 ML/retrieval dependencies import.")
        return 0
    print("OVERALL: FAILURE - one or more dependencies failed to import.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
