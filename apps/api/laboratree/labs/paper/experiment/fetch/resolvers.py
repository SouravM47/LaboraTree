"""Deterministic web resolvers for the dataset auto-fetch chain (zero LLM tokens).

Papers usually cite datasets by NAME ("UCI Chronic Kidney Disease dataset") without a direct
file link. These resolvers search public registries (OpenML, UCI) by name and, on a confident
match, download the data and normalize it to CSV.

Frugality contract (module-wide):
- >= 1.5s between any two outbound HTTP requests (module-level throttle),
- <= 6 HTTP requests per ``try_fetch`` call (per-call budget),
- 20s timeout and a 25 MB response cap per request (Content-Length + streamed),
- polite User-Agent, at most one retry (transport errors only),
- return None on any doubt — the chain's manual-upload fallback stays the honest default.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import threading
import time
from urllib.parse import quote

log = logging.getLogger(__name__)

USER_AGENT = "Laboratree/0.1 (dataset resolver)"
REQUEST_TIMEOUT = 20.0
MAX_RESPONSE_BYTES = 25 * 1024 * 1024
MIN_REQUEST_INTERVAL = 1.5
MAX_REQUESTS_PER_RESOLVE = 6

_throttle_lock = threading.Lock()
_last_request_at = 0.0


def _throttle() -> None:
    """Sleep so that outbound requests are spaced >= MIN_REQUEST_INTERVAL apart, module-wide."""
    global _last_request_at
    with _throttle_lock:
        wait = MIN_REQUEST_INTERVAL - (time.monotonic() - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()


class _Budget:
    """Per-resolve() cap on outbound HTTP requests."""

    def __init__(self, limit: int = MAX_REQUESTS_PER_RESOLVE) -> None:
        self.remaining = limit

    def spend(self) -> bool:
        if self.remaining <= 0:
            return False
        self.remaining -= 1
        return True


def _http_get(url: str, budget: _Budget, _retry: bool = True) -> bytes | None:
    """One rate-limited, size-capped GET. Returns body bytes or None. Never raises."""
    import httpx

    if not budget.spend():
        log.info("request budget exhausted; skipping %s", url)
        return None
    _throttle()
    try:
        with httpx.stream(
            "GET",
            url,
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as resp:
            if resp.status_code != 200:
                log.debug("GET %s -> HTTP %s", url, resp.status_code)
                return None
            length = resp.headers.get("content-length", "")
            if length.isdigit() and int(length) > MAX_RESPONSE_BYTES:
                log.info("GET %s: Content-Length %s exceeds %s cap; aborting", url, length, MAX_RESPONSE_BYTES)
                return None
            chunks: list[bytes] = []
            total = 0
            for chunk in resp.iter_bytes():
                total += len(chunk)
                if total > MAX_RESPONSE_BYTES:
                    log.info("GET %s: body exceeded %s-byte cap mid-stream; aborting", url, MAX_RESPONSE_BYTES)
                    return None
                chunks.append(chunk)
            return b"".join(chunks)
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        log.debug("GET %s transport failure: %s", url, exc)
        if _retry:  # at most one retry; it still spends request budget
            return _http_get(url, budget, _retry=False)
        return None
    except Exception as exc:
        log.debug("GET %s failed: %s", url, exc)
        return None


def _get_json(url: str, budget: _Budget):
    raw = _http_get(url, budget)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except Exception as exc:
        log.debug("non-JSON response from %s: %s", url, exc)
        return None


# --- name handling -------------------------------------------------------------------------

_STOPWORDS = {"dataset", "data", "set", "the", "a", "an", "uci", "benchmark", "corpus", "repository", "database"}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _slug_candidates(name: str) -> list[str]:
    """Slug variants to try against a registry: as-is, stopwords dropped, hyphenated."""
    full = _slug(name)
    trimmed = "_".join(w for w in full.split("_") if w not in _STOPWORDS)
    out: list[str] = []
    for cand in (full, trimmed, trimmed.replace("_", "-")):
        if cand and cand not in out:
            out.append(cand)
    return out[:3]


def _name_matches(slug: str, candidate_name: str) -> bool:
    """Exact-ish match: equal after normalization, or one is a word-boundary phrase of the other."""
    cand = _slug(candidate_name)
    query = _slug(slug)
    if not cand or not query:
        return False
    return f"_{query}_" in f"_{cand}_" or f"_{cand}_" in f"_{query}_"


# --- format handling -----------------------------------------------------------------------


def _looks_like_csv(data: bytes) -> bool:
    """Cheap sanity check that bytes are a plausible multi-column CSV (not HTML/JSON/binary)."""
    if not data:
        return False
    head = data[:4096]
    if b"\x00" in head:
        return False
    stripped = head.lstrip()
    if stripped[:1] in (b"<", b"{", b"["):
        return False
    text = stripped.decode("utf-8", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return len(lines) >= 2 and "," in lines[0]


def _looks_like_arff(data: bytes) -> bool:
    head = data[:4096].decode("utf-8", errors="replace").lower()
    return "@relation" in head or "@attribute" in head


def _arff_to_csv(raw: bytes) -> bytes | None:
    """Small dependency-light ARFF -> CSV conversion (dense ARFF only; sparse returns None)."""
    text = raw.decode("utf-8", errors="replace")
    columns: list[str] = []
    data_lines: list[str] = []
    in_data = False
    attr_re = re.compile(r"@attribute\s+(?:'([^']+)'|\"([^\"]+)\"|(\S+))", re.IGNORECASE)
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("%"):
            continue
        if not in_data:
            low = stripped.lower()
            if low.startswith("@attribute"):
                m = attr_re.match(stripped)
                if m:
                    columns.append(m.group(1) or m.group(2) or m.group(3))
            elif low.startswith("@data"):
                in_data = True
        else:
            if stripped.startswith("{"):
                log.debug("sparse ARFF encountered; refusing to guess a dense conversion")
                return None
            data_lines.append(stripped)
    if not columns or not data_lines:
        return None
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(columns)
    kept = 0
    for row in csv.reader(data_lines, quotechar="'", skipinitialspace=True):
        if len(row) != len(columns):
            continue  # malformed line — skip, don't guess
        writer.writerow(["" if cell.strip() == "?" else cell for cell in row])
        kept += 1
    if kept == 0 or kept < len(data_lines) // 2:
        log.debug("ARFF conversion kept %s/%s rows; not confident enough", kept, len(data_lines))
        return None
    return buf.getvalue().encode("utf-8")


# --- resolvers ------------------------------------------------------------------------------


class OpenMLResolver:
    """Resolves a dataset cited by NAME via the OpenML registry (no API key) and returns CSV."""

    name = "openml"
    SEARCH_URL = "https://www.openml.org/api/v1/json/data/list/data_name/{slug}/limit/5"
    DESC_URL = "https://www.openml.org/api/v1/json/data/{did}"

    def try_fetch(self, ref) -> "FetchResult | None":  # noqa: F821 - resolved at runtime below
        budget = _Budget()
        try:
            return self._resolve(ref, budget)
        except Exception:
            log.exception("openml resolver failed for %r", ref.name)
            return None

    def _resolve(self, ref, budget: _Budget):
        from laboratree.labs.paper.experiment.fetch import FetchResult

        for slug in _slug_candidates(ref.name):
            payload = _get_json(self.SEARCH_URL.format(slug=quote(slug, safe="")), budget)
            if not isinstance(payload, dict):
                continue
            datasets = ((payload.get("data") or {}).get("dataset")) or []
            best = self._pick(slug, datasets)
            if best is None:
                continue
            did = str(best.get("did", "")).strip()
            if not did.isdigit():
                continue
            desc_payload = _get_json(self.DESC_URL.format(did=did), budget)
            desc = (desc_payload or {}).get("data_set_description") or {}
            file_url = desc.get("url")
            if not file_url:
                log.debug("openml did=%s has no downloadable url", did)
                continue
            raw = _http_get(file_url, budget)
            if raw is None:
                continue
            fmt = str(desc.get("format", "")).lower()
            if "arff" in fmt or file_url.lower().endswith(".arff") or _looks_like_arff(raw):
                csv_bytes = _arff_to_csv(raw)
            elif _looks_like_csv(raw):
                csv_bytes = raw
            else:
                csv_bytes = None
            if csv_bytes is not None and _looks_like_csv(csv_bytes):
                log.info("openml resolved %r -> did=%s (%s)", ref.name, did, best.get("name"))
                return FetchResult(
                    ref, csv_bytes, f"{_slug(ref.name)}.csv", self.name, f"https://www.openml.org/d/{did}"
                )
        return None

    def _pick(self, slug: str, datasets: list) -> dict | None:
        matches = [
            d for d in datasets if isinstance(d, dict) and _name_matches(slug, str(d.get("name", "")))
        ]
        if not matches:
            return None

        def rank(d: dict):
            exact = _slug(str(d.get("name", ""))) == _slug(slug)
            active = str(d.get("status", "")).lower() == "active"
            did = str(d.get("did", ""))
            return (not exact, not active, int(did) if did.isdigit() else 1 << 30)

        return sorted(matches, key=rank)[0]


class UCIResolver:
    """Resolves a dataset cited by NAME via the UCI ML Repository JSON API; CSV only, no guessing."""

    name = "uci"
    # NOTE: probed live — "api/datasets?search=" 404s; the JSON search API is "api/datasets/list".
    # It returns {"status": 200, "data": [{"id": 336, "name": "Chronic Kidney Disease"}, ...]}.
    SEARCH_URL = "https://archive.ics.uci.edu/api/datasets/list?search={query}"
    STATIC_CSV_URL = "https://archive.ics.uci.edu/static/public/{id}/data.csv"

    def try_fetch(self, ref) -> "FetchResult | None":  # noqa: F821 - resolved at runtime below
        budget = _Budget()
        try:
            return self._resolve(ref, budget)
        except Exception:
            log.exception("uci resolver failed for %r", ref.name)
            return None

    def _resolve(self, ref, budget: _Budget):
        from laboratree.labs.paper.experiment.fetch import FetchResult

        raw_query = re.sub(r"\s+", " ", ref.name).strip()
        trimmed_query = " ".join(w for w in raw_query.split(" ") if w.lower() not in _STOPWORDS)
        queries: list[str] = []
        for q in (raw_query, trimmed_query):
            if q and q not in queries:
                queries.append(q)

        for query in queries:
            payload = _get_json(self.SEARCH_URL.format(query=quote(query, safe="")), budget)
            hits = _find_hit_list(payload)
            best = self._pick(query, hits)
            if best is None:
                continue
            for url in self._candidate_urls(best):
                data = _http_get(url, budget)
                if data is not None and _looks_like_csv(data):
                    log.info("uci resolved %r -> %s (%s)", ref.name, url, best.get("name"))
                    return FetchResult(ref, data, f"{_slug(ref.name)}.csv", self.name, url)
        return None

    def _pick(self, query: str, hits: list) -> dict | None:
        matches = [d for d in hits if _name_matches(query, str(d.get("name", "")))]
        if not matches:
            return None

        def rank(d: dict):
            exact = _slug(str(d.get("name", ""))) == _slug(query)
            return (not exact,)

        return sorted(matches, key=rank)[0]

    def _candidate_urls(self, hit: dict) -> list[str]:
        urls: list[str] = []
        data_url = str(hit.get("data_url") or "").strip()
        if data_url.lower().startswith("http") and ".csv" in data_url.lower().split("?")[0]:
            urls.append(data_url)
        ds_id = str(hit.get("id", "")).strip()
        if ds_id.isdigit():
            urls.append(self.STATIC_CSV_URL.format(id=ds_id))
        return urls


def _find_hit_list(node) -> list[dict]:
    """Defensively locate a list of dataset dicts (having a 'name') in an unknown JSON shape."""
    if isinstance(node, list):
        return [d for d in node if isinstance(d, dict) and d.get("name") is not None]
    if isinstance(node, dict):
        for value in node.values():
            found = _find_hit_list(value)
            if found:
                return found
    return []
