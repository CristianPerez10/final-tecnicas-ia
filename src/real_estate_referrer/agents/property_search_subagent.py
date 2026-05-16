"""Sub-agente 2a — orquesta uno o varios `PropertyConnector` y deduplica."""

from __future__ import annotations

from collections.abc import Iterable

from real_estate_referrer.connectors.base import ConnectorError, PropertyConnector
from real_estate_referrer.models import PropertyCandidate
from real_estate_referrer.models.requirements import UserPropertyRequirements


class PropertySearchSubAgent:
    """Combina conectores reales + fixtures con degradación tolerante."""

    def __init__(self, connectors: Iterable[PropertyConnector]) -> None:
        self._connectors = list(connectors)
        if not self._connectors:
            raise ValueError("Se requiere al menos un PropertyConnector")

    @property
    def connectors(self) -> list[PropertyConnector]:
        return list(self._connectors)

    def search(
        self,
        requirements: UserPropertyRequirements,
        *,
        max_candidates: int,
        log: list[str] | None = None,
    ) -> list[PropertyCandidate]:
        bag: list[PropertyCandidate] = []
        seen_urls: set[str] = set()
        for connector in self._connectors:
            try:
                results = connector.search(requirements, max_candidates=max_candidates)
            except ConnectorError as exc:
                if log is not None:
                    log.append(f"connector_error[{connector.name}]: {exc.detail}")
                continue
            for candidate in results:
                key = str(candidate.source_url)
                if key in seen_urls:
                    continue
                seen_urls.add(key)
                bag.append(candidate)
                if len(bag) >= max_candidates:
                    return bag
        return bag
