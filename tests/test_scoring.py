"""Tests P5 — scoring determinístico y coordinador."""

from __future__ import annotations

from pathlib import Path

import pytest

from real_estate_referrer.agents import (
    PropertySearchSubAgent,
    SafetyNewsSubAgent,
    SearchCoordinatorAgent,
)
from real_estate_referrer.config import ScoringWeights, SearchConfig
from real_estate_referrer.connectors import (
    FixturesNewsConnector,
    FixturesPropertyConnector,
)
from real_estate_referrer.models import (
    LocationHint,
    Money,
    PropertyCandidate,
    Range,
    SafetyAssessment,
)
from real_estate_referrer.models.requirements import UserPropertyRequirements
from real_estate_referrer.scoring import compute_final_score, compute_match_score

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _candidate(**overrides) -> PropertyCandidate:
    base = dict(
        id="x",
        title="t",
        property_type="apartamento",
        operation="arriendo",
        price=Money(amount=1_400_000),
        area_sqm=70,
        bedrooms=2,
        bathrooms=2,
        parking_spots=1,
        floors=1,
        location=LocationHint(city="Medellín", neighborhood="Laureles"),
        source_url="https://example.com/listing/0",
        source_name="fixtures",
    )
    base.update(overrides)
    return PropertyCandidate(**base)


def _requirements(**overrides) -> UserPropertyRequirements:
    base = dict(
        raw_user_prompt="apto",
        property_type="apartamento",
        operation="arriendo",
        location=LocationHint(city="Medellín", neighborhood="Laureles"),
        bedrooms=Range[int](min=2, max=2),
        bathrooms=Range[int](min=1, max=2),
        parking_spots=Range[int](min=1),
        price=Range[float](max=1_500_000.0),
    )
    base.update(overrides)
    return UserPropertyRequirements(**base)


def _safety(score: float = 0.8) -> SafetyAssessment:
    return SafetyAssessment(
        location=LocationHint(city="Medellín", neighborhood="Laureles"),
        risk_score=round(1.0 - score, 4),
        safety_score=score,
        confidence="medium",
    )


def test_match_score_is_one_when_perfect_fit() -> None:
    score, deductions = compute_match_score(_candidate(), _requirements())
    assert score == 1.0
    assert deductions == {}


def test_match_score_penalises_price_over_max() -> None:
    candidate = _candidate(price=Money(amount=1_800_000))
    score, deductions = compute_match_score(candidate, _requirements())
    assert score < 1.0
    assert "price.over_max" in deductions


def test_match_score_penalises_property_type_mismatch() -> None:
    candidate = _candidate(property_type="casa")
    score, deductions = compute_match_score(candidate, _requirements())
    assert score < 1.0
    assert "property_type.mismatch" in deductions


def test_final_score_is_weighted_combination() -> None:
    weights = ScoringWeights(match=0.7, safety=0.3)
    final, breakdown = compute_final_score(
        candidate=_candidate(),
        requirements=_requirements(),
        safety=_safety(0.8),
        weights=weights,
    )
    assert final == pytest.approx(0.7 * 1.0 + 0.3 * 0.8)
    assert breakdown.weight_match == 0.7
    assert breakdown.safety_score == 0.8


def test_final_score_clamped_to_zero_when_huge_penalty() -> None:
    final, _ = compute_final_score(
        candidate=_candidate(price=Money(amount=10_000_000), property_type="local"),
        requirements=_requirements(),
        safety=_safety(0.0),
        weights=ScoringWeights(match=0.7, safety=0.3),
    )
    assert 0.0 <= final <= 1.0


def test_search_coordinator_end_to_end_with_fixtures() -> None:
    config = SearchConfig(
        connector_mode="fixtures",
        enabled_property_sources=["fixtures"],
        enabled_news_sources=["fixtures"],
    )
    property_sub = PropertySearchSubAgent(
        connectors=[
            FixturesPropertyConnector(FIXTURES_DIR / "properties_medellin.json")
        ]
    )
    safety_sub = SafetyNewsSubAgent(
        connectors=[FixturesNewsConnector(FIXTURES_DIR / "news_default.json")],
        news_window_days=180,
        max_hits=10,
    )
    coordinator = SearchCoordinatorAgent(property_sub, safety_sub, config=config)

    requirements = _requirements()
    log: list[str] = []
    scored = coordinator.find_and_score(requirements, log=log)

    assert len(scored) >= 3
    assert scored == sorted(scored, key=lambda s: s.final_score, reverse=True)
    assert scored[0].breakdown.weight_match == config.weights.match
    assert scored[0].safety.safety_score >= 0
    assert all(s.candidate.operation == "arriendo" for s in scored)


def test_search_coordinator_returns_empty_log_when_no_candidates(tmp_path: Path) -> None:
    empty = tmp_path / "empty.json"
    empty.write_text("[]", encoding="utf-8")
    property_sub = PropertySearchSubAgent(
        connectors=[FixturesPropertyConnector(empty)]
    )
    safety_sub = SafetyNewsSubAgent(
        connectors=[FixturesNewsConnector(FIXTURES_DIR / "news_default.json")],
        news_window_days=180,
    )
    coordinator = SearchCoordinatorAgent(property_sub, safety_sub)
    log: list[str] = []
    result = coordinator.find_and_score(_requirements(), log=log)
    assert result == []
    assert any("sin candidatos" in line for line in log)
