"""Respuesta final que la fachada `RealEstateReferrerApp` retorna al usuario."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from real_estate_referrer.models.property import ScoredProperty
from real_estate_referrer.models.requirements import UserPropertyRequirements


class FinalResponse(BaseModel):
    """Resultado expuesto al consumidor (CLI, API, tests)."""

    model_config = ConfigDict(extra="forbid")

    requirements: UserPropertyRequirements
    ranking: list[ScoredProperty] = Field(default_factory=list)
    rounds: int = Field(ge=1)
    log: list[str] = Field(default_factory=list)
