"""Resultado del agente 3 (validación + flexibilización)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from real_estate_referrer.models.property import ScoredProperty
from real_estate_referrer.models.requirements import UserPropertyRequirements

RejectionReason = Literal[
    "duplicate",
    "out_of_range_price",
    "missing_evidence",
    "low_score",
    "other",
]


class RejectedProperty(BaseModel):
    """Una propiedad descartada por el validador, con motivo trazable."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    reason_code: RejectionReason
    detail: str


class RelaxationApplied(BaseModel):
    """Cambio explícito aplicado al relajar requisitos."""

    model_config = ConfigDict(extra="forbid")

    field: str
    before: str
    after: str
    rationale: str


class ValidationResult(BaseModel):
    """Salida del `ValidationAgent`."""

    model_config = ConfigDict(extra="forbid")

    approved_properties: list[ScoredProperty] = Field(default_factory=list)
    rejected_properties: list[RejectedProperty] = Field(default_factory=list)
    relaxed_requirements: UserPropertyRequirements | None = None
    relaxations_applied: list[RelaxationApplied] = Field(default_factory=list)
    round_index: int = Field(ge=0)
    max_rounds: int = Field(ge=1)
