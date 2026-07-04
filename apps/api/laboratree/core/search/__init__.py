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


__all__ = ["SearchHit", "search_available", "web_search"]
