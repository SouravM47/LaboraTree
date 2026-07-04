"""Anomaly-detection family — isolation-forest style outlier scoring.

Training view: the rows on a 2-D map, colored normal vs anomaly by the fitted detector.
Testing view: per held-out row, its anomaly score vs the threshold -> normal or anomaly.
Like clustering there is no answer column — the model learns what "usual" looks like.
"""

from __future__ import annotations

from . import register_tracer
from .common import resolve_params, split_holdout, table_rows
from .schema import ModelTrace

MAX_POINTS = 140

SPEC = [
    {"key": "contamination", "label": "Contamination", "type": "float", "default": 0.08,
     "min": 0.01, "max": 0.4, "step": 0.01,
     "help": "Expected fraction of rows that are anomalies — sets how many get flagged."},
    {"key": "n_estimators", "label": "Trees in forest", "type": "int", "default": 100,
     "min": 20, "max": 400, "step": 20, "help": "How many random isolation trees to average over."},
]


@register_tracer("anomaly")
def trace_anomaly(X, y, feats, target, task, labels, params=None) -> ModelTrace:
    from sklearn.ensemble import IsolationForest

    p, param_spec = resolve_params(SPEC, params)
    Xtr, Xte, _ytr, _yte = split_holdout(X, y)
    iso = IsolationForest(
        contamination=p["contamination"], n_estimators=p["n_estimators"], random_state=0
    ).fit(Xtr)

    variances = [(f, float(X[f].std())) for f in feats]
    variances.sort(key=lambda t: -t[1])
    fx, fy = (variances[0][0], variances[1][0]) if len(variances) > 1 else (feats[0], feats[0])
    show = [f for f, _ in variances[:6]]

    tr_flag = iso.predict(Xtr)  # 1 normal, -1 anomaly
    step = max(1, len(Xtr) // MAX_POINTS)
    points = [
        {"x": round(float(Xtr.iloc[i][fx]), 3), "y": round(float(Xtr.iloc[i][fy]), 3),
         "label": "anomaly" if tr_flag[i] < 0 else "normal"}
        for i in range(0, len(Xtr), step)
    ]

    scores = iso.decision_function(Xte)  # >0 normal, <0 anomaly
    flags = iso.predict(Xte)
    test_rows = []
    for j in range(len(Xte)):
        test_rows.append({
            "values": {f: round(float(Xte.iloc[j][f]), 3) for f in show},
            "x": round(float(Xte.iloc[j][fx]), 3), "y": round(float(Xte.iloc[j][fy]), 3),
            "score": round(float(scores[j]), 3),
            "predicted": "anomaly" if flags[j] < 0 else "normal", "actual": None,
            "correct": None, "error": None,
        })

    n_anom = int((tr_flag < 0).sum())
    return ModelTrace(
        family="anomaly", target=target, task="anomaly", features=show, labels=labels,
        table=table_rows(X, y, show, target, task, labels),
        points=points,
        series={"x": fx, "y": fy, "threshold": 0.0, "n_anomalies": n_anom, "n_train": int(len(Xtr))},
        test_rows=test_rows, params=p, param_spec=param_spec,
        note="An isolation forest repeatedly slices the data with random cuts. Unusual rows get "
        "isolated in very few cuts (they sit alone), typical rows need many — so 'few cuts to "
        "isolate' becomes an anomaly score. Rows scoring below the threshold are flagged.",
    )
