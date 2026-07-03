"""Decision components — threshold rules and expected-value choice."""

from __future__ import annotations

from typing import Any

from laboratree_sdk import Component, ComponentKind, ComponentSpec, Port, RunContext, register


@register
class ThresholdRule(Component):
    spec = ComponentSpec(
        kind=ComponentKind.DECISION,
        id="decision.threshold_rule",
        name="Threshold rule",
        summary="Recommend an action per row based on a column threshold.",
        params_schema={
            "type": "object",
            "required": ["column", "threshold"],
            "properties": {
                "column": {"type": "string"},
                "threshold": {"type": "number"},
                "direction": {"type": "string", "enum": ["above", "below"], "default": "above"},
                "action_true": {"type": "string", "default": "act"},
                "action_false": {"type": "string", "default": "hold"},
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="decision", dtype="decision")],
        tags=["decision", "rules"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        df = ctx.inputs["dataset"]
        col = ctx.params["column"]
        thr = float(ctx.params["threshold"])
        above = ctx.params.get("direction", "above") == "above"
        at, af = ctx.params.get("action_true", "act"), ctx.params.get("action_false", "hold")

        mask = df[col] >= thr if above else df[col] <= thr
        n_true = int(mask.sum())
        summary = {
            "action_true": at, "action_false": af,
            "n_true": n_true, "n_false": int(len(df) - n_true),
            "rule": f"{col} {'>=' if above else '<='} {thr}",
        }
        ctx.emit("n_recommended", n_true, kind="metric", component=self.spec.id)
        ctx.emit("recommendation_summary", summary, kind="claim", component=self.spec.id)
        return {"summary": summary}


@register
class ExpectedValue(Component):
    spec = ComponentSpec(
        kind=ComponentKind.DECISION,
        id="decision.expected_value",
        name="Expected value choice",
        summary="Rank options by expected value (value × probability) and recommend the best.",
        params_schema={
            "type": "object",
            "required": ["options"],
            "properties": {
                "options": {
                    "type": "array",
                    "title": "Options",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "value": {"type": "number"},
                            "probability": {"type": "number"},
                        },
                    },
                }
            },
        },
        inputs=[],
        outputs=[Port(name="decision", dtype="decision")],
        tags=["decision", "uncertainty"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        options = ctx.params["options"]
        ranked = sorted(
            (
                {
                    "name": o.get("name", f"option_{i}"),
                    "ev": round(float(o.get("value", 0)) * float(o.get("probability", 0)), 4),
                }
                for i, o in enumerate(options)
            ),
            key=lambda x: -x["ev"],
        )
        recommended = ranked[0]["name"] if ranked else None
        ctx.emit("best_ev", ranked[0]["ev"] if ranked else 0, kind="metric", component=self.spec.id)
        ctx.emit("recommended", recommended, kind="claim", component=self.spec.id)
        return {"ranked": ranked, "recommended": recommended}
