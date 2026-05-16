"""Conector de noticias contra DuckDuckGo (HTML lite, sin API key)."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from real_estate_referrer.connectors.base import ConnectorError, NewsHit
from real_estate_referrer.models import LocationHint

DDG_HTML = "https://duckduckgo.com/html/"


class DuckDuckGoNewsConnector:
    """Busca noticias relevantes a una ubicación combinando keywords de seguridad."""

    name = "duckduckgo_news"

    SAFETY_KEYWORDS = (
        "seguridad",
        "hurto",
        "homicidio",
        "atraco",
        "robo",
        "policía",
    )

    def __init__(
        self,
        *,
        user_agent: str,
        timeout: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._timeout = timeout
        self._user_agent = user_agent
        self._client = client

    def search(
        self,
        location: LocationHint,
        days: int,
        max_hits: int,
    ) -> list[NewsHit]:
        query = self._build_query(location)
        html = self._fetch(query)
        hits = self._parse(html)
        cutoff = datetime.now().date() - timedelta(days=days)
        recent = [h for h in hits if h.published_at is None or h.published_at >= cutoff]
        return recent[:max_hits]

    def _build_query(self, location: LocationHint) -> str:
        place_parts = [
            part
            for part in (location.neighborhood, location.city)
            if part
        ]
        place = " ".join(place_parts) or "Colombia"
        keywords = " OR ".join(self.SAFETY_KEYWORDS)
        return f'"{place}" ({keywords}) noticias'

    def _fetch(self, query: str) -> str:
        client = self._client or httpx.Client(
            timeout=self._timeout,
            follow_redirects=True,
            headers={"User-Agent": self._user_agent},
        )
        owns_client = self._client is None
        try:
            response = client.get(
                DDG_HTML,
                params={"q": query, "kl": "co-es", "iar": "news"},
            )
            if response.status_code >= 400:
                raise ConnectorError(
                    self.name, f"HTTP {response.status_code} en búsqueda DDG"
                )
            return response.text
        except httpx.HTTPError as exc:
            raise ConnectorError(self.name, f"Fallo HTTP: {exc}") from exc
        finally:
            if owns_client:
                client.close()

    def _parse(self, html: str) -> list[NewsHit]:
        soup = BeautifulSoup(html, "html.parser")
        hits: list[NewsHit] = []
        for result in soup.select("div.result, div.web-result"):
            anchor = result.select_one("a.result__a, a.result__url")
            if not anchor:
                continue
            href = anchor.get("href")
            title = anchor.get_text(strip=True)
            if not href or not title:
                continue
            snippet_tag = result.select_one(
                "a.result__snippet, div.result__snippet"
            )
            snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else None
            published = self._parse_date(result)
            try:
                hit = NewsHit(
                    title=title,
                    source=_domain(str(href)),
                    published_at=published,
                    url=str(href),
                    snippet=snippet,
                )
            except Exception:  # noqa: BLE001 — pydantic valida HttpUrl
                continue
            hits.append(hit)
        return hits

    @staticmethod
    def _parse_date(result: Tag) -> date | None:
        timestamp = result.select_one("span.result__timestamp")
        if not timestamp:
            return None
        text = timestamp.get_text(strip=True)
        match = re.search(r"\d{4}-\d{2}-\d{2}", text)
        if match:
            try:
                return datetime.strptime(match.group(0), "%Y-%m-%d").date()
            except ValueError:
                return None
        return None


def _domain(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc or url
    return host.replace("www.", "")
