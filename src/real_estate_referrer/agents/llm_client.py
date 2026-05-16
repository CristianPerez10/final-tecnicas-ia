"""`LLMClient` Protocol y dos implementaciones determinísticas.

`RuleBasedStubLLMClient` cubre el agente 1 (extracción de requisitos en español)
sin llamar a un proveedor real. `EchoLLMClient` se usa en tests para inyectar
respuestas pre-cocidas sin depender de heurísticas.
"""

from __future__ import annotations

import json
import re
from typing import Any, Protocol, runtime_checkable

# Catálogo mínimo: ciudades soportadas y barrios conocidos. Se puede ampliar sin
# tocar agentes — los conectores leen `LocationHint` directo.
KNOWN_CITIES = (
    "medellín",
    "medellin",
    "envigado",
    "itagüí",
    "itagui",
    "sabaneta",
    "bello",
    "rionegro",
    "bogotá",
    "bogota",
    "cali",
    "barranquilla",
)

KNOWN_NEIGHBORHOODS = (
    "laureles",
    "el poblado",
    "poblado",
    "envigado",
    "belen",
    "belén",
    "robledo",
    "estadio",
    "san javier",
    "calasanz",
    "los colores",
    "la américa",
    "la america",
    "loma del esmeraldal",
    "loma de las brujas",
    "chapinero",
    "usaquén",
    "usaquen",
    "el chico",
    "santa monica",
    "ciudad jardín",
)


@runtime_checkable
class LLMClient(Protocol):
    """Contrato mínimo para invocar un LLM con salida JSON estructurada.

    `complete` devuelve un dict ya parseado. Cualquier implementación es libre
    de simular o de llamar a un proveedor real (OpenAI, Anthropic, etc.).
    """

    def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


class EchoLLMClient:
    """Cliente determinístico que devuelve siempre el mismo dict.

    Útil para tests donde se inyecta una respuesta fija.
    """

    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response

    def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return json.loads(json.dumps(self._response))


class RuleBasedStubLLMClient:
    """Stub determinístico para el agente 1 basado en regex en español.

    No es un LLM real; sirve para correr el pipeline end-to-end sin SDK
    externo. Cubre los casos típicos del enunciado (precio, área, habitaciones,
    baños, parqueaderos, pisos, ciudad, barrio, operación).
    """

    _SAFETY_HIGH = re.compile(
        r"\b(barrio\s+tranquilo|zona\s+segura|seguridad\s+alta|muy\s+seguro)\b",
        re.IGNORECASE,
    )
    _SAFETY_LOW = re.compile(
        r"\b(no\s+importa\s+seguridad|barrio\s+popular|zona\s+barata)\b",
        re.IGNORECASE,
    )
    _OPERATION_RENT = re.compile(
        r"\b(arriendo|arrendar|alquiler|alquilar|renta|rentar)\b", re.IGNORECASE
    )
    _OPERATION_BUY = re.compile(
        r"\b(compra(r)?|venta|vender|comprar)\b", re.IGNORECASE
    )
    _PROPERTY_TYPES = {
        "apartaestudio": re.compile(r"\bapartaestudio\b", re.IGNORECASE),
        "apartamento": re.compile(r"\b(apartamento|apto|depa)\b", re.IGNORECASE),
        "casa": re.compile(r"\bcasa(s)?\b", re.IGNORECASE),
        "finca": re.compile(r"\bfinca(s)?\b", re.IGNORECASE),
        "local": re.compile(r"\blocal(es)?\b", re.IGNORECASE),
    }

    def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        text, defaults_json = self._split_user_template(user)
        return self._extract_requirements(text)

    @staticmethod
    def _split_user_template(user: str) -> tuple[str, dict[str, Any]]:
        """El RequirementsAgent envía el prompt con el formato del template.

        Recuperamos `user_text` y `defaults_json` si están presentes; si no, el
        contenido entero es el texto del usuario.
        """
        match = re.search(
            r"Mensaje del usuario:\s*(?P<user>.*?)\s*Configuración de defaults disponible.*?:\s*(?P<defaults>\{.*?\})\s*$",
            user,
            re.DOTALL,
        )
        if match:
            try:
                defaults = json.loads(match.group("defaults"))
            except json.JSONDecodeError:
                defaults = {}
            return match.group("user").strip(), defaults
        return user.strip(), {}

    def _extract_requirements(self, text: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "raw_user_prompt": text,
            "property_type": self._extract_property_type(text),
            "operation": self._extract_operation(text),
            "area_sqm": self._extract_area(text),
            "price": self._extract_price(text),
            "currency": "USD" if re.search(r"\bUSD|US\$|d[oó]lares\b", text) else "COP",
            "location": self._extract_location(text),
            "desired_safety_level": self._extract_safety_level(text),
            "layout_notes": None,
            "layout_flags": self._extract_layout_flags(text),
            "floors": self._extract_int_range(
                text,
                r"(?P<n>\d+)\s*pisos?",
                r"hasta\s+(?P<n>\d+)\s*pisos?",
                r"m[ií]nimo\s+(?P<n>\d+)\s*pisos?",
            ),
            "parking_spots": self._extract_parking(text),
            "bedrooms": self._extract_int_range(
                text,
                r"(?P<n>\d+)\s*(habitaciones?|alcobas?|cuartos?|hab)",
                r"hasta\s+(?P<n>\d+)\s*(habitaciones?|alcobas?|hab)",
                r"m[ií]nimo\s+(?P<n>\d+)\s*(habitaciones?|alcobas?|hab)",
            ),
            "bathrooms": self._extract_int_range(
                text,
                r"(?P<n>\d+)\s*ba[ñn]os?",
                r"hasta\s+(?P<n>\d+)\s*ba[ñn]os?",
                r"m[ií]nimo\s+(?P<n>\d+)\s*ba[ñn]os?",
            ),
            "defaults_applied": [],
            "flexibility_notes": None,
        }
        return result

    def _extract_property_type(self, text: str) -> str:
        for ptype, pattern in self._PROPERTY_TYPES.items():
            if pattern.search(text):
                return ptype
        return "unknown"

    def _extract_operation(self, text: str) -> str:
        if self._OPERATION_RENT.search(text):
            return "arriendo"
        if self._OPERATION_BUY.search(text):
            return "venta"
        return "unknown"

    def _extract_safety_level(self, text: str) -> str:
        if self._SAFETY_HIGH.search(text):
            return "high"
        if self._SAFETY_LOW.search(text):
            return "low"
        return "unknown"

    def _extract_layout_flags(self, text: str) -> list[str]:
        flags: list[str] = []
        if re.search(r"cocina\s+(abierta|integrada)", text, re.IGNORECASE):
            flags.append("cocina_abierta")
        if re.search(r"\bestudio\b", text, re.IGNORECASE):
            flags.append("estudio")
        if re.search(r"\bbalc[oó]n\b", text, re.IGNORECASE):
            flags.append("balcon")
        if re.search(r"\bterraza\b", text, re.IGNORECASE):
            flags.append("terraza")
        return flags

    def _extract_area(self, text: str) -> dict[str, float | None]:
        result: dict[str, float | None] = {"min": None, "max": None}
        max_match = re.search(
            r"hasta\s+(?P<n>\d+)\s*(m2|m²|metros)", text, re.IGNORECASE
        )
        min_match = re.search(
            r"m[ií]nimo\s+(?P<n>\d+)\s*(m2|m²|metros)", text, re.IGNORECASE
        )
        single_match = re.search(
            r"(?P<n>\d{2,3})\s*(m2|m²|metros)", text, re.IGNORECASE
        )
        if max_match:
            result["max"] = float(max_match.group("n"))
        if min_match:
            result["min"] = float(min_match.group("n"))
        if not max_match and not min_match and single_match:
            result["min"] = float(single_match.group("n"))
        return result

    def _extract_price(self, text: str) -> dict[str, float | None]:
        result: dict[str, float | None] = {"min": None, "max": None}
        max_match = re.search(
            r"hasta\s+\$?\s*(?P<n>[\d.,]+)\s*(millones|m|cop)?",
            text,
            re.IGNORECASE,
        )
        min_match = re.search(
            r"desde\s+\$?\s*(?P<n>[\d.,]+)\s*(millones|m|cop)?",
            text,
            re.IGNORECASE,
        )
        if max_match:
            result["max"] = self._parse_amount(
                max_match.group("n"), max_match.group(2)
            )
        if min_match:
            result["min"] = self._parse_amount(
                min_match.group("n"), min_match.group(2)
            )
        return result

    @staticmethod
    def _parse_amount(raw: str, suffix: str | None) -> float:
        normalized = raw.replace(".", "").replace(",", "")
        try:
            value = float(normalized)
        except ValueError:
            return 0.0
        if suffix and suffix.lower().startswith("m"):
            value *= 1_000_000
        return value

    def _extract_parking(self, text: str) -> dict[str, int | None]:
        result: dict[str, int | None] = {"min": None, "max": None}
        explicit = re.search(
            r"(?P<n>\d+)\s*(parqueadero(s)?|garaje(s)?|cup(o|os)\s+de\s+parqueo)",
            text,
            re.IGNORECASE,
        )
        if explicit:
            n = int(explicit.group("n"))
            result["min"] = n
            result["max"] = n
            return result
        if re.search(r"con\s+parqueadero|ojal[áa]\s+con\s+parqueadero", text, re.IGNORECASE):
            result["min"] = 1
        return result

    def _extract_int_range(
        self, text: str, exact: str, upper: str, lower: str
    ) -> dict[str, int | None]:
        result: dict[str, int | None] = {"min": None, "max": None}
        upper_match = re.search(upper, text, re.IGNORECASE)
        lower_match = re.search(lower, text, re.IGNORECASE)
        exact_match = re.search(exact, text, re.IGNORECASE)
        if upper_match:
            result["max"] = int(upper_match.group("n"))
        if lower_match:
            result["min"] = int(lower_match.group("n"))
        if not upper_match and not lower_match and exact_match:
            n = int(exact_match.group("n"))
            result["min"] = n
            result["max"] = n
        return result

    def _extract_location(self, text: str) -> dict[str, Any]:
        text_lower = text.lower()
        city = next((c for c in KNOWN_CITIES if c in text_lower), None)
        neighborhood = next(
            (n for n in KNOWN_NEIGHBORHOODS if n in text_lower), None
        )
        landmarks: list[str] = []
        for landmark in ("upb", "universidad pontificia", "estadio", "exito", "éxito"):
            if landmark in text_lower:
                landmarks.append(landmark)
        if city:
            city = city.title()
        if neighborhood:
            neighborhood = neighborhood.title()
        return {
            "city": city,
            "neighborhood": neighborhood,
            "landmarks": landmarks,
            "lat": None,
            "lon": None,
        }
