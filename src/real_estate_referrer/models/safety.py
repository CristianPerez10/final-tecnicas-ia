"""Modelos para la salida del sub-agente de noticias / seguridad."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from real_estate_referrer.models.common import LocationHint


class NewsReference(BaseModel):
    """Referencia a una noticia evaluada por el sub-agente de seguridad."""

    model_config = ConfigDict(extra="forbid")

    title: str
    source: str
    published_at: date | None = None
    url: HttpUrl


class SafetyAssessment(BaseModel):
    """Evaluación de seguridad para una zona.

    `risk_score` y `safety_score` son complementarios y se mantienen ambos
    explícitos para que el código consumidor no tenga que recordar la dirección.
    """

    model_config = ConfigDict(extra="forbid")

    location: LocationHint
    risk_score: float = Field(ge=0, le=1)
    safety_score: float = Field(ge=0, le=1)
    confidence: Literal["low", "medium", "high"]
    references: list[NewsReference] = Field(default_factory=list)
    notes: str | None = None

    @model_validator(mode="after")
    def _check_complement(self) -> SafetyAssessment:
        if abs((self.risk_score + self.safety_score) - 1.0) > 1e-6:
            raise ValueError(
                "risk_score + safety_score debe ser 1.0 "
                f"(got risk={self.risk_score}, safety={self.safety_score})"
            )
        return self
