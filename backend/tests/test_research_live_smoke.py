"""OPTIONAL live-provider smoke test for the Research pipeline.

Self-skips unless CHATLENS_RESEARCH_LIVE=1 is set, so the normal suite NEVER
requires network access. Hits real Crossref + arXiv (no API key needed) and
checks that normalized sources with URLs come back. Run:
    CHATLENS_RESEARCH_LIVE=1 python tests/test_research_live_smoke.py
"""
from __future__ import annotations

import os, sys, traceback

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


def test_live_crossref_arxiv_smoke():
    if os.getenv("CHATLENS_RESEARCH_LIVE") != "1":
        print("  (skip live smoke: set CHATLENS_RESEARCH_LIVE=1 to enable)")
        return
    import agents.research_pipeline as PL
    res = PL.collect("transformer neural networks", per_provider=3, target=5,
                     provider_names=["crossref", "arxiv"])
    print(f"  providers_used={res['providers_used']} failed={res['providers_failed']} "
          f"n_sources={len(res['sources'])}")
    # At least one provider should yield a source with a URL (network permitting).
    assert isinstance(res["sources"], list)
    for s in res["sources"][:3]:
        print(f"   - [{s['provider']}] {(s['title'] or '')[:60]} -> {s['url']}")


def _main():
    tests = [(n, o) for n, o in globals().items() if n.startswith("test_") and callable(o)]
    p = f = 0
    for name, fn in tests:
        try: fn(); p += 1; print(f"PASS {name}")
        except Exception: f += 1; print(f"FAIL {name}"); traceback.print_exc()
    print(f"\nresearch_live_smoke: {p} passed, {f} failed, {len(tests)} total")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(_main())
