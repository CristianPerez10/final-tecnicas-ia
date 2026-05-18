"""Adaptador LangChain → `LLMClient` y fábrica por proveedor."""

from __future__ import annotations

import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from real_estate_referrer.agents.llm_client import LLMClient, RuleBasedStubLLMClient
from real_estate_referrer.models.requirements import UserPropertyRequirements

SUPPORTED_PROVIDERS = frozenset({"stub", "openai"})


class LangChainStructuredLLMClient:
    """Invoca ChatOpenAI con salida estructurada Pydantic."""

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.0,
    ) -> None:
        model_name = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError(
                "OPENAI_API_KEY es obligatorio cuando LLM_PROVIDER=openai"
            )
        chat = ChatOpenAI(
            model=model_name,
            api_key=key,
            temperature=temperature,
        )
        self._structured = chat.with_structured_output(UserPropertyRequirements)

    def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del schema  # el schema canónico es UserPropertyRequirements
        result = self._structured.invoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        if isinstance(result, UserPropertyRequirements):
            return result.model_dump(mode="json")
        if isinstance(result, dict):
            return result
        raise TypeError(
            f"Salida inesperada del modelo: {type(result).__name__}"
        )


def create_llm_client(provider: str | None = None) -> LLMClient:
    """Construye el cliente LLM según `provider` o `LLM_PROVIDER` del entorno."""
    chosen = (provider or os.environ.get("LLM_PROVIDER", "stub")).strip().lower()
    if chosen == "stub":
        return RuleBasedStubLLMClient()
    if chosen == "openai":
        return LangChainStructuredLLMClient()
    raise ValueError(
        f"Proveedor LLM no soportado: {chosen!r}. "
        f"Valores válidos: {', '.join(sorted(SUPPORTED_PROVIDERS))}"
    )
