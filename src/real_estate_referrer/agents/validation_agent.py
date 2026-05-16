"""Agente 3 — validación + política de flexibilización determinística."""

from __future__ import annotations

from real_estate_referrer.config import SearchConfig
from real_estate_referrer.models import (
    Range,
    RejectedProperty,
    RelaxationApplied,
    ScoredProperty,
    ValidationResult,
)
from real_estate_referrer.models.requirements import UserPropertyRequirements

# Mapa explícito de barrios "vecinos" para Medellín. Se amplía aquí cuando se
# añadan nuevas zonas; el agente sólo se mueve dentro de este conjunto cerrado.
NEIGHBORHOOD_NEIGHBORS: dict[str, list[str]] = {
    "laureles": ["Estadio", "Belén", "La América"],
    "el poblado": ["Envigado", "Sabaneta"],
    "envigado": ["El Poblado", "Sabaneta"],
    "belén": ["Laureles", "La América"],
    "robledo": ["La América", "San Javier"],
    "estadio": ["Laureles", "Belén"],
    "chapinero": ["Usaquén", "Teusaquillo"],
    "usaquén": ["Chapinero"],
}


class ValidationAgent:
    """Audita el lote y, si nada pasa el umbral, propone relajaciones."""

    def __init__(self, config: SearchConfig | None = None) -> None:
        self._config = config or SearchConfig()

    def validate(
        self,
        candidates: list[ScoredProperty],
        requirements: UserPropertyRequirements,
        *,
        round_index: int,
    ) -> ValidationResult:
        deduped, rejections = self._dedupe(candidates)
        approved: list[ScoredProperty] = []
        for scored in deduped:
            reason = self._reject_reason(scored, requirements)
            if reason is None:
                approved.append(scored)
                continue
            rejections.append(reason)

        approved.sort(key=lambda s: s.final_score, reverse=True)

        relaxed_requirements: UserPropertyRequirements | None = None
        relaxations: list[RelaxationApplied] = []
        if not approved and round_index < (self._config.max_rounds - 1):
            relaxed_requirements, relaxations = self._relax(requirements)

        return ValidationResult(
            approved_properties=approved,
            rejected_properties=rejections,
            relaxed_requirements=relaxed_requirements,
            relaxations_applied=relaxations,
            round_index=round_index,
            max_rounds=self._config.max_rounds,
        )

    def _dedupe(
        self,
        candidates: list[ScoredProperty],
    ) -> tuple[list[ScoredProperty], list[RejectedProperty]]:
        seen_urls: set[str] = set()
        seen_pairs: set[tuple[str, float]] = set()
        out: list[ScoredProperty] = []
        rejections: list[RejectedProperty] = []
        for scored in candidates:
            url_key = str(scored.candidate.source_url)
            pair_key = (
                scored.candidate.title.strip().lower(),
                scored.candidate.price.amount,
            )
            if url_key in seen_urls or pair_key in seen_pairs:
                rejections.append(
                    RejectedProperty(
                        candidate_id=scored.candidate.id,
                        reason_code="duplicate",
                        detail="Ya existe candidato con misma URL o título+precio.",
                    )
                )
                continue
            seen_urls.add(url_key)
            seen_pairs.add(pair_key)
            out.append(scored)
        return out, rejections

    def _reject_reason(
        self,
        scored: ScoredProperty,
        requirements: UserPropertyRequirements,
    ) -> RejectedProperty | None:
        cfg = self._config
        if scored.final_score < cfg.min_final_score:
            return RejectedProperty(
                candidate_id=scored.candidate.id,
                reason_code="low_score",
                detail=(
                    f"final_score {scored.final_score:.2f} < umbral "
                    f"{cfg.min_final_score:.2f}"
                ),
            )
        price_max = requirements.price.max
        if price_max is not None:
            tolerance = price_max * 1.10
            if scored.candidate.price.amount > tolerance:
                return RejectedProperty(
                    candidate_id=scored.candidate.id,
                    reason_code="out_of_range_price",
                    detail=(
                        f"precio {scored.candidate.price.amount:.0f} > "
                        f"price.max ({price_max:.0f}) + 10% tolerancia"
                    ),
                )
        if not str(scored.candidate.source_url):
            return RejectedProperty(
                candidate_id=scored.candidate.id,
                reason_code="missing_evidence",
                detail="source_url vacía",
            )
        return None

    def _relax(
        self,
        requirements: UserPropertyRequirements,
    ) -> tuple[UserPropertyRequirements, list[RelaxationApplied]]:
        cfg = self._config
        relaxations: list[RelaxationApplied] = []

        new_price = requirements.price.model_copy()
        if new_price.max is not None:
            before = new_price.max
            new_price = Range[float](
                min=new_price.min,
                max=before * (1 + cfg.relax_price_pct),
            )
            relaxations.append(
                RelaxationApplied(
                    field="price.max",
                    before=f"{before:.0f}",
                    after=f"{new_price.max:.0f}",
                    rationale=(
                        f"Subir techo de precio +{cfg.relax_price_pct * 100:.0f}% "
                        "para ampliar el universo de candidatos."
                    ),
                )
            )

        new_area = requirements.area_sqm.model_copy()
        if new_area.min is not None:
            before = new_area.min
            new_area = Range[float](
                min=before * (1 - cfg.relax_area_pct),
                max=new_area.max,
            )
            relaxations.append(
                RelaxationApplied(
                    field="area_sqm.min",
                    before=f"{before:.0f}",
                    after=f"{new_area.min:.0f}",
                    rationale=(
                        f"Bajar área mínima -{cfg.relax_area_pct * 100:.0f}% "
                        "para ampliar la oferta."
                    ),
                )
            )

        new_landmarks = requirements.location.model_copy()
        if new_landmarks.neighborhood:
            key = new_landmarks.neighborhood.strip().lower()
            neighbors = NEIGHBORHOOD_NEIGHBORS.get(key)
            if neighbors:
                expanded = list(dict.fromkeys(new_landmarks.landmarks + neighbors))
                relaxations.append(
                    RelaxationApplied(
                        field="location.landmarks",
                        before=", ".join(new_landmarks.landmarks) or "-",
                        after=", ".join(expanded),
                        rationale=(
                            "Ampliar a barrios vecinos cuando el barrio "
                            "objetivo no produjo aprobaciones."
                        ),
                    )
                )
                new_landmarks = new_landmarks.model_copy(
                    update={"landmarks": expanded}
                )

        if (
            requirements.desired_safety_level == "high"
            and not relaxations
        ):
            relaxations.append(
                RelaxationApplied(
                    field="desired_safety_level",
                    before="high",
                    after="medium",
                    rationale=(
                        "No hubo coincidencias con seguridad alta; se baja "
                        "el umbral una notch para esta ronda."
                    ),
                )
            )
            relaxed_safety = "medium"
        else:
            relaxed_safety = requirements.desired_safety_level

        relaxed = requirements.model_copy(
            update={
                "price": new_price,
                "area_sqm": new_area,
                "location": new_landmarks,
                "desired_safety_level": relaxed_safety,
                "flexibility_notes": (
                    "Aplicado: " + ", ".join(r.field for r in relaxations)
                    if relaxations
                    else "Sin cambios materiales."
                ),
            }
        )
        return relaxed, relaxations
