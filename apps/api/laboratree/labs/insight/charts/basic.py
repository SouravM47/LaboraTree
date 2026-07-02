"""Chart components — emit self-contained Vega-Lite specs (data embedded) for the frontend.

Light-forest palette: leaf #6DB33F, forest #14342A.
"""

from __future__ import annotations

from typing import Any

from laboratree_sdk import Component, ComponentKind, ComponentSpec, Port, RunContext, register

VEGA = "https://vega.github.io/schema/vega-lite/v5.json"
_SAMPLE = 5000


def _records(df, cols: list[str]) -> list[dict[str, Any]]:
    sub = df[cols].dropna()
    if len(sub) > _SAMPLE:
        sub = sub.sample(_SAMPLE, random_state=1729)
    return sub.to_dict(orient="records")


@register
class HistogramChart(Component):
    spec = ComponentSpec(
        kind=ComponentKind.CHART,
        id="chart.histogram",
        name="Histogram",
        summary="Distribution of a numeric column.",
        params_schema={
            "type": "object",
            "required": ["column"],
            "properties": {
                "column": {"type": "string", "title": "Column"},
                "maxbins": {"type": "integer", "default": 30},
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="spec", dtype="vega")],
        tags=["chart", "insight"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        col = ctx.params["column"]
        df = ctx.inputs["dataset"]
        spec = {
            "$schema": VEGA,
            "title": f"Distribution of {col}",
            "data": {"values": _records(df, [col])},
            "mark": {"type": "bar", "color": "#6DB33F"},
            "encoding": {
                "x": {"field": col, "bin": {"maxbins": ctx.params.get("maxbins", 30)},
                      "type": "quantitative"},
                "y": {"aggregate": "count", "type": "quantitative", "title": "count"},
            },
        }
        ctx.emit("points", len(spec["data"]["values"]), kind="metric", component=self.spec.id)
        return {"spec": spec}


@register
class ScatterChart(Component):
    spec = ComponentSpec(
        kind=ComponentKind.CHART,
        id="chart.scatter",
        name="Scatter plot",
        summary="Relationship between two numeric columns (optional color).",
        params_schema={
            "type": "object",
            "required": ["x", "y"],
            "properties": {
                "x": {"type": "string"},
                "y": {"type": "string"},
                "color": {"type": "string", "title": "Color by (optional)"},
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="spec", dtype="vega")],
        tags=["chart", "insight"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        x, y = ctx.params["x"], ctx.params["y"]
        color = ctx.params.get("color")
        cols = [x, y] + ([color] if color else [])
        enc: dict[str, Any] = {
            "x": {"field": x, "type": "quantitative"},
            "y": {"field": y, "type": "quantitative"},
        }
        if color:
            enc["color"] = {"field": color, "type": "nominal", "scale": {"scheme": "greens"}}
        spec = {
            "$schema": VEGA,
            "title": f"{y} vs {x}",
            "data": {"values": _records(ctx.inputs["dataset"], cols)},
            "mark": {"type": "point", "filled": True, "color": "#14342A", "opacity": 0.6},
            "encoding": enc,
        }
        ctx.emit("points", len(spec["data"]["values"]), kind="metric", component=self.spec.id)
        return {"spec": spec}


@register
class CorrelationHeatmap(Component):
    spec = ComponentSpec(
        kind=ComponentKind.CHART,
        id="chart.correlation_heatmap",
        name="Correlation heatmap",
        summary="Pairwise correlation of numeric columns.",
        params_schema={"type": "object", "properties": {}},
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="spec", dtype="vega")],
        tags=["chart", "insight", "correlation"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        numeric = ctx.inputs["dataset"].select_dtypes("number")
        if numeric.shape[1] < 2:
            raise ValueError("need at least 2 numeric columns for a correlation heatmap")
        corr = numeric.corr(numeric_only=True)
        long = [
            {"a": str(a), "b": str(b), "corr": round(float(corr.loc[a, b]), 3)}
            for a in corr.columns
            for b in corr.columns
        ]
        spec = {
            "$schema": VEGA,
            "title": "Correlation heatmap",
            "data": {"values": long},
            "mark": "rect",
            "encoding": {
                "x": {"field": "a", "type": "nominal", "title": ""},
                "y": {"field": "b", "type": "nominal", "title": ""},
                "color": {"field": "corr", "type": "quantitative",
                          "scale": {"scheme": "redyellowgreen", "domain": [-1, 1]}},
                "tooltip": [{"field": "a"}, {"field": "b"}, {"field": "corr"}],
            },
        }
        ctx.emit("n_cells", len(long), kind="metric", component=self.spec.id)
        return {"spec": spec}
