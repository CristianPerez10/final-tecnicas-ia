"""Sub-agente 2b — convierte noticias en una `SafetyAssessment` por zona."""

from __future__ import annotations

import re
from collections.abc import Iterable

from real_estate_referrer.connectors.base import (
    ConnectorError,
    NewsConnector,
    NewsHit,
)
from real_estate_referrer.models import LocationHint, NewsReference, SafetyAssessment

RISK_KEYWORDS = (
    "hurto",
    "atraco",
    "homicidio",
    "robo",
    "asalto",
    "balacera",
    "extorsión",
    "violencia",
)


class SafetyNewsSubAgent:
    """Calcula `risk_score` por densidad de keywords de inseguridad en titulares."""

    def __init__(
        self,
        connectors: Iterable[NewsConnector],
        *,
        news_window_days: int,
        max_hits: int = 10,
    ) -> None:
        self._connectors = list(connectors)
        self._news_window_days = news_window_days
        self._max_hits = max_hits
        if not self._connectors:
            raise ValueError("Se requiere al menos un NewsConnector")

    def assess_area(
        self,
        location: LocationHint,
        *,
        log: list[str] | None = None,
    ) -> SafetyAssessment:
        hits: list[NewsHit] = []
        for connector in self._connectors:
            try:
                results = connector.search(
                    location,
                    days=self._news_window_days,
                    max_hits=self._max_hits,
                )
            except ConnectorError as exc:
                if log is not None:
                    log.append(f"news_connector_error[{connector.name}]: {exc.detail}")
                continue
            hits.extend(results)
            if len(hits) >= self._max_hits:
                break

        if not hits:
            return SafetyAssessment(
                location=location,
                risk_score=0.3,
                safety_score=0.7,
                confidence="low",
                references=[],
                notes="Sin cobertura noticiosa relevante en la ventana.",
            )

        risk = self._risk_from_hits(hits)
        confidence = "high" if len(hits) >= 5 else "medium" if len(hits) >= 2 else "low"
        references = [
            NewsReference(
                title=hit.title,
                source=hit.source,
                published_at=hit.published_at,
                url=hit.url,
            )
            for hit in hits[: self._max_hits]
        ]
        return SafetyAssessment(
            location=location,
            risk_score=risk,
            safety_score=round(1.0 - risk, 4),
            confidence=confidence,
            references=references,
            notes=f"Basado en {len(hits)} noticia(s) de la ventana.",
        )

    @staticmethod
    def _risk_from_hits(hits: Iterable[NewsHit]) -> float:
        kw_pattern = re.compile("|".join(RISK_KEYWORDS), re.IGNORECASE)
        flagged = 0
        total = 0
        for hit in hits:
            total += 1
            blob = " ".join(filter(None, (hit.title, hit.snippet)))
            if kw_pattern.search(blob):
                flagged += 1
        if total == 0:
            return 0.3
        ratio = flagged / total
        return round(min(0.95, max(0.05, 0.2 + 0.6 * ratio)), 4)
