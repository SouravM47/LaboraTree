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


def numeric_features(df, target: str, features: list[str] | None) -> list[str]:
    """Pick usable numeric feature columns (excluding the target)."""
    if features:
        return [c for c in features if c in df.columns and c != target]
    return [c for c in df.select_dtypes("number").columns if c != target]


def as_metric_dict(d: dict[str, Any]) -> dict[str, float]:
    return {k: round(float(v), 6) for k, v in d.items()}
