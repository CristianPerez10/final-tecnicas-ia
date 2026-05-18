"""Construcción y compilación del StateGraph."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from real_estate_referrer.agents.requirements_agent import RequirementsAgent
from real_estate_referrer.agents.search_coordinator import SearchCoordinatorAgent
from real_estate_referrer.agents.validation_agent import ValidationAgent
from real_estate_referrer.graph.nodes import (
    make_coordinate_node,
    make_extract_node,
    make_validate_node,
)
from real_estate_referrer.graph.state import GraphRoute, ReferrerState
from real_estate_referrer.models import FinalResponse


def route_after_validate(state: ReferrerState) -> GraphRoute:
    """Arista condicional tras validación."""
    return state["route"]


def build_referrer_graph(
    requirements_agent: RequirementsAgent,
    coordinator: SearchCoordinatorAgent,
    validator: ValidationAgent,
):
    """Compila el grafo del pipeline (extract → coordinate ↔ validate)."""
    graph = StateGraph(ReferrerState)
    graph.add_node("extract_requirements", make_extract_node(requirements_agent))
    graph.add_node("coordinate_search", make_coordinate_node(coordinator))
    graph.add_node("validate_candidates", make_validate_node(validator))

    graph.add_edge(START, "extract_requirements")
    graph.add_edge("extract_requirements", "coordinate_search")
    graph.add_edge("coordinate_search", "validate_candidates")
    graph.add_conditional_edges(
        "validate_candidates",
        route_after_validate,
        {"end": END, "coordinate": "coordinate_search"},
    )

    return graph.compile()


def state_to_final_response(state: ReferrerState) -> FinalResponse:
    """Mapea el estado final del grafo a `FinalResponse`."""
    requirements = state["requirements"]
    if requirements is None:
        raise RuntimeError("state_to_final_response: requirements ausentes")

    rounds = state.get("rounds_used") or 0
    if rounds < 1:
        rounds = 1

    return FinalResponse(
        requirements=requirements,
        ranking=state.get("approved") or [],
        rounds=rounds,
        log=state.get("log") or [],
    )


def initial_state(
    user_prompt: str,
    config,
) -> ReferrerState:
    """Estado inicial para `graph.invoke`."""
    return ReferrerState(
        user_prompt=user_prompt,
        config=config,
        requirements=None,
        scored=[],
        approved=[],
        round_index=0,
        rounds_used=0,
        route="end",
        log=[],
    )
