"""Web search — one client, reused everywhere (dataset auto-fetch, and the Ideation Lab's
evidence/data discovery).

Provider order follows ``settings.web_search_provider``: **Brave** first (fast, cheap, good for
open-web coverage), **SerpAPI** as a fallback (Google-quality when Brave misses). Keys live only in
the gitignored ``.env``. All failures degrade to an empty list — search is best-effort, never fatal.

Frugality: one HTTP call per provider attempt, short timeout, capped result count. Synchronous
(callers run it via ``asyncio.to_thread`` when inside the event loop).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..config import settings

log = logging.getLogger(__name__)

_TIMEOUT = 12.0
_USER_AGENT = "Laboratree/0.1 (research assistant)"


@dataclass
class SearchHit:
    title: str
    url: str
    description: str = ""
    source: str = ""  # which provider returned it


def _brave(query: str, count: int) -> list[SearchHit]:
    import httpx

    key = settings.brave_search_api_key
    if not key:
        return []
    try:
        resp = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": min(count, 20)},
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": key,
                "User-Agent": _USER_AGENT,
            },
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            log.info("brave search HTTP %s for %r", resp.status_code, query)
            return []
        results = ((resp.json() or {}).get("web") or {}).get("results") or []
        return [
            SearchHit(
                title=str(r.get("title", "")),
                url=str(r.get("url", "")),
                description=str(r.get("description", "")),
                source="brave",
            )
            for r in results
            if r.get("url")
        ][:count]
    except Exception as exc:  # network/JSON — never fatal
        log.info("brave search failed for %r: %s", query, exc)
        return []


def _serpapi(query: str, count: int) -> list[SearchHit]:
    import httpx

    key = settings.serpapi_key
    if not key:
        return []
    try:
        resp = httpx.get(
            "https://serpapi.com/search.json",
            params={"engine": "google", "q": query, "num": min(count, 20), "api_key": key},
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            log.info("serpapi HTTP %s for %r", resp.status_code, query)
            return []
        organic = (resp.json() or {}).get("organic_results") or []
        return [
            SearchHit(
                title=str(r.get("title", "")),
                url=str(r.get("link", "")),
                description=str(r.get("snippet", "")),
                source="serpapi",
            )
            for r in organic
            if r.get("link")
        ][:count]
    except Exception as exc:
        log.info("serpapi failed for %r: %s", query, exc)
        return []


_PROVIDERS = {"brave": _brave, "serpapi": _serpapi}


def web_search(query: str, count: int | None = None) -> list[SearchHit]:
    """Search the open web. Tries the configured provider first, then the other as a fallback.
    Returns [] if search is disabled (`web_search_provider="none"`) or no key is set."""
    provider = (settings.web_search_provider or "none").lower()
    if provider == "none":
        return []
    n = count or settings.web_search_max_results
    order = [provider] + [p for p in _PROVIDERS if p != provider]
    for name in order:
        fn = _PROVIDERS.get(name)
        if fn is None:
            continue
        hits = fn(query, n)
        if hits:
            return hits
    return []


def search_available() -> bool:
    """True when at least one provider has a key configured (so callers can offer the feature)."""
    if (settings.web_search_provider or "none").lower() == "none":
        return False
    return bool(settings.brave_search_api_key or settings.serpapi_key)


# ---- scholarly search: real journals/studies from free academic databases (no API key) ----------


def _openalex_abstract(inv: dict | None) -> str:
    """OpenAlex ships abstracts as an inverted index {word: [positions]} (a copyright dodge) —
    reconstruct the running text from it."""
    if not inv:
        return ""
    positions: dict[int, str] = {}
    for word, idxs in inv.items():
        for i in idxs:
            positions[i] = word
    return " ".join(positions[i] for i in sorted(positions))[:600]


def openalex_search(query: str, count: int) -> list[SearchHit]:
    """Search OpenAlex (openalex.org) — a free, keyless scholarly graph spanning ALL disciplines
    (incl. social science), with abstracts. The strongest evidence source for the deep agent."""
    import httpx

    try:
        mailto = settings.openalex_mailto or "hello@laboratree.dev"  # OpenAlex "polite pool"
        resp = httpx.get(
            "https://api.openalex.org/works",
            params={"search": query, "per_page": min(count, 25), "mailto": mailto},
            headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            log.info("openalex HTTP %s for %r", resp.status_code, query)
            return []
        hits: list[SearchHit] = []
        for r in (resp.json() or {}).get("results") or []:
            title = r.get("title") or ""
            url = r.get("doi") or r.get("id") or ""
            if not (title and url):
                continue
            year = r.get("publication_year")
            venue = ((r.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
            abstract = _openalex_abstract(r.get("abstract_inverted_index"))
            meta = " · ".join(x for x in [str(year) if year else "", venue] if x)
            hits.append(SearchHit(
                title=title, url=url,
                description=(f"{meta}. {abstract}" if meta else abstract) or venue,
                source="openalex",
            ))
        return hits[:count]
    except Exception as exc:
        log.info("openalex failed for %r: %s", query, exc)
        return []


def semantic_scholar_search(query: str, count: int) -> list[SearchHit]:
    """Search Semantic Scholar (200M+ papers) via its free REST API — includes TLDRs (one-line AI
    summaries) that sharpen the evidence synthesis. Keyless works but is rate-limited (429s degrade
    to []); an optional API key raises the limit. No MCP runtime needed."""
    import httpx

    if not settings.semantic_scholar_enabled:
        return []
    headers = {"User-Agent": _USER_AGENT}
    if settings.semantic_scholar_api_key:
        headers["x-api-key"] = settings.semantic_scholar_api_key
    try:
        resp = httpx.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": query, "limit": min(count, 20),
                    "fields": "title,abstract,year,venue,externalIds,tldr,url"},
            headers=headers, timeout=_TIMEOUT,
        )
        if resp.status_code != 200:  # 429 (rate limit) etc. — never fatal
            log.info("semantic scholar HTTP %s for %r", resp.status_code, query)
            return []
        hits: list[SearchHit] = []
        for r in (resp.json() or {}).get("data") or []:
            title = r.get("title") or ""
            doi = (r.get("externalIds") or {}).get("DOI")
            url = f"https://doi.org/{doi}" if doi else (r.get("url") or "")
            if not (title and url):
                continue
            tldr = (r.get("tldr") or {}).get("text") or ""
            body = tldr or (r.get("abstract") or "")
            meta = " · ".join(str(x) for x in [r.get("year"), r.get("venue")] if x)
            hits.append(SearchHit(
                title=title, url=url,
                description=(f"{meta}. {body}" if meta else body)[:600] or (r.get("venue") or ""),
                source="semantic_scholar",
            ))
        return hits[:count]
    except Exception as exc:
        log.info("semantic scholar failed for %r: %s", query, exc)
        return []


def _doi_key(url: str) -> str:
    """Normalize a URL to a DOI (lowercased) when possible, so the same paper from OpenAlex and
    Semantic Scholar dedupes to one source."""
    low = (url or "").lower()
    if "doi.org/" in low:
        return low.split("doi.org/", 1)[1].strip("/")
    return low


def research_search(query: str, count: int | None = None) -> list[SearchHit]:
    """Evidence search for the Ideation deep agent: real papers first (OpenAlex + Semantic Scholar —
    both keyless), then the open web (Brave→SerpAPI) to fill in. Deduped by DOI. Works even with NO
    web key, since the scholarly sources need none."""
    n = count or settings.web_search_max_results
    hits: list[SearchHit] = []
    seen: set[str] = set()
    # scholarly sources first (papers), then web to fill any gap
    for provider in (openalex_search, semantic_scholar_search, lambda q, c: web_search(q, c)):
        if len(hits) >= n:
            break
        for h in provider(query, n):
            key = _doi_key(h.url)
            if key and key not in seen:
                hits.append(h)
                seen.add(key)
            if len(hits) >= n:
                break
    return hits[:n]


def research_available() -> bool:
    """Scholarly evidence is available whenever a keyless academic source is on, or a web key exists."""
    return settings.openalex_enabled or settings.semantic_scholar_enabled or search_available()


def _extract_doi(url: str) -> str | None:
    low = (url or "").lower()
    if "doi.org/" in low:
        return url.split("doi.org/", 1)[1].strip("/")
    if low.startswith("10."):
        return url
    return None


def _openalex_oa_pdf(ident: str) -> str | None:
    import httpx

    try:
        resp = httpx.get(
            f"https://api.openalex.org/works/{ident}",
            params={"mailto": settings.openalex_mailto or "hello@laboratree.dev"},
            headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            return None
        w = resp.json() or {}
        loc = w.get("best_oa_location") or {}
        return loc.get("pdf_url") or (w.get("open_access") or {}).get("oa_url")
    except Exception:
        return None


def _unpaywall_oa_pdf(doi: str) -> str | None:
    import httpx

    try:
        resp = httpx.get(
            f"https://api.unpaywall.org/v2/{doi}",
            params={"email": settings.openalex_mailto or "hello@laboratree.dev"},
            headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            return None
        loc = (resp.json() or {}).get("best_oa_location") or {}
        return loc.get("url_for_pdf") or loc.get("url")
    except Exception:
        return None


def open_access_pdf(url: str) -> str | None:
    """Resolve a paper URL/DOI to a directly-downloadable OPEN-ACCESS PDF. Tries, in order: the URL
    itself if it's already a PDF/arXiv, OpenAlex's OA locations, then Unpaywall (broader coverage).
    Returns None only when the paper is genuinely paywalled with no free full text."""
    low = (url or "").lower().split("?")[0]
    # 0) the source link is already full text
    if low.endswith(".pdf"):
        return url
    if "arxiv.org/abs/" in low:
        return url.replace("/abs/", "/pdf/")            # arXiv abstract page → its PDF (redirects)
    if "/pmc/articles/" in low or "ncbi.nlm.nih.gov/pmc" in low:
        return url.rstrip("/") + "/pdf/"

    ident = url.rstrip("/").split("/")[-1] if "openalex.org/" in low else None
    doi = _extract_doi(url)
    if not ident and doi:
        ident = f"doi:{doi}"

    if ident:
        pdf = _openalex_oa_pdf(ident)
        if pdf:
            return pdf
    if doi:  # OpenAlex missed → Unpaywall often still has an OA copy
        pdf = _unpaywall_oa_pdf(doi)
        if pdf:
            return pdf
    return None


# Hosts that commonly serve a raw, directly-downloadable data file.
_RAW_DATA_HOSTS = (
    "raw.githubusercontent.com", "zenodo.org", "figshare.com", "ndownloader.figshare.com",
    "data.gov", "gist.githubusercontent.com", "media.githubusercontent.com",
    "storage.googleapis.com", "s3.amazonaws.com", "ourworldindata.org",
)
_DATA_SUFFIX = (".csv", ".tsv", ".data", ".xlsx", ".xls", ".json", ".parquet")


def looks_like_data_url(url: str) -> bool:
    """Heuristic: does this URL point at a directly-downloadable data file (vs a portal/article)?
    Shared by the dataset fetch resolver and the Ideation data hunt."""
    low = (url or "").lower().split("?")[0]
    if low.endswith(_DATA_SUFFIX):
        return True
    host = low.split("//")[-1].split("/")[0]
    return any(h in host for h in _RAW_DATA_HOSTS)


__all__ = [
    "SearchHit",
    "looks_like_data_url",
    "open_access_pdf",
    "openalex_search",
    "research_available",
    "research_search",
    "search_available",
    "semantic_scholar_search",
    "web_search",
]
