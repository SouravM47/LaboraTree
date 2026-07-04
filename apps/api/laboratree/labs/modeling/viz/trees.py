"""Trees family — decision tree / random forest / XGBoost-style boosting.

Training view: the real fitted tree (splits + information gain). Testing view: the highlighted
root-to-leaf path for each held-out row.
"""

from __future__ import annotations

from . import register_tracer
from .common import lbl, resolve_params, split_holdout, table_rows
from .schema import ModelTrace

SPEC = [
    {"key": "max_depth", "label": "Tree depth", "type": "int", "default": 3, "min": 1, "max": 6,
     "step": 1, "help": "How many question-levels deep the single decision tree may grow."},
    {"key": "n_estimators", "label": "Boosting trees", "type": "int", "default": 3, "min": 1,
     "max": 6, "step": 1, "help": "How many trees the boosting ensemble (XGBoost-style) stacks."},
    {"key": "learning_rate", "label": "Learning rate", "type": "float", "default": 1.0, "min": 0.1,
     "max": 1.0, "step": 0.1, "help": "How much each new boosting tree is allowed to correct the last."},
]


def tree_to_dict(t, node_id, feats, task, labels):
    left, right = int(t.children_left[node_id]), int(t.children_right[node_id])
    n = int(t.n_node_samples[node_id])
    if left == right:  # leaf
        val = t.value[node_id][0]
        if task == "classification":
            cls = int(val.argmax())
            return {
                "leaf": True, "samples": n,
                "prediction": labels[cls] if labels else str(cls),
                "confidence": round(float(val.max() / (val.sum() or 1)), 2),
            }
        return {"leaf": True, "samples": n, "prediction": round(float(val[0]), 3)}
    imp = float(t.impurity[node_id])
    nl, nr = int(t.n_node_samples[left]), int(t.n_node_samples[right])
    gain = imp - (nl * float(t.impurity[left]) + nr * float(t.impurity[right])) / (n or 1)
    return {
        "leaf": False,
        "feature": feats[int(t.feature[node_id])],
        "threshold": round(float(t.threshold[node_id]), 3),
        "gain": round(float(gain), 4),
        "samples": n,
        "left": tree_to_dict(t, left, feats, task, labels),
        "right": tree_to_dict(t, right, feats, task, labels),
    }


def tree_path(t, feats, row):
    node, steps = 0, []
    while int(t.children_left[node]) != int(t.children_right[node]):
        f = feats[int(t.feature[node])]
        thr = float(t.threshold[node])
        val = float(row[f])
        go_left = val <= thr
        steps.append(
            {"feature": f, "value": round(val, 3), "threshold": round(thr, 3),
             "go": "left" if go_left else "right"}
        )
        node = int(t.children_left[node]) if go_left else int(t.children_right[node])
    return steps


def _fit_boosting(Xtr, ytr, task, n_rounds, lr):
    """A tiny REAL gradient-boosting ensemble (depth-2 trees) so the animation can show the actual
    additive mechanics: baseline -> tree1 -> +tree2 -> … -> score. Binary/regression only (multiclass
    boosting has one tree per class per round — too much to animate)."""
    import numpy as np
    from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor

    if task == "classification":
        if len(np.unique(ytr)) != 2:
            return None, None
        gb = GradientBoostingClassifier(
            n_estimators=n_rounds, max_depth=2, learning_rate=lr, random_state=0
        ).fit(Xtr, ytr)
        p = float(np.clip(ytr.mean(), 1e-6, 1 - 1e-6))
        baseline = float(np.log(p / (1 - p)))  # starting log-odds before any tree
    else:
        gb = GradientBoostingRegressor(
            n_estimators=n_rounds, max_depth=2, learning_rate=lr, random_state=0
        ).fit(Xtr, ytr)
        baseline = float(ytr.mean())
    return gb, baseline


@register_tracer("trees")
def trace_trees(X, y, feats, target, task, labels, params=None) -> ModelTrace:
    import numpy as np
    from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

    cfg, param_spec = resolve_params(SPEC, params)
    n_rounds, lr = cfg["n_estimators"], cfg["learning_rate"]
    Xtr, Xte, ytr, yte = split_holdout(X, y)
    Model = DecisionTreeClassifier if task == "classification" else DecisionTreeRegressor
    tree = Model(max_depth=cfg["max_depth"], random_state=0).fit(Xtr, ytr)
    t = tree.tree_
    show = feats[:24]  # the testing table shows every feature (scrolls horizontally)

    # the real boosting ensemble (for XGBoost-style papers)
    gb, baseline = _fit_boosting(Xtr, ytr, task, n_rounds, lr)
    rounds = None
    if gb is not None:
        rounds = [
            {"tree": tree_to_dict(gb.estimators_[r][0].tree_, 0, feats, "regression", None)}
            for r in range(n_rounds)
        ]

    preds = tree.predict(Xte)
    test_rows = []
    for j in range(len(Xte)):
        row = Xte.iloc[j]
        pred = lbl(preds[j], task, labels)
        actual = lbl(yte.iloc[j], task, labels)
        tr = {
            "values": {f: round(float(row[f]), 3) for f in show},
            "path": tree_path(t, feats, row),
            "predicted": pred, "actual": actual,
            "correct": (pred == actual) if task == "classification" else None,
            "error": None if task == "classification" else round(float(preds[j]) - float(yte.iloc[j]), 3),
        }
        if gb is not None:
            contribs = []
            for r in range(n_rounds):
                est = gb.estimators_[r][0]
                contribs.append({
                    "path": tree_path(est.tree_, feats, row),
                    "value": round(float(est.predict(row.to_frame().T)[0]), 3),
                })
            s = baseline + sum(c["value"] for c in contribs)
            tr["rounds"] = contribs
            tr["boost_score"] = round(float(s), 3)
            if task == "classification":
                prob = 1.0 / (1.0 + np.exp(-s))
                pi = 1 if prob > 0.5 else 0
                tr["boost_prob"] = round(float(prob), 3)
                tr["boost_pred"] = labels[pi] if labels else str(pi)
            else:
                tr["boost_pred"] = round(float(s), 3)
        test_rows.append(tr)

    return ModelTrace(
        family="trees", target=target, task=task, features=show, labels=labels,
        table=table_rows(X, y, feats[:8], target, task, labels),
        tree=tree_to_dict(t, 0, feats, task, labels),
        baseline=None if baseline is None else round(baseline, 3),
        rounds=rounds, test_rows=test_rows, params=cfg, param_spec=param_spec,
        note="A decision tree asks yes/no questions about the features. Each split is picked to best "
        "separate the groups — 'gain' measures how much cleaner (more one-class) the two sides become. "
        "Boosting (XGBoost) stacks several small trees: each new tree is trained on the mistakes left "
        "by the ones before it, and their outputs ADD UP into the final score.",
    )
