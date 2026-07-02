"""Component specification types — the declarative contract for every Lab capability.

A `ComponentSpec` is pure data: it describes what a component is, what it consumes and
produces, and what parameters it accepts (as JSON Schema). The same spec drives BOTH the
agent tool list and the frontend forms, so adding a plugin needs zero UI code.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ComponentKind(str, Enum):
    """The category of work a component performs. Labs are collections of components."""

    CONNECTOR = "connector"        # Data/Signal Lab: bring data in
    TRANSFORM = "transform"        # Data Lab: clean / encode / scale / impute
    CHART = "chart"                # Insight Lab: a visualization spec
    MODEL = "model"                # Model Lab: fit / predict (ml | dl | econometrics | ts | anomaly)
    EVALUATOR = "evaluator"        # Model Lab: metrics
    ANALYZER = "analyzer"          # Trend Lab: decompose / detect / causal-impact
    DECISION = "decision"          # Decision Lab: rules / scenarios / counterfactuals
    REPORT_BLOCK = "report_block"  # Intelligence Lab: a report section
    TOOL = "tool"                  # generic agent tool
    SKILL = "skill"                # a learned, reusable procedure distilled from past runs


class Port(BaseModel):
    """A named input or output slot of a component."""

    name: str
    dtype: str = Field(description="Logical type, e.g. 'dataset', 'model', 'figure', 'metrics'.")
    required: bool = True
    description: str = ""


class ComponentSpec(BaseModel):
    """Declarative description of a component. `params_schema` is a JSON Schema object."""

    kind: ComponentKind
    id: str = Field(description="Stable unique id, e.g. 'model.ml.linear_regression'.")
    name: str
    version: str = "0.1.0"
    summary: str = ""
    params_schema: dict = Field(default_factory=lambda: {"type": "object", "properties": {}})
    inputs: list[Port] = Field(default_factory=list)
    outputs: list[Port] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    def matches(self, kind: ComponentKind | None = None, tags: list[str] | None = None) -> bool:
        if kind is not None and self.kind != kind:
            return False
        if tags and not set(tags).issubset(set(self.tags)):
            return False
        return True
