"""Helpers shared by every family tracer: X/y prep, label formatting, sample tables, holdout."""

from __future__ import annotations


def prep_xy(df, target):
    """Numeric feature matrix X, numeric-coded target y, task, and the label names.
    Drops ID-like columns (leakage) and shuffles rows (files are often sorted by class,
    which would make the tail-of-file holdout single-class)."""
    import pandas as pd

    from ..evaluation.metrics import id_like

    df = df.dropna().sample(frac=1.0, random_state=42).reset_index(drop=True)
    y_raw = df[target]
    if pd.api.types.is_numeric_dtype(y_raw) and y_raw.nunique() > 10:
        task = "regression"
        y = y_raw.astype(float)
        labels = None
    else:
        task = "classification"
        cat = y_raw.astype("category")
        y = cat.cat.codes.astype(float)
        labels = list(cat.cat.categories.astype(str))
    feats = [
        c for c in df.select_dtypes("number").columns
        if c != target and not id_like(df[c], c)
    ]
    X = df[feats]
    return X, y, feats, task, labels


def lbl(v, task, labels):
    return labels[int(v)] if (task == "classification" and labels) else round(float(v), 3)


def table_rows(X, y, feats, target, task, labels, n=6):
    rows = []
    for i in range(min(n, len(X))):
        r = {f: round(float(X.iloc[i][f]), 3) for f in feats}
        r[target] = lbl(y.iloc[i], task, labels)
        rows.append(r)
    return rows


def split_holdout(X, y):
    ntest = min(6, max(1, len(X) // 5))
    return X.iloc[:-ntest], X.iloc[-ntest:], y.iloc[:-ntest], y.iloc[-ntest:]


def resolve_params(spec: list[dict], user: dict | None) -> tuple[dict, list[dict]]:
    """Merge user-supplied hyperparameters over a family's declared defaults, coercing + clamping
    to keep the refit safe, and return (values, param_spec) — the spec carries the live ``value`` so
    the UI renders sliders/selects seeded with the paper's (or user's) settings.

    Each spec item: {key, label, type: 'int'|'float'|'select', default, min?, max?, step?, options?, help?}.
    """
    user = user or {}
    values: dict = {}
    out: list[dict] = []
    for s in spec:
        key, typ = s["key"], s["type"]
        v = user.get(key, s["default"])
        try:
            if typ == "int":
                v = int(round(float(v)))
            elif typ == "float":
                v = float(v)
        except (TypeError, ValueError):
            v = s["default"]
        if typ in ("int", "float"):
            if "min" in s:
                v = max(s["min"], v)
            if "max" in s:
                v = min(s["max"], v)
        elif typ == "select" and v not in s.get("options", []):
            v = s["default"]
        values[key] = v
        out.append({**s, "value": v})
    return values, out
