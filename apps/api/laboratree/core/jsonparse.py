"""Lenient JSON extraction from LLM output.

LLMs (especially reasoning models on long outputs) wrap JSON in prose/code fences and sometimes get
CUT OFF mid-object when the completion-token budget runs out — leaving the trailing braces/quotes
unclosed. `loads_lenient` finds the first JSON value, and if it's truncated, closes the open string
+ brackets so a partial-but-valid object still parses. Shared by the Paper Card and Ideation agents.
"""

from __future__ import annotations

import json
from typing import Any


def _scan_balanced(text: str, open_c: str, close_c: str) -> str | None:
    """Return the substring from the first `open_c` to its matching close (string/escape aware). If
    the reply was truncated, close the open string + brackets so a partial value still parses."""
    i = text.find(open_c)
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
    # truncated: close an open string, drop a dangling "key": / trailing comma, then close brackets
    frag = text[i:]
    if in_str:
        frag += '"'
    frag = frag.rstrip()
    while frag and frag[-1] in ",:":
        if frag[-1] == ":":
            cut = max(frag.rfind(","), frag.rfind("{"), frag.rfind("["))
            frag = frag[:cut] if cut > 0 else frag[:-1]
        else:
            frag = frag[:-1]
        frag = frag.rstrip()
    return frag + "".join(reversed(stack)) if stack else frag


def loads_lenient(raw: str) -> Any | None:
    """Parse the first JSON object/array from an LLM reply — tolerant of prose, code fences, and a
    truncated tail. Returns the parsed value, or None if nothing parseable is found."""
    text = (raw or "").strip()
    if text.startswith("```"):                      # ```json … ``` fence
        parts = text.split("```")
        if len(parts) >= 2:
            body = parts[1]
            text = body[4:] if body.lstrip().lower().startswith("json") else body
            text = text.strip()
    obj_at, arr_at = text.find("{"), text.find("[")
    order = (("[", "]"), ("{", "}")) if (arr_at != -1 and (obj_at == -1 or arr_at < obj_at)) \
        else (("{", "}"), ("[", "]"))
    for open_c, close_c in order:
        s, e = text.find(open_c), text.rfind(close_c)
        if 0 <= s < e:                              # fast path: outermost span
            try:
                return json.loads(text[s : e + 1])
            except json.JSONDecodeError:
                pass
        candidate = _scan_balanced(text, open_c, close_c)   # robust path: balanced + truncation repair
        if candidate:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    return None


__all__ = ["loads_lenient"]
