"""Tests de la fábrica LLM y adaptador LangChain (sin llamadas reales)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from real_estate_referrer.agents import (
    LangChainStructuredLLMClient,
    RuleBasedStubLLMClient,
    create_llm_client,
)
from real_estate_referrer.models.requirements import UserPropertyRequirements


def test_create_llm_client_stub_default() -> None:
    client = create_llm_client("stub")
    assert isinstance(client, RuleBasedStubLLMClient)


def test_create_llm_client_unknown_raises() -> None:
    with pytest.raises(ValueError, match="no soportado"):
        create_llm_client("unknown-provider")


def test_langchain_client_complete_returns_dict(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    requirements = UserPropertyRequirements.model_validate(
        {
            "raw_user_prompt": "test",
            "property_type": "apartamento",
            "operation": "arriendo",
            "area_sqm": {"min": None, "max": None},
            "price": {"min": None, "max": 1_500_000},
            "currency": "COP",
            "location": {
                "city": "Medellín",
                "neighborhood": "Laureles",
                "landmarks": [],
                "lat": None,
                "lon": None,
            },
            "desired_safety_level": "medium",
            "layout_notes": None,
            "layout_flags": [],
            "floors": {"min": None, "max": None},
            "parking_spots": {"min": None, "max": None},
            "bedrooms": {"min": 2, "max": 2},
            "bathrooms": {"min": None, "max": None},
            "defaults_applied": [],
            "flexibility_notes": None,
        }
    )
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = requirements
    mock_chat = MagicMock()
    mock_chat.with_structured_output.return_value = mock_structured

    with patch(
        "real_estate_referrer.agents.langchain_llm.ChatOpenAI",
        return_value=mock_chat,
    ):
        client = LangChainStructuredLLMClient()
        out = client.complete(system="sys", user="user prompt")

    assert out["property_type"] == "apartamento"
    assert out["location"]["city"] == "Medellín"
    mock_structured.invoke.assert_called_once()


def test_create_llm_client_openai_without_key_raises(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with patch(
        "real_estate_referrer.agents.langchain_llm.ChatOpenAI",
    ):
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            create_llm_client("openai")
