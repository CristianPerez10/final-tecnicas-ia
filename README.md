# Real Estate Referrer

Sistema multi-agente en Python que recibe un texto libre del usuario y produce
un ranking puntuado de propiedades, validando la seguridad percibida del
entorno con noticias públicas.

**Documentación del proyecto** (arquitectura, estado, grafo, actividades,
relajación de condiciones, ejemplos de ejecución y reflexión crítica):
[`DOCUMENTACION_PROYECTO.md`](DOCUMENTACION_PROYECTO.md).

Especificación de implementación: [`agente-constructor.md`](agente-constructor.md)
(UPB — *Técnicas avanzadas de IA*).

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Copia `.env.example` a `.env` si vas a usar OpenAI o conectores reales.

## Uso por CLI

```bash
python -m real_estate_referrer "Apto en arriendo en Laureles 2 hab hasta 1.500.000" \
  --mode fixtures --show-log
```

| Opción | Descripción |
|--------|-------------|
| `--mode {real,fixtures,hybrid}` | Fuente de los conectores (default: `hybrid`). |
| `--max-rounds N` | Tope del bucle de flexibilización (1–5). |
| `--llm-provider {stub,openai}` | Proveedor LLM (default: `LLM_PROVIDER` o `stub`). |
| `--show-log` | Imprime el log estructurado del pipeline. |

Con OpenAI (`OPENAI_API_KEY` en `.env`):

```bash
python -m real_estate_referrer "Apto en Laureles..." --mode fixtures --llm-provider openai
```

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

Modo recomendado sin API keys: `--mode fixtures` y `LLM_PROVIDER=stub` (ver
`.env.example`).

## Variables de entorno

| Variable | Uso |
|----------|-----|
| `USER_AGENT` | HTTP en conectores reales |
| `LLM_PROVIDER` | `stub` (default) o `openai` |
| `OPENAI_API_KEY` | Obligatoria si `LLM_PROVIDER=openai` |
| `OPENAI_MODEL` | Modelo OpenAI (default `gpt-4o-mini`) |

Detalle en [`.env.example`](.env.example).

## Documentación adicional

| Archivo | Contenido |
|---------|-----------|
| [`DOCUMENTACION_PROYECTO.md`](DOCUMENTACION_PROYECTO.md) | Informe técnico del sistema |
| [`agente-constructor.md`](agente-constructor.md) | Especificación funcional |
| [`lineamientos.md`](lineamientos.md) | Lineamientos del curso |
