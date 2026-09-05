"""Multi-provider research aggregation: topic-aware selection, dedup, ranking.

Pure/deterministic (given provider functions) so it is fully unit-testable with
mocked providers and no network. Used by the Research Agent.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

from . import research_providers as P

# Topic keyword hints -> which providers to consult (topic-aware selection).
_BIO_HINTS = re.compile(
    r"(?i)\b(medic\w*|clinical|patient|disease|cancer|tumou?r|gene\w*|protein|"
    r"biolog\w*|health\w*|therap\w*|drug|vaccine|covid|neuro\w*|cardio\w*|"
    r"diabet\w*|pharma\w*|immun\w*|surg\w*|epidem\w*)\b"
)
_CS_HINTS = re.compile(
    r"(?i)\b(machine learning|deep learning|neural|transformer|algorithm|"
    r"computer|software|dataset|nlp|llm|reinforcement|comput\w*|ai\b|"
    r"artificial intelligence|robot\w*|quantum comput\w*)\b"
)

ProviderFn = Callable[[str, int], List[Dict[str, Any]]]

# Default provider registry (name -> callable). Injectable for tests.
DEFAULT_PROVIDERS: Dict[str, ProviderFn] = {
    "openalex": P.fetch_openalex,
    "crossref": P.fetch_crossref,
    "arxiv": P.fetch_arxiv,
    "pubmed": P.fetch_pubmed,
    "ddgs": P.fetch_ddgs,
}

# Credibility weight per source type (used in ranking; scholarly > web).
_TYPE_WEIGHT = {"scholarly": 1.0, "preprint": 0.85, "web": 0.5}
# Provider tie-break preference.
_PROVIDER_WEIGHT = {"OpenAlex": 1.0, "PubMed": 0.98, "Crossref": 0.95,
                    "arXiv": 0.9, "DDGS": 0.4}


def select_providers(query: str) -> List[str]:
    """Choose relevant providers for the query (avoids querying everything)."""
    q = query or ""
    if _BIO_HINTS.search(q):
        return ["pubmed", "openalex", "crossref", "ddgs"]
    if _CS_HINTS.search(q):
        return ["openalex", "arxiv", "crossref", "ddgs"]
    # General/academic default: scholarly + discovery fallback.
    return ["openalex", "crossref", "ddgs"]


def _norm_title(t: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def _dedup_key(s: Dict[str, Any]) -> str:
    doi = (s.get("doi") or "").lower().strip()
    if doi:
        return f"doi:{doi}"
    ident = (s.get("identifier") or "").lower().strip()
    if ident:
        return f"id:{ident}"
    url = (s.get("url") or "").lower().strip().rstrip("/")
    if url:
        return f"url:{url}"
    return f"title:{_norm_title(s.get('title'))}"


def deduplicate(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Dedup by DOI, provider identifier, canonical URL, then normalized title.

    Keeps the first (higher-priority) occurrence; merges in metadata that the
    kept record is missing from the duplicate (never overwrites present values).
    """
    seen: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    # also track title keys to catch cross-provider title dupes without DOI
    title_index: Dict[str, str] = {}
    for s in sources:
        key = _dedup_key(s)
        tkey = _norm_title(s.get("title"))
        existing_key = seen and title_index.get(tkey)
        if key in seen:
            _merge_into(seen[key], s)
            continue
        if tkey and existing_key and existing_key in seen:
            _merge_into(seen[existing_key], s)
            continue
        seen[key] = dict(s)
        order.append(key)
        if tkey:
            title_index.setdefault(tkey, key)
    return [seen[k] for k in order]


def _merge_into(keep: Dict[str, Any], other: Dict[str, Any]) -> None:
    for f in ("authors", "publication_date", "year", "doi", "identifier",
              "abstract", "snippet", "url"):
        if not keep.get(f) and other.get(f):
            keep[f] = other[f]


def _relevance(query: str, s: Dict[str, Any]) -> float:
    """Deterministic relevance: term overlap in title/abstract x credibility."""
    q_terms = set(_norm_title(query).split())
    if not q_terms:
        overlap = 0.0
    else:
        text = _norm_title(f"{s.get('title') or ''} {s.get('abstract') or s.get('snippet') or ''}")
        t_terms = set(text.split())
        overlap = len(q_terms & t_terms) / len(q_terms)
    cred = _TYPE_WEIGHT.get(s.get("source_type"), 0.5)
    prov = _PROVIDER_WEIGHT.get(s.get("provider"), 0.5)
    has_meta = 1.0 + (0.1 if s.get("doi") else 0.0) + (0.05 if s.get("abstract") else 0.0)
    return round(overlap * 0.6 + cred * 0.3 + prov * 0.1, 4) * has_meta


def rank(query: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for s in sources:
        s["relevance_score"] = round(_relevance(query, s), 4)
    return sorted(sources, key=lambda s: s["relevance_score"], reverse=True)


def collect(
    query: str,
    per_provider: int = 5,
    target: int = 5,
    providers: Optional[Dict[str, ProviderFn]] = None,
    provider_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run selected providers, aggregate, dedup, rank. Providers fail independently.

    Returns {sources, providers_used, providers_failed, provider_counts}.
    """
    registry = providers or DEFAULT_PROVIDERS
    names = provider_names or select_providers(query)
    aggregated: List[Dict[str, Any]] = []
    used: List[str] = []
    failed: List[str] = []
    counts: Dict[str, int] = {}
    for name in names:
        fn = registry.get(name)
        if fn is None:
            continue
        try:
            rows = fn(query, per_provider) or []
        except Exception:  # noqa: BLE001 - isolate provider failure
            failed.append(name)
            continue
        if rows:
            used.append(name)
            counts[name] = len(rows)
            aggregated.extend(rows)
        else:
            # empty is not a failure, just no hits
            used.append(name)
            counts[name] = 0
    deduped = deduplicate(aggregated)
    ranked = rank(query, deduped)
    return {
        "sources": ranked[:max(target, 5)] if ranked else [],
        "providers_used": used,
        "providers_failed": failed,
        "provider_counts": counts,
    }
