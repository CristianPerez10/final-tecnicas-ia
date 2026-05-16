"""Modelos Pydantic v2 que viajan tipados entre agentes del pipeline."""

from real_estate_referrer.models.common import LocationHint, Money, Range
from real_estate_referrer.models.property import (
    PropertyCandidate,
    ScoreBreakdown,
    ScoredProperty,
)
from real_estate_referrer.models.requirements import UserPropertyRequirements
from real_estate_referrer.models.response import FinalResponse
from real_estate_referrer.models.safety import NewsReference, SafetyAssessment
from real_estate_referrer.models.validation import (
    RejectedProperty,
    RelaxationApplied,
    ValidationResult,
)

__all__ = [
    "FinalResponse",
    "LocationHint",
    "Money",
    "NewsReference",
    "PropertyCandidate",
    "Range",
    "RejectedProperty",
    "RelaxationApplied",
    "SafetyAssessment",
    "ScoreBreakdown",
    "ScoredProperty",
    "UserPropertyRequirements",
    "ValidationResult",
]
