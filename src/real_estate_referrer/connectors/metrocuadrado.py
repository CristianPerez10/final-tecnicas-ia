"""Scraper de Metrocuadrado (https://www.metrocuadrado.com).

El portal devuelve HTML con tarjetas de listado. Este conector arma la URL
desde `UserPropertyRequirements`, descarga la página y parsea los datos
estructurados que se exponen en cada tarjeta.

Notas operativas:

- Es un sitio con anti-bot agresivo; cualquier 403 / vacío se reporta como
  `ConnectorError` y el caller (sub-agente) puede degradar a fixtures.
- El selector exacto puede cambiar; `_extract_cards` usa varios fallbacks.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from real_estate_referrer.connectors.base import ConnectorError
from real_estate_referrer.models import LocationHint, Money, PropertyCandidate
from real_estate_referrer.models.requirements import UserPropertyRequirements

BASE_URL = "https://www.metrocuadrado.com"


class MetrocuadradoConnector:
    """`PropertyConnector` real contra Metrocuadrado."""

    name = "metrocuadrado"

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
        requirements: UserPropertyRequirements,
        max_candidates: int,
    ) -> list[PropertyCandidate]:
        url = self._build_url(requirements)
        html = self._fetch(url)
        return self._parse_html(html, requirements)[:max_candidates]

    def _build_url(self, req: UserPropertyRequirements) -> str:
        operation = "arriendo" if req.operation == "arriendo" else "venta"
        property_type = (
            req.property_type if req.property_type != "unknown" else "apartamento"
        )
        city = _slugify(req.location.city or "medellin")
        path = f"/{operation}/{property_type}/{city}/"
        params: list[str] = []
        if req.bedrooms.min:
            params.append(f"habitaciones={req.bedrooms.min}")
        if req.price.max:
            params.append(f"precio-hasta={int(req.price.max)}")
        if req.price.min:
            params.append(f"precio-desde={int(req.price.min)}")
        if req.area_sqm.min:
            params.append(f"area-desde={int(req.area_sqm.min)}")
        query = ("?" + "&".join(params)) if params else ""
        return urljoin(BASE_URL, path) + query

    def _fetch(self, url: str) -> str:
        client = self._client or httpx.Client(
            timeout=self._timeout,
            follow_redirects=True,
            headers={"User-Agent": self._user_agent},
        )
        owns_client = self._client is None
        try:
            response = client.get(url)
            if response.status_code >= 400:
                raise ConnectorError(
                    self.name,
                    f"HTTP {response.status_code} al consultar {url}",
                )
            return response.text
        except httpx.HTTPError as exc:
            raise ConnectorError(self.name, f"Fallo HTTP: {exc}") from exc
        finally:
            if owns_client:
                client.close()

    def _parse_html(
        self,
        html: str,
        requirements: UserPropertyRequirements,
    ) -> list[PropertyCandidate]:
        soup = BeautifulSoup(html, "html.parser")
        cards = self._extract_cards(soup)
        results: list[PropertyCandidate] = []
        for card in cards:
            try:
                candidate = self._card_to_candidate(card, requirements)
            except (ValueError, KeyError):
                continue
            if candidate is None:
                continue
            results.append(candidate)
        return results

    @staticmethod
    def _extract_cards(soup: BeautifulSoup) -> list[Tag]:
        candidates: list[Tag] = []
        for selector in (
            "article.realestate-card",
            "div.card-realestate",
            "div.sc-property-card",
            "article",
        ):
            found = soup.select(selector)
            if found:
                candidates = list(found)
                break
        return candidates

    def _card_to_candidate(
        self,
        card: Tag,
        requirements: UserPropertyRequirements,
    ) -> PropertyCandidate | None:
        link = card.find("a", href=True)
        if not link:
            return None
        href = str(link["href"])
        url = urljoin(BASE_URL, href)
        title = (link.get_text(strip=True) or card.get_text(strip=True))[:140]

        price_amount = _first_number(card.find(string=re.compile(r"\$"))) or 0.0
        area_text = card.find(string=re.compile(r"m²|m2", re.IGNORECASE))
        area_sqm = _first_number(area_text)

        bedrooms = _first_int(card.find(string=re.compile(r"hab", re.IGNORECASE)))
        bathrooms = _first_int(card.find(string=re.compile(r"ba[ñn]", re.IGNORECASE)))
        parking = _first_int(card.find(string=re.compile(r"parqueader", re.IGNORECASE)))

        location = LocationHint(
            city=requirements.location.city,
            neighborhood=requirements.location.neighborhood,
        )
        listing_id = (
            card.get("data-id")
            or _hash_url(url)
        )
        operation = requirements.operation if requirements.operation != "unknown" else "venta"

        return PropertyCandidate(
            id=f"metrocuadrado:{listing_id}",
            title=title or "Listado Metrocuadrado",
            description=None,
            property_type=(
                requirements.property_type
                if requirements.property_type != "unknown"
                else "apartamento"
            ),
            operation=operation,
            price=Money(currency=requirements.currency, amount=price_amount),
            area_sqm=area_sqm,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            parking_spots=parking,
            floors=None,
            location=location,
            source_url=url,
            source_name=self.name,
        )


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    no_accents = "".join(c for c in normalized if not unicodedata.combining(c))
    cleaned = re.sub(r"[^a-z0-9]+", "-", no_accents.lower()).strip("-")
    return cleaned or "medellin"


def _first_number(text: Any) -> float | None:
    if text is None:
        return None
    match = re.search(r"([\d.,]+)", str(text))
    if not match:
        return None
    raw = match.group(1).replace(".", "").replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _first_int(text: Any) -> int | None:
    value = _first_number(text)
    return int(value) if value is not None else None


def _hash_url(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
