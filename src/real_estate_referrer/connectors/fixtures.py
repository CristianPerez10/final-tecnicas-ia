"""Conectores stub que leen JSON local (modo simulado puro)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from real_estate_referrer.connectors.base import ConnectorError, NewsHit
from real_estate_referrer.models import LocationHint, PropertyCandidate
from real_estate_referrer.models.requirements import UserPropertyRequirements


class FixturesPropertyConnector:
    """Lee `properties_*.json` (lista de `PropertyCandidate`) de un directorio."""

    name = "fixtures"

    def __init__(self, fixture_path: Path) -> None:
        self._path = fixture_path
        self._adapter: TypeAdapter[list[PropertyCandidate]] = TypeAdapter(
            list[PropertyCandidate]
        )

    def search(
        self,
        requirements: UserPropertyRequirements,
        max_candidates: int,
    ) -> list[PropertyCandidate]:
        if not self._path.exists():
            raise ConnectorError("fixtures", f"No existe fixture: {self._path}")
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            candidates = self._adapter.validate_python(data)
        except Exception as exc:  # noqa: BLE001
            raise ConnectorError("fixtures", f"JSON inválido: {exc}") from exc

        filtered = self._filter(candidates, requirements)
        return filtered[:max_candidates]

    @staticmethod
    def _filter(
        candidates: list[PropertyCandidate],
        requirements: UserPropertyRequirements,
    ) -> list[PropertyCandidate]:
        target_city = (requirements.location.city or "").lower()
        results: list[PropertyCandidate] = []
        for candidate in candidates:
            if (
                target_city
                and candidate.location.city
                and target_city not in candidate.location.city.lower()
            ):
                continue
            if (
                requirements.operation != "unknown"
                and candidate.operation != requirements.operation
            ):
                continue
            results.append(candidate)
        return results


class FixturesNewsConnector:
    """Lee `news_*.json` (lista de `NewsHit`) de un directorio."""

    name = "fixtures"

    def __init__(self, fixture_path: Path) -> None:
        self._path = fixture_path
        self._adapter: TypeAdapter[list[NewsHit]] = TypeAdapter(list[NewsHit])

    def search(
        self,
        location: LocationHint,
        days: int,
        max_hits: int,
    ) -> list[NewsHit]:
        if not self._path.exists():
            raise ConnectorError("fixtures", f"No existe fixture: {self._path}")
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            hits = self._adapter.validate_python(data)
        except Exception as exc:  # noqa: BLE001
            raise ConnectorError("fixtures", f"JSON inválido: {exc}") from exc
        return hits[:max_hits]
