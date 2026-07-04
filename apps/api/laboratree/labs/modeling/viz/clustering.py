"""Clustering family — k-means style unsupervised grouping.

Training view: the rows on a 2-D map, colored by the cluster k-means found, with centroids.
Testing view: per held-out row, its distance to every centroid -> assigned to the nearest.
No "correct answer" exists — clustering discovers structure instead of predicting a label.
"""

from __future__ import annotations

from . import register_tracer
from .common import resolve_params, split_holdout, table_rows
from .schema import ModelTrace

MAX_POINTS = 140

SPEC = [
    {"key": "k", "label": "Clusters (k)", "type": "int", "default": 3, "min": 2, "max": 8,
     "step": 1, "help": "How many groups k-means should split the data into."},
]


@register_tracer("clustering")
def trace_clustering(X, y, feats, target, task, labels, params=None) -> ModelTrace:
    import numpy as np
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    p, param_spec = resolve_params(SPEC, params)
    Xtr, Xte, _ytr, _yte = split_holdout(X, y)
    scaler = StandardScaler().fit(Xtr)
    km = KMeans(n_clusters=min(p["k"], len(Xtr)), n_init=5, random_state=0).fit(scaler.transform(Xtr))

    # the 2 highest-variance features become the map's axes
    variances = [(f, float(X[f].std())) for f in feats]
    variances.sort(key=lambda t: -t[1])
    fx, fy = (variances[0][0], variances[1][0]) if len(variances) > 1 else (feats[0], feats[0])
    show = [f for f, _ in variances[:6]]

    tr_assign = km.labels_
    step = max(1, len(Xtr) // MAX_POINTS)
    points = [
        {"x": round(float(Xtr.iloc[i][fx]), 3), "y": round(float(Xtr.iloc[i][fy]), 3),
         "label": f"cluster {int(tr_assign[i]) + 1}"}
        for i in range(0, len(Xtr), step)
    ]

    test_rows = []
    for j in range(len(Xte)):
        srow = scaler.transform(Xte.iloc[[j]])
        dists = np.linalg.norm(km.cluster_centers_ - srow, axis=1)
        order = np.argsort(dists)
        contribs = [
            {"feature": f"→ cluster {int(c) + 1}", "value": round(float(dists[c]), 3),
             "weight": 0.0, "product": round(float(dists[c]), 3)}
            for c in order
        ]
        test_rows.append({
            "values": {f: round(float(Xte.iloc[j][f]), 3) for f in show},
            "x": round(float(Xte.iloc[j][fx]), 3), "y": round(float(Xte.iloc[j][fy]), 3),
            "distances": [
                {"cluster": f"cluster {int(c) + 1}", "distance": round(float(dists[c]), 3)}
                for c in order
            ],
            "predicted": f"cluster {int(order[0]) + 1}", "actual": None,
            "correct": None, "error": None,
        })

    sizes = [int((tr_assign == c).sum()) for c in range(km.n_clusters)]
    return ModelTrace(
        family="clustering", target=target, task="clustering", features=show, labels=labels,
        table=table_rows(X, y, show, target, task, labels),
        points=points,
        series={"x": fx, "y": fy, "k": km.n_clusters, "sizes": sizes},
        test_rows=test_rows, params=p, param_spec=param_spec,
        note="Clustering has NO answer column — it looks for natural groups. k-means places k centre "
        "points, assigns every row to its nearest centre, moves each centre to the middle of its "
        "rows, and repeats until stable. A new row simply joins the cluster whose centre is closest.",
    )
