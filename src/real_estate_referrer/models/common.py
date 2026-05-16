"""Modelos comunes reutilizados por el resto del paquete."""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

T = TypeVar("T", int, float)


class Range(BaseModel, Generic[T]):
    """Rango opcional [min, max]. Cualquiera de los dos extremos puede faltar."""

    model_config = ConfigDict(extra="forbid")

    min: T | None = None
    max: T | None = None

    @model_validator(mode="after")
    def _check_order(self) -> Range[T]:
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"Range.min ({self.min}) > Range.max ({self.max})")
        return self

    def is_empty(self) -> bool:
        return self.min is None and self.max is None

    def contains(self, value: T) -> bool:
        if self.min is not None and value < self.min:
            return False
        if self.max is not None and value > self.max:
            return False
        return True


class Money(BaseModel):
    """Importe monetario. Por defecto en pesos colombianos (COP)."""

    model_config = ConfigDict(extra="forbid")

    currency: Literal["COP", "USD"] = "COP"
    amount: float = Field(ge=0)


class LocationHint(BaseModel):
    """Pista de ubicación; cualquier campo puede ser desconocido."""

    model_config = ConfigDict(extra="forbid")

    city: str | None = None
    neighborhood: str | None = None
    landmarks: list[str] = Field(default_factory=list)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)

    def key(self) -> str:
        """Clave estable para agrupar propiedades por zona."""
        city = (self.city or "").strip().lower()
        neigh = (self.neighborhood or "").strip().lower()
        return f"{city}|{neigh}"
