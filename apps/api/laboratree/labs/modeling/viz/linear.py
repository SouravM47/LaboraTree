"""Linear family — logistic / linear regression, SVM-style weighted scoring, probit.

Training view: one learned weight per feature. Testing view: per-row feature x weight
contributions summed into a score (sigmoid -> probability for classification).
"""

from __future__ import annotations

from . import register_tracer
from .common import lbl, resolve_params, split_holdout, table_rows
from .schema import ModelTrace

SPEC_CLF = [
    {"key": "C", "label": "Inverse regularization (C)", "type": "float", "default": 1.0,
     "min": 0.01, "max": 10.0, "step": 0.01,
     "help": "Smaller C = stronger regularization (weights pulled toward 0, simpler boundary)."},
    {"key": "max_iter", "label": "Max iterations", "type": "int", "default": 500, "min": 100,
     "max": 2000, "step": 100, "help": "How long the optimizer may run to fit the weights."},
]
SPEC_REG = [
    {"key": "alpha", "label": "Ridge penalty (α)", "type": "float", "default": 0.0, "min": 0.0,
     "max": 10.0, "step": 0.1,
     "help": "0 = plain least squares; larger α shrinks the weights to curb overfitting."},
]


@register_tracer("linear")
def trace_linear(X, y, feats, target, task, labels, params=None) -> ModelTrace:
    import numpy as np

    Xtr, Xte, ytr, yte = split_holdout(X, y)
    if task == "classification":
        from sklearn.linear_model import LogisticRegression

        p, param_spec = resolve_params(SPEC_CLF, params)
        model = LogisticRegression(C=p["C"], max_iter=p["max_iter"]).fit(Xtr, ytr)
        coef = model.coef_[0]
        intercept = float(model.intercept_[0])
    else:
        from sklearn.linear_model import LinearRegression, Ridge

        p, param_spec = resolve_params(SPEC_REG, params)
        model = (
            Ridge(alpha=p["alpha"]) if p["alpha"] > 0 else LinearRegression()
        ).fit(Xtr, ytr)
        coef = model.coef_
        intercept = float(model.intercept_)
    order = np.argsort(-np.abs(coef))[:6]
    top = [feats[i] for i in order]
    coef_list = [{"feature": feats[i], "weight": round(float(coef[i]), 4)} for i in order]

    def contribs_for(row):
        return [
            {"feature": f, "value": round(float(row[f]), 3),
             "weight": round(float(coef[feats.index(f)]), 4),
             "product": round(float(row[f] * coef[feats.index(f)]), 3)}
            for f in top
        ]

    test_rows = []
    for j in range(len(Xte)):
        row = Xte.iloc[j]
        cs = contribs_for(row)
        s = float(intercept + sum(c["product"] for c in cs))
        if task == "classification":
            prob = 1.0 / (1.0 + np.exp(-s))
            pi = 1 if prob > 0.5 else 0
            pred = labels[pi] if labels else str(pi)
            score = round(float(prob), 3)
            err = None
        else:
            pred = round(s, 3)
            score = None
            err = round(s - float(yte.iloc[j]), 3)
        actual = lbl(yte.iloc[j], task, labels)
        test_rows.append({
            "values": {f: round(float(row[f]), 3) for f in feats[:24]},
            "contributions": cs, "sum": round(s, 3), "score": score,
            "predicted": pred, "actual": actual,
            "correct": (pred == actual) if task == "classification" else None, "error": err,
        })
    return ModelTrace(
        family="linear", target=target, task=task, features=top, labels=labels,
        table=table_rows(X, y, top, target, task, labels),
        intercept=round(intercept, 4), coef=coef_list, test_rows=test_rows,
        params=p, param_spec=param_spec,
        note="Each feature is multiplied by a learned weight (bigger weight = more influence). The "
        + ("products are added up, then the sigmoid squeezes the total into a probability, then a class."
           if task == "classification" else "products are added up to give the predicted number."),
    )
