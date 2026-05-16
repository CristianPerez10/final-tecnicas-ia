"""Agente 1 — extracción de requisitos a `UserPropertyRequirements`."""

from __future__ import annotations

import json

from pydantic import ValidationError

from real_estate_referrer.agents.llm_client import LLMClient
from real_estate_referrer.config import (
    PROMPT_REQUIREMENTS,
    SearchConfig,
    load_prompt,
)
from real_estate_referrer.models import UserPropertyRequirements


class RequirementsAgentError(RuntimeError):
    """Error al producir requisitos válidos a partir del texto del usuario."""


class RequirementsAgent:
    """Agente 1 — convierte texto libre en `UserPropertyRequirements`."""

    def __init__(self, llm: LLMClient, config: SearchConfig | None = None) -> None:
        self._llm = llm
        self._config = config or SearchConfig()
        self._system_prompt = load_prompt(
            PROMPT_REQUIREMENTS, prompts_dir=self._config.prompts_dir
        )

    def extract(
        self,
        user_text: str,
        config: SearchConfig | None = None,
    ) -> UserPropertyRequirements:
        """Extraer requisitos y rellenar defaults configurados."""
        cfg = config or self._config
        prompt = self._build_user_prompt(user_text, cfg)
        schema = UserPropertyRequirements.model_json_schema()
        raw = self._llm.complete(
            system=self._system_prompt, user=prompt, schema=schema
        )
        if not isinstance(raw, dict):
            raise RequirementsAgentError(
                f"LLMClient devolvió tipo inesperado: {type(raw).__name__}"
            )
        raw.setdefault("raw_user_prompt", user_text)
        try:
            requirements = UserPropertyRequirements.model_validate(raw)
        except ValidationError as exc:
            raise RequirementsAgentError(
                f"Salida del LLM no respeta el schema: {exc}"
            ) from exc
        return cfg.apply_defaults(requirements)

    def _build_user_prompt(self, user_text: str, config: SearchConfig) -> str:
        defaults_payload = config.defaults.model_dump(mode="json")
        return (
            "Mensaje del usuario:\n"
            f"{user_text}\n\n"
            "Configuración de defaults disponible (JSON):\n"
            f"{json.dumps(defaults_payload, ensure_ascii=False)}"
        )
