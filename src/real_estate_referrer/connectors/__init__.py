"""Conectores HTTP / fixtures hacia fuentes de propiedades y noticias."""

from real_estate_referrer.connectors.base import (
    ConnectorError,
    NewsConnector,
    NewsHit,
    PropertyConnector,
)
from real_estate_referrer.connectors.duckduckgo_news import DuckDuckGoNewsConnector
from real_estate_referrer.connectors.fixtures import (
    FixturesNewsConnector,
    FixturesPropertyConnector,
)
from real_estate_referrer.connectors.metrocuadrado import MetrocuadradoConnector

__all__ = [
    "ConnectorError",
    "DuckDuckGoNewsConnector",
    "FixturesNewsConnector",
    "FixturesPropertyConnector",
    "MetrocuadradoConnector",
    "NewsConnector",
    "NewsHit",
    "PropertyConnector",
]
