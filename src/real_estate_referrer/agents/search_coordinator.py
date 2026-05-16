"""Agente 2 — coordinador. Empareja propiedades con assessments y puntúa."""

from __future__ import annotations

from real_estate_referrer.agents.property_search_subagent import (
    PropertySearchSubAgent,
)
from real_estate_referrer.agents.safety_news_subagent import SafetyNewsSubAgent
from real_estate_referrer.config import SearchConfig
from real_estate_referrer.models import (
    LocationHint,
    PropertyCandidate,
    SafetyAssessment,
    ScoredProperty,
)
from real_estate_referrer.models.requirements import UserPropertyRequirements
from real_estate_referrer.scoring import compute_final_score


class SearchCoordinatorAgent:
    """Fusiona resultados de los sub-agentes y produce `ScoredProperty`."""

    def __init__(
        self,
        property_subagent: PropertySearchSubAgent,
        safety_subagent: SafetyNewsSubAgent,
        config: SearchConfig | None = None,
    ) -> None:
        self._property_subagent = property_subagent
        self._safety_subagent = safety_subagent
        self._config = config or SearchConfig()

    def find_and_score(
        self,
        requirements: UserPropertyRequirements,
        *,
        log: list[str] | None = None,
    ) -> list[ScoredProperty]:
        log = log if log is not None else []
        candidates = self._property_subagent.search(
            requirements,
            max_candidates=self._config.max_candidates,
            log=log,
        )
        if not candidates:
            log.append("coordinator: sin candidatos del sub-agente de propiedades")
            return []

        assessments = self._build_assessments(candidates, log=log)
        scored = []
        for candidate in candidates:
            assessment = self._match_assessment(candidate, assessments)
            final, breakdown = compute_final_score(
                candidate=candidate,
                requirements=requirements,
                safety=assessment,
                weights=self._config.weights,
            )
            reasoning = self._reasoning(candidate, breakdown, assessment)
            scored.append(
                ScoredProperty(
                    candidate=candidate,
                    breakdown=breakdown,
                    safety=assessment,
                    final_score=final,
                    reasoning=reasoning,
                )
            )
        scored.sort(key=lambda s: s.final_score, reverse=True)
        return scored

    def _build_assessments(
        self,
        candidates: list[PropertyCandidate],
        *,
        log: list[str],
    ) -> dict[str, SafetyAssessment]:
        unique_locations: dict[str, LocationHint] = {}
        for candidate in candidates:
            key = candidate.location.key()
            if key not in unique_locations:
                unique_locations[key] = candidate.location

        assessments: dict[str, SafetyAssessment] = {}
        for key, location in unique_locations.items():
            assessment = self._safety_subagent.assess_area(location, log=log)
            assessments[key] = assessment
        return assessments

    @staticmethod
    def _match_assessment(
        candidate: PropertyCandidate,
        assessments: dict[str, SafetyAssessment],
    ) -> SafetyAssessment:
        key = candidate.location.key()
        if key in assessments:
            return assessments[key]
        city = (candidate.location.city or "").strip().lower()
        for stored_key, value in assessments.items():
            if stored_key.startswith(city + "|"):
                return value
        return next(iter(assessments.values()))

    @staticmethod
    def _reasoning(
        candidate: PropertyCandidate,
        breakdown,
        assessment: SafetyAssessment,
    ) -> str:
        parts = [
            f"Match {breakdown.match_score:.2f} (deducciones: "
            f"{', '.join(breakdown.deductions.keys()) or 'ninguna'})",
            f"Seguridad {assessment.safety_score:.2f} (confianza {assessment.confidence})",
            f"Fuente: {candidate.source_name}",
        ]
        return " · ".join(parts)
