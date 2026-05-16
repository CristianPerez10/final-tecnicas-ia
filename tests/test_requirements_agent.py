"""Tests P3 — RequirementsAgent con stubs determinísticos y mocks."""

from __future__ import annotations

import pytest

from real_estate_referrer.agents import (
    EchoLLMClient,
    RequirementsAgent,
    RequirementsAgentError,
    RuleBasedStubLLMClient,
)
from real_estate_referrer.config import SearchConfig


def test_requirements_agent_with_rule_based_stub() -> None:
    agent = RequirementsAgent(llm=RuleBasedStubLLMClient(), config=SearchConfig())
    req = agent.extract(
        "Busco apartamento en arriendo en Laureles, Medellín, 2 habitaciones, "
        "hasta 1.500.000, ojalá con parqueadero."
    )
    assert req.property_type == "apartamento"
    assert req.operation == "arriendo"
    assert req.bedrooms.min == 2 and req.bedrooms.max == 2
    assert req.price.max == 1_500_000.0
    assert req.location.city == "Medellín"
    assert req.location.neighborhood == "Laureles"
    assert req.parking_spots.min == 1


def test_requirements_agent_applies_defaults_when_minimal_prompt() -> None:
    agent = RequirementsAgent(llm=RuleBasedStubLLMClient())
    req = agent.extract("Necesito una casa")
    assert req.location.city == "Medellín"
    assert "location.city" in req.defaults_applied
    assert req.bedrooms.min == 1
    assert "bedrooms" in req.defaults_applied
    assert req.price.min == 500_000.0
    assert "price" in req.defaults_applied


def test_requirements_agent_with_echo_client_uses_full_payload() -> None:
    echo_payload = {
        "raw_user_prompt": "test",
        "property_type": "apartaestudio",
        "operation": "arriendo",
        "area_sqm": {"min": 30, "max": 45},
        "price": {"min": None, "max": 1200000},
        "currency": "COP",
        "location": {
            "city": "Medellín",
            "neighborhood": "El Poblado",
            "landmarks": [],
            "lat": None,
            "lon": None,
        },
        "desired_safety_level": "high",
        "layout_notes": None,
        "layout_flags": ["estudio"],
        "floors": {"min": None, "max": None},
        "parking_spots": {"min": None, "max": None},
        "bedrooms": {"min": 1, "max": 1},
        "bathrooms": {"min": 1, "max": 1},
        "defaults_applied": [],
        "flexibility_notes": None,
    }
    agent = RequirementsAgent(llm=EchoLLMClient(echo_payload))
    req = agent.extract("test")
    assert req.property_type == "apartaestudio"
    assert req.location.neighborhood == "El Poblado"
    assert req.bedrooms.min == 1
    assert "estudio" in req.layout_flags


def test_requirements_agent_rejects_invalid_payload() -> None:
    bad = EchoLLMClient({"raw_user_prompt": "x", "property_type": "supersónico"})
    agent = RequirementsAgent(llm=bad)
    with pytest.raises(RequirementsAgentError):
        agent.extract("texto")
