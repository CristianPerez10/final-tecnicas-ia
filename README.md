# Real Estate Referrer

Sistema multi-agente en Python que recibe un texto libre del usuario y produce
un ranking puntuado de propiedades, validando la seguridad percibida del
entorno con noticias públicas. Implementación tomada del documento de
especificación `agente-constructor.md` (Real Estate Referrer / UPB —
"Técnicas avanzadas de IA").

## Arquitectura

Tres agentes principales orquestados por la fachada
`RealEstateReferrerApp.run(prompt)`:

1. `RequirementsAgent` (agente 1) — texto libre → `UserPropertyRequirements`.
2. `SearchCoordinatorAgent` (agente 2) — coordina:
   - `PropertySearchSubAgent` con conectores (`MetrocuadradoConnector`,
     `FixturesPropertyConnector`).
   - `SafetyNewsSubAgent` con conectores
     (`DuckDuckGoNewsConnector`, `FixturesNewsConnector`).
   - Calcula `final_score = w_match · match_score + w_safety · safety_score`.
3. `ValidationAgent` (agente 3) — aprueba/rechaza, deduplica y, si nada
   pasa el umbral, devuelve `relaxed_requirements` (subir `price.max`,
   bajar `area_sqm.min`, ampliar a barrios vecinos) hasta `max_rounds`.

```
texto -> RequirementsAgent -> Coordinator -> Validation -> ranking
                                ^                |
                                |---- relax -----|  (hasta max_rounds)
```

Las invocaciones de agentes pasan **siempre** por métodos de clase. El
único punto de entrada público es `RealEstateReferrerApp.run`.

## Decisiones de implementación

- **LLMClient** es un `Protocol` (en `agents/llm_client.py`). Se incluyen
  dos implementaciones determinísticas: `RuleBasedStubLLMClient` (regex en
  español para el agente 1) y `EchoLLMClient` (tests). Cualquier proveedor
  real (OpenAI/Anthropic/Ollama) se enchufa implementando ese contrato.
- **Conectores reales**: `MetrocuadradoConnector` (scraping HTML) y
  `DuckDuckGoNewsConnector` (búsqueda HTML lite, sin API key). Ambos
  degradan a fixtures si fallan.
- **Modos** vía `SearchConfig.connector_mode`: `real`, `fixtures`,
  `hybrid` (default).

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Uso por CLI

```bash
python -m real_estate_referrer "Apto en arriendo en Laureles 2 hab hasta 1.500.000" \
  --mode fixtures --show-log
```

Opciones útiles:

- `--mode {real,fixtures,hybrid}` — fuente de los conectores.
- `--max-rounds N` — tope del bucle de flexibilización (1–5).
- `--show-log` — imprime el log estructurado del pipeline.

## Uso por API

```python
from real_estate_referrer import RealEstateReferrerApp, SearchConfig

app = RealEstateReferrerApp(config=SearchConfig(connector_mode="hybrid"))
response = app.run("Apto en arriendo en Laureles 2 hab hasta 1.500.000")
for scored in response.ranking:
    print(scored.final_score, scored.candidate.title)
```

## Tests

```bash
pytest -q
```

Los tests cubren:

- `tests/test_models.py` — schemas Pydantic y round-trip JSON.
- `tests/test_config.py` — defaults y carga de prompts.
- `tests/test_llm_client.py` — stub determinístico para el agente 1.
- `tests/test_requirements_agent.py` — parsing del agente 1 con mocks.
- `tests/test_connectors.py` — Metrocuadrado y DuckDuckGo News con mocks
  HTTP via `respx`, fixtures locales para los stubs.
- `tests/test_scoring.py` — scoring determinístico del coordinador.
- `tests/test_validation_flexibility.py` — política de flexibilización.
- `tests/test_app_integration.py` — pipeline end-to-end + CLI.

## Estructura

```
src/real_estate_referrer/
  models/        # Pydantic v2 — UserPropertyRequirements, PropertyCandidate, ...
  agents/        # LLMClient + 5 agentes concretos
  connectors/    # Metrocuadrado, DuckDuckGo News, fixtures
  prompts/       # 5 archivos versionados (sec 9 de la spec)
  config.py      # SearchConfig + defaults
  scoring.py     # match_score, safety_score, final_score
  app.py         # RealEstateReferrerApp + CLI typer/rich
tests/
  fixtures/      # JSON / HTML reproducibles para tests
.env.example
README.md
pyproject.toml
```

## Variables de entorno

Ver `.env.example`. La fachada usa `USER_AGENT` si está definido al construir
los conectores reales. No se requieren API keys para el modo por defecto.

## Riesgos conocidos

- Metrocuadrado puede responder 403 / cambiar selectores. El conector lanza
  `ConnectorError` y el sub-agente degrada a fixtures.
- El stub LLM cubre frases típicas; para producción enchufa un proveedor real
  vía `LLMClient`.
- DuckDuckGo News puede cambiar su HTML. Los selectores admiten varias
  variantes; ajusta en `connectors/duckduckgo_news.py` si se rompe.
