"""Nodos LangGraph que delegan en las clases de agente existentes."""

from __future__ import annotations

from real_estate_referrer.agents.requirements_agent import RequirementsAgent
from real_estate_referrer.agents.search_coordinator import SearchCoordinatorAgent
from real_estate_referrer.agents.validation_agent import ValidationAgent
from real_estate_referrer.graph.state import ReferrerState


def make_extract_node(requirements_agent: RequirementsAgent):
    """Factory del nodo de extracción de requisitos."""

    def extract_requirements(state: ReferrerState) -> dict:
        cfg = state["config"]
        requirements = requirements_agent.extract(state["user_prompt"], cfg)
        return {
            "requirements": requirements,
            "log": [
                "requirements_agent: extracción ok "
                f"(defaults_applied={requirements.defaults_applied})"
            ],
        }

    return extract_requirements


def make_coordinate_node(coordinator: SearchCoordinatorAgent):
    """Factory del nodo coordinador de búsqueda y scoring."""

    def coordinate_search(state: ReferrerState) -> dict:
        cfg = state["config"]
        requirements = state["requirements"]
        if requirements is None:
            raise RuntimeError("coordinate_search: requirements no inicializados")
        log_buffer: list[str] = []
        log_buffer.append(
            f"coordinator: ronda {state['round_index'] + 1}/{cfg.max_rounds}"
        )
        scored = coordinator.find_and_score(requirements, log=log_buffer)
        return {"scored": scored, "log": log_buffer}

    return coordinate_search


def make_validate_node(validator: ValidationAgent):
    """Factory del nodo de validación y flexibilización."""

    def validate_candidates(state: ReferrerState) -> dict:
        cfg = state["config"]
        requirements = state["requirements"]
        if requirements is None:
            raise RuntimeError("validate_candidates: requirements no inicializados")

        round_index = state["round_index"]
        validation = validator.validate(
            state["scored"], requirements, round_index=round_index
        )
        rounds_used = round_index + 1
        log_entries = [
            "validation: aprobadas "
            f"{len(validation.approved_properties)} | rechazadas "
            f"{len(validation.rejected_properties)}"
        ]

        if validation.approved_properties:
            return {
                "approved": validation.approved_properties,
                "rounds_used": rounds_used,
                "route": "end",
                "log": log_entries,
            }

        if validation.relaxed_requirements is not None:
            log_entries.append(
                "validation: aplicando relajaciones "
                + ", ".join(r.field for r in validation.relaxations_applied)
            )
            return {
                "requirements": validation.relaxed_requirements,
                "round_index": round_index + 1,
                "rounds_used": rounds_used,
                "route": "coordinate",
                "log": log_entries,
            }

        return {
            "rounds_used": rounds_used,
            "route": "end",
            "log": log_entries,
        }

    return validate_candidates
