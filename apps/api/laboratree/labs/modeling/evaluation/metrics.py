"""Pure metric functions shared by model components and the Red-Team critic (later)."""

from __future__ import annotations

from typing import Any


def classification_metrics(y_true, y_pred, y_proba=None) -> dict[str, float]:
    from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

    out: dict[str, float] = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
    }
    if y_proba is not None:
        try:
            import numpy as np

            classes = np.unique(y_true)
            if len(classes) == 2:
                proba = y_proba[:, 1] if getattr(y_proba, "ndim", 1) == 2 else y_proba
                out["roc_auc"] = float(roc_auc_score(y_true, proba))
        except Exception:
            pass
    return out


def regression_metrics(y_true, y_pred) -> dict[str, float]:
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    mse = float(mean_squared_error(y_true, y_pred))
    return {
        "r2": float(r2_score(y_true, y_pred)),
        "rmse": mse ** 0.5,
        "mae": float(mean_absolute_error(y_true, y_pred)),
    }


_ID_NAMES = {"id", "index", "idx", "sno", "s.no", "no", "row", "rowid", "unnamed: 0", "patient_id"}


def id_like(s, name: str) -> bool:
    """True for row-identifier columns (by name, or unique monotonically-increasing integers).
    They must never be used as features: on sorted files an ID literally encodes the answer
    (classic leakage — a tree splitting on `id` with 100% 'accuracy')."""
    import pandas as pd

    if str(name).strip().lower() in _ID_NAMES:
        return True
    if not pd.api.types.is_integer_dtype(s):
        return False
    return bool(s.is_unique and (s.is_monotonic_increasing or s.is_monotonic_decreasing))


def numeric_features(df, target: str, features: list[str] | None) -> list[str]:
    """Pick usable numeric feature columns (excluding the target and ID-like columns)."""
    if features:
        return [c for c in features if c in df.columns and c != target]
    return [
        c for c in df.select_dtypes("number").columns
        if c != target and not id_like(df[c], c)
    ]


def as_metric_dict(d: dict[str, Any]) -> dict[str, float]:
    return {k: round(float(v), 6) for k, v in d.items()}


def _native(v: Any) -> Any:
    """numpy scalar -> python scalar (int/float/str), never crashes on labels like 'CKD'."""
    v = v.item() if hasattr(v, "item") else v
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return v
    return str(v)


def sample_predictions(y_true, y_pred, task: str, n: int = 40) -> list[dict[str, Any]]:
    """First N test rows as {actual, predicted} — powers the 'predicted vs actual' node. Robust to
    numeric OR string class labels."""
    import numpy as np

    yt = np.asarray(y_true)
    yp = np.asarray(y_pred)
    out: list[dict[str, Any]] = []
    for i in range(min(n, len(yt))):
        if task == "regression":
            out.append({"actual": round(float(yt[i]), 4), "predicted": round(float(yp[i]), 4)})
        else:
            out.append({"actual": _native(yt[i]), "predicted": _native(yp[i])})
    return out
