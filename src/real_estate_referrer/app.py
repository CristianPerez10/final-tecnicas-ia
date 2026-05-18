"""Fachada `RealEstateReferrerApp` + CLI mínima."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from real_estate_referrer.agents import (
    LLMClient,
    PropertySearchSubAgent,
    RequirementsAgent,
    SafetyNewsSubAgent,
    SearchCoordinatorAgent,
    ValidationAgent,
    create_llm_client,
)
from real_estate_referrer.graph import build_referrer_graph, initial_state, state_to_final_response
from real_estate_referrer.config import SearchConfig
from real_estate_referrer.connectors import (
    DuckDuckGoNewsConnector,
    FixturesNewsConnector,
    FixturesPropertyConnector,
    MetrocuadradoConnector,
)
from real_estate_referrer.connectors.base import (
    NewsConnector,
    PropertyConnector,
)
from real_estate_referrer.models import FinalResponse

DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures"


class RealEstateReferrerApp:
    """Fachada única del pipeline (entrada `run(prompt)`)."""

    def __init__(
        self,
        *,
        config: SearchConfig | None = None,
        llm: LLMClient | None = None,
        property_connectors: Iterable[PropertyConnector] | None = None,
        news_connectors: Iterable[NewsConnector] | None = None,
        fixtures_dir: Path | None = None,
    ) -> None:
        self._config = config or SearchConfig()
        self._llm = llm or create_llm_client()
        self._fixtures_dir = fixtures_dir or DEFAULT_FIXTURES_DIR
        property_conns = list(
            property_connectors or self._default_property_connectors()
        )
        news_conns = list(news_connectors or self._default_news_connectors())

        self._requirements_agent = RequirementsAgent(self._llm, self._config)
        property_sub = PropertySearchSubAgent(property_conns)
        safety_sub = SafetyNewsSubAgent(
            news_conns,
            news_window_days=self._config.news_window_days,
        )
        self._coordinator = SearchCoordinatorAgent(
            property_sub, safety_sub, config=self._config
        )
        self._validator = ValidationAgent(self._config)
        self._graph = build_referrer_graph(
            self._requirements_agent,
            self._coordinator,
            self._validator,
        )

    def run(
        self,
        user_prompt: str,
        config: SearchConfig | None = None,
    ) -> FinalResponse:
        """Ejecuta el pipeline completo vía LangGraph (loop de rondas y flex)."""
        cfg = config or self._config
        final_state = self._graph.invoke(initial_state(user_prompt, cfg))
        return state_to_final_response(final_state)

    def _default_property_connectors(self) -> list[PropertyConnector]:
        connectors: list[PropertyConnector] = []
        mode = self._config.connector_mode
        sources = self._config.enabled_property_sources
        if mode in ("real", "hybrid") and "metrocuadrado" in sources:
            connectors.append(
                MetrocuadradoConnector(
                    user_agent=self._config.user_agent,
                    timeout=self._config.http_timeout_seconds,
                )
            )
        if mode in ("fixtures", "hybrid") and "fixtures" in sources:
            connectors.append(
                FixturesPropertyConnector(
                    self._fixtures_dir / "properties_medellin.json"
                )
            )
        if not connectors:
            connectors.append(
                FixturesPropertyConnector(
                    self._fixtures_dir / "properties_medellin.json"
                )
            )
        return connectors

    def _default_news_connectors(self) -> list[NewsConnector]:
        connectors: list[NewsConnector] = []
        mode = self._config.connector_mode
        sources = self._config.enabled_news_sources
        if mode in ("real", "hybrid") and "duckduckgo_news" in sources:
            connectors.append(
                DuckDuckGoNewsConnector(
                    user_agent=self._config.user_agent,
                    timeout=self._config.http_timeout_seconds,
                )
            )
        if mode in ("fixtures", "hybrid") and "fixtures" in sources:
            connectors.append(
                FixturesNewsConnector(self._fixtures_dir / "news_default.json")
            )
        if not connectors:
            connectors.append(
                FixturesNewsConnector(self._fixtures_dir / "news_default.json")
            )
        return connectors


cli_app = typer.Typer(
    add_completion=False,
    help="Real Estate Referrer — recomendador multi-agente.",
)


@cli_app.command()
def run(
    prompt: str = typer.Argument(..., help="Texto libre del usuario"),
    mode: str = typer.Option(
        "fixtures",
        "--mode",
        help="Modo de conectores: real | fixtures | hybrid",
    ),
    max_rounds: int = typer.Option(
        2, "--max-rounds", min=1, max=5, help="Tope de rondas de flex"
    ),
    show_log: bool = typer.Option(
        False, "--show-log", help="Imprimir el log estructurado"
    ),
    llm_provider: str = typer.Option(
        None,
        "--llm-provider",
        help="Proveedor LLM: stub | openai (default: LLM_PROVIDER o stub)",
    ),
) -> None:
    """Ejecuta el pipeline e imprime un ranking en consola."""
    load_dotenv(override=False)
    user_agent = os.environ.get(
        "USER_AGENT", SearchConfig.model_fields["user_agent"].default
    )
    if llm_provider:
        os.environ["LLM_PROVIDER"] = llm_provider
    config = SearchConfig(
        connector_mode=mode,  # type: ignore[arg-type]
        max_rounds=max_rounds,
        user_agent=user_agent,
    )
    app = RealEstateReferrerApp(config=config)
    response = app.run(prompt)
    _render(response, show_log=show_log)


def _render(response: FinalResponse, *, show_log: bool) -> None:
    console = Console()
    console.print(
        f"[bold]Requisitos finales:[/bold] {response.requirements.location.city or '?'} "
        f"| {response.requirements.property_type} | "
        f"{response.requirements.operation}"
    )
    if response.requirements.defaults_applied:
        console.print(
            "[dim]defaults_applied: "
            + ", ".join(response.requirements.defaults_applied)
            + "[/dim]"
        )
    if not response.ranking:
        console.print("[yellow]Sin propiedades aprobadas en este pipeline.[/yellow]")
    else:
        table = Table(title=f"Ranking ({len(response.ranking)})")
        table.add_column("#", style="cyan", justify="right")
        table.add_column("Score", justify="right")
        table.add_column("Título")
        table.add_column("Barrio")
        table.add_column("Precio", justify="right")
        table.add_column("Razón")
        for index, scored in enumerate(response.ranking, start=1):
            table.add_row(
                str(index),
                f"{scored.final_score:.2f}",
                scored.candidate.title,
                scored.candidate.location.neighborhood or "-",
                f"{scored.candidate.price.amount:,.0f} {scored.candidate.price.currency}",
                scored.reasoning,
            )
        console.print(table)
    console.print(f"[dim]Rondas usadas: {response.rounds}[/dim]")
    if show_log:
        console.rule("log")
        for entry in response.log:
            console.print(f"- {entry}")


def cli() -> None:  # entry point en pyproject
    cli_app()


if __name__ == "__main__":
    cli()
