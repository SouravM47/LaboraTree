---
name: laboratree-scaffold
description: Scaffold a new Laboratree Lab or Component from the plugin-SDK template. Use when the user wants to add a capability (transform, model, chart, evaluator, connector, analyzer, decision, report_block) or a whole new Lab under apps/api/laboratree/labs. Keeps the plug-in/plug-out pattern consistent.
---

# Laboratree scaffold

Add Labs and Components consistently. Everything an agent or the UI can use is a `Component`
registered with the global registry; the `ComponentSpec` drives both the agent tool list and the
frontend forms, so **no UI code is needed** for a new component.

## Add a Component to an existing Lab

1. Pick the Lab package: `apps/api/laboratree/labs/<lab>/`.
2. Create (or extend) a module and add a `Component` subclass with a class-level `spec`.
3. It is auto-discovered on startup — no registration list to edit.

Template:

```python
from typing import Any

from laboratree_sdk import Component, ComponentKind, ComponentSpec, Port, RunContext, register


@register
class MyThing(Component):
    spec = ComponentSpec(
        kind=ComponentKind.TRANSFORM,          # or MODEL / CHART / EVALUATOR / CONNECTOR / ...
        id="transform.my_thing",               # stable, unique, dotted; family in the path
        name="My thing",
        summary="One line describing what it does.",
        params_schema={                          # JSON Schema -> renders a UI form automatically
            "type": "object",
            "properties": {
                "threshold": {"type": "number", "default": 0.5, "title": "Threshold"},
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="dataset", dtype="dataset")],
        tags=["cleaning"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        df = ctx.inputs["dataset"]
        # ... do work using ctx.params ...
        ctx.emit("some_metric", 123, kind="metric", component=self.spec.id)  # provenance-locked
        return {"dataset": df}
```

Rules:
- **Every reported number** goes through `ctx.emit(...)` (Evidence Ledger) — never return metrics
  that weren't actually computed.
- Model families live under `labs/modeling/<family>/` where family ∈
  `ml | dl_pytorch | econometrics | timeseries | anomaly`. Variants (AR1/AR2) = same id + params.
- Reuse mature libraries; don't reimplement algorithms.
- Heavy/DL model code that an agent generates runs in the sandbox, not in-process.

## Add a new Lab

1. `apps/api/laboratree/labs/<lab>/__init__.py` with a one-line docstring.
2. Add components as above. (Discovery walks all `laboratree.labs.*` packages.)
3. If the Lab needs endpoints, add a router in `apps/api/laboratree/api/<lab>.py` and include it in
   `main.py`. If it needs an agent team, add a LangGraph graph under `laboratree/agents/`.
4. Add a page under `apps/web/app/<lab>/` and a card on the home Labs grid.

## Verify

```bash
cd apps/api && uv run python -c "from laboratree.core.registry import discover, REGISTRY; discover(); print(REGISTRY.ids())"
```
The new component id should appear, and `GET /api/components` should list it.
