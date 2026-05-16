"""Tests P0 — validación de schemas y round-trip JSON."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from real_estate_referrer.models import (
    LocationHint,
    Money,
    NewsReference,
    PropertyCandidate,
    Range,
    SafetyAssessment,
    ScoreBreakdown,
    ScoredProperty,
    UserPropertyRequirements,
    ValidationResult,
)


def test_range_defaults_are_empty() -> None:
    r: Range[int] = Range()
    assert r.is_empty()
    assert r.min is None and r.max is None


def test_range_min_must_be_less_or_equal_to_max() -> None:
    with pytest.raises(ValidationError):
        Range[int](min=10, max=5)


def test_range_contains() -> None:
    r = Range[int](min=2, max=4)
    assert r.contains(2)
    assert r.contains(4)
    assert not r.contains(1)
    assert not r.contains(5)


def test_user_requirements_minimal_roundtrip() -> None:
    req = UserPropertyRequirements(raw_user_prompt="apto en Laureles 2 hab")
    payload = req.model_dump_json()
    parsed = UserPropertyRequirements.model_validate_json(payload)
    assert parsed == req
    assert parsed.property_type == "unknown"
    assert parsed.location.city is None


def test_user_requirements_full_payload() -> None:
    payload = {
        "raw_user_prompt": "apto en Laureles, 2 hab, hasta 1.500.000",
        "property_type": "apartamento",
        "operation": "arriendo",
        "area_sqm": {"min": 60.0, "max": 90.0},
        "price": {"min": None, "max": 1_500_000.0},
        "currency": "COP",
        "location": {"city": "Medellín", "neighborhood": "Laureles", "landmarks": []},
        "desired_safety_level": "high",
        "layout_notes": "cocina abierta",
        "layout_flags": ["cocina_abierta"],
        "floors": {"min": None, "max": None},
        "parking_spots": {"min": 1, "max": None},
        "bedrooms": {"min": 2, "max": 2},
        "bathrooms": {"min": 1, "max": None},
        "defaults_applied": ["currency"],
        "flexibility_notes": None,
    }
    req = UserPropertyRequirements.model_validate(payload)
    assert req.bedrooms.min == 2 and req.bedrooms.max == 2
    assert req.price.max == 1_500_000
    assert "cocina_abierta" in req.layout_flags
    assert req.location.key() == "medellín|laureles"


def test_safety_assessment_complementary_scores() -> None:
    sa = SafetyAssessment(
        location=LocationHint(city="Medellín", neighborhood="El Poblado"),
        risk_score=0.2,
        safety_score=0.8,
        confidence="medium",
    )
    assert sa.safety_score == pytest.approx(0.8)
    with pytest.raises(ValidationError):
        SafetyAssessment(
            location=LocationHint(city="Medellín"),
            risk_score=0.3,
            safety_score=0.5,
            confidence="low",
        )


def _sample_candidate() -> PropertyCandidate:
    return PropertyCandidate(
        id="mc-001",
        title="Apartamento en Laureles",
        property_type="apartamento",
        operation="arriendo",
        price=Money(amount=1_400_000),
        area_sqm=72.0,
        bedrooms=2,
        bathrooms=2,
        parking_spots=1,
        floors=1,
        location=LocationHint(city="Medellín", neighborhood="Laureles"),
        source_url="https://www.metrocuadrado.com/inmueble/123",
        source_name="metrocuadrado",
    )


def test_scored_property_roundtrip() -> None:
    candidate = _sample_candidate()
    safety = SafetyAssessment(
        location=candidate.location,
        risk_score=0.25,
        safety_score=0.75,
        confidence="medium",
        references=[
            NewsReference(
                title="Reporte semanal",
                source="El Colombiano",
                url="https://example.com/n/1",
            )
        ],
    )
    scored = ScoredProperty(
        candidate=candidate,
        breakdown=ScoreBreakdown(
            match_score=0.9,
            safety_score=0.75,
            weight_match=0.7,
            weight_safety=0.3,
            deductions={"price": 0.05},
        ),
        safety=safety,
        final_score=0.85,
        reasoning="Match alto en habitaciones y precio dentro de rango.",
    )
    payload = scored.model_dump_json()
    again = ScoredProperty.model_validate_json(payload)
    assert again == scored


def test_validation_result_defaults() -> None:
    vr = ValidationResult(round_index=0, max_rounds=2)
    assert vr.approved_properties == []
    assert vr.rejected_properties == []
    assert vr.relaxed_requirements is None


def test_user_requirements_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        UserPropertyRequirements.model_validate(
            {"raw_user_prompt": "x", "unexpected": True}
        )


def test_models_json_schema_contains_required_concepts() -> None:
    schema = json.loads(json.dumps(UserPropertyRequirements.model_json_schema()))
    required_concepts = {
        "raw_user_prompt",
        "area_sqm",
        "price",
        "location",
        "desired_safety_level",
        "floors",
        "parking_spots",
        "bedrooms",
        "bathrooms",
        "defaults_applied",
    }
    assert required_concepts.issubset(schema["properties"].keys())
