"""Lógica de scoring determinística usada por el coordinador.

`compute_match_score` recibe un candidato y los requisitos, y devuelve un
score en [0, 1] junto con un diccionario de penalizaciones aplicadas. El
score final se compone como `w_match * match + w_safety * safety`.
"""

from __future__ import annotations

from real_estate_referrer.config import ScoringWeights
from real_estate_referrer.models import (
    PropertyCandidate,
    SafetyAssessment,
    ScoreBreakdown,
)
from real_estate_referrer.models.requirements import UserPropertyRequirements


def compute_match_score(
    candidate: PropertyCandidate,
    requirements: UserPropertyRequirements,
) -> tuple[float, dict[str, float]]:
    """Devuelve (score en [0,1], deducciones por concepto)."""
    deductions: dict[str, float] = {}
    score = 1.0

    if candidate.price is not None and candidate.price.amount > 0:
        if (
            requirements.price.max is not None
            and candidate.price.amount > requirements.price.max
        ):
            ratio = (candidate.price.amount - requirements.price.max) / max(
                requirements.price.max, 1.0
            )
            penalty = min(0.5, ratio)
            deductions["price.over_max"] = penalty
            score -= penalty
        if (
            requirements.price.min is not None
            and candidate.price.amount < requirements.price.min
        ):
            ratio = (requirements.price.min - candidate.price.amount) / max(
                requirements.price.min, 1.0
            )
            penalty = min(0.2, ratio)
            deductions["price.under_min"] = penalty
            score -= penalty

    score -= _range_penalty(
        candidate.area_sqm, requirements.area_sqm.min, requirements.area_sqm.max,
        weight=0.2, label="area_sqm", deductions=deductions,
    )
    score -= _range_penalty(
        candidate.bedrooms, requirements.bedrooms.min, requirements.bedrooms.max,
        weight=0.15, label="bedrooms", deductions=deductions, integer=True,
    )
    score -= _range_penalty(
        candidate.bathrooms, requirements.bathrooms.min, requirements.bathrooms.max,
        weight=0.1, label="bathrooms", deductions=deductions, integer=True,
    )
    score -= _range_penalty(
        candidate.parking_spots,
        requirements.parking_spots.min,
        requirements.parking_spots.max,
        weight=0.1,
        label="parking_spots",
        deductions=deductions,
        integer=True,
    )
    score -= _range_penalty(
        candidate.floors, requirements.floors.min, requirements.floors.max,
        weight=0.05, label="floors", deductions=deductions, integer=True,
    )

    if (
        requirements.property_type != "unknown"
        and candidate.property_type != requirements.property_type
    ):
        deductions["property_type.mismatch"] = 0.15
        score -= 0.15

    if (
        requirements.operation != "unknown"
        and candidate.operation != requirements.operation
    ):
        deductions["operation.mismatch"] = 0.25
        score -= 0.25

    return _clamp(score), deductions


def compute_final_score(
    *,
    candidate: PropertyCandidate,
    requirements: UserPropertyRequirements,
    safety: SafetyAssessment,
    weights: ScoringWeights,
) -> tuple[float, ScoreBreakdown]:
    """Combinar match + safety con los pesos configurados."""
    match_score, deductions = compute_match_score(candidate, requirements)
    final = weights.match * match_score + weights.safety * safety.safety_score
    breakdown = ScoreBreakdown(
        match_score=match_score,
        safety_score=safety.safety_score,
        weight_match=weights.match,
        weight_safety=weights.safety,
        deductions=deductions,
    )
    return _clamp(final), breakdown


def _range_penalty(
    value: float | int | None,
    min_value: float | int | None,
    max_value: float | int | None,
    *,
    weight: float,
    label: str,
    deductions: dict[str, float],
    integer: bool = False,
) -> float:
    if value is None:
        if min_value is not None or max_value is not None:
            deductions[f"{label}.unknown"] = weight * 0.5
            return weight * 0.5
        return 0.0
    penalty = 0.0
    if min_value is not None and value < min_value:
        ratio = (min_value - value) / max(abs(min_value) if integer else min_value, 1)
        penalty = max(penalty, min(weight, ratio * weight))
        deductions[f"{label}.under_min"] = penalty
    if max_value is not None and value > max_value:
        ratio = (value - max_value) / max(abs(max_value) if integer else max_value, 1)
        penalty = max(penalty, min(weight, ratio * weight))
        deductions[f"{label}.over_max"] = penalty
    return penalty


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))
