"""Tests del grafo LangGraph — routing y estado final."""

from __future__ import annotations

from pathlib import Path

from real_estate_referrer.config import SearchConfig
from real_estate_referrer.agents import (
    RequirementsAgent,
    RuleBasedStubLLMClient,
    SearchCoordinatorAgent,
    ValidationAgent,
)
from real_estate_referrer.agents.property_search_subagent import PropertySearchSubAgent
from real_estate_referrer.agents.safety_news_subagent import SafetyNewsSubAgent
from real_estate_referrer.connectors import (
    FixturesNewsConnector,
    FixturesPropertyConnector,
)
from real_estate_referrer.graph import build_referrer_graph, initial_state, state_to_final_response
from real_estate_referrer.graph.state import ReferrerState

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _graph_app(config: SearchConfig | None = None):
    cfg = config or SearchConfig(
        connector_mode="fixtures",
        enabled_property_sources=["fixtures"],
        enabled_news_sources=["fixtures"],
        max_rounds=2,
    )
    llm = RuleBasedStubLLMClient()
    property_sub = PropertySearchSubAgent(
        [FixturesPropertyConnector(FIXTURES_DIR / "properties_medellin.json")]
    )
    safety_sub = SafetyNewsSubAgent(
        [FixturesNewsConnector(FIXTURES_DIR / "news_default.json")],
        news_window_days=cfg.news_window_days,
    )
    coordinator = SearchCoordinatorAgent(property_sub, safety_sub, config=cfg)
    requirements_agent = RequirementsAgent(llm, cfg)
    validator = ValidationAgent(cfg)
    graph = build_referrer_graph(requirements_agent, coordinator, validator)
    return graph, cfg


def test_graph_invoke_returns_ranking_for_typical_prompt() -> None:
    graph, cfg = _graph_app()
    state = graph.invoke(
        initial_state(
            "Busco apartamento en arriendo en Laureles, Medellín, 2 habitaciones, "
            "hasta 1.500.000, ojalá con parqueadero.",
            cfg,
        )
    )
    response = state_to_final_response(state)
    assert response.requirements.location.city == "Medellín"
    assert response.ranking
    assert response.rounds >= 1
    assert any("requirements_agent" in entry for entry in response.log)


def test_graph_routes_through_relaxation_when_needed() -> None:
    graph, cfg = _graph_app(
        SearchConfig(
            connector_mode="fixtures",
            enabled_property_sources=["fixtures"],
            enabled_news_sources=["fixtures"],
            max_rounds=2,
            min_final_score=0.55,
        )
    )
    state = graph.invoke(
        initial_state(
            "Apto en arriendo en Laureles, Medellín, 2 habitaciones, hasta 1.000.000.",
            cfg,
        )
    )
    response = state_to_final_response(state)
    assert response.rounds >= 1
    assert any("ronda" in entry for entry in response.log)


def test_route_after_validate_values() -> None:
    from real_estate_referrer.graph.builder import route_after_validate

    end_state: ReferrerState = {
        "user_prompt": "x",
        "config": SearchConfig(),
        "requirements": None,
        "scored": [],
        "approved": [],
        "round_index": 0,
        "rounds_used": 1,
        "route": "end",
        "log": [],
    }
    assert route_after_validate(end_state) == "end"

    loop_state = {**end_state, "route": "coordinate"}
    assert route_after_validate(loop_state) == "coordinate"
