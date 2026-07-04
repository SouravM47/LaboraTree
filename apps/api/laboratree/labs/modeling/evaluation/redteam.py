"""Adversarial Red-Team Critic — independently stress-tests a candidate model.

Attacks: noise robustness, feature ablation (fragility), subgroup performance, and a leakage
re-check. Produces findings + a PASS/FAIL verdict so only models that survive scrutiny ship.
Deterministic (seeded) — no LLM required.
"""

from __future__ import annotations

from typing import Any

from laboratree_sdk import Component, ComponentKind, ComponentSpec, Port, RunContext, register

from ..leakage import audit_leakage
from .metrics import classification_metrics, numeric_features, regression_metrics

_SEED = 1729


def _is_classification(y) -> bool:
    import pandas as pd

    # pandas 2.x infers the "str" dtype (not object) for text columns — treat all as categorical.
    if y.dtype == object or str(y.dtype).startswith(("category", "str")):
        return True
    return bool(pd.api.types.is_integer_dtype(y) and y.nunique() <= 10)


def _metric(task: str, y_true, y_pred) -> float:
    if task == "classification":
        return classification_metrics(y_true, y_pred)["accuracy"]
    return regression_metrics(y_true, y_pred)["r2"]


@register
class RedTeamCritic(Component):
    spec = ComponentSpec(
        kind=ComponentKind.EVALUATOR,
        id="critic.red_team",
        name="Red-Team Critic",
        summary="Stress-test a model: noise robustness, ablation, subgroups, leakage -> verdict.",
        params_schema={
            "type": "object",
            "required": ["target"],
            "properties": {
                "target": {"type": "string"},
                "features": {"type": "array", "items": {"type": "string"}},
                "test_size": {"type": "number", "default": 0.25},
                "noise_scale": {"type": "number", "default": 0.5, "title": "Perturbation σ (×std)"},
                "subgroup_column": {"type": "string"},
                "drop_tolerance": {"type": "number", "default": 0.2, "title": "Max relative metric drop"},
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="verdict", dtype="verdict")],
        tags=["trust", "red-team", "evaluation"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        import numpy as np
        import pandas as pd
        from sklearn.linear_model import LinearRegression, LogisticRegression
        from sklearn.model_selection import train_test_split

        df: pd.DataFrame = ctx.inputs["dataset"].dropna()
        target = ctx.params["target"]
        feats = numeric_features(df, target, ctx.params.get("features"))
        if not feats:
            raise ValueError("no numeric features for the red-team critic")

        y_raw = df[target]
        task = "classification" if _is_classification(y_raw) else "regression"
        # encode any non-numeric class labels (object/str/category), not just object dtype
        needs_encode = task == "classification" and not pd.api.types.is_numeric_dtype(y_raw)
        y = y_raw.astype("category").cat.codes if needs_encode else y_raw
        X = df[feats]
        strat = y if task == "classification" and y.nunique() > 1 else None
        Xtr, Xte, ytr, yte = train_test_split(
            X, y, test_size=ctx.params.get("test_size", 0.25), random_state=_SEED, stratify=strat
        )

        def _fit(cols):
            model = (LogisticRegression(max_iter=1000) if task == "classification"
                     else LinearRegression())
            model.fit(Xtr[cols], ytr)
            return model

        base_model = _fit(feats)
        base = _metric(task, yte, base_model.predict(Xte[feats]))

        # 1) noise robustness
        rng = np.random.default_rng(_SEED)
        noise = rng.normal(0, ctx.params.get("noise_scale", 0.5) * Xte[feats].std().to_numpy(), Xte[feats].shape)
        perturbed = _metric(task, yte, base_model.predict(Xte[feats] + noise))
        robustness_drop = round(base - perturbed, 4)

        # 2) feature ablation
        ablation = {}
        for f in feats:
            rest = [c for c in feats if c != f]
            if rest:
                ablation[f] = round(base - _metric(task, yte, _fit(rest).predict(Xte[rest])), 4)

        # 3) subgroup performance
        subgroup: dict[str, Any] = {}
        subcol = ctx.params.get("subgroup_column")
        if subcol and subcol in df.columns:
            te_groups = df.loc[Xte.index, subcol]
            per = {}
            for g, idx in te_groups.groupby(te_groups).groups.items():
                sel = [i for i in idx if i in Xte.index]
                if len(sel) >= 3:
                    per[str(g)] = round(_metric(task, y.loc[sel], base_model.predict(X.loc[sel, feats])), 4)
            if per:
                subgroup = {"per_group": per, "gap": round(base - min(per.values()), 4)}

        # 4) leakage re-check
        leakage = audit_leakage(df, target, feature_cols=feats)

        rel_drop = robustness_drop / abs(base) if base else 1.0
        tol = ctx.params.get("drop_tolerance", 0.2)
        findings = []
        if rel_drop > tol:
            findings.append({"check": "robustness", "severity": "high",
                             "detail": f"metric drops {robustness_drop} under noise ({rel_drop:.0%})"})
        if any(f["severity"] == "high" for f in leakage):
            findings.append({"check": "leakage", "severity": "high", "detail": "target/temporal leakage detected"})
        if subgroup and subgroup["gap"] > tol:
            findings.append({"check": "subgroup", "severity": "medium",
                             "detail": f"subgroup gap {subgroup['gap']}"})

        verdict = "FAIL" if any(f["severity"] == "high" for f in findings) else "PASS"

        ctx.emit("base_metric", round(base, 4), kind="metric", component=self.spec.id)
        ctx.emit("robustness_drop", robustness_drop, kind="metric", component=self.spec.id)
        ctx.emit("verdict", verdict, kind="claim", component=self.spec.id)
        return {
            "verdict": verdict,
            "task": task,
            "base_metric": round(base, 4),
            "robustness_drop": robustness_drop,
            "ablation": ablation,
            "subgroup": subgroup,
            "leakage_findings": leakage,
            "findings": findings,
        }
