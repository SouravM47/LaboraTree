"""Neural-network family — MLP / deep-learning style models.

Training view: the layer structure + a forward pass. Testing view: input -> hidden activations ->
output for each held-out row.
"""

from __future__ import annotations

from . import register_tracer
from .common import lbl, resolve_params, split_holdout, table_rows
from .schema import ModelTrace

SPEC = [
    {"key": "hidden", "label": "Hidden units", "type": "int", "default": 5, "min": 2, "max": 12,
     "step": 1, "help": "Neurons in the hidden layer — more = more capacity to fit complex patterns."},
    {"key": "activation", "label": "Activation", "type": "select", "default": "tanh",
     "options": ["tanh", "relu", "logistic"],
     "help": "The squashing function each hidden unit applies to its weighted input."},
    {"key": "max_iter", "label": "Training epochs", "type": "int", "default": 150, "min": 50,
     "max": 500, "step": 50, "help": "How many passes over the data the network trains for."},
]


@register_tracer("nn")
def trace_nn(X, y, feats, target, task, labels, params=None) -> ModelTrace:
    import numpy as np
    from sklearn.neural_network import MLPClassifier, MLPRegressor
    from sklearn.preprocessing import StandardScaler

    p, param_spec = resolve_params(SPEC, params)
    act = p["activation"]
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)
    Xtr, Xte, ytr, yte = split_holdout(X, y)
    m = min(600, len(Xs) - len(Xte))
    Model = MLPClassifier if task == "classification" else MLPRegressor
    net = Model(
        hidden_layer_sizes=(p["hidden"],), activation=act, max_iter=p["max_iter"], random_state=0
    ).fit(Xs[:m], y.iloc[:m])
    show = feats[:6]

    def _activate(z):
        if act == "relu":
            return np.maximum(0.0, z)
        if act == "logistic":
            return 1.0 / (1.0 + np.exp(-z))
        return np.tanh(z)

    def forward(scaled_row):
        hidden = _activate(scaled_row @ net.coefs_[0] + net.intercepts_[0])
        out = hidden @ net.coefs_[1] + net.intercepts_[1]
        return np.ravel(hidden), float(np.ravel(out)[0])

    preds = net.predict(scaler.transform(Xte))
    test_rows = []
    for j in range(len(Xte)):
        srow = scaler.transform(Xte.iloc[[j]])[0]
        hidden, out = forward(srow)
        pred = lbl(preds[j], task, labels)
        actual = lbl(yte.iloc[j], task, labels)
        test_rows.append({
            "values": {f: round(float(Xte.iloc[j][f]), 3) for f in feats[:24]},
            "input": [round(float(v), 2) for v in srow[: len(show)]],
            "hidden": [round(float(v), 2) for v in hidden],
            "output": round(float(out), 3),
            "predicted": pred, "actual": actual,
            "correct": (pred == actual) if task == "classification" else None,
            "error": None if task == "classification" else round(float(preds[j]) - float(yte.iloc[j]), 3),
        })
    h0, o0 = forward(Xs[0])
    # real learned weights for the literal network drawing (shown features x hidden, hidden x out)
    idx = [feats.index(f) for f in show]
    w1 = [[round(float(net.coefs_[0][i][j]), 3) for j in range(net.coefs_[0].shape[1])] for i in idx]
    w2 = [round(float(net.coefs_[1][j][0]), 3) for j in range(net.coefs_[1].shape[0])]
    return ModelTrace(
        family="nn", target=target, task=task, features=show, labels=labels,
        table=table_rows(X, y, show, target, task, labels),
        layers=[len(feats), p["hidden"], 1],
        forward={
            "input": [round(float(v), 2) for v in Xs[0][: len(show)]],
            "input_names": show,
            "hidden": [round(float(v), 2) for v in h0],
            "output": round(float(o0), 3),
            "w1": w1,
            "w2": w2,
        },
        test_rows=test_rows, params=p, param_spec=param_spec,
        note="Standardized feature values flow into the hidden layer (each unit is a weighted mix "
        "passed through a squashing function), then combine into the output.",
    )
