"""k-nearest-neighbors family.

Training view: KNN doesn't really "train" — it memorizes the rows; we show them on a 2-D map of the
two most informative features. Testing view: for each held-out row, its k closest memorized rows
(with distances), and the majority vote / average that becomes the prediction.
"""

from __future__ import annotations

from . import register_tracer
from .common import lbl, resolve_params, split_holdout, table_rows
from .schema import ModelTrace

MAX_POINTS = 140  # keep the scatter payload light

SPEC = [
    {"key": "k", "label": "Neighbours (k)", "type": "int", "default": 5, "min": 1, "max": 15,
     "step": 1, "help": "How many nearest rows vote on each prediction. Small k = jagged, large k = smooth."},
    {"key": "weights", "label": "Vote weighting", "type": "select", "default": "uniform",
     "options": ["uniform", "distance"],
     "help": "'uniform' = every neighbour counts equally; 'distance' = closer neighbours count more."},
]


@register_tracer("knn")
def trace_knn(X, y, feats, target, task, labels, params=None) -> ModelTrace:
    import numpy as np
    from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
    from sklearn.preprocessing import StandardScaler

    p, param_spec = resolve_params(SPEC, params)
    Xtr, Xte, ytr, yte = split_holdout(X, y)
    K = min(p["k"], len(Xtr))

    # the 2 most target-correlated features become the map's axes
    corr = [(f, abs(float(np.corrcoef(X[f], y)[0, 1]) if X[f].std() else 0.0)) for f in feats]
    corr.sort(key=lambda t: -t[1])
    fx, fy = (corr[0][0], corr[1][0]) if len(corr) > 1 else (feats[0], feats[0])
    show = [f for f, _ in corr[:6]]

    scaler = StandardScaler().fit(Xtr)
    Model = KNeighborsClassifier if task == "classification" else KNeighborsRegressor
    knn = Model(n_neighbors=K, weights=p["weights"]).fit(scaler.transform(Xtr), ytr)
    preds = knn.predict(scaler.transform(Xte))

    step = max(1, len(Xtr) // MAX_POINTS)
    points = [
        {"x": round(float(Xtr.iloc[i][fx]), 3), "y": round(float(Xtr.iloc[i][fy]), 3),
         "label": lbl(ytr.iloc[i], task, labels)}
        for i in range(0, len(Xtr), step)
    ]

    test_rows = []
    for j in range(len(Xte)):
        row = Xte.iloc[j]
        dists, idxs = knn.kneighbors(scaler.transform(Xte.iloc[[j]]))
        neighbors = [
            {"x": round(float(Xtr.iloc[i][fx]), 3), "y": round(float(Xtr.iloc[i][fy]), 3),
             "label": lbl(ytr.iloc[i], task, labels), "distance": round(float(d), 3)}
            for d, i in zip(dists[0], idxs[0], strict=False)
        ]
        pred = lbl(preds[j], task, labels)
        actual = lbl(yte.iloc[j], task, labels)
        test_rows.append({
            "values": {f: round(float(row[f]), 3) for f in feats[:24]},
            "x": round(float(row[fx]), 3), "y": round(float(row[fy]), 3),
            "neighbors": neighbors,
            "predicted": pred, "actual": actual,
            "correct": (pred == actual) if task == "classification" else None,
            "error": None if task == "classification" else round(float(preds[j]) - float(yte.iloc[j]), 3),
        })

    return ModelTrace(
        family="knn", target=target, task=task, features=show, labels=labels,
        table=table_rows(X, y, show, target, task, labels),
        points=points, series={"x": fx, "y": fy, "k": K, "weights": p["weights"]},
        test_rows=test_rows, params=p, param_spec=param_spec,
        note="KNN keeps every training row in memory. To predict a new row it finds the k most "
        "similar rows (smallest distance across ALL features — the map shows just the 2 strongest) "
        "and lets them vote (or averages them for numbers). No equations are learned — similarity IS "
        "the model.",
    )
