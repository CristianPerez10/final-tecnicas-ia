"""Tests P7 — integración del pipeline completo (modo fixtures)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from real_estate_referrer import RealEstateReferrerApp, SearchConfig
from real_estate_referrer.app import cli_app
from real_estate_referrer.connectors import (
    FixturesNewsConnector,
    FixturesPropertyConnector,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _app_with_fixtures(config: SearchConfig | None = None) -> RealEstateReferrerApp:
    return RealEstateReferrerApp(
        config=config
        or SearchConfig(
            connector_mode="fixtures",
            enabled_property_sources=["fixtures"],
            enabled_news_sources=["fixtures"],
        ),
        property_connectors=[
            FixturesPropertyConnector(FIXTURES_DIR / "properties_medellin.json")
        ],
        news_connectors=[FixturesNewsConnector(FIXTURES_DIR / "news_default.json")],
    )


def test_app_run_returns_ranking_for_typical_prompt() -> None:
    app = _app_with_fixtures()
    response = app.run(
        "Busco apartamento en arriendo en Laureles, Medellín, 2 habitaciones, "
        "hasta 1.500.000, ojalá con parqueadero."
    )
    assert response.requirements.location.city == "Medellín"
    assert response.requirements.location.neighborhood == "Laureles"
    assert response.ranking, "Esperaba al menos un candidato aprobado"
    assert response.ranking[0].final_score >= 0.55
    assert response.rounds >= 1
    assert response.log


def test_app_run_falls_back_via_relaxation_when_no_initial_match() -> None:
    config = SearchConfig(
        connector_mode="fixtures",
        enabled_property_sources=["fixtures"],
        enabled_news_sources=["fixtures"],
        max_rounds=2,
        min_final_score=0.55,
    )
    app = _app_with_fixtures(config)
    response = app.run(
        "Apto en arriendo en Laureles, Medellín, 2 habitaciones, hasta 1.000.000."
    )
    assert response.rounds >= 1
    assert any("ronda" in entry for entry in response.log)


def test_cli_run_smoke() -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        [
            "Apto en arriendo en Laureles 2 habitaciones hasta 1.500.000",
            "--mode",
            "fixtures",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Ranking" in result.output or "Sin propiedades" in result.output
