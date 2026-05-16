"""Modelos de propiedad candidata y propiedad puntuada."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from real_estate_referrer.models.common import LocationHint, Money
from real_estate_referrer.models.safety import SafetyAssessment


class PropertyCandidate(BaseModel):
    """Listado bruto extraído por un `PropertyConnector`."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    description: str | None = None
    property_type: str
    operation: Literal["arriendo", "venta"]
    price: Money
    area_sqm: float | None = Field(default=None, ge=0)
    bedrooms: int | None = Field(default=None, ge=0)
    bathrooms: int | None = Field(default=None, ge=0)
    parking_spots: int | None = Field(default=None, ge=0)
    floors: int | None = Field(default=None, ge=0)
    location: LocationHint
    source_url: HttpUrl
    source_name: str


class ScoreBreakdown(BaseModel):
    """Descomposición trazable de cómo se compuso el `final_score`."""

    model_config = ConfigDict(extra="forbid")

    match_score: float = Field(ge=0, le=1)
    safety_score: float = Field(ge=0, le=1)
    weight_match: float = Field(ge=0, le=1)
    weight_safety: float = Field(ge=0, le=1)
    deductions: dict[str, float] = Field(default_factory=dict)


class ScoredProperty(BaseModel):
    """Propiedad candidata combinada con su score y la evaluación de seguridad."""

    model_config = ConfigDict(extra="forbid")

    candidate: PropertyCandidate
    breakdown: ScoreBreakdown
    safety: SafetyAssessment
    final_score: float = Field(ge=0, le=1)
    reasoning: str
