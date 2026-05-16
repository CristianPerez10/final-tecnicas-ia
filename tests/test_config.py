"""Tests P1 — SearchConfig, defaults y carga de prompts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from real_estate_referrer.config import (
    ALL_PROMPTS,
    ScoringWeights,
    SearchConfig,
    assert_prompts_present,
    load_prompt,
)
from real_estate_referrer.models import LocationHint, Range, UserPropertyRequirements


def test_scoring_weights_must_sum_to_one() -> None:
    with pytest.raises(ValidationError):
        ScoringWeights(match=0.6, safety=0.3)


def test_search_config_defaults() -> None:
    config = SearchConfig()
    assert config.max_candidates == 10
    assert config.max_rounds == 2
    assert config.weights.match == 0.7
    assert config.defaults.city == "Medellín"
    assert "metrocuadrado" in config.enabled_property_sources


def test_apply_defaults_fills_missing_fields_and_logs_them() -> None:
    config = SearchConfig()
    base = UserPropertyRequirements(raw_user_prompt="quiero un apto")
    enriched = config.apply_defaults(base)
    assert enriched.location.city == "Medellín"
    assert enriched.property_type == "apartamento"
    assert enriched.bedrooms.min == 1
    assert enriched.price.min == 500_000.0
    assert enriched.desired_safety_level == "medium"
    assert "location.city" in enriched.defaults_applied
    assert "price" in enriched.defaults_applied


def test_apply_defaults_preserves_user_values() -> None:
    config = SearchConfig()
    base = UserPropertyRequirements(
        raw_user_prompt="apto 3 hab en Envigado, 2.500.000",
        location=LocationHint(city="Envigado", neighborhood="Loma del Esmeraldal"),
        bedrooms=Range[int](min=3, max=3),
        price=Range[float](max=2_500_000.0),
        property_type="apartamento",
        desired_safety_level="high",
    )
    enriched = config.apply_defaults(base)
    assert enriched.location.city == "Envigado"
    assert enriched.bedrooms.min == 3
    assert enriched.price.max == 2_500_000
    assert "location.city" not in enriched.defaults_applied
    assert "bedrooms" not in enriched.defaults_applied


def test_all_prompts_are_present_and_loadable() -> None:
    assert_prompts_present()
    for name in ALL_PROMPTS:
        content = load_prompt(name)
        assert content.strip(), f"Prompt vacío: {name}"
