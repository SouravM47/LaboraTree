"""Deep-learning family — real PyTorch nets: 1-D CNN and recurrent (RNN/LSTM/GRU, optional
bidirectional).

Tabular adaptation (what CNN/LSTM papers on tabular data actually do): each row's k standardized
features become a length-k sequence with one channel. Auto-detects classification vs regression.
PyTorch is imported lazily inside run() so registry discovery stays fast.
"""

from __future__ import annotations

from typing import Any

from laboratree_sdk import Component, ComponentKind, ComponentSpec, Port, RunContext, register

from ...evaluation.metrics import (
    as_metric_dict,
    classification_metrics,
    numeric_features,
    regression_metrics,
    sample_predictions,
)

_SEED = 1729


def _is_classification(y) -> bool:
    if y.dtype == object or str(y.dtype).startswith("category") or str(y.dtype) == "bool":
        return True
    return y.nunique() <= 10


def _train_torch(component: Component, ctx: RunContext, build_net) -> dict[str, Any]:
    """Shared loop: standardize -> split -> minibatch Adam training -> metrics -> Evidence emits.
    ``build_net(k, out_dim)`` returns an nn.Module taking (batch, k) float tensors."""
    import numpy as np
    import pandas as pd
    import torch
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from torch import nn

    df: pd.DataFrame = ctx.inputs["dataset"].dropna()
    target = ctx.params["target"]
    feats = numeric_features(df, target, ctx.params.get("features"))
    if not feats:
        raise ValueError(f"no numeric features available for {component.spec.name}")

    y = df[target]
    classify = _is_classification(y)
    # pandas 3 infers `str` dtype (not object) for text columns — code ANY non-numeric target
    if classify and not pd.api.types.is_numeric_dtype(y):
        y = y.astype("category").cat.codes
    task = "classification" if classify else "regression"
    n_out = int(y.nunique()) if classify else 1

    Xs = StandardScaler().fit_transform(df[feats]).astype("float32")
    yv = y.to_numpy()
    strat = yv if (classify and len(np.unique(yv)) > 1) else None
    Xtr, Xte, ytr, yte = train_test_split(
        Xs, yv, test_size=ctx.params.get("test_size", 0.25), random_state=_SEED, stratify=strat
    )

    torch.manual_seed(_SEED)
    net = build_net(len(feats), n_out)
    loss_fn = nn.CrossEntropyLoss() if classify else nn.MSELoss()
    opt = torch.optim.Adam(net.parameters(), lr=ctx.params.get("lr", 1e-3))
    epochs = int(ctx.params.get("epochs", 30))

    Xt = torch.from_numpy(Xtr)
    yt = torch.from_numpy(ytr.astype("int64" if classify else "float32"))
    ds = torch.utils.data.TensorDataset(Xt, yt)
    loader = torch.utils.data.DataLoader(ds, batch_size=64, shuffle=True)

    net.train()
    for _ in range(epochs):
        for xb, yb in loader:
            opt.zero_grad()
            out = net(xb)
            loss = loss_fn(out if classify else out.squeeze(-1), yb)
            loss.backward()
            opt.step()

    net.eval()
    with torch.no_grad():
        logits = net(torch.from_numpy(Xte))
        if classify:
            proba = torch.softmax(logits, dim=1).numpy()
            pred = proba.argmax(axis=1)
            metrics = as_metric_dict(classification_metrics(yte, pred, proba))
        else:
            pred = logits.squeeze(-1).numpy()
            metrics = as_metric_dict(regression_metrics(yte, pred))

    for k, v in metrics.items():
        ctx.emit(k, v, kind="metric", component=component.spec.id)
    return {
        "metrics": metrics,
        "task": task,
        "n_test": int(len(yte)),
        "predictions": sample_predictions(pd.Series(yte), pred, task),
    }


@register
class CNNModel(Component):
    spec = ComponentSpec(
        kind=ComponentKind.MODEL,
        id="model.dl.cnn",
        name="CNN (PyTorch, 1-D)",
        summary="Convolutional net over the feature sequence — real PyTorch training loop. "
        "Auto-detects classification vs regression.",
        params_schema={
            "type": "object",
            "required": ["target"],
            "properties": {
                "target": {"type": "string", "title": "Target column"},
                "features": {"type": "array", "items": {"type": "string"}, "title": "Features"},
                "test_size": {"type": "number", "default": 0.25},
                "epochs": {"type": "integer", "default": 30, "title": "Training epochs"},
                "channels": {"type": "integer", "default": 16, "title": "Conv channels"},
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="metrics", dtype="metrics")],
        tags=["dl", "pytorch", "cnn", "classification", "regression"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        from torch import nn

        ch = int(ctx.params.get("channels", 16))

        def build(k: int, out: int):
            class Net(nn.Module):
                def __init__(self):
                    super().__init__()
                    self.conv = nn.Sequential(
                        nn.Conv1d(1, ch, kernel_size=3, padding=1),
                        nn.ReLU(),
                        nn.Conv1d(ch, ch * 2, kernel_size=3, padding=1),
                        nn.ReLU(),
                        nn.AdaptiveAvgPool1d(1),
                    )
                    self.fc = nn.Linear(ch * 2, out)

                def forward(self, x):  # x: (batch, k)
                    z = self.conv(x.unsqueeze(1)).squeeze(-1)
                    return self.fc(z)

            return Net()

        return _train_torch(self, ctx, build)


@register
class RecurrentNetModel(Component):
    spec = ComponentSpec(
        kind=ComponentKind.MODEL,
        id="model.dl.rnn",
        name="Recurrent Net (PyTorch: RNN/LSTM/GRU)",
        summary="Recurrent network over the feature sequence — cell type and bidirectionality are "
        "params (LSTM/GRU/RNN, BiLSTM = lstm + bidirectional). Real PyTorch training loop.",
        params_schema={
            "type": "object",
            "required": ["target"],
            "properties": {
                "target": {"type": "string", "title": "Target column"},
                "features": {"type": "array", "items": {"type": "string"}, "title": "Features"},
                "test_size": {"type": "number", "default": 0.25},
                "cell": {
                    "type": "string",
                    "enum": ["lstm", "gru", "rnn"],
                    "default": "lstm",
                    "title": "Recurrent cell",
                },
                "bidirectional": {"type": "boolean", "default": False, "title": "Bidirectional"},
                "hidden": {"type": "integer", "default": 32, "title": "Hidden units"},
                "epochs": {"type": "integer", "default": 30, "title": "Training epochs"},
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="metrics", dtype="metrics")],
        tags=["dl", "pytorch", "rnn", "lstm", "gru", "classification", "regression"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        from torch import nn

        cell = str(ctx.params.get("cell", "lstm")).lower()
        bidir = bool(ctx.params.get("bidirectional", False))
        hidden = int(ctx.params.get("hidden", 32))
        Cell = {"rnn": nn.RNN, "lstm": nn.LSTM, "gru": nn.GRU}.get(cell, nn.LSTM)

        def build(k: int, out: int):
            class Net(nn.Module):
                def __init__(self):
                    super().__init__()
                    self.rnn = Cell(1, hidden, batch_first=True, bidirectional=bidir)
                    self.fc = nn.Linear(hidden * (2 if bidir else 1), out)

                def forward(self, x):  # x: (batch, k)
                    o, _ = self.rnn(x.unsqueeze(-1))
                    return self.fc(o[:, -1, :])

            return Net()

        return _train_torch(self, ctx, build)
