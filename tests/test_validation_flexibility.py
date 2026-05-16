"""Tests P6 — política de validación y flexibilización determinística."""

from __future__ import annotations

import pytest

from real_estate_referrer.agents import ValidationAgent
from real_estate_referrer.config import SearchConfig
from real_estate_referrer.models import (
    LocationHint,
    Money,
    PropertyCandidate,
    Range,
    SafetyAssessment,
    ScoreBreakdown,
    ScoredProperty,
)
from real_estate_referrer.models.requirements import UserPropertyRequirements


def _scored(
    *,
    final: float,
    candidate_id: str = "c1",
    title: str = "Apto",
    amount: float = 1_400_000,
    url: str = "https://example.com/a",
) -> ScoredProperty:
    candidate = PropertyCandidate(
        id=candidate_id,
        title=title,
        property_type="apartamento",
        operation="arriendo",
        price=Money(amount=amount),
        location=LocationHint(city="Medellín", neighborhood="Laureles"),
        source_url=url,
        source_name="fixtures",
    )
    safety = SafetyAssessment(
        location=candidate.location,
        risk_score=round(1 - 0.8, 4),
        safety_score=0.8,
        confidence="medium",
    )
    breakdown = ScoreBreakdown(
        match_score=0.9,
        safety_score=0.8,
        weight_match=0.7,
        weight_safety=0.3,
    )
    return ScoredProperty(
        candidate=candidate,
        breakdown=breakdown,
        safety=safety,
        final_score=final,
        reasoning="ok",
    )


def _requirements() -> UserPropertyRequirements:
    return UserPropertyRequirements(
        raw_user_prompt="apto laureles",
        property_type="apartamento",
        operation="arriendo",
        location=LocationHint(city="Medellín", neighborhood="Laureles"),
        price=Range[float](max=1_500_000.0),
        area_sqm=Range[float](min=60.0),
        bedrooms=Range[int](min=2),
        desired_safety_level="high",
    )


def test_validation_approves_when_above_threshold() -> None:
    agent = ValidationAgent(SearchConfig())
    result = agent.validate([_scored(final=0.9)], _requirements(), round_index=0)
    assert len(result.approved_properties) == 1
    assert result.relaxed_requirements is None


def test_validation_rejects_low_score_and_keeps_log() -> None:
    agent = ValidationAgent(SearchConfig())
    result = agent.validate([_scored(final=0.4)], _requirements(), round_index=0)
    assert result.approved_properties == []
    assert result.rejected_properties[0].reason_code == "low_score"


def test_validation_rejects_price_outside_tolerance() -> None:
    agent = ValidationAgent(SearchConfig())
    over = _scored(final=0.85, amount=2_000_000)
    result = agent.validate([over], _requirements(), round_index=0)
    assert any(
        r.reason_code == "out_of_range_price" for r in result.rejected_properties
    )


def test_validation_dedupes_by_url_and_title_price() -> None:
    agent = ValidationAgent(SearchConfig())
    a = _scored(final=0.9, candidate_id="a", url="https://example.com/x")
    b = _scored(final=0.9, candidate_id="b", url="https://example.com/x")
    result = agent.validate([a, b], _requirements(), round_index=0)
    assert len(result.approved_properties) == 1
    assert any(r.reason_code == "duplicate" for r in result.rejected_properties)


def test_validation_relaxes_when_no_approved_and_rounds_left() -> None:
    config = SearchConfig(max_rounds=2, min_final_score=0.7)
    agent = ValidationAgent(config)
    rejected = _scored(final=0.4)
    result = agent.validate([rejected], _requirements(), round_index=0)
    assert result.approved_properties == []
    assert result.relaxed_requirements is not None
    assert result.relaxations_applied
    new_price_max = result.relaxed_requirements.price.max
    assert new_price_max == pytest.approx(1_500_000.0 * 1.15)
    new_area_min = result.relaxed_requirements.area_sqm.min
    assert new_area_min == pytest.approx(60.0 * 0.85)
    assert "Estadio" in result.relaxed_requirements.location.landmarks


def test_validation_does_not_relax_after_max_rounds() -> None:
    config = SearchConfig(max_rounds=2, min_final_score=0.7)
    agent = ValidationAgent(config)
    rejected = _scored(final=0.4)
    result = agent.validate([rejected], _requirements(), round_index=1)
    assert result.relaxed_requirements is None
    assert result.approved_properties == []
