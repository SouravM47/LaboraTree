"""Time-series family — ARIMA-style autoregression.

Training view: the series + the fitted AR equation (value today ~ c + phi1*yesterday +
phi2*day-before). Testing view: each held-out point predicted from its own recent past, with the
lag x coefficient contributions shown — the same additive story as the linear family, but over time.
"""

from __future__ import annotations

from . import register_tracer
from .common import resolve_params, table_rows
from .schema import ModelTrace

HOLDOUT = 6
HISTORY = 80  # points sent to the chart

SPEC = [
    {"key": "p", "label": "AR order (lags)", "type": "int", "default": 2, "min": 1, "max": 5,
     "step": 1, "help": "How many past values feed each prediction — the 'p' in ARIMA(p,0,0)."},
]


@register_tracer("timeseries")
def trace_timeseries(X, y, feats, target, task, labels, params=None) -> ModelTrace:
    import numpy as np
    from sklearn.linear_model import LinearRegression

    if task != "regression":
        raise ValueError(
            f"a time-series model needs a numeric target over time, but '{target}' is categorical — "
            "this looks like a classification task, so try the tree/linear walkthroughs instead"
        )

    p_cfg, param_spec = resolve_params(SPEC, params)
    LAGS = p_cfg["p"]
    # row order = time; the target column is the series (ARIMA(p,0,0) == AR(p))
    v = y.to_numpy(dtype=float)
    if len(v) < LAGS + HOLDOUT + 10:
        raise ValueError("not enough rows to trace a time-series model")
    lagmat = np.column_stack([v[LAGS - 1 - i : len(v) - 1 - i] for i in range(LAGS)])
    yy = v[LAGS:]
    ntr = len(yy) - HOLDOUT
    ar = LinearRegression().fit(lagmat[:ntr], yy[:ntr])
    phi = [round(float(c), 4) for c in ar.coef_]
    c0 = round(float(ar.intercept_), 4)
    fitted = ar.predict(lagmat)

    h0 = max(0, len(v) - HISTORY)
    series = {
        "history": [round(float(x), 3) for x in v[h0:]],
        "fitted": [None] * max(0, LAGS - h0) + [round(float(x), 3) for x in fitted[max(0, h0 - LAGS):]],
        "start": h0,
        "coef": {"c": c0, "phi": phi},
        "split": ntr + LAGS - h0,  # index in the trimmed arrays where the holdout begins
    }

    test_rows = []
    for j in range(ntr, len(yy)):
        lags = lagmat[j]
        contribs = [
            {"feature": f"value(t−{i + 1})", "value": round(float(lags[i]), 3),
             "weight": phi[i], "product": round(float(lags[i] * phi[i]), 3)}
            for i in range(LAGS)
        ]
        pred = float(c0 + sum(c["product"] for c in contribs))
        actual = float(yy[j])
        test_rows.append({
            "values": {f"value(t−{i + 1})": round(float(lags[i]), 3) for i in range(LAGS)},
            "contributions": contribs, "sum": round(pred, 3), "score": None,
            "predicted": round(pred, 3), "actual": round(actual, 3),
            "correct": None, "error": round(pred - actual, 3),
        })

    return ModelTrace(
        family="timeseries", target=target, task=task,
        features=[f"value(t−{i + 1})" for i in range(LAGS)], labels=labels,
        table=table_rows(X, y, feats[:4], target, task, labels),
        intercept=c0,
        coef=[{"feature": f"value(t−{i + 1})", "weight": phi[i]} for i in range(LAGS)],
        series=series, test_rows=test_rows, params=p_cfg, param_spec=param_spec,
        note="An autoregressive (ARIMA-style) model predicts the NEXT value from the last few values "
        "of the same series: tomorrow ≈ c + φ₁·today + φ₂·yesterday. Training finds the φ weights that "
        "best explain the history; forecasting slides that equation forward one step at a time.",
    )
