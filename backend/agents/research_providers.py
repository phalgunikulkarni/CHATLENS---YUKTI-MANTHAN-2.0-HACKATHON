"""Scholarly + general research providers for the Research Agent.

Provider-based pipeline (NO new agent): each provider fetches and NORMALIZES to
a common Source dict. Every provider fails INDEPENDENTLY (bounded timeout, never
raises out) so one outage cannot crash research. No paid API; only:

  - OpenAlex  (optional OPENALEX_API_KEY via env; works without a key too)
  - Crossref  (public REST, no key)
  - arXiv     (public Atom API, no key)
  - PubMed    (NCBI E-utilities, no key for low volume)
  - DDGS      (existing general-web discovery fallback)

Secrets: OPENALEX_API_KEY is read from the environment only, never hard-coded,
never logged, never returned to callers.
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import requests

_TIMEOUT = 8.0            # bounded per-request timeout
_MAILTO = os.getenv("CHATLENS_RESEARCH_MAILTO", "chatlens@example.org")


def _source(
    *, title, url, provider, source_type,
    authors=None, publication_date=None, year=None, doi=None,
    identifier=None, abstract=None, snippet=None, relevance_score=None,
) -> Dict[str, Any]:
    """Build a normalized source record. Missing metadata stays None (never guessed)."""
    return {
        "title": (title or None),
        "url": (url or None),
        "provider": provider,
        "source_type": source_type,
        "authors": authors or [],
        "publication_date": publication_date,
        "year": year,
        "doi": doi,
        "identifier": identifier,
        "abstract": abstract,
        "snippet": snippet,
        "relevance_score": relevance_score,
    }


def _clean(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = re.sub(r"<[^>]+>", " ", str(text))     # strip any HTML/JATS tags
    t = re.sub(r"\s+", " ", t).strip()
    return t or None


def _year_from_date(d: Optional[str]) -> Optional[int]:
    if not d:
        return None
    m = re.match(r"(\d{4})", str(d))
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# OpenAlex
# ---------------------------------------------------------------------------
def fetch_openalex(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    try:
        params = {"search": query, "per-page": max(1, min(limit, 10)), "mailto": _MAILTO}
        headers = {"User-Agent": f"ChatLens/1.0 (mailto:{_MAILTO})"}
        api_key = os.getenv("OPENALEX_API_KEY")
        if api_key:
            params["api_key"] = api_key  # never logged/returned
        resp = requests.get("https://api.openalex.org/works", params=params,
                            headers=headers, timeout=_TIMEOUT)
        if resp.status_code >= 400:
            return []
        data = resp.json()
    except Exception:  # noqa: BLE001 - provider fails independently
        return []
    out: List[Dict[str, Any]] = []
    for w in (data or {}).get("results", [])[:limit]:
        authors = [
            (a.get("author") or {}).get("display_name")
            for a in (w.get("authorships") or [])
        ]
        authors = [a for a in authors if a]
        doi = w.get("doi")
        if doi and doi.startswith("https://doi.org/"):
            doi = doi[len("https://doi.org/"):]
        url = w.get("doi") or (w.get("primary_location") or {}).get("landing_page_url") or w.get("id")
        out.append(_source(
            title=w.get("display_name"), url=url, provider="OpenAlex",
            source_type="scholarly", authors=authors,
            publication_date=w.get("publication_date"),
            year=w.get("publication_year") or _year_from_date(w.get("publication_date")),
            doi=doi, identifier=w.get("id"),
            abstract=_reconstruct_openalex_abstract(w.get("abstract_inverted_index")),
        ))
    return out


def _reconstruct_openalex_abstract(inv: Optional[Dict[str, List[int]]]) -> Optional[str]:
    if not inv or not isinstance(inv, dict):
        return None
    positions: List[tuple] = []
    for word, idxs in inv.items():
        for i in idxs:
            positions.append((i, word))
    if not positions:
        return None
    positions.sort(key=lambda x: x[0])
    return _clean(" ".join(w for _, w in positions))


# ---------------------------------------------------------------------------
# Crossref
# ---------------------------------------------------------------------------
def fetch_crossref(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    try:
        params = {"query": query, "rows": max(1, min(limit, 10)), "mailto": _MAILTO}
        headers = {"User-Agent": f"ChatLens/1.0 (mailto:{_MAILTO})"}
        resp = requests.get("https://api.crossref.org/works", params=params,
                            headers=headers, timeout=_TIMEOUT)
        if resp.status_code >= 400:
            return []
        data = resp.json()
    except Exception:  # noqa: BLE001
        return []
    out: List[Dict[str, Any]] = []
    for it in ((data or {}).get("message") or {}).get("items", [])[:limit]:
        title_list = it.get("title") or []
        title = title_list[0] if title_list else None
        authors = []
        for a in it.get("author") or []:
            name = " ".join(x for x in [a.get("given"), a.get("family")] if x)
            if name:
                authors.append(name)
        container = it.get("container-title") or []
        publisher = container[0] if container else it.get("publisher")
        # date parts
        dp = ((it.get("issued") or {}).get("date-parts") or [[None]])[0]
        year = dp[0] if dp and dp[0] else None
        pub_date = "-".join(str(x).zfill(2) for x in dp if x) if dp and dp[0] else None
        doi = it.get("DOI")
        url = it.get("URL") or (f"https://doi.org/{doi}" if doi else None)
        out.append(_source(
            title=_clean(title), url=url, provider="Crossref",
            source_type="scholarly", authors=authors,
            publication_date=pub_date, year=year, doi=doi, identifier=doi,
            abstract=_clean(it.get("abstract")), snippet=publisher,
        ))
    return out


# ---------------------------------------------------------------------------
# arXiv (Atom XML)
# ---------------------------------------------------------------------------
_ATOM = "{http://www.w3.org/2005/Atom}"


def fetch_arxiv(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    try:
        params = {"search_query": f"all:{query}", "start": 0,
                  "max_results": max(1, min(limit, 10))}
        resp = requests.get("http://export.arxiv.org/api/query", params=params,
                            timeout=_TIMEOUT)
        if resp.status_code >= 400:
            return []
        root = ET.fromstring(resp.text)
    except Exception:  # noqa: BLE001
        return []
    out: List[Dict[str, Any]] = []
    for entry in root.findall(f"{_ATOM}entry")[:limit]:
        title = _clean((entry.findtext(f"{_ATOM}title")))
        summary = _clean(entry.findtext(f"{_ATOM}summary"))
        published = entry.findtext(f"{_ATOM}published")
        arxiv_id = entry.findtext(f"{_ATOM}id")
        authors = [a.findtext(f"{_ATOM}name") for a in entry.findall(f"{_ATOM}author")]
        authors = [a for a in authors if a]
        out.append(_source(
            title=title, url=arxiv_id, provider="arXiv", source_type="preprint",
            authors=authors, publication_date=(published or "")[:10],
            year=_year_from_date(published), identifier=arxiv_id, abstract=summary,
        ))
    return out


# ---------------------------------------------------------------------------
# PubMed (NCBI E-utilities: esearch -> esummary)
# ---------------------------------------------------------------------------
def fetch_pubmed(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    try:
        es = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={"db": "pubmed", "term": query, "retmode": "json",
                    "retmax": max(1, min(limit, 10))},
            timeout=_TIMEOUT,
        )
        if es.status_code >= 400:
            return []
        ids = (((es.json() or {}).get("esearchresult") or {}).get("idlist") or [])[:limit]
        if not ids:
            return []
        summ = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
            timeout=_TIMEOUT,
        )
        if summ.status_code >= 400:
            return []
        result = (summ.json() or {}).get("result") or {}
    except Exception:  # noqa: BLE001
        return []
    out: List[Dict[str, Any]] = []
    for pmid in ids:
        rec = result.get(pmid) or {}
        if not rec:
            continue
        authors = [a.get("name") for a in (rec.get("authors") or []) if a.get("name")]
        pubdate = rec.get("pubdate")
        out.append(_source(
            title=_clean(rec.get("title")),
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            provider="PubMed", source_type="scholarly", authors=authors,
            publication_date=pubdate, year=_year_from_date(pubdate),
            doi=(rec.get("elocationid") or "").replace("doi: ", "") or None,
            identifier=f"PMID:{pmid}", snippet=rec.get("source"),
        ))
    return out


# ---------------------------------------------------------------------------
# DDGS general-web discovery fallback (reuses existing web_search seam)
# ---------------------------------------------------------------------------
def fetch_ddgs(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    try:
        from . import web_search
        rows = web_search.ddgs_text_search(query, max_results=max(1, min(limit, 10)))
    except Exception:  # noqa: BLE001 - includes SearchError; provider-independent
        return []
    out: List[Dict[str, Any]] = []
    for r in rows or []:
        out.append(_source(
            title=r.get("title"), url=r.get("url"), provider="DDGS",
            source_type="web", snippet=r.get("snippet"),
        ))
    return out
