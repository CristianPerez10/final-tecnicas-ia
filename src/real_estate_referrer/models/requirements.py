"""`UserPropertyRequirements` — esquema estándar producido por el agente 1."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from real_estate_referrer.models.common import LocationHint, Range

PropertyType = Literal[
    "apartamento",
    "casa",
    "apartaestudio",
    "finca",
    "local",
    "unknown",
]
Operation = Literal["arriendo", "venta", "unknown"]
SafetyLevel = Literal["low", "medium", "high", "unknown"]
Currency = Literal["COP", "USD"]


class UserPropertyRequirements(BaseModel):
    """Requisitos normalizados a partir del texto libre del usuario.

    Nota: cada campo del rango (`area_sqm`, `price`, `floors`, `parking_spots`,
    `bedrooms`, `bathrooms`) puede tener `min`, `max`, o ambos `None`. El agente 1
    debe rellenar lo que el texto del usuario menciona explícitamente; los
    `defaults_applied` documentan qué fue inferido por configuración.
    """

    model_config = ConfigDict(extra="forbid")

    raw_user_prompt: str
    property_type: PropertyType = "unknown"
    operation: Operation = "unknown"
    area_sqm: Range[float] = Field(default_factory=Range[float])
    price: Range[float] = Field(default_factory=Range[float])
    currency: Currency = "COP"
    location: LocationHint = Field(default_factory=LocationHint)
    desired_safety_level: SafetyLevel = "unknown"
    layout_notes: str | None = None
    layout_flags: list[str] = Field(default_factory=list)
    floors: Range[int] = Field(default_factory=Range[int])
    parking_spots: Range[int] = Field(default_factory=Range[int])
    bedrooms: Range[int] = Field(default_factory=Range[int])
    bathrooms: Range[int] = Field(default_factory=Range[int])
    defaults_applied: list[str] = Field(default_factory=list)
    flexibility_notes: str | None = None
