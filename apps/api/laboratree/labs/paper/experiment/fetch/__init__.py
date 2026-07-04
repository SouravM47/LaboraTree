"""Auto data-fetch agent — try hard to retrieve a paper's datasets; hand off to a human when not.

Design: a chain of pluggable Resolvers. The agent tries each; the first that returns bytes wins.
Anything unresolved becomes explicit, honest HITL guidance (exact source + manual steps) — never a
fake success.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

CompleteFn = Callable[[str, str], str]

_URL_RE = re.compile(r"https?://[^\s)\"'>]+", re.IGNORECASE)
_DATA_EXT = (".csv", ".tsv", ".xlsx", ".xls", ".json", ".zip", ".parquet", ".data")


@dataclass
class DatasetRef:
    name: str
    url: str | None = None
    source: str | None = None
    description: str = ""


@dataclass
class FetchResult:
    ref: DatasetRef
    data: bytes
    filename: str
    resolver: str
    source: str


@dataclass
class Guidance:
    name: str
    reason: str
    source: str | None
    url: str | None
    instructions: str


@dataclass
class FetchOutcome:
    fetched: list[FetchResult] = field(default_factory=list)
    unresolved: list[Guidance] = field(default_factory=list)

    @property
    def needs_human(self) -> bool:
        return len(self.unresolved) > 0


@runtime_checkable
class Resolver(Protocol):
    name: str

    def try_fetch(self, ref: DatasetRef) -> FetchResult | None: ...


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


class SklearnToyResolver:
    """Resolves well-known toy datasets bundled with scikit-learn (fully offline)."""

    name = "sklearn_toy"
    _LOADERS = {
        "iris": "load_iris",
        "wine": "load_wine",
        "breast_cancer": "load_breast_cancer",
        "breast_cancer_wisconsin": "load_breast_cancer",
        "diabetes": "load_diabetes",
        "digits": "load_digits",
    }

    def try_fetch(self, ref: DatasetRef) -> FetchResult | None:
        key = _norm(ref.name)
        loader = self._LOADERS.get(key)
        if loader is None:
            return None
        import sklearn.datasets as ds

        bunch = getattr(ds, loader)(as_frame=True)
        df = bunch.frame
        return FetchResult(ref, df.to_csv(index=False).encode(), f"{key}.csv", self.name, "scikit-learn")


class DirectUrlResolver:
    """Downloads a data file when the reference carries a direct URL."""

    name = "direct_url"

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout

    def try_fetch(self, ref: DatasetRef) -> FetchResult | None:
        url = ref.url
        if not url or not url.lower().startswith("http"):
            return None
        if not any(url.lower().split("?")[0].endswith(ext) for ext in _DATA_EXT):
            return None

        from laboratree.core.net import safe_fetch

        # URL comes from paper text / LLM extraction — untrusted. SSRF-safe (per-hop) + size-capped.
        content = safe_fetch(url, timeout=self.timeout)
        if content is None:
            return None
        filename = url.split("?")[0].rstrip("/").split("/")[-1] or f"{_norm(ref.name)}.csv"
        return FetchResult(ref, content, filename, self.name, url)


def default_resolvers() -> list[Resolver]:
    # Local/cheap first, then the registries (OpenML/UCI), then an open-web search (Brave→SerpAPI)
    # as the last automated attempt before the agent's manual-upload fallback. Lazy import avoids a
    # package-import cycle. WebSearchResolver is a no-op when no search key is configured.
    from .resolvers import OpenMLResolver, UCIResolver, WebSearchResolver

    return [
        DirectUrlResolver(),
        SklearnToyResolver(),
        OpenMLResolver(),
        UCIResolver(),
        WebSearchResolver(),
    ]


class DataFetchAgent:
    def __init__(self, resolvers: list[Resolver] | None = None, max_tries: int = 3) -> None:
        self.resolvers = resolvers if resolvers is not None else default_resolvers()
        self.max_tries = max_tries

    def resolve(self, refs: list[DatasetRef]) -> FetchOutcome:
        outcome = FetchOutcome()
        for ref in refs:
            result = self._try_ref(ref)
            if result is not None:
                outcome.fetched.append(result)
            else:
                outcome.unresolved.append(self._guidance(ref))
        return outcome

    def _try_ref(self, ref: DatasetRef) -> FetchResult | None:
        for resolver in self.resolvers:
            for _ in range(self.max_tries):
                try:
                    res = resolver.try_fetch(ref)
                except Exception:
                    res = None
                if res is not None:
                    return res
                break  # deterministic resolvers: don't retry a clean miss
        return None

    def _guidance(self, ref: DatasetRef) -> Guidance:
        where = ref.url or ref.source or "the source cited in the paper"
        return Guidance(
            name=ref.name,
            reason="could not be fetched automatically",
            source=ref.source,
            url=ref.url,
            instructions=(
                f"Please download '{ref.name}' from {where}, then upload it here to continue the "
                f"experiment."
            ),
        )


def extract_dataset_refs(text: str, complete_fn: CompleteFn | None = None) -> list[DatasetRef]:
    """Extract dataset references from paper text. Uses the LLM when provided, always merges
    any data URLs found by regex."""
    refs: dict[str, DatasetRef] = {}

    if complete_fn is not None:
        import json

        system = (
            "You extract dataset references from a research paper. Return STRICT JSON: an array of "
            "objects {name, url, source}. url/source may be empty. Only real datasets used."
        )
        try:
            raw = complete_fn(system, text[:12000])
            body = raw.strip()
            s, e = body.find("["), body.rfind("]")
            if 0 <= s < e:
                for item in json.loads(body[s : e + 1]):
                    name = str(item.get("name", "")).strip()
                    if name:
                        refs[_norm(name)] = DatasetRef(
                            name=name,
                            url=item.get("url") or None,
                            source=item.get("source") or None,
                        )
        except Exception:
            pass

    for url in _URL_RE.findall(text or ""):
        if any(url.lower().split("?")[0].endswith(ext) for ext in _DATA_EXT):
            key = _norm(url.split("/")[-1])
            refs.setdefault(key, DatasetRef(name=url.split("/")[-1], url=url, source="url-in-paper"))

    return list(refs.values())
