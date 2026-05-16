"""Tests P4 — conectores de propiedades y noticias (mocks HTTP + fixtures)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from real_estate_referrer.connectors import (
    ConnectorError,
    DuckDuckGoNewsConnector,
    FixturesNewsConnector,
    FixturesPropertyConnector,
    MetrocuadradoConnector,
)
from real_estate_referrer.models import LocationHint, Range
from real_estate_referrer.models.requirements import UserPropertyRequirements

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _requirements() -> UserPropertyRequirements:
    return UserPropertyRequirements(
        raw_user_prompt="apto laureles 2 hab",
        property_type="apartamento",
        operation="arriendo",
        location=LocationHint(city="Medellín", neighborhood="Laureles"),
        bedrooms=Range[int](min=2),
        price=Range[float](max=1_500_000.0),
    )


def test_fixtures_property_connector_filters_by_city_and_operation() -> None:
    connector = FixturesPropertyConnector(FIXTURES_DIR / "properties_medellin.json")
    candidates = connector.search(_requirements(), max_candidates=10)
    assert all(c.location.city == "Medellín" for c in candidates)
    assert all(c.operation == "arriendo" for c in candidates)
    assert len(candidates) >= 3


def test_fixtures_property_connector_missing_path_raises() -> None:
    connector = FixturesPropertyConnector(FIXTURES_DIR / "no_existe.json")
    with pytest.raises(ConnectorError):
        connector.search(_requirements(), max_candidates=5)


def test_fixtures_news_connector_loads_payload() -> None:
    connector = FixturesNewsConnector(FIXTURES_DIR / "news_default.json")
    hits = connector.search(LocationHint(city="Medellín", neighborhood="Laureles"), days=180, max_hits=10)
    assert len(hits) == 4
    assert hits[0].url.host.endswith("elcolombiano.com")


@respx.mock
def test_metrocuadrado_connector_parses_sample_html() -> None:
    html = (FIXTURES_DIR / "metrocuadrado_sample.html").read_text(encoding="utf-8")
    respx.get(host="www.metrocuadrado.com").mock(
        return_value=httpx.Response(200, text=html)
    )
    client = httpx.Client(headers={"User-Agent": "test-agent"})
    try:
        connector = MetrocuadradoConnector(user_agent="test-agent", client=client)
        results = connector.search(_requirements(), max_candidates=5)
    finally:
        client.close()
    assert len(results) == 3
    first = results[0]
    assert first.source_name == "metrocuadrado"
    assert first.id.startswith("metrocuadrado:")
    assert first.location.neighborhood == "Laureles"


@respx.mock
def test_metrocuadrado_connector_handles_403() -> None:
    respx.get(host="www.metrocuadrado.com").mock(
        return_value=httpx.Response(403, text="bloqueado")
    )
    client = httpx.Client(headers={"User-Agent": "test-agent"})
    try:
        connector = MetrocuadradoConnector(user_agent="test-agent", client=client)
        with pytest.raises(ConnectorError):
            connector.search(_requirements(), max_candidates=5)
    finally:
        client.close()


@respx.mock
def test_duckduckgo_news_connector_parses_sample_html() -> None:
    html = (FIXTURES_DIR / "duckduckgo_sample.html").read_text(encoding="utf-8")
    respx.get(url__regex=r"https://duckduckgo\.com/html.*").mock(
        return_value=httpx.Response(200, text=html)
    )
    client = httpx.Client(headers={"User-Agent": "test-agent"})
    try:
        connector = DuckDuckGoNewsConnector(user_agent="test-agent", client=client)
        hits = connector.search(
            LocationHint(city="Medellín", neighborhood="Laureles"),
            days=365 * 2,
            max_hits=10,
        )
    finally:
        client.close()
    titles = [h.title for h in hits]
    assert any("Laureles" in t for t in titles)
    assert any(h.published_at == date(2026, 4, 15) for h in hits)
    assert all(h.source for h in hits)


@respx.mock
def test_duckduckgo_news_connector_filters_by_window() -> None:
    html = (FIXTURES_DIR / "duckduckgo_sample.html").read_text(encoding="utf-8")
    respx.get(url__regex=r"https://duckduckgo\.com/html.*").mock(
        return_value=httpx.Response(200, text=html)
    )
    client = httpx.Client(headers={"User-Agent": "test-agent"})
    try:
        connector = DuckDuckGoNewsConnector(user_agent="test-agent", client=client)
        hits = connector.search(
            LocationHint(city="Medellín", neighborhood="Laureles"),
            days=30,
            max_hits=10,
        )
    finally:
        client.close()
    assert all(
        h.published_at is None or (date(2026, 4, 7) <= h.published_at)
        for h in hits
    )
