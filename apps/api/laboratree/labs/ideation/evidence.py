"""Evidence Hunt — turn a conceptual hypothesis into a cited, synthesized evidence brief.

Flow (all dependencies injectable, so it runs fully offline in tests):
  1. plan_queries  — LLM turns the hypothesis into a few targeted web queries
  2. search        — web_search (Brave→SerpAPI) gathers related papers / studies / articles
  3. synthesize    — LLM reads titles+snippets and writes a comprehensive brief: what the evidence
                     says, whether it supports / refutes / is mixed, the key findings, insights,
                     the variables worth testing, and the gaps — every claim tied to numbered sources.

The user brings the conceptual hypothesis; this does the reading and returns something to reason with
(and to hand to the auto-experiment stage next). Search misses degrade gracefully to an empty brief.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from ...core.llm.context import use_llm_operation

log = logging.getLogger(__name__)

CompleteFn = Callable[..., str]
# search_fn(query, count) -> list of objects with .title / .url / .description / .source
SearchFn = Callable[[str, int], list[Any]]

MAX_SOURCES = 12
QUERIES = 4


def _scan_balanced(text: str, start: int, open_c: str, close_c: str) -> str | None:
    """Return the substring from the first `open_c` at/after `start` to its matching close (string-
    and escape-aware). If the reply was truncated mid-object, close the open brackets so a partial
    but valid JSON still parses — reasoning models occasionally cut the JSON tail."""
    i = text.find(open_c, start)
    if i < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    stack: list[str] = []
    pairs = {"{": "}", "[": "]"}
    for j in range(i, len(text)):
        ch = text[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in pairs:
            stack.append(pairs[ch])
            depth += 1
        elif ch in ("}", "]"):
            depth -= 1
            if stack:
                stack.pop()
            if depth == 0:
                return text[i : j + 1]
    # truncated mid-object: close an open string, drop a dangling "key": or trailing comma, then
    # close the still-open brackets so a partial-but-valid JSON survives.
    frag = text[i:]
    if in_str:
        frag += '"'
    frag = frag.rstrip()
    while frag and frag[-1] in ",:":
        # a trailing ':' means a key with no value — cut the key too
        if frag[-1] == ":":
            cut = max(frag.rfind(","), frag.rfind("{"), frag.rfind("["))
            frag = frag[:cut] if cut > 0 else frag[:-1]
        else:
            frag = frag[:-1]
        frag = frag.rstrip()
    return frag + "".join(reversed(stack)) if stack else frag


def _parse_json(raw: str) -> Any:
    """Extract the first JSON object/array from an LLM reply (tolerant of prose/code fences and of a
    truncated tail). Tries whichever bracket type OPENS FIRST — so an array of objects isn't
    mis-sliced from its first '{' to its last '}' (which would drop the enclosing brackets)."""
    text = (raw or "").strip()
    obj_at, arr_at = text.find("{"), text.find("[")
    # order the two bracket types by which appears first in the text
    if arr_at != -1 and (obj_at == -1 or arr_at < obj_at):
        order = (("[", "]"), ("{", "}"))
    else:
        order = (("{", "}"), ("[", "]"))
    for open_c, close_c in order:
        s, e = text.find(open_c), text.rfind(close_c)
        if 0 <= s < e:  # fast path: outermost span
            try:
                return json.loads(text[s : e + 1])
            except json.JSONDecodeError:
                pass
        candidate = _scan_balanced(text, 0, open_c, close_c)  # robust path: balanced + truncation repair
        if candidate:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    return None


def plan_queries(hypothesis: str, complete_fn: CompleteFn, n: int = QUERIES) -> list[str]:
    """Ask the LLM for a handful of targeted search queries; fall back to the raw hypothesis."""
    system = (
        "You plan web searches to find rigorous evidence (papers, studies, official statistics, "
        "reputable articles) for or against a research hypothesis. Return ONLY a JSON array of "
        f"{n} short, specific search-query strings covering different angles (empirical studies, "
        "official data, counter-evidence). No prose."
    )
    try:
        with use_llm_operation("evidence.plan_queries"):
            parsed = _parse_json(complete_fn(system, f"Hypothesis: {hypothesis}"))
        queries = [str(q).strip() for q in parsed if str(q).strip()] if isinstance(parsed, list) else []
    except Exception as exc:
        log.info("query planning failed, using fallback: %s", exc)
        queries = []
    if not queries:
        queries = [hypothesis, f"{hypothesis} study evidence", f"{hypothesis} statistics data"]
    return queries[:n]


def _collect_sources(queries: list[str], search_fn: SearchFn, limit: int) -> list[dict[str, Any]]:
    """Run each query, dedupe by URL then by domain, and keep the first `limit` distinct sources."""
    seen_urls: set[str] = set()
    per_domain: dict[str, int] = {}
    sources: list[dict[str, Any]] = []
    for q in queries:
        try:
            hits = search_fn(q, 8)
        except Exception as exc:
            log.info("search failed for %r: %s", q, exc)
            continue
        for h in hits:
            url = getattr(h, "url", "") or ""
            if not url or url in seen_urls:
                continue
            domain = urlparse(url).netloc.lower()
            # allow at most 2 sources per domain so one site can't dominate the brief
            if per_domain.get(domain, 0) >= 2:
                continue
            seen_urls.add(url)
            per_domain[domain] = per_domain.get(domain, 0) + 1
            sources.append({
                "title": getattr(h, "title", "") or url,
                "url": url,
                "snippet": getattr(h, "description", "") or "",
                "provider": getattr(h, "source", "") or "",
                "query": q,
            })
            if len(sources) >= limit:
                return sources
    return sources


def _sources_block(sources: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"[{i + 1}] {s['title']}\n    {s['url']}\n    {s['snippet'][:400]}"
        for i, s in enumerate(sources)
    )


def synthesize(hypothesis: str, sources: list[dict[str, Any]], complete_fn: CompleteFn) -> dict[str, Any]:
    """LLM reads the numbered sources and returns the structured brief. Citations are 1-based indices
    into `sources`."""
    if not sources:
        return {
            "summary": "No web sources were found for this hypothesis (search may be disabled or the "
            "topic too specific). Try rephrasing, or add sources manually.",
            "stance": "inconclusive",
            "key_findings": [],
            "insights": [],
            "variables_to_test": [],
            "gaps": ["No evidence retrieved."],
        }
    system = (
        "You are a rigorous research analyst. Using ONLY the numbered sources, write an evidence brief "
        "for the user's hypothesis. Be balanced — include supporting AND contradicting evidence. Cite "
        "sources by their number in square brackets like [2]. Keep it compact to stay within length: "
        "summary <= 5 sentences, and AT MOST 6 items in any array. Return ONLY minified JSON (no prose, "
        "no code fences) with keys: "
        "summary (multi-sentence synthesis with inline [n] citations), "
        "stance (one of 'supports' | 'refutes' | 'mixed' | 'inconclusive'), "
        "confidence (0-1 number for how well the evidence settles the question), "
        "key_findings (array of {finding, sources:[n]}), "
        "insights (array of strings — non-obvious takeaways for the researcher), "
        "gaps (array of strings — what evidence is missing or where sources are weak)."
    )
    prompt = f"Hypothesis: {hypothesis}\n\nSources:\n{_sources_block(sources)}"
    with use_llm_operation("evidence.synthesize"):
        parsed = _parse_json(complete_fn(system, prompt))
        if not isinstance(parsed, dict):  # one compact retry — truncation/garbled first pass
            retry_system = system + " Your previous reply was not valid JSON — return STRICT minified JSON only."
            parsed = _parse_json(complete_fn(retry_system, prompt))
    if not isinstance(parsed, dict):
        return {
            "summary": "Could not structure the evidence into a brief this time — the sources are listed "
            "below; try again or rephrase the hypothesis.",
            "stance": "inconclusive", "confidence": 0.0,
            "key_findings": [], "insights": [], "variables_to_test": [],
            "gaps": ["Synthesis step returned an unparseable response twice."],
        }
    parsed.setdefault("stance", "inconclusive")
    parsed.setdefault("key_findings", [])
    parsed.setdefault("insights", [])
    parsed.setdefault("variables_to_test", [])
    parsed.setdefault("gaps", [])
    return parsed


_VAR_ROLES = {"independent", "dependent", "target", "control", "confounder", "mediator",
              "moderator", "instrument"}
MAX_VARIABLES = 16


def extract_variables(
    hypothesis: str, sources: list[dict[str, Any]], complete_fn: CompleteFn
) -> list[dict[str, Any]]:
    """A dedicated, EXHAUSTIVE pass at the measurable variables needed to test the hypothesis —
    grounded in how the actual studies operationalize things PLUS the standard confounders/controls
    the literature would demand. Each variable is tied to the source(s) that motivate it. Separate
    from the summary so it gets its own budget (and its own observability operation)."""
    if not sources:
        return []
    system = (
        "You are a research methodologist designing an empirical test of the hypothesis. From the "
        "hypothesis AND the numbered sources, produce an EXHAUSTIVE list of the measurable variables "
        "needed to test it well — not just the obvious treatment and outcome. Ground each variable in "
        "how the actual studies below operationalize things, and ALSO add the standard confounders, "
        "controls, mediators, moderators and instruments the literature on this topic would demand. "
        "Return ONLY a JSON array (no prose) of objects with keys: "
        "name (a concrete measurable variable), "
        "role (one of 'independent'|'dependent'|'control'|'confounder'|'mediator'|'moderator'|'instrument'), "
        "measure (how to operationalize it — a concrete proxy, unit, or scale), "
        "expected_direction (one of 'positive'|'negative'|'none'|'unclear' — its expected relationship to the outcome), "
        "source_refs (array of the [n] source numbers that motivate it; [] if it is a standard control from your own knowledge), "
        "rationale (one short clause on why it matters). "
        "Aim for 8-14 variables spanning all the roles. Be thorough and specific to THIS topic."
    )
    prompt = f"Hypothesis: {hypothesis}\n\nSources:\n{_sources_block(sources)}"
    with use_llm_operation("evidence.extract_variables"):
        parsed = _parse_json(complete_fn(system, prompt))
        if not isinstance(parsed, list):
            retry = system + " Return ONLY a valid minified JSON array."
            parsed = _parse_json(complete_fn(retry, prompt))
    if not isinstance(parsed, list):
        return []
    out: list[dict[str, Any]] = []
    for v in parsed:
        if not isinstance(v, dict) or not str(v.get("name", "")).strip():
            continue
        role = str(v.get("role", "")).lower().strip()
        out.append({
            "name": str(v["name"]).strip(),
            "role": role if role in _VAR_ROLES else "control",
            "measure": str(v.get("measure", "")),
            "expected_direction": str(v.get("expected_direction", "unclear")).lower(),
            "source_refs": [n for n in (v.get("source_refs") or []) if isinstance(n, int)],
            "rationale": str(v.get("rationale", "")),
        })
    return out[:MAX_VARIABLES]


def gather_evidence(
    hypothesis: str,
    *,
    search_fn: SearchFn,
    complete_fn: CompleteFn,
    max_sources: int = MAX_SOURCES,
) -> dict[str, Any]:
    """Full evidence hunt: plan queries -> search -> synthesize -> exhaustively extract the
    study-grounded variables to test. Returns {hypothesis, queries, sources, brief}. Never raises for
    search/LLM hiccups — returns a best-effort brief."""
    queries = plan_queries(hypothesis, complete_fn)
    sources = _collect_sources(queries, search_fn, max_sources)
    brief = synthesize(hypothesis, sources, complete_fn)
    variables = extract_variables(hypothesis, sources, complete_fn)
    if variables:  # the dedicated, exhaustive pass supersedes the summary's rough list
        brief["variables_to_test"] = variables
    return {"hypothesis": hypothesis, "queries": queries, "sources": sources, "brief": brief}


MAX_HISTORY_TURNS = 8


def _brief_context(brief: dict[str, Any]) -> str:
    """Compact, plain-text rendering of the brief so the brainstorm partner stays grounded in it."""
    lines = [f"Summary: {brief.get('summary', '')}", f"Stance: {brief.get('stance', 'inconclusive')}"]
    kf = brief.get("key_findings") or []
    if kf:
        lines.append("Key findings: " + "; ".join(
            f.get("finding", "") if isinstance(f, dict) else str(f) for f in kf
        ))
    vs = brief.get("variables_to_test") or []
    if vs:
        lines.append("Variables to test: " + ", ".join(
            f"{v.get('name', '')} ({v.get('role', '')})" if isinstance(v, dict) else str(v) for v in vs
        ))
    gaps = brief.get("gaps") or []
    if gaps:
        lines.append("Gaps: " + "; ".join(str(g) for g in gaps))
    return "\n".join(lines)


def brainstorm(
    hypothesis: str,
    brief: dict[str, Any],
    sources: list[dict[str, Any]],
    question: str,
    history: list[dict[str, str]] | None,
    complete_fn: CompleteFn,
) -> dict[str, Any]:
    """Grounded brainstorming turn: answer a follow-up about the hypothesis using the evidence brief
    + sources as context. Honest about uncertainty; suggests study designs, confounders, and the data
    to gather next. Cites sources by [n]. Stateless — the client passes the brief/sources/history."""
    system = (
        "You are a sharp, honest research brainstorming partner. Ground every claim in the evidence "
        "brief and the numbered sources provided; when you use a source, cite it like [2]. Be candid "
        "about uncertainty and confounders, and push the thinking forward with concrete next steps — "
        "study designs, variables/controls to measure, datasets to gather, and threats to validity. "
        "Keep replies focused and conversational (a few short paragraphs, not an essay)."
    )
    convo = ""
    for turn in (history or [])[-MAX_HISTORY_TURNS:]:
        who = "Researcher" if turn.get("role") == "user" else "You"
        convo += f"{who}: {turn.get('content', '')}\n"
    prompt = (
        f"Hypothesis: {hypothesis}\n\n"
        f"Evidence brief:\n{_brief_context(brief)}\n\n"
        f"Sources:\n{_sources_block(sources)}\n\n"
        f"{('Conversation so far:' + chr(10) + convo + chr(10)) if convo else ''}"
        f"Researcher: {question}\nYou:"
    )
    try:
        with use_llm_operation("evidence.brainstorm"):
            answer = complete_fn(system, prompt).strip()
    except Exception as exc:
        log.info("brainstorm failed: %s", exc)
        answer = ""
    return {"answer": answer or "I couldn't generate a response just now — try rephrasing."}
