"""Protocols comunes para conectores de propiedades y noticias."""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, HttpUrl

from real_estate_referrer.models import LocationHint, PropertyCandidate
from real_estate_referrer.models.requirements import UserPropertyRequirements


class ConnectorError(RuntimeError):
    """Falla recuperable de un conector — el caller decide degradar."""

    def __init__(self, source: str, detail: str) -> None:
        super().__init__(f"[{source}] {detail}")
        self.source = source
        self.detail = detail


class NewsHit(BaseModel):
    """Resultado bruto del conector de noticias antes de scoring."""

    model_config = ConfigDict(extra="forbid")

    title: str
    source: str
    published_at: date | None = None
    url: HttpUrl
    snippet: str | None = None


@runtime_checkable
class PropertyConnector(Protocol):
    """Buscador de propiedades — devuelve candidatos respetando el schema."""

    name: str

    def search(
        self, requirements: UserPropertyRequirements, max_candidates: int
    ) -> list[PropertyCandidate]: ...


@runtime_checkable
class NewsConnector(Protocol):
    """Buscador de noticias por ubicación + ventana temporal."""

    name: str

    def search(
        self, location: LocationHint, days: int, max_hits: int
    ) -> list[NewsHit]: ...
