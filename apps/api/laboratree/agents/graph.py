"""The core agent graph — a minimal, durable, human-in-the-loop research loop on LangGraph.

Flow:  planner -> human_gate (interrupt for approval) -> engineer -> critic -> END.

The gate uses LangGraph's `interrupt`, so a run pauses with its state checkpointed and resumes
only when a human decision arrives (mirrored to a `GateTask` in the API layer). The LLM call is
injected (`complete_fn`) so the graph is fully testable without a live model, and in production
defaults to the Azure-backed `LLMClient`.
"""

from __future__ import annotations

from typing import Any, Callable, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

CompleteFn = Callable[[str, str], str]  # (system, prompt) -> text


class AgentState(TypedDict, total=False):
    task: str
    plan: str
    approved: bool
    result: str
    verdict: str


def _default_complete(system: str, prompt: str) -> str:
    from ..core.llm import get_llm

    return get_llm().complete(prompt, system=system)


def build_graph(complete_fn: CompleteFn | None = None, checkpointer: Any | None = None):
    """Compile the agent graph. `checkpointer` defaults to in-memory (use PostgresSaver in prod)."""
    complete = complete_fn or _default_complete

    def planner(state: AgentState) -> dict[str, Any]:
        plan = complete(
            "You are the Planner. Draft a short numbered plan to accomplish the task.",
            state["task"],
        )
        return {"plan": plan}

    def human_gate(state: AgentState) -> dict[str, Any]:
        decision = interrupt({"action": "approve_plan", "plan": state.get("plan", "")})
        approved = bool(decision.get("approved")) if isinstance(decision, dict) else bool(decision)
        return {"approved": approved}

    def engineer(state: AgentState) -> dict[str, Any]:
        result = complete(
            "You are the Engineer. Execute the approved plan and report the outcome.",
            f"Task: {state['task']}\nPlan:\n{state.get('plan', '')}",
        )
        return {"result": result}

    def critic(state: AgentState) -> dict[str, Any]:
        verdict = complete(
            "You are the Critic. Judge whether the result satisfies the task. Reply PASS or FAIL "
            "with one sentence.",
            f"Task: {state['task']}\nResult:\n{state.get('result', '')}",
        )
        return {"verdict": verdict}

    def route_after_gate(state: AgentState) -> str:
        return "engineer" if state.get("approved") else END

    g = StateGraph(AgentState)
    g.add_node("planner", planner)
    g.add_node("human_gate", human_gate)
    g.add_node("engineer", engineer)
    g.add_node("critic", critic)

    g.add_edge(START, "planner")
    g.add_edge("planner", "human_gate")
    g.add_conditional_edges("human_gate", route_after_gate, {"engineer": "engineer", END: END})
    g.add_edge("engineer", "critic")
    g.add_edge("critic", END)

    return g.compile(checkpointer=checkpointer or MemorySaver())


def start(graph, task: str, thread_id: str) -> dict[str, Any]:
    """Run until the human gate interrupts (or completion). Returns the result dict."""
    return graph.invoke({"task": task}, config={"configurable": {"thread_id": thread_id}})


def resume(graph, thread_id: str, approved: bool, **extra: Any) -> dict[str, Any]:
    """Resume a paused run with the human decision."""
    payload = {"approved": approved, **extra}
    return graph.invoke(
        Command(resume=payload), config={"configurable": {"thread_id": thread_id}}
    )


def is_interrupted(result: dict[str, Any]) -> bool:
    return "__interrupt__" in result
