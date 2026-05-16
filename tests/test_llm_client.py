"""Tests P2 — LLMClient Protocol y stubs determinísticos."""

from __future__ import annotations

from real_estate_referrer.agents import (
    EchoLLMClient,
    LLMClient,
    RuleBasedStubLLMClient,
)


def test_echo_client_implements_protocol() -> None:
    client = EchoLLMClient({"raw_user_prompt": "x"})
    assert isinstance(client, LLMClient)
    out = client.complete(system="s", user="u")
    assert out == {"raw_user_prompt": "x"}


def test_rule_based_stub_extracts_typical_prompt() -> None:
    client = RuleBasedStubLLMClient()
    text = (
        "Busco apartamento en arriendo en Laureles, Medellín, 2 habitaciones, "
        "hasta 1.500.000, ojalá con parqueadero y barrio tranquilo."
    )
    out = client.complete(system="s", user=f"Mensaje del usuario:\n{text}")
    assert out["property_type"] == "apartamento"
    assert out["operation"] == "arriendo"
    assert out["bedrooms"] == {"min": 2, "max": 2}
    assert out["price"]["max"] == 1_500_000
    assert out["location"]["city"] == "Medellín"
    assert out["location"]["neighborhood"] == "Laureles"
    assert out["parking_spots"]["min"] == 1
    assert out["desired_safety_level"] == "high"
    assert out["currency"] == "COP"


def test_rule_based_stub_handles_buy_with_millions_suffix() -> None:
    client = RuleBasedStubLLMClient()
    text = "Compra de casa en Envigado, mínimo 120 m2, 3 habitaciones, hasta 600 millones."
    out = client.complete(system="s", user=text)
    assert out["operation"] == "venta"
    assert out["property_type"] == "casa"
    assert out["bedrooms"] == {"min": 3, "max": 3}
    assert out["area_sqm"]["min"] == 120
    assert out["price"]["max"] == 600_000_000
    assert out["location"]["city"] == "Envigado"


def test_rule_based_stub_handles_minimal_prompt() -> None:
    client = RuleBasedStubLLMClient()
    out = client.complete(system="s", user="Necesito un apto")
    assert out["property_type"] == "apartamento"
    assert out["operation"] == "unknown"
    assert out["bedrooms"]["min"] is None
    assert out["price"]["max"] is None


def test_rule_based_stub_extracts_parking_count() -> None:
    client = RuleBasedStubLLMClient()
    out = client.complete(
        system="s", user="apto con 2 parqueaderos y 2 baños en Bogotá"
    )
    assert out["parking_spots"] == {"min": 2, "max": 2}
    assert out["bathrooms"] == {"min": 2, "max": 2}
    assert out["location"]["city"] == "Bogotá"
