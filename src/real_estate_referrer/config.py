"""Configuración global del pipeline y carga de prompts versionados."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from real_estate_referrer.models.common import LocationHint, Range
from real_estate_referrer.models.requirements import (
    Currency,
    PropertyType,
    UserPropertyRequirements,
)

ConnectorMode = Literal["real", "fixtures", "hybrid"]
PROMPTS_DIR = Path(__file__).parent / "prompts"


class ScoringWeights(BaseModel):
    """Pesos del `final_score`. Deben sumar 1.0."""

    model_config = ConfigDict(extra="forbid")

    match: float = Field(default=0.7, ge=0, le=1)
    safety: float = Field(default=0.3, ge=0, le=1)

    @model_validator(mode="after")
    def _check_sum(self) -> ScoringWeights:
        if abs((self.match + self.safety) - 1.0) > 1e-6:
            raise ValueError("ScoringWeights.match + safety debe ser 1.0")
        return self


class DefaultRequirements(BaseModel):
    """Defaults aplicables si el usuario no especifica algo."""

    model_config = ConfigDict(extra="forbid")

    currency: Currency = "COP"
    city: str = "Medellín"
    property_type: PropertyType = "apartamento"
    bedrooms: Range[int] = Field(default_factory=lambda: Range[int](min=1))
    price: Range[float] = Field(
        default_factory=lambda: Range[float](min=500_000.0, max=3_000_000.0)
    )
    desired_safety_level: Literal["low", "medium", "high"] = "medium"


class SearchConfig(BaseModel):
    """Configuración global del referrer."""

    model_config = ConfigDict(extra="forbid")

    max_candidates: int = Field(default=10, ge=1, le=100)
    max_rounds: int = Field(default=2, ge=1, le=5)
    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    relax_price_pct: float = Field(default=0.15, ge=0, le=1)
    relax_area_pct: float = Field(default=0.15, ge=0, le=1)
    min_final_score: float = Field(default=0.55, ge=0, le=1)
    news_window_days: int = Field(default=90, ge=1, le=365)
    http_timeout_seconds: float = Field(default=10.0, gt=0)
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
    connector_mode: ConnectorMode = "hybrid"
    enabled_property_sources: list[str] = Field(
        default_factory=lambda: ["metrocuadrado", "fixtures"]
    )
    enabled_news_sources: list[str] = Field(
        default_factory=lambda: ["duckduckgo_news", "fixtures"]
    )
    defaults: DefaultRequirements = Field(default_factory=DefaultRequirements)
    prompts_dir: Path = Field(default=PROMPTS_DIR)

    def apply_defaults(
        self, requirements: UserPropertyRequirements
    ) -> UserPropertyRequirements:
        """Rellenar campos vacíos con defaults; registrar en `defaults_applied`."""
        applied = list(requirements.defaults_applied)
        location = requirements.location.model_copy()
        if not location.city:
            location.city = self.defaults.city
            applied.append("location.city")

        property_type = requirements.property_type
        if property_type == "unknown":
            property_type = self.defaults.property_type
            applied.append("property_type")

        currency = requirements.currency
        bedrooms = requirements.bedrooms
        if bedrooms.is_empty():
            bedrooms = self.defaults.bedrooms.model_copy()
            applied.append("bedrooms")

        price = requirements.price
        if price.is_empty():
            price = self.defaults.price.model_copy()
            applied.append("price")

        safety_level = requirements.desired_safety_level
        if safety_level == "unknown":
            safety_level = self.defaults.desired_safety_level
            applied.append("desired_safety_level")

        return requirements.model_copy(
            update={
                "location": location,
                "property_type": property_type,
                "currency": currency,
                "bedrooms": bedrooms,
                "price": price,
                "desired_safety_level": safety_level,
                "defaults_applied": applied,
            }
        )


@cache
def load_prompt(name: str, prompts_dir: Path | None = None) -> str:
    """Cargar un prompt versionado desde `prompts/`. Cachea por (name, dir)."""
    base = prompts_dir or PROMPTS_DIR
    path = base / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt no encontrado: {path}")
    return path.read_text(encoding="utf-8")


PROMPT_REQUIREMENTS = "01_requirements_agent.md"
PROMPT_PROPERTY_SEARCH = "02_property_search_subagent.md"
PROMPT_SAFETY_NEWS = "03_safety_news_subagent.md"
PROMPT_SEARCH_COORDINATOR = "04_search_coordinator.md"
PROMPT_VALIDATION = "05_validation_agent.md"

ALL_PROMPTS = (
    PROMPT_REQUIREMENTS,
    PROMPT_PROPERTY_SEARCH,
    PROMPT_SAFETY_NEWS,
    PROMPT_SEARCH_COORDINATOR,
    PROMPT_VALIDATION,
)


def assert_prompts_present(prompts_dir: Path | None = None) -> None:
    """Verificar al arranque que los 5 prompts existen en disco."""
    base = prompts_dir or PROMPTS_DIR
    missing = [name for name in ALL_PROMPTS if not (base / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"Faltan prompts en {base}: {', '.join(missing)}"
        )


__all__ = [
    "ALL_PROMPTS",
    "ConnectorMode",
    "DefaultRequirements",
    "LocationHint",
    "PROMPTS_DIR",
    "PROMPT_PROPERTY_SEARCH",
    "PROMPT_REQUIREMENTS",
    "PROMPT_SAFETY_NEWS",
    "PROMPT_SEARCH_COORDINATOR",
    "PROMPT_VALIDATION",
    "ScoringWeights",
    "SearchConfig",
    "assert_prompts_present",
    "load_prompt",
]
