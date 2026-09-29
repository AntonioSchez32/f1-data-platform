# 05 · Arquitectura de aplicación y estructura del proyecto

> Nota de trabajo para el informe de situación de `f1-data-platform`. Estado del repositorio en el
> commit `cceddd3` («Direcciones públicas en el README y pruebas contra la web desplegada»), rama
> `main`. Medidas tomadas el 28-09-2026 hacia las 23:25 UTC. Todas las rutas son relativas a la raíz
> del repositorio salvo que se indique lo contrario.

## 1. Estructura del repositorio

### 1.1. Visión general

El repositorio es un *monorepo* con cuatro componentes desplegables o ejecutables de forma
independiente: la ingesta (`ingestion/`, paquete Python con CLI `f1-ingest`), la transformación
(`transform/`, proyecto dbt sobre DuckDB), la API (`api/`, FastAPI) y la web (`web/`, Next.js). Los
datos **no** se versionan en Git: viven en la GitHub Release `data-latest`, que el pipeline
regenera cada semana y de la que se alimentan tanto la CI como la API desplegada.

`git ls-files` devuelve 218 ficheros versionados. Reparto por carpeta de primer nivel:

| Carpeta / fichero | Ficheros | Líneas (aprox.) | Papel |
|---|---:|---:|---|
| `api/` (app) | 16 | 1 799 | API FastAPI de solo lectura |
| `api/tests/` | 4 + 18 Parquet | 361 (+504 KB de fixture) | Pruebas de la API |
| `ingestion/` | 9 | 740 | Cargadores bronze y snapshots |
| `transform/` | 74 | 3 217 | Proyecto dbt (staging, intermediate, marts, quality, seeds, tests) |
| `web/src/app/` | 22 | 2 661 | Rutas (App Router) |
| `web/src/components/` | 23 | 1 821 | Componentes React |
| `web/src/lib/` | 8 | 164 (sin contar `openapi.json` 4 404 y `schema.d.ts` 2 125, generados) | Cliente API, formato, i18n |
| `web/src/dictionaries/` | 2 | 676 | Textos es/en |
| `web/tests/` | 2 | 129 | Playwright + axe |
| `tests/` | 2 | 125 | Pruebas de la ingesta |
| `scripts/` | 3 | 237 | Utilidades de mantenimiento |
| `.github/workflows/` | 2 | 311 | CI y pipeline |
| `docs/` | 9 | — | Revisión de divergencias entre fuentes (CSV + Markdown) |
| Raíz | 10 | — | Configuración (`pyproject.toml`, `uv.lock` de 1 563 líneas, `render.yaml`, README de 299 líneas…) |

### 1.2. Árbol comentado

```text
f1-data-platform/
├── .github/workflows/
│   ├── ci.yml                 # CI: jobs python, dbt, api-image, web
│   └── pipeline.yml           # Pipeline de datos semanal (lunes 06:00 UTC) + docs dbt opcionales
├── api/
│   ├── Dockerfile             # Imagen python:3.12-slim + uv; solo grupo «api»
│   ├── __init__.py
│   ├── app/
│   │   ├── config.py          # Settings (dataclass inmutable leída de variables F1_*)
│   │   ├── database.py        # Database: DuckDB read_only, cursor por consulta, swap()
│   │   ├── release.py         # Descarga de f1.duckdb desde GitHub Releases (stdlib)
│   │   ├── cache.py           # DataCacheMiddleware: ETag débil + Cache-Control + 304
│   │   ├── deps.py            # get_database, DB (Annotated), not_found, split_ids
│   │   ├── schemas.py         # 33 modelos Pydantic de respuesta (382 líneas)
│   │   ├── main.py            # create_app(), lifespan, middlewares, /health, /quality
│   │   └── routers/           # seasons, races, drivers, constructors, records, rankings, circuits
│   └── tests/
│       ├── conftest.py        # Construye un DuckDB temporal a partir de los Parquet de ejemplo
│       ├── test_endpoints.py  # 20 pruebas funcionales de endpoints
│       ├── test_infrastructure.py  # 10 pruebas: caché, CORS, swap, descarga verificada
│       └── fixtures/sample/   # 18 Parquet (gold.* y quality.qa_summary), 504 KB
├── docs/revision_divergencias/  # INFORME.md, PROPUESTA_F1DB.md y CSV de evidencias
├── ingestion/                 # cli.py (f1-ingest), f1db/fastf1/legacy/ergast loaders, io.py, snapshot.py
├── scripts/
│   ├── export_openapi.py      # Vuelca create_app().openapi() a web/src/lib/api/openapi.json
│   ├── make_api_fixture.py    # Genera api/tests/fixtures/sample desde dist/f1.duckdb
│   └── generate_override_seed.py  # Genera transform/seeds/race_data_overrides.csv
├── tests/                     # test_ingestion.py (5), test_snapshot.py (5)
├── transform/                 # dbt: dbt_project.yml, profiles.yml, macros, models, seeds, tests
├── web/
│   ├── src/
│   │   ├── proxy.ts           # Redirección / -> /{es|en} según Accept-Language
│   │   ├── app/
│   │   │   ├── globals.css    # Tailwind 4 + tokens de diseño (claro/oscuro)
│   │   │   ├── favicon.ico
│   │   │   └── [lang]/        # Segmento de idioma: layout raíz, páginas, error, not-found
│   │   ├── components/        # ui.tsx, formularios GET, mapas SVG, charts/ (ECharts)
│   │   ├── dictionaries/      # es.json, en.json
│   │   └── lib/               # api/{client.ts, openapi.json, schema.d.ts}, format, i18n, race, text, tyres
│   ├── tests/                 # accesibilidad.spec.ts, navegacion.spec.ts
│   ├── playwright.config.ts, next.config.ts (vacío), eslint.config.mjs, postcss.config.mjs
│   ├── package.json, package-lock.json (7 354 líneas), tsconfig.json, .env.example
│   └── AGENTS.md / CLAUDE.md  # Aviso generado por `next dev` sobre la versión de Next
├── .dockerignore  .gitattributes  .gitignore  .pre-commit-config.yaml  .python-version (3.12)
├── pyproject.toml  uv.lock  render.yaml  README.md
```

### 1.3. `pyproject.toml` y `uv.lock`

- Proyecto `f1-data-platform` 0.1.0, `requires-python = ">=3.12,<3.13"`, backend `hatchling`; el
  *wheel* empaqueta `ingestion` y `api`.
- Dependencia base única: `duckdb>=1.1` (común a ingesta, dbt y API).
- **Grupos de dependencias** (`[dependency-groups]`, PEP 735) para que cada consumidor instale solo lo
  suyo:

  | Grupo | Paquetes | Quién lo usa |
  |---|---|---|
  | `ingest` | `fastf1>=3.4`, `pandas>=2.2`, `pyarrow>=17`, `requests>=2.32` | CLI de ingesta, pipeline |
  | `api` | `fastapi>=0.115`, `uvicorn>=0.30` | Imagen Docker (`--no-default-groups --group api`) |
  | `transform` | `dbt-core>=1.9`, `dbt-duckdb>=1.9` | dbt en local y en CI |
  | `dev` | `httpx2>=2.13.1`, `pre-commit>=4`, `pytest>=8`, `ruff>=0.8` | Desarrollo y CI |

  `[tool.uv] default-groups` activa los cuatro en desarrollo. `httpx2` es la dependencia que exige
  el `TestClient` de Starlette 1.7 (se comprobó en `starlette/testclient.py`).
- Script de consola: `f1-ingest = "ingestion.cli:main"` (subcomandos `f1db`, `fastf1`, `legacy`,
  `ergast` y `snapshot {pack,restore,notes}`).
- Ruff: `line-length = 100`, `target-version = "py312"`, reglas `E, F, I, UP, B, SIM`.
- Pytest: `testpaths = ["tests", "api/tests"]`.
- `uv.lock` fija las versiones reales resueltas (p. ej. `duckdb 1.5.5`, `fastapi 0.141.1`,
  `starlette 1.7.0`, `ruff 0.16.9`); CI, pipeline y Dockerfile usan `uv sync --locked`, por lo que
  una desincronización entre `pyproject.toml` y el lock hace fallar la construcción.

### 1.4. Ficheros de configuración de la raíz

- **`.pre-commit-config.yaml`**: `pre-commit-hooks` v5.0.0 (`trailing-whitespace`,
  `end-of-file-fixer`, `check-yaml`, `check-added-large-files --maxkb=1024`) y `ruff-pre-commit`
  v0.8.4 (`ruff --fix` y `ruff-format`). Nota: el hook fija ruff 0.8.4 mientras que el lock resuelve
  ruff 0.16.9, que es el que ejecuta la CI (posible deriva de reglas/formato).
- **`.gitignore`**: excluye `data/`, `*.duckdb`, `*.parquet` (salvo
  `!api/tests/fixtures/sample/*.parquet`), entornos y cachés de Python, artefactos de dbt
  (`transform/target/`, `logs/`), Node/Next (`node_modules/`, `web/.next/`), `.env*` (salvo
  `.env.example`), `dist/`, `snapshot/`, `site/` (salidas del pipeline) y `.claude/`.
- **`.dockerignore`**: el contexto de Docker es la raíz, pero se excluye todo lo que no es la API:
  `.git`, `.github`, `.venv`, `data`, `dist`, `snapshot`, `site`, `docs`, `transform`, `tests`,
  `api/tests`, `web`, `scripts`, `*.duckdb`, `*.parquet`.
- **`.gitattributes`**: `* text=auto eol=lf` (finales de línea LF aunque se desarrolle en Windows) y
  `*.parquet`/`*.duckdb` como binarios.
- **`.python-version`**: `3.12`.
- **`render.yaml`**: Blueprint de Render (ver §4.3).
- **README.md** (299 líneas): arquitectura, ingesta, pipeline (tabla de ficheros de la release y
  puesta en marcha), API (tabla de endpoints y variables de entorno), web (correspondencia con las
  figuras del TFG) y despliegue. La tabla de endpoints del README no menciona `/rankings/*`.

### 1.5. `scripts/` y `tests/`

| Script | Qué hace |
|---|---|
| `scripts/export_openapi.py` | Importa `create_app()` y escribe `web/src/lib/api/openapi.json` (JSON indentado, UTF-8). Es el primer eslabón del contrato API→web. |
| `scripts/make_api_fixture.py` | Adjunta `dist/f1.duckdb` como `warehouse` (solo lectura) y exporta cada tabla a `api/tests/fixtures/sample/<esquema>.<tabla>.parquet` (zstd). Dimensiones y agregados completos; resultados y clasificaciones 2021-2024; vueltas, paradas y pasos por boxes solo del GP de Baréin 2024; telemetría solo de Verstappen, Leclerc y Hamilton en esa carrera. |
| `scripts/generate_override_seed.py` | Genera el *seed* `race_data_overrides.csv` a partir de las evidencias de `docs/revision_divergencias` y falla si la corrección ya no encaja con F1DB. |

`tests/test_ingestion.py` (5 pruebas: conversión de `timedelta` a ms, submuestreo de telemetría,
particionado, idempotencia de escritura, limpieza de duplicados del CSV legado) y
`tests/test_snapshot.py` (5 pruebas: `pack`/`restore` ida y vuelta, que la base de la API solo
contiene `gold` y `quality.qa_summary`, requisitos de `pack`, rechazo de archivos ajenos en
`restore` y notas de la release).

## 2. API (`api/app/`)

### 2.1. Configuración (`config.py`)

`Settings` es un `dataclass(frozen=True)` cuyos campos se leen de variables de entorno mediante
`default_factory` (así se pueden crear instancias en pruebas con valores explícitos):

| Campo | Variable | Por defecto | Uso |
|---|---|---|---|
| `db_path` | `F1_API_DB_PATH` | `None` | Fichero DuckDB fijo, sin refresco |
| `data_repo` | `F1_DATA_REPO` | `None` | `owner/repo` de la release de datos |
| `data_tag` | `F1_DATA_TAG` | `data-latest` | Etiqueta de la release |
| `github_token` | `F1_GITHUB_TOKEN` | `None` | Solo para repositorio privado |
| `data_dir` | `F1_API_DATA_DIR` | `data/api` (en Docker `/data`) | Dónde guardar las versiones descargadas |
| `refresh_hours` | `F1_API_REFRESH_HOURS` | `6` | Periodo de comprobación (0 = nunca) |
| `cors_origins` | `F1_API_CORS_ORIGINS` | `http://localhost:3000` | Lista separada por comas |
| `cache_max_age` | `F1_API_CACHE_MAX_AGE` | `600` | `max-age` de `Cache-Control` |

`local_candidates()` devuelve `dist/f1.duckdb` y `data/gold/f1.duckdb` para desarrollo.

### 2.2. Acceso a datos (`database.py`)

- **Resolución del origen** (`resolve_database(settings)`), por prioridad: (1) `F1_API_DB_PATH`
  (debe existir; se intenta leer un `manifest.json` hermano con `_local_manifest`), (2)
  `F1_DATA_REPO` → `release.ensure_database(...)`, (3) candidatos locales; si no hay nada,
  `FileNotFoundError` con instrucciones.
- **`DataVersion`** (`id`, `generated_at`, `f1db_release`, `last_completed_race`): `id` son los 12
  primeros caracteres del SHA-256 de `f1.duckdb` según el manifiesto; sin manifiesto se deriva de
  ruta + tamaño + `mtime_ns`. Alimenta las ETag y `/health`.
- **Clase `Database`**:
  - `_open(path, manifest)`: `duckdb.connect(path, read_only=True)`, comprueba que existe al menos
    una tabla en el esquema `gold` (si no, `ValueError`), y bajo un `threading.Lock` sustituye la
    conexión activa; la anterior pasa a la lista `_retired`.
  - `query(sql, params)`: toma el *lock* solo para crear un **cursor por consulta**
    (`connection.cursor()`; DuckDB permite cursores concurrentes de una misma conexión desde varios
    hilos), ejecuta con parámetros posicionales `?`, construye `list[dict]` con los nombres de
    columna y cierra el cursor en `finally`. `query_one` devuelve la primera fila o `None`.
  - `swap(path, manifest)`: **intercambio atómico de versión**: abre la nueva conexión y la publica;
    las consultas en curso siguen con su cursor de la conexión antigua.
  - `close_retired()` cierra las conexiones retiradas; `close()` cierra todo.
- Los *endpoints* son funciones síncronas (`def`), así que FastAPI las ejecuta en su *threadpool*;
  el paralelismo real lo aporta DuckDB por cursor.

### 2.3. Descarga de datos (`release.py`)

Solo biblioteca estándar (`urllib`, `hashlib`, `json`), para no añadir dependencias a la imagen.

- Con repositorio **público** (sin token) usa enlaces directos
  `https://github.com/{repo}/releases/download/{tag}/{name}`, que no consumen el límite de 60
  peticiones/h de la API de GitHub (compartido por IP en proveedores *cloud*).
- Con **token** consulta `GET /repos/{repo}/releases/tags/{tag}` y descarga el *asset* con
  `Accept: application/octet-stream`; un `_NoRedirect` evita reenviar `Authorization` al almacén
  externo al que redirige GitHub (se sigue la redirección a mano en `_open`).
- `fetch_manifest()` descarga `manifest.json` (fecha, versión de F1DB, última carrera, calidad y
  SHA-256 de cada fichero).
- `ensure_database(repo, tag, token, data_dir)`: calcula `versioned_path` =
  `f1-<sha256[:12]>.duckdb`; si existe y su SHA coincide, lo reutiliza; si no, descarga en bloques
  de 1 MiB a `*.download` (timeout 600 s), **verifica el SHA-256** contra el manifiesto (si no
  coincide, borra y lanza `ValueError`) y renombra con `Path.replace`. El nombre versionado permite
  abrir la versión nueva mientras la antigua sigue abierta (necesario en Windows).
- `remove_old_versions(data_dir, keep)` borra las otras `f1-*.duckdb` ignorando `OSError`.

### 2.4. Ciclo de vida y refresco (`main.py`)

- `create_app(settings=None, database=None)` es una **factoría** (las pruebas inyectan una
  `Database` sobre el fixture). El módulo expone `app = create_app()` para Uvicorn y configura
  `logging.basicConfig(level=INFO)`.
- **`lifespan`**: si no se inyecta base de datos, ejecuta `resolve_database` en un hilo
  (`asyncio.to_thread`, para no bloquear el bucle con la descarga de ~52 MB) y crea `Database`.
  Si hay `data_repo`, `refresh_hours > 0` y no hay `db_path`, lanza la tarea
  `refresh_periodically`. Al cerrar, cancela la tarea y cierra la base de datos.
- **`refresh_periodically(app, settings)`**: bucle infinito que *primero duerme*
  `refresh_hours × 3600` s, descarga el manifiesto, compara `sha[:12]` con `database.version.id`,
  y si difiere llama a `ensure_database`, `database.swap(...)`, espera 120 s de margen,
  `close_retired()` y `remove_old_versions()`. Cualquier excepción se registra
  (`log.exception`) y se sigue sirviendo la versión actual.
- **Middlewares** (Starlette aplica como más externo el último añadido):

  | Orden (petición) | Middleware | Configuración |
  |---|---|---|
  | 1 | `CORSMiddleware` | `allow_origins=settings.cors_origins`, `allow_methods=["GET"]`, `allow_headers=["If-None-Match"]`, `expose_headers=["ETag"]` |
  | 2 | `GZipMiddleware` | `minimum_size=1024` |
  | 3 | `DataCacheMiddleware` | `max_age=settings.cache_max_age` |

- Metadatos OpenAPI: título «F1 Data Platform API», `version="1.0.0"`; documentación interactiva
  en `/docs` (Swagger) y `/redoc`, contrato en `/openapi.json`.

### 2.5. Caché HTTP (`cache.py`)

`DataCacheMiddleware` (subclase de `BaseHTTPMiddleware`) actúa solo sobre `GET` cuando ya hay base
de datos y la ruta no está en `UNCACHED_PATHS = {"/health"}`:

1. Calcula `etag_for(version_id, request)` = `W/"<version>-<sha1(path?query)[:16]>"`.
2. Si `If-None-Match` contiene esa ETag, responde **304** sin ejecutar la consulta.
3. En caso contrario ejecuta el *endpoint* y, solo si el estado es 200, añade `ETag` y
   `Cache-Control: public, max-age=600, stale-while-revalidate=86400`. Los errores (404, 422) no se
   marcan como cacheables.

Al publicarse datos nuevos cambia `version.id` y, con él, todas las ETag (invalidación implícita).

### 2.6. Dependencias y esquemas

- `deps.py`: `get_database(request)` devuelve `request.app.state.database`; alias
  `DB = Annotated[Database, Depends(get_database)]`; `not_found(what)` → `HTTPException(404,
  "No existe …")`; `split_ids(value, limit)` divide listas separadas por comas y responde 422 si se
  supera el límite.
- `schemas.py`: 33 modelos Pydantic agrupados en estado (`Ref`, `RaceRef`, `DataInfo`, `Health`,
  `QualityCheck`), temporadas (`SeasonSummary`, `RaceSummary`, `SeasonDetail`, `DriverStanding`,
  `ConstructorStanding`, `StandingsProgression`), carreras (`RaceDetail` hereda de `RaceSummary`,
  `RaceResult`, `QualifyingResult`, `Lap`, `Stint`, `PitStop`, `PitLanePass`, `TelemetryLap`),
  pilotos y constructores (`DriverSummary`, `DriverDetail`, `DriverSeason`, `TeammateComparison`,
  `DriverRaceResult`, `ConstructorSummary`, `ConstructorDetail`, `ConstructorSeason`) y récords
  (`RecordEntry`, `ConstructorRanking`, `DriverRanking` hereda de `ConstructorRanking`, `Circuit`).
  Convenciones: tiempos en milisegundos, identificadores de F1DB (`lewis-hamilton`, `ferrari`),
  `race_id` entero.

### 2.7. Catálogo de *endpoints*

28 operaciones `GET` (26 en 7 *routers* + `/health` y `/quality` en `main.py`). Parámetros con `*`
son obligatorios. Las consultas usan siempre parámetros enlazados; cuando se interpola texto en el
SQL (nombre de columna o tabla) procede de un `Literal` o de un diccionario cerrado
(`DRIVER_METRICS`, `CONSTRUCTOR_METRICS`, `ORDER`), nunca de la entrada del usuario.

#### Estado (`main.py`)

| Endpoint | Parámetros | Respuesta | Tablas |
|---|---|---|---|
| `GET /health` | — | `Health` (`status`, `data.version`, `generated_at`, `f1db_release`, `last_completed_race`) | ninguna (versión en memoria); sin caché |
| `GET /quality` | — | `list[QualityCheck]` ordenada FAIL → PASS → resto | `quality.qa_summary` |

#### Temporadas (`routers/seasons.py`, prefijo `/seasons`)

| Endpoint | Parámetros | Respuesta | Tablas gold |
|---|---|---|---|
| `GET /seasons` | — | `list[SeasonSummary]` (carreras, disputadas, campeones de pilotos y constructores), de la más reciente a la más antigua | `dim_race`, `agg_driver_season`, `fact_constructor_standing`, `dim_constructor` |
| `GET /seasons/{season}` | `season*` | `SeasonDetail` (calendario con ganador) | `dim_race`, `fact_race_result`, `dim_driver` (SQL compartido `RACE_SUMMARY_SQL`) |
| `GET /seasons/{season}/standings/drivers` | `season*`, `round` (≥1) | `list[DriverStanding]` tras la ronda pedida o la última disputada | `dim_race`, `fact_driver_standing`, `fact_race_result`, `dim_driver`, `dim_constructor` |
| `GET /seasons/{season}/standings/constructors` | `season*`, `round` | `list[ConstructorStanding]` (con motor) | `dim_race`, `fact_constructor_standing`, `fact_race_result`, `dim_constructor`, `dim_engine_manufacturer` |
| `GET /seasons/{season}/standings/progression` | `season*`, `type` (`drivers`\|`constructors`), `top` (1-50, 10) | `list[StandingsProgression]` (puntos acumulados por ronda de los N primeros) | `dim_race`, `fact_driver_standing`/`fact_constructor_standing`, `dim_driver`/`dim_constructor` |

`RACE_SUMMARY_SQL` resuelve el caso de coches compartidos de los años 50 escogiendo un único
ganador por carrera (mínimo `position_display_order`). `_standings_race()` elige la carrera de
referencia de la clasificación.

#### Carreras (`routers/races.py`, prefijo `/races`)

Todas validan antes la existencia con `_require_race()` (404 si no existe).

| Endpoint | Parámetros | Respuesta | Tablas gold |
|---|---|---|---|
| `GET /races/{race_id}` | `race_id*` | `RaceDetail` (resumen + hora UTC, vueltas, distancia, tipo de circuito, sentido, longitud, curvas, coordenadas, `is_season_final_race`) | `dim_race`, `fact_race_result`, `dim_driver` |
| `GET /races/{race_id}/results` | `session` (`race`\|`sprint`) | `list[RaceResult]` con `corrected_fields` (columnas corregidas por *overrides*) | `fact_race_result`, `dim_driver`, `dim_constructor` |
| `GET /races/{race_id}/qualifying` | `session` (`qualifying`\|`sprint_qualifying`) | `list[QualifyingResult]` (Q1-Q3, mejor tiempo, % respecto a la pole) | `fact_qualifying_result`, `dim_driver`, `dim_constructor` |
| `GET /races/{race_id}/laps` | `drivers` (≤30, por comas) | `list[Lap]`: posición, tiempo, *gap*, sectores, compuesto relativo/Pirelli, edad, *pit in/out*, banderas, SC/VSC, fuente, estado de validación | `fact_laptimes` (excluye `is_incomplete_lap`) |
| `GET /races/{race_id}/stints` | — | `list[Stint]`: tramos calculados con funciones ventana (nuevo tramo tras entrar en boxes o cambio de compuesto) | `fact_laptimes` |
| `GET /races/{race_id}/pitstops` | — | `list[PitStop]` (vuelta, número, duración) | `fact_pit_stops`, `dim_driver` |
| `GET /races/{race_id}/pit-lane-passes` | — | `list[PitLanePass]` tipificados (parada, SC, sanción…) | `fact_pit_lane_passes` |
| `GET /races/{race_id}/telemetry` | `drivers*` (1-4) | `list[TelemetryLap]`: listas de distancia, velocidad, acelerador, freno, marcha y x/y de la vuelta más rápida de clasificación, en el orden pedido | `fact_quali_telemetry` (2024+) |

#### Pilotos (`routers/drivers.py`, prefijo `/drivers`)

| Endpoint | Parámetros | Respuesta | Tablas gold |
|---|---|---|---|
| `GET /drivers` | `search` (≥2, insensible a acentos con `strip_accents(lower())`), `season`, `limit` (1-1000, 50), `offset` | `list[DriverSummary]` ordenada por victorias, podios, salidas | `agg_driver_career`, `agg_driver_season` |
| `GET /drivers/{driver_id}` | — | `DriverDetail` (biografía + estadísticas de carrera, tasas de victoria/podio) | `agg_driver_career`, `dim_driver` |
| `GET /drivers/{driver_id}/seasons` | — | `list[DriverSeason]` | `agg_driver_season` |
| `GET /drivers/{driver_id}/results` | `season` | `list[DriverRaceResult]` (carrera y sprint) | `fact_race_result`, `dim_race` |
| `GET /drivers/{driver_id}/teammates` | — | `list[TeammateComparison]` (carreras/clasificaciones por delante, puntos) | `agg_teammate_h2h`, `dim_constructor`, `dim_driver` |

#### Constructores (`routers/constructors.py`, prefijo `/constructors`)

| Endpoint | Parámetros | Respuesta | Tablas gold |
|---|---|---|---|
| `GET /constructors` | `search`, `season`, `limit` (1-500, 50), `offset` | `list[ConstructorSummary]` | `agg_constructor_career`, `fact_race_result`, `dim_race` |
| `GET /constructors/{constructor_id}` | — | `ConstructorDetail` (podios, dobletes, poles, vueltas rápidas, puntos, mejor posición) | `agg_constructor_career`, `dim_constructor` |
| `GET /constructors/{constructor_id}/seasons` | — | `list[ConstructorSeason]` (posición final vía `qualify row_number()`, victorias, pilotos) | `fact_race_result`, `dim_race`, `dim_driver`, `fact_constructor_standing`, `dim_constructor` |

#### Récords y rankings (`routers/records.py` y `routers/rankings.py`)

| Endpoint | Parámetros | Respuesta | Tablas gold |
|---|---|---|---|
| `GET /records/drivers` | `metric` (`championships`, `wins`, `podiums`, `pole_positions`, `fastest_laps`, `race_starts`, `points`, `grand_slams`; por defecto `wins`), `limit` (1-100, 20) | `list[RecordEntry]` (`rank()` SQL, `id`, `name`, `country_alpha2`, `value`) | `agg_driver_career` |
| `GET /records/constructors` | `metric` (`championships`, `wins`, `podiums`, `pole_positions`, `fastest_laps`, `race_entries`, `one_two_finishes`, `points`→`race_points`), `limit` | `list[RecordEntry]` | `agg_constructor_career` |
| `GET /rankings/drivers` | `season_from`, `season_to`, `order_by` (`wins`, `championships`, `podiums`, `pole_positions`, `fastest_laps`, `points`, `entries`), `limit` (1-500, 50) | `list[DriverRanking]` recalculado desde resultados carrera a carrera en el rango (inscripciones, salidas —excluye DNQ/DNPQ/DNP/EX/DNS—, victorias, podios, poles, VR, puntos, títulos) | `fact_race_result`, `dim_race`, `fact_driver_standing`, `dim_driver` |
| `GET /rankings/constructors` | ídem | `list[ConstructorRanking]` (podios contados por coche: `race_id || '-' || driver_number`) | `fact_race_result`, `dim_race`, `fact_constructor_standing`, `dim_constructor` |

`/records` lee los agregados precalculados; `/rankings` los recalcula para un rango de temporadas
(con el rango completo coinciden con los totales oficiales de F1DB, lo que prueba
`test_rankings_match_season_totals`).

#### Circuitos (`routers/circuits.py`)

| Endpoint | Parámetros | Respuesta | Tablas gold |
|---|---|---|---|
| `GET /circuits` | `season_from`, `season_to` | `list[Circuit]` (coordenadas, nº de carreras, primera y última temporada, GP disputados) | `dim_race` (solo `is_completed`) |

### 2.8. Imagen Docker (`api/Dockerfile`)

1. `FROM python:3.12-slim`; copia el binario de `uv` desde `ghcr.io/astral-sh/uv:0.12`.
   Variables `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`, `UV_PYTHON_DOWNLOADS=never`,
   `PYTHONUNBUFFERED=1`.
2. Capa de dependencias cacheable: copia `pyproject.toml uv.lock README.md` y ejecuta
   `uv sync --locked --no-default-groups --group api --no-install-project` (solo DuckDB, FastAPI,
   Uvicorn: sin pandas ni FastF1).
3. Copia `ingestion/__init__.py` (necesario porque el *wheel* declara el paquete), `api/__init__.py`
   y `api/app`, y repite `uv sync` para instalar el proyecto.
4. Usuario sin privilegios `app` (UID 1000), carpeta `/data` propia; `F1_API_DATA_DIR=/data`,
   `PORT=8000`.
5. `HEALTHCHECK --interval=30s --timeout=5s --start-period=120s` con un `urllib.request.urlopen` a
   `/health` (sin `curl` en la imagen).
6. `CMD uvicorn api.app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers
   --forwarded-allow-ips='*'`.

### 2.9. Pruebas de la API

- **Fixture**: `api/tests/conftest.py` crea en una carpeta temporal `sample.duckdb` a partir de los
  18 Parquet de `api/tests/fixtures/sample/` (nombre `esquema.tabla.parquet` → `create schema` +
  `create table ... as select * from '<parquet>'`), y el *fixture* `client` monta
  `create_app(Settings(cors_origins=["https://f1.example.org"], refresh_hours=0),
  Database(sample_db_path))` con `TestClient`. Las pruebas no necesitan red ni la release.
- `test_endpoints.py` (20 pruebas): salud, calidad ordenada, temporadas con campeones, calendario,
  clasificaciones final y tras ronda, progresión (un punto por ronda y piloto), detalle de carrera,
  resultados y clasificación, vueltas filtradas, *stints* coherentes con paradas, pasos por boxes
  tipificados, telemetría (orden y límite de 4), búsqueda de pilotos (con y sin acentos),
  constructores, récords, circuitos por rango, 404, y rankings que cuadran con los totales.
- `test_infrastructure.py` (10 pruebas): ETag + 304, `/health` sin caché, errores sin caché, CORS
  solo para el origen configurado, `swap` cambia la versión, prioridad de `F1_API_DB_PATH`, descarga
  verificada/versionada/reutilizada (con una release falsa), descarte por SHA incorrecto, borrado de
  versiones antiguas y uso de enlaces directos para repos públicos.
- Resultado local: `pytest` recoge **40 pruebas** (30 de la API + 10 de ingesta) y pasan todas en
  2,4 s.

## 3. Web (`web/`)

### 3.1. Pila y convenciones de Next.js 16

- `next 16.3.6`, `react`/`react-dom 19.2.8`, TypeScript 5 (`strict`), Tailwind CSS 4
  (`@tailwindcss/postcss`), ESLint 9 (`eslint-config-next` *core-web-vitals* + *typescript*).
  Dependencias de ejecución mínimas: `echarts ^6.1`, `d3-geo`, `topojson-client`, `world-atlas`,
  `server-only`.
- **App Router** con todo bajo el segmento dinámico `src/app/[lang]/`; no hay `app/layout.tsx`
  global: el *layout* raíz es `[lang]/layout.tsx`, que fija `<html lang={locale}>`.
- **`src/proxy.ts`** (en Next 16 sustituye a `middleware.ts`): si la ruta no empieza por `/es` o
  `/en`, calcula el idioma preferido a partir de `Accept-Language` (ordenado por `q`) y redirige
  (307) a `/{locale}{pathname}`. `matcher: ["/((?!_next|.*\\..*).*)"]` excluye internos y estáticos.
- **i18n** (`src/lib/i18n.ts`, `server-only`): diccionarios `es.json`/`en.json` cargados con
  `import()` dinámico; `getDictionary(lang)` devuelve `{locale, t}` o llama a `notFound()`.
  `src/lib/text.ts::fill()` sustituye marcadores `{clave}`. El cambio de idioma
  (`LanguageSwitch` en `nav-links.tsx`) reescribe el prefijo de la ruta actual y marca
  `hrefLang`/`lang`.
- **`params` y `searchParams` son `Promise`** (Next 15+): todas las páginas hacen
  `await params` / `await searchParams`. Los tipos `PageProps<"/[lang]/…">` y `LayoutProps<…>` los
  genera **`next typegen`** (el script `typecheck` es `next typegen && tsc --noEmit`; el commit
  `66c61e0` lo añadió a la CI porque sin él faltaban los tipos de rutas).
- **Scripts npm**: `dev`, `build`, `start`, `lint`, `gen:api` (`openapi-typescript
  src/lib/api/openapi.json -o src/lib/api/schema.d.ts`), `test:e2e`, `typecheck`.
- `next.config.ts` está vacío (sin cabeceras, sin `images`, sin `output`).

### 3.2. Cliente API tipado (`src/lib/api/`)

- `openapi.json` (exportado por `scripts/export_openapi.py`) → `schema.d.ts` (generado por
  `openapi-typescript`). `client.ts` exporta `Schemas = components["schemas"]`, de modo que las
  páginas escriben `apiGetRequired<Schemas["RaceResult"][]>(…)`.
- `client.ts` es `server-only`: la URL de la API (`F1_API_URL`, por defecto
  `http://127.0.0.1:8000`) nunca llega al navegador y **el navegador no llama a la API** (el CORS de
  la API no interviene en la web).
- `apiGet<T>(path, query)`: construye la URL omitiendo parámetros vacíos, `fetch` con
  `next: { revalidate: 3600 }` y `Accept: application/json`; 404 → `null`; otro error →
  `ApiError(status, path)`. `apiGetRequired<T>` convierte `null` en `ApiError(404)`.
- `src/lib/race.ts`: `getRace` (valida `^\d+$`, 404 si no existe), `getResults` y
  `getDriverNames`, memorizados por petición con `React.cache` (los usan el *layout* de carrera y
  cada pestaña sin duplicar llamadas).
- `src/lib/format.ts`: `lapTime`, `raceTime`, `gap`, `number` e `date` con `Intl`, `driverCode`.
- `src/lib/tyres.ts`: colores Pirelli y **letra** de cada compuesto (S, M, H, I, W, HS, US, SS, SH)
  para no depender solo del color; `compoundStyle()`.

### 3.3. Mapa de rutas

20 ficheros de ruta bajo `[lang]` (16 `page.tsx`, 2 `layout.tsx`, `error.tsx`, `not-found.tsx`) →
**16 páginas por idioma, 32 URL‑patrón en total** (es/en).

| Ruta | Qué muestra | Endpoints | Figura del TFG |
|---|---|---|---|
| `/` (proxy) | Redirección 307 a `/es` o `/en` | — | — |
| `/[lang]` | Inicio: temporada en curso (calendario, clasificaciones, último resultado) y **mapa mundial** de GP por país o circuito (`?view=`), filtrable por rango (`?from=&to=`) | `/seasons`, `/seasons/{y}`, `/seasons/{y}/standings/drivers`, `…/constructors`, `/circuits?season_from&season_to`, `/races/{id}/results` | 5.23 |
| `/[lang]/seasons` | Selector de temporada (formulario GET; con `?year=` hace `redirect`) | `/seasons` | — |
| `/[lang]/seasons/[year]` | Campeones, clasificación de pilotos y constructores, gráfico de evolución y calendario | `/seasons/{y}`, `/seasons`, `…/standings/drivers`, `…/standings/constructors`, `…/standings/progression?top=10` | 5.26 |
| `/[lang]/races/[id]` (*layout*) | Cabecera de la carrera, navegación anterior/siguiente y pestañas (`TabNav`); telemetría solo si `season ≥ 2024`; carreras futuras sin pestañas | `/races/{id}`, `/seasons/{y}` | — |
| `/[lang]/races/[id]` | Resultado (carrera o sprint, `?session=`) | `/races/{id}/results` | — |
| `/[lang]/races/[id]/qualifying` | Clasificación y gráfico de barras de *gaps* (pilotos o constructores; clasificación normal o sprint) | `/races/{id}/qualifying?session=` | 5.27 |
| `/[lang]/races/[id]/lap-chart` | Posiciones vuelta a vuelta | `/races/{id}/laps`, `/races/{id}/results` | 5.28 |
| `/[lang]/races/[id]/tyres` | Estrategia (`StintChart`) y matriz de compuestos vuelta a vuelta (`CompoundMatrix`) | `/races/{id}/stints`, `/races/{id}/laps`, `/results` | 5.29 |
| `/[lang]/races/[id]/pace` | Tiempos por vuelta (líneas) y ritmo (violín) | `/races/{id}/laps`, `/results` | 5.30, 5.31 |
| `/[lang]/races/[id]/pitstops` | Paradas, media por constructor (barras) y todos los pasos por el *pit lane* | `/pitstops`, `/pit-lane-passes`, `/results` | 5.32 |
| `/[lang]/races/[id]/telemetry` | Comparación de dos pilotos (`?a=&b=`, validados contra el resultado): velocidad/acelerador/freno/marcha y **trazado coloreado por velocidad** | `/races/{id}/telemetry?drivers=a,b`, `/results` | nueva |
| `/[lang]/drivers` | Buscador (`?q=`, ≥2 caracteres) y listado | `/drivers?search&limit` | — |
| `/[lang]/drivers/[id]` | Ficha, cifras, puntos por temporada, comparativas con compañeros (puntos y % por delante) | `/drivers/{id}`, `…/seasons`, `…/teammates` | 5.33 |
| `/[lang]/constructors` | Buscador y listado | `/constructors?search&limit` | — |
| `/[lang]/constructors/[id]` | Ficha y puntos por temporada | `/constructors/{id}`, `…/seasons` | nueva |
| `/[lang]/records` | Títulos y «más laureados» de pilotos o constructores (`?entity=&order=&from=&to=`) con gráfico de barras | `/seasons`, `/rankings/{entity}` (×2) | 5.24, 5.25 |
| `/[lang]/quality` | Controles de calidad (bloqueantes e informativos) y fuentes | `/quality` | nueva |
| `error.tsx` | *Error boundary* cliente con textos es/en embebidos y botón de reintento | — | — |
| `not-found.tsx` | 404 del sitio | — | — |

Además, **todas las páginas** llaman a `GET /health` desde `SiteFooter` (componente de servidor
asíncrono) para mostrar la fecha de los datos y la versión de F1DB; el error se captura
(`.catch(() => null)`) para que el pie no rompa la página si la API no responde.

No se usan `generateStaticParams` (ni siquiera para `[lang]`); las páginas de detalle validan el
identificador con una expresión regular antes de llamar a la API y usan `generateMetadata` para el
`<title>`.

### 3.4. Componentes (`src/components/`)

**Gráficos (`charts/`, todos `"use client"`)**

- `echart.tsx`: núcleo de ECharts **tree-shaken** (`echarts/core` + solo `BarChart`,
  `BoxplotChart`, `LineChart`, `ScatterChart`, `DataZoom`, `Grid`, `Legend`, `MarkLine`, `Tooltip`,
  `VisualMap` y **`SVGRenderer`**). El componente `EChart({build, height, label})` lee los *tokens*
  CSS del documento (`readTheme()`), inicializa con `renderer: "svg"`, desactiva la animación si
  `prefers-reduced-motion: reduce`, redimensiona con `ResizeObserver` y se redibuja al cambiar
  `prefers-color-scheme`. El contenedor es `role="img"` con `aria-label`.
  Paletas **Okabe-Ito** clara y oscura (`LIGHT_SERIES`, `DARK_SERIES`) y `seriesStyle()` que combina
  color + tipo de línea + símbolo para no depender solo del color. Utilidades `baseOption`,
  `axisStyle`, `tooltipStyle`.
- `chart-figure.tsx`: `ChartFigure` = `<figure>` con `<figcaption>` (título + **resumen textual**) y
  la **tabla de datos completa en `<details>`**.
- Gráficos concretos: `bar-chart.tsx`, `lap-chart.tsx`, `lap-times-chart.tsx`,
  `progression-chart.tsx`, `season-points-chart.tsx`, `stint-chart.tsx`, `teammate-charts.tsx`
  (`TeammatePointsChart`, `TeammateShareChart`), `telemetry-chart.tsx`, `violin-chart.tsx` (violín
  con SVG propio, colores por variables CSS `.violin`).

**Servidor (sin JavaScript en el cliente)**

- `world-map.tsx`: mapa mundial con `d3-geo` (`geoEqualEarth`) y `world-atlas/countries-110m`
  (TopoJSON → GeoJSON con `topojson-client`), **calculado en el servidor** como SVG estático
  960×470; los contornos se calculan una vez a nivel de módulo; círculos con radio ∝ √carreras;
  `<title>`/`<desc>` accesibles.
- `track-map.tsx`: trazado del circuito a partir de x/y de telemetría, coloreado por velocidad
  (escala de 4 paradas), SVG con proporciones reales.
- `compound-matrix.tsx`: matriz piloto × vuelta con color y letra del compuesto.
- `ui.tsx`: `PageHeader`, `Section`, `DataTable<T>` (tabla accesible con `<caption>`, `th
  scope="col"`, celdas `th scope="row"`, `aria-sort`, contenedor `role="region"` desplazable y
  enfocable con `tabIndex=0`), `Pill`, `EmptyState`, `Stat`, `Highlight`.
- Formularios **GET sin JavaScript**: `search-form.tsx` (buscador), `season-picker.tsx`
  (selector de temporada), `season-range-form.tsx` (desde/hasta + `parseYear()` que acota valores),
  `session-switch.tsx` (conmutador como enlaces).
- Navegación: `site-header.tsx`, `site-footer.tsx`, `nav-links.tsx` (`NavLinks` con
  `aria-current`, `LanguageSwitch`), `tab-nav.tsx` (pestañas como enlaces con URL propia y
  `aria-current="page"`); estos dos últimos son componentes cliente solo por `usePathname()`.

### 3.5. Estrategia de caché y renderizado

- Cada `fetch` a la API lleva `next: { revalidate: 3600 }` (Data Cache de Next/Vercel con
  revalidación incremental: tras 1 h la siguiente petición recibe el dato antiguo y dispara la
  regeneración en segundo plano). El *layout* raíz declara además `export const revalidate = 3600`.
- En la práctica **todas las páginas medidas se sirven dinámicamente**: Vercel devuelve
  `Cache-Control: private, no-cache, no-store, max-age=0, must-revalidate` y
  `X-Vercel-Cache: MISS` en `/es`, `/es/drivers/lewis-hamilton`, `/es/seasons/2021` y
  `/es/races/1102`. El HTML se renderiza en una función en cada visita; lo que se reutiliza es la
  respuesta de la API guardada en la Data Cache. Las páginas con filtros leen `searchParams` (API
  dinámica, renderizado por petición inevitable); en las que no los leen (p. ej. la ficha de piloto)
  el código no usa `headers()`, `cookies()` ni `force-dynamic`, así que la causa más probable es
  que ningún segmento (empezando por `[lang]`) declare `generateStaticParams`, de modo que Next no
  genera ni conserva HTML estático para esas rutas. Conviene confirmarlo con la salida de
  `next build` (columna de tipo de ruta).
- La cabecera `X-Vercel-Id: cdg1::iad1::…` indica que la petición entra por el *edge* de París pero
  la función se ejecuta en **iad1 (Washington)**, mientras que la API está en **Frankfurt**: cada
  fallo de la Data Cache cruza el Atlántico.

### 3.6. Estilos

- Tailwind 4 con `@import "tailwindcss"` y `@theme inline` que mapea los *tokens* a utilidades
  (`bg-surface`, `text-muted`, `border-line`, `fill-red`…).
- *Tokens* en `:root` de `globals.css` (`--bg`, `--surface`, `--surface-2`, `--ink`, `--muted`,
  `--line`, `--red`, `--purple` = «lo más rápido», `--green` = mejora personal, `--amber`,
  `--focus`, `--on-accent`) redefinidos en `@media (prefers-color-scheme: dark)`; `color-scheme`
  acorde. Modo oscuro automático según el sistema (no hay conmutador manual).
- Tipografías con `next/font/google` autoalojadas: Titillium Web (titulares), IBM Plex Sans
  (texto), IBM Plex Mono (tiempos; clase `.tabular` con `tabular-nums`).

### 3.7. Accesibilidad

- Enlace «Saltar al contenido» como primer elemento enfocable; `<main id="contenido"
  tabIndex={-1}>`.
- `:focus-visible` con contorno de 3 px en `--focus`.
- Cada gráfico: `figcaption` con resumen en texto + tabla alternativa en `<details>`; el lienzo
  ECharts es `role="img"` con `aria-label` y `aria.enabled: false` para no duplicar lectura.
- Codificación redundante: color + forma/línea en series, color + letra en neumáticos.
- `prefers-reduced-motion`: regla global que anula animaciones y transiciones y desactiva la
  animación de ECharts.
- Formularios y pestañas funcionan sin JavaScript (enlaces y GET).
- Tablas con semántica completa (`caption`, `scope`, `aria-sort`) y desplazamiento horizontal
  accesible por teclado.

### 3.8. Pruebas de la web

`playwright.config.ts`: `testDir: ./tests`, *timeout* 60 s, `fullyParallel`, 1 reintento en CI,
*reporter* `github`+`list` en CI. Proyectos `escritorio` (Desktop Chrome) y `movil` (Pixel 7, solo
`navegacion`). En local usa el Edge del sistema (`channel: "msedge"`), en CI el Chromium de
Playwright. `webServer`: `npx next start --port 3100` salvo que se defina `BASE_URL`, en cuyo caso se
prueba contra la web desplegada (commit `cceddd3`).

| Fichero | Pruebas | Contenido |
|---|---:|---|
| `accesibilidad.spec.ts` | 26 | axe WCAG 2.0/2.1/2.2 A y AA en 21 URL (incl. `/en`, filtros de récords, búsqueda); 1 prueba de que cada `<figure>` tiene `figcaption` y `details summary`; 4 de contraste en tema oscuro (`colorScheme: "dark"`) |
| `navegacion.spec.ts` | 6 × 2 proyectos = 12 | Redirección por idioma, *skip link*, del inicio a una carrera y sus pestañas (`aria-current`), buscador **sin JavaScript** (`javaScriptEnabled: false`), cambio de idioma que conserva la ruta y `lang`, ausencia de desbordamiento horizontal en 9 páginas |

Total: **38 ejecuciones** de prueba e2e por pasada. La carrera de referencia es Baréin 2024
(`race_id` 1102).

## 4. CI/CD

### 4.1. `ci.yml` (push a `main` y *pull requests*)

Permisos `contents: read`; `concurrency: ci-${{ github.ref }}` con cancelación de ejecuciones
anteriores. Cuatro *jobs* en paralelo:

1. **`python`** (15 min): `actions/checkout@v5` → `astral-sh/setup-uv@v6` (caché) →
   `uv sync --locked` → `ruff check .` → `ruff format --check .` → `pytest`.
2. **`dbt`** (30 min): checkout, uv, `uv sync --locked`; descarga `bronze.tar.gz` de
   `data-latest` con `gh release download` y `f1-ingest snapshot restore` (si no existe, aviso y
   `available=false`); `dbt parse`; `dbt build` solo si hay datos; en fallo sube `transform/logs/`
   y `run_results.json` con `actions/upload-artifact@v4`.
3. **`api-image`** (20 min): `docker build -f api/Dockerfile -t f1-api .`; descarga `f1.duckdb` y
   `manifest.json`; **prueba de humo**: `docker run` con `F1_API_DB_PATH=/snapshot/f1.duckdb`
   (volumen de solo lectura), espera hasta 60 s a `/health`, pide `/seasons` y comprueba que
   `/races/999999` da 404; en fallo muestra `docker logs`.
4. **`web`** (30 min, `F1_API_URL=http://127.0.0.1:8000`): checkout, uv, `actions/setup-node@v5`
   (Node 24, caché npm), `uv sync`, `npm ci`; **comprobación de contrato**:
   `export_openapi.py` + `npm run gen:api` + `git diff --exit-code web/src/lib/api` (falla si los
   tipos TS no están al día con la API); `npm run lint`, `npm run typecheck`, `npm run build`;
   descarga la base publicada, arranca `uvicorn` con `F1_API_DB_PATH`, instala Chromium y ejecuta
   `npx playwright test`; en fallo sube `playwright-report/`.

Duración observada (API pública de GitHub Actions): entre 30 s y 2,5 min por ejecución de CI. De
las 6 ejecuciones de CI del 28-09-2026, 4 terminaron bien y 2 fallaron (22:37 y 22:45 UTC); las
siguientes, tras los commits de corrección (`66c61e0`, tipos de rutas; `d0d9bd5`, desbordamiento
de la matriz de neumáticos), volvieron a pasar.

### 4.2. `pipeline.yml` (datos)

- Disparadores: `cron: "0 6 * * 1"` (lunes 06:00 UTC) y `workflow_dispatch` con entradas `seasons`
  (temporadas FastF1) y `force_f1db`. Permisos `contents: write`; `concurrency: data-pipeline` sin
  cancelación.
- Pasos del *job* `pipeline` (120 min): checkout → setup-uv → `uv sync --locked` → **restaurar
  snapshot** (`bronze.tar.gz`; error si no existe) → `f1-ingest f1db [--force]` → `f1-ingest
  fastf1 --season <año> --telemetry` (`continue-on-error: true`; en enero incluye también el año
  anterior; valida el formato de temporadas con expresión regular) → **`dbt build`** (si falla una
  prueba de calidad, no se publica nada) → `snapshot pack --out dist` + `snapshot notes` (al
  *step summary*) → **publicación**: crea `data-latest` si no existe (`--latest=false`), sube
  `f1.duckdb`, `gold-parquet.zip`, `manifest.json` y, al final, `bronze.tar.gz` (`--clobber`), y
  actualiza las notas → aviso si FastF1 falló → opcional: `dbt docs generate --static` y
  `upload-pages-artifact@v3` si `vars.PUBLISH_DOCS == 'true'` → logs de dbt si falla.
- *Job* `docs` (`needs: pipeline`, condicionado a `PUBLISH_DOCS`): `actions/deploy-pages@v4`.
- Última ejecución: manual el 28-09-2026 19:45 UTC, ~1 min, correcta. Release actual: `f1.duckdb`
  52,2 MB, `bronze.tar.gz` 51,7 MB, `gold-parquet.zip` 28,1 MB, `manifest.json` 1,5 KB; versión
  servida `35677c2df776`, F1DB `v2026.15.1`, última carrera: GP de Azerbaiyán 2026 (ronda 15).

### 4.3. Despliegue continuo

- **Render** (`render.yaml`): servicio web `f1-data-api`, `runtime: docker`, `plan: free`,
  `region: frankfurt`, `dockerfilePath: ./api/Dockerfile`, `dockerContext: .`,
  `healthCheckPath: /health`, `autoDeploy: true` con **`buildFilter.paths`**: `api/**`,
  `pyproject.toml`, `uv.lock` (un cambio en la web o en dbt no reconstruye la API). Variables:
  `F1_DATA_REPO=AntonioSchez32/f1-data-platform`, `F1_API_REFRESH_HOURS=6`,
  `F1_API_CORS_ORIGINS` (`sync: false`, se rellena en el panel). Render construye su propia imagen:
  la imagen de `api-image` en CI no se publica ni se reutiliza.
- **Vercel**: proyecto con *Root Directory* `web`, variable `F1_API_URL` apuntando a Render;
  despliegue automático en cada push a `main` (producción) y *previews* por rama/PR. No hay
  `vercel.json`.
- Ninguno de los dos despliegues espera a que la CI pase: se disparan por el push en paralelo.

### 4.4. Flujo de refresco de datos extremo a extremo

¿Cuándo aparece en la web una carrera disputada el domingo?

1. **Lunes 06:00 UTC** (+ cola de GitHub, típicamente minutos): el pipeline ingiere F1DB/FastF1,
   `dbt build`, y publica `f1.duckdb` + `manifest.json` en `data-latest`.
2. **API**: el bucle `refresh_periodically` comprueba el manifiesto cada 6 h **contadas desde el
   arranque del proceso**; al detectar un SHA distinto descarga, verifica y hace `swap`. En el plan
   gratuito la instancia se duerme tras ~15 min sin tráfico y al despertar vuelve a ejecutar
   `resolve_database`, que descarga siempre la última versión: en la práctica, la API sirve datos
   nuevos en **0-6 h** tras la publicación (antes si ha habido un *cold start*).
3. **Web**: las respuestas de la API quedan en la Data Cache de Next hasta **1 h**; al caducar, la
   primera visita recibe el dato antiguo y dispara la revalidación. Además, las ETag de la API
   cambian con la versión, así que las revalidaciones posteriores no reutilizan nada antiguo.
4. **Peor caso**: ~7 h tras la publicación (≈ lunes 13:00 UTC); caso habitual con la instancia
   dormida: pocos minutos tras la primera visita posterior a la publicación.

## 5. Diagramas

### 5.1. Arquitectura de despliegue

```text
NODOS
  dev      [actor]      "Desarrollador (Windows, uv, npm)"
  gh       [repo]       "GitHub: AntonioSchez32/f1-data-platform (main)"
  ci       [proceso]    "GitHub Actions · ci.yml (python, dbt, api-image, web)"
  pipe     [proceso]    "GitHub Actions · pipeline.yml (lunes 06:00 UTC)"
  rel      [almacén]    "GitHub Release data-latest (f1.duckdb, manifest.json, bronze.tar.gz, gold-parquet.zip)"
  f1db     [externo]    "F1DB (GitHub releases)"
  ff1      [externo]    "FastF1 / F1 Live Timing"
  pages    [externo]    "GitHub Pages (docs dbt, opcional)"
  render   [servicio]   "Render · f1-data-api (Docker, free, Frankfurt) · uvicorn + FastAPI"
  duck     [almacén]    "DuckDB f1-<sha>.duckdb (solo lectura, /data efímero)"
  cf       [red]        "Cloudflare (delante de Render, cf-cache-status: DYNAMIC)"
  vercel   [servicio]   "Vercel · Next.js 16 (edge cdg1, funciones iad1) + Data Cache"
  user     [actor]      "Navegador"

ARISTAS
  dev   -> gh      "git push"
  gh    -> ci      "push / pull_request"
  gh    -> render  "autoDeploy (buildFilter: api/**, pyproject.toml, uv.lock)"
  gh    -> vercel  "deploy (root: web)"
  pipe  -> rel     "gh release download bronze.tar.gz / upload --clobber"
  f1db  -> pipe    "f1-ingest f1db"
  ff1   -> pipe    "f1-ingest fastf1 --telemetry"
  pipe  -> pages   "dbt docs (si PUBLISH_DOCS)"
  ci    -> rel     "descarga snapshot para dbt build, humo y e2e"
  rel   -> render  "arranque + cada 6 h: manifest.json, f1.duckdb (SHA-256)"
  render-> duck    "cursor por consulta"
  user  -> vercel  "HTTPS (HTML + RSC)"
  vercel-> cf      "fetch server-side (F1_API_URL), revalidate 3600"
  cf    -> render  "proxy"
```

### 5.2. Secuencia de una petición (`/es/races/1102/pace`)

```text
PARTICIPANTES: Navegador, VercelEdge(cdg1), FuncionNext(iad1), DataCache, APIRender(FRA), DuckDB

1. Navegador      -> VercelEdge     GET /es/races/1102/pace
2. VercelEdge     -> FuncionNext    (X-Vercel-Cache: MISS; página dinámica)
3. FuncionNext    : proxy.ts ya tiene prefijo /es -> sin redirección
4. FuncionNext    : [lang]/layout -> getDictionary("es")
5. FuncionNext    : races/[id]/layout -> getRace("1102") (React.cache)
6. FuncionNext    -> DataCache      GET /races/1102 (revalidate 3600)
7a. DataCache     --> FuncionNext   HIT (dato < 1 h)            [camino rápido]
7b. DataCache     -> APIRender      MISS/caducado: GET /races/1102
8.  APIRender     : CORS -> GZip -> DataCacheMiddleware (ETag W/"35677c2df776-…")
9.  APIRender     -> DuckDB         cursor.execute(sql, params)  [threadpool]
10. DuckDB        --> APIRender     filas -> list[dict] -> Pydantic RaceDetail
11. APIRender     --> DataCache     200 JSON gzip + ETag + Cache-Control
12. FuncionNext   : en paralelo (Promise.all) /seasons/2024, /races/1102/laps, /races/1102/results;
                    SiteFooter pide /health (mismo camino 6-11, sin ETag)
13. FuncionNext   : render RSC (servidor) + props serializadas para LapTimesChart/ViolinChart
14. FuncionNext   --> VercelEdge    HTML (~497 KB) no-store
15. VercelEdge    --> Navegador     HTML; hidratación; ECharts (SVG) dibuja en el cliente
```

## 6. Medidas reales

### 6.1. Tamaño del código y superficie

| Métrica | Valor |
|---|---|
| Ficheros versionados | 218 |
| Líneas API (`api/app`) | 1 799 en 16 ficheros (7 *routers*) |
| Líneas web (`src/app` + `components` + `lib` + diccionarios) | 2 661 + 1 821 + 164 + 676 = 5 322 (más 6 529 generadas: `openapi.json`, `schema.d.ts`) |
| Líneas ingesta / dbt / scripts / workflows | 740 / 3 217 / 237 / 311 |
| *Endpoints* | 28 `GET` (33 esquemas en OpenAPI) |
| Rutas web | 16 páginas × 2 idiomas + `error`/`not-found` + 2 *layouts* |
| Componentes | 23 ficheros (12 generales + 11 de gráficos) |
| Pruebas Python | 40 (30 API + 10 ingesta), todas correctas en 2,4 s |
| Pruebas e2e | 38 ejecuciones (32 de escritorio + 6 móvil) |

### 6.2. Tiempos de respuesta de la API desplegada

Medidos con `curl` desde España (vía Cloudflare MAD) el 28-09-2026 23:25 UTC. **No hubo *cold
start***: la instancia estaba despierta (la primera petición a `/health` tardó 171 ms). Tres rondas:

| Petición | TTFB (s) r1 / r2 / r3 | Tamaño JSON | Tamaño gzip |
|---|---|---:|---:|
| `/health` | 0,102 / 0,108 / 0,094 | — | 205 B |
| `/seasons` | 0,171 / 0,118 / 0,116 | 12 952 B | 1 367 B |
| `/races/1102/laps` | 0,304 / 0,348 / 0,317 | 465 464 B | 27 401 B |
| `/rankings/drivers?order_by=wins&season_from=2000` | 0,130 / 0,299 / 0,133 | — | 2 461 B* |
| `/drivers/lewis-hamilton` | 0,095 / 0,119 / 0,100 | — | — |
| `/races/1102/telemetry?drivers=max-verstappen,charles-leclerc` | 0,118 | 59 141 B | 23 478 B |
| `/seasons` con `If-None-Match` vigente | 0,096 → **304** | 0 | 0 |

\* sin filtro de temporada. Cabeceras observadas en `/seasons`: `Cache-Control: public,
max-age=600, stale-while-revalidate=86400`, `Content-Encoding: gzip`, `etag:
W/"35677c2df776-7b5df41fd06336e7"`, `vary: Accept-Encoding, Origin`, `Server: cloudflare`,
`cf-cache-status: DYNAMIC` (Cloudflare **no** cachea), `x-render-origin-server: uvicorn`. CORS: con
`Origin: https://f1-data-platform.vercel.app` responde `access-control-allow-origin`; con un origen
ajeno no. `/docs` público (200). `/races/999999` → 404.

El *cold start* no se pudo observar en esta sesión; por diseño incluye arrancar el contenedor,
descargar 52 MB de GitHub, calcular su SHA-256 y abrir DuckDB (el `HEALTHCHECK` concede 120 s de
`start-period`), por lo que cabe esperar decenas de segundos.

### 6.3. Tiempos de la web desplegada

| URL | TTFB (s) | Total (s) | HTML |
|---|---:|---:|---:|
| `/` | 0,679 | 0,679 | 307 → `/es` |
| `/es` | 1,470 / 1,308 | 1,799 / 1,485 | 413 731 B |
| `/es/seasons/2021` | 0,421 | 0,524 | 181 345 B |
| `/es/races/1102/pace` | 0,559 | 0,825 | 497 443 B |
| `/es/drivers/lewis-hamilton` | 0,323 | 0,347 | 136 511 B |
| `/es/records` | 0,298 | 0,322 | 144 764 B |

Todas `X-Vercel-Cache: MISS`, `Cache-Control: private, no-store`, función en `iad1`.

## 7. Debilidades y propuestas de mejora

### 7.1. API

| # | Debilidad observada | Propuesta concreta | Justificación |
|---|---|---|---|
| A1 | **Cold start del plan gratuito de Render**: tras ~15 min sin tráfico la instancia se detiene; al volver hay que arrancar el contenedor y descargar/verificar 52 MB antes de responder. Si Next recibe un error, la página muestra `error.tsx`. | (a) Plan de pago mínimo (instancia siempre activa) o (b) hornear la base en la imagen/usar un disco persistente para no descargarla en cada arranque; (c) un *ping* de disponibilidad (p. ej. cada 10 min) que además sirva de monitorización; (d) en Next, `timeout` + reintento y servir la última respuesta en caché. | La web depende en tiempo real de la API; con la Data Cache de Next el impacto se limita a las páginas no cacheadas, pero la primera visita tras un periodo inactivo es lenta o falla. |
| A2 | **Refresco con retraso de hasta 6 h** y reloj que se reinicia en cada arranque (el bucle duerme antes de la primera comprobación). | Endpoint `POST /admin/refresh` protegido con un secreto (o un *deploy hook* de Render) que el `pipeline.yml` invoque tras publicar la release; mantener el sondeo como respaldo. | Reduce la latencia de datos a minutos y hace el comportamiento determinista. |
| A3 | **Sin versionado de la API** (rutas en la raíz; `version="1.0.0"` solo informativo). | Prefijo `/v1` (con `APIRouter(prefix="/v1")` y redirección de las rutas actuales) y política de *deprecación* con cabecera `Deprecation`/`Sunset`. | Permite evolucionar esquemas sin romper a terceros; hoy la única garantía es el tipado de la propia web. |
| A4 | **Observabilidad mínima**: `logging.basicConfig` en texto, sin identificador de petición, sin métricas ni trazas; los logs del plan gratuito tienen retención corta. | Logs JSON con `request_id`, ruta, estado, duración y versión de datos; métricas Prometheus (`/metrics`) o OpenTelemetry → Grafana Cloud/Honeycomb gratuitos; Sentry para excepciones; cabecera `Server-Timing` con el tiempo de consulta. | Sin ello no se puede medir el *cold start*, ni detectar consultas lentas (p. ej. `/rankings` con rangos amplios) ni fallos del refresco (que solo se registran). |
| A5 | **Sin limitación de tasa** en una API pública con consultas costosas (`/races/{id}/laps` devuelve 465 KB; `/rankings` agrega todos los resultados). | `slowapi` (limitador por IP) o reglas de Cloudflare/Render; límites más estrictos en `/rankings`; *timeout* de consulta en DuckDB. | Una instancia gratuita (0,1 CPU, 512 MB) se satura con pocas peticiones concurrentes. |
| A6 | **La caché CDN no se aprovecha**: la respuesta lleva `Cache-Control: public` pero Cloudflare de Render responde `cf-cache-status: DYNAMIC`. | Poner un dominio propio en Cloudflare con *Cache Rules* para `GET` (respetando `Vary`) o servir la API detrás de Vercel/Cloudflare Workers; añadir `s-maxage`. | Con datos que cambian una vez a la semana, casi el 100 % de las peticiones serían aciertos de caché y la API apenas trabajaría (mitiga A1 y A5). |
| A7 | Middleware de caché basado en `BaseHTTPMiddleware` (coste por petición y problemas conocidos con *streaming*); ETag calculada sobre la *query* sin normalizar (`?a=1&b=2` ≠ `?b=2&a=1`). | Middleware ASGI puro; normalizar los parámetros ordenándolos antes del hash. | Más rendimiento y mayor tasa de 304. |
| A8 | Pruebas sobre un *fixture* de 2021-2024: no cubren casos históricos (coches compartidos de los 50, temporadas sin constructores antes de 1958) ni el contrato real frente a la base publicada. | Tests de contrato/propiedades con **Schemathesis** sobre `openapi.json` contra la base publicada en el job `api-image`; *snapshot tests* de respuestas clave. | Detecta respuestas que no cumplen el esquema (p. ej. `None` en un campo no opcional) con datos reales. |
| A9 | `/docs` y `/openapi.json` públicos, CORS abierto solo a la web; sin cabeceras de seguridad. | Mantener `/docs` (útil para divulgación) pero añadir `X-Content-Type-Options: nosniff` y documentar la política de uso; fijar la imagen base por *digest*. | Endurecimiento básico con coste nulo. |

### 7.2. Web

| # | Debilidad | Propuesta | Justificación |
|---|---|---|---|
| W1 | **Región de funciones en iad1 (EE. UU.)** mientras la API está en Frankfurt: cada llamada no cacheada cruza el Atlántico dos veces; `/es` hace 5-6 llamadas y tarda 1,3-1,5 s de TTFB. | Fijar la región de funciones en `fra1` (ajuste del proyecto en Vercel o `vercel.json` con `"regions": ["fra1"]`). | Cambio de una línea que reduce la latencia de cada fallo de caché en ~100-200 ms por ida y vuelta. |
| W2 | **Ninguna página se cachea en el CDN** (`no-store`, `MISS`): leer `searchParams` o parámetros dinámicos sin `generateStaticParams` fuerza el renderizado por petición pese a `revalidate = 3600`. | Separar las páginas sin filtros (fichas de piloto/constructor, temporadas, pestañas de carrera) para renderizarlas con ISR (`generateStaticParams` para temporadas recientes + `dynamicParams`), o activar *Cache Components*/PPR de Next 16 con `"use cache"` y `cacheLife`. Mover los filtros a componentes que no invaliden la página entera. | Los datos cambian semanalmente: servir HTML estático desde el CDN eliminaría casi toda la latencia y el consumo de funciones. |
| W3 | **HTML muy pesado** (hasta 497 KB en `pace`, 414 KB en inicio) porque las series completas se serializan como *props* de componentes cliente además de las tablas alternativas. | Reducir los datos enviados a los gráficos (solo columnas necesarias, submuestreo), cargar las tablas `<details>` bajo demanda o generar en servidor los gráficos más simples como SVG. | Mejora LCP/INP en móvil y el consumo de datos. |
| W4 | **Invalidación de caché desacoplada**: la web puede mostrar datos de hasta 1 h tras cambiar la API. | Usar `next: { tags: ["f1-data"] }` y un *route handler* `POST /api/revalidate` (con secreto) que llame a `revalidateTag`; invocarlo desde el pipeline tras A2. | Publicación de datos coherente en toda la cadena. |
| W5 | `next.config.ts` vacío: `X-Powered-By: Next.js` expuesto, sin CSP ni `Referrer-Policy`/`Permissions-Policy`. | `poweredByHeader: false` y `headers()` con CSP estricta (ECharts en SVG no necesita `unsafe-eval`). | Endurecimiento básico; Vercel ya aporta HSTS. |
| W6 | Resiliencia ante la API: `apiGet` no tiene *timeout* ni reintento; un *cold start* largo acaba en `error.tsx`. | `AbortSignal.timeout()` + un reintento con espera; mensaje de «despertando el servicio» en `error.tsx`. | Complementa A1. |
| W7 | SEO/i18n: no se declaran `alternates.languages` (`hreflang`) ni `sitemap.ts`/`robots.ts`; la elección de idioma no se recuerda (solo `Accept-Language`). | `generateMetadata` con `alternates`, `app/sitemap.ts`, cookie `NEXT_LOCALE` leída en `proxy.ts`. | Indexación correcta de las dos versiones y mejor experiencia. |
| W8 | Sin pruebas unitarias de `src/lib` (formato de tiempos, `driverCode`, `parseYear`) ni *visual regression*. | Vitest para `lib/` y *snapshots* visuales de Playwright para los gráficos. | Errores de formato de tiempos son difíciles de detectar con axe/e2e. |

### 7.3. CI/CD

| # | Debilidad | Propuesta | Justificación |
|---|---|---|---|
| C1 | **Acciones sobre Node 20 en retirada**: `actions/upload-artifact@v4`, `astral-sh/setup-uv@v6`, `actions/upload-pages-artifact@v3`, `actions/deploy-pages@v4` (GitHub ya avisa de la deprecación del *runtime* Node 20). | Actualizar a las versiones mayores con Node 24 (`upload-artifact@v5`+, `setup-uv@v7`, etc.) y fijar por SHA. | Evita que los workflows empiecen a fallar cuando GitHub retire Node 20. |
| C2 | **Sin Dependabot/Renovate** ni auditoría de dependencias (`uv.lock`, `package-lock.json`, acciones, imagen Docker). | `.github/dependabot.yml` con ecosistemas `uv`, `npm`, `github-actions` y `docker`, agrupando actualizaciones menores; `npm audit`/`pip-audit` en CI; CodeQL. | Mantenimiento de seguridad automatizado. |
| C3 | **Deriva de herramientas**: pre-commit fija ruff 0.8.4 pero la CI usa ruff 0.16.9 del lock. | Hook `local` que ejecute `uv run ruff`, o actualizar `rev` con `pre-commit autoupdate` (Dependabot no lo cubre). | Lo que pasa en local debe pasar en CI. |
| C4 | **Despliegues sin puerta de calidad**: Render y Vercel despliegan en el push aunque la CI falle (el 28-09 hubo dos pushes con la CI en rojo; con la configuración actual nada impide que se desplieguen). | Render: `autoDeploy: false` + *deploy hook* llamado desde un job `deploy` con `needs: [python, api-image]`; Vercel: *Required checks*/«Ignored Build Step» o despliegue con `vercel deploy --prebuilt` desde Actions. | Evita publicar una versión rota. |
| C5 | Doble construcción de la imagen (CI y Render) y ninguna se versiona. | Publicar la imagen en GHCR desde CI (etiqueta = SHA) y desplegar esa imagen en Render (`image:` en lugar de `dockerfilePath`). | Lo probado es exactamente lo desplegado; despliegues más rápidos. |
| C6 | Las pruebas e2e dependen de la release `data-latest` viva (no reproducibles en el tiempo) y el pipeline no verifica el despliegue tras publicar. | E2E en PR contra la base fijada por `manifest` (guardar el SHA); tras publicar, un paso de *smoke test* contra la API/web de producción (`BASE_URL`, ya soportado por `playwright.config.ts`). | Separar fallos de código de cambios de datos y detectar regresiones en producción. |
| C7 | Los workflows programados de un repo público se desactivan tras 60 días sin actividad (lo avisa el README). | Monitorizar con una alerta (p. ej. `/health` → `generated_at` con antigüedad > 8 días) o *keepalive*. | Evita que la plataforma deje de actualizarse en silencio. |

### 7.4. Infraestructura

- **Punto único de fallo**: una única instancia gratuita (0,1 CPU/512 MB) sin réplicas. Alternativas
  de bajo coste: servir los Parquet/DuckDB estáticos y consultar con DuckDB-WASM, o desplegar la API
  en una plataforma con *scale-to-zero* rápido (Fly.io, Cloud Run) con la base dentro de la imagen.
- **Almacenamiento efímero**: `/data` se pierde en cada reinicio; un disco persistente o una capa de
  imagen con los datos evitaría descargas repetidas (y el consumo de ancho de banda de GitHub).
- **Latencia geográfica**: alinear Render (Frankfurt) y Vercel (`fra1`) y poner una CDN delante de
  la API (A6, W1, W2).
- **Seguridad de la cadena de suministro**: verificación SHA-256 de la base ya implementada (bien);
  faltaría firmar el manifiesto o usar *artifact attestations* de GitHub para que la API compruebe
  que la release la generó el workflow del repositorio.
- **Monitorización externa**: un comprobador de disponibilidad (UptimeRobot/Better Stack) sobre
  `/health` y la web, con alerta si `data.generated_at` supera 8 días.

## 8. Resumen

La aplicación sigue una arquitectura de tres capas muy desacoplada: los datos se publican como
artefacto inmutable y verificado (release `data-latest`), la API es un servicio sin estado de solo
lectura sobre DuckDB con intercambio en caliente de versiones y caché HTTP por versión, y la web es
un cliente de servidor tipado extremo a extremo (OpenAPI → TypeScript, comprobado en CI) con un nivel
de accesibilidad verificado automáticamente (axe WCAG 2.2 AA en 21 URL, tema oscuro, sin JS). Los
puntos débiles son operativos más que de diseño: *cold start* y recursos del plan gratuito, ninguna
capa de caché CDN efectiva (ni en la API ni en la web), funciones de Vercel en otra región que la
API, despliegues no condicionados a la CI, acciones en Node 20 y ausencia de observabilidad y de
actualización automática de dependencias.
