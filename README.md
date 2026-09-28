# F1 Data Platform

Evolución del Trabajo Fin de Grado *«Formula 1 Dashboard»* (Antonio Sánchez de la Blanca Romero,
ESI – UCLM, 2024) desde un informe de Power BI hacia una **plataforma de datos completa**:
ingesta automatizada, modelo dimensional versionado y probado, API y web pública accesible.

```
F1DB (release GitHub, SQLite) ─┐
FastF1 (vueltas, neumáticos,   ├─► ingestion/ ─► data/bronze (Parquet)
  telemetría 2018+)           ─┤                      │
CSV históricos del TFG        ─┘        transform/ (dbt + DuckDB)
                                                       ▼
                               silver (staging, correcciones, cruces)
                                                       ▼
                               gold (dimensiones + hechos + métricas) ─► data/gold/f1.duckdb
                                                       ▼
                                         api/ (FastAPI) ─► web/ (Next.js)
```

## Estado

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Repositorio, entorno `uv`, lint | ✅ |
| 1 | Ingesta a bronze (F1DB, FastF1, histórico) | ✅ |
| 2 | Modelo dbt silver/gold, métricas y tests de calidad | ✅ |
| 3 | Orquestación con GitHub Actions | ⏳ |
| 4 | API FastAPI | ⏳ |
| 5 | Web Next.js accesible | ⏳ |
| 6 | Despliegue y analítica avanzada | ⏳ |

## Puesta en marcha

Requisitos: [uv](https://docs.astral.sh/uv/) (instala Python 3.12 automáticamente).

```bash
uv sync

# 1. Ingesta (bronze)
uv run f1-ingest f1db                                  # última release de F1DB
uv run f1-ingest fastf1 --season 2024 2025 --telemetry # vueltas, neumáticos y telemetría
uv run f1-ingest legacy                                # CSV del TFG (carga única)
uv run f1-ingest ergast                                # volcado Ergast, solo validación (carga única)

# 2. Transformación (silver + gold) y tests
mkdir -p data/gold
cd transform
DBT_PROFILES_DIR=. uv run dbt build
DBT_PROFILES_DIR=. uv run dbt docs generate && DBT_PROFILES_DIR=. uv run dbt docs serve
```

Todas las cargas son **idempotentes**: cada carrera se guarda en su propio Parquet
(`bronze/fastf1/laps/season=2024/round=01.parquet`) y volver a ejecutar reemplaza, nunca duplica.
FastF1 limita a 500 peticiones/hora: si se alcanza el límite, el comando se detiene limpiamente y la
siguiente ejecución continúa donde lo dejó.

## Fuentes de datos

| Fuente | Cobertura | Uso |
|---|---|---|
| [F1DB](https://github.com/f1db/f1db) | 1950 – actualidad | Resultados, clasificación, paradas, campeonatos, pilotos, equipos, circuitos |
| formula1db.com (scraping del TFG) | 1950 – 2024 | **Fuente principal de las vueltas**: tiempo, posición, sectores, compuesto real, entradas a boxes |
| [FastF1](https://docs.fastf1.dev) | 2018 – actualidad | Completa las vueltas (stint, vida del neumático, speed trap, estado de pista), telemetría y las carreras posteriores a 2024 |
| Ergast (volcado de 2022 del TFG) | 1996 – 2022 | **Solo validación**: tercera fuente para contrastar las vueltas históricas |

Prioridad cuando las fuentes discrepan: F1DB y formula1db.com (si está claro que son mejores),
después FastF1 y, por último, Ergast. Los empates se resuelven con documentos oficiales de la FIA o,
en su defecto, con Stats F1 (ver `docs/revision_divergencias/`).

Los scripts de Selenium del TFG (`../FORMULA 1 DB/*.py`) dejan de usarse: dependían de XPaths y
clases CSS que cambian con la web. Sus datos se conservan como carga histórica.

## Modelo de datos (capa gold)

Reproduce el esquema en constelación de la memoria (Fig. 5.7):

- **Dimensiones**: `dim_driver`, `dim_race` (con circuito y Gran Premio desnormalizados),
  `dim_constructor`, `dim_engine_manufacturer`, `dim_tyre_manufacturer`.
- **Hechos**: `fact_race_result` (carrera y sprint), `fact_qualifying_result`, `fact_pit_stops`,
  `fact_laptimes`, `fact_driver_standing`, `fact_constructor_standing`, y dos nuevos:
  `fact_quali_telemetry` y `fact_pit_lane_passes` (todas las entradas al pit lane, tipificadas).
- **Métricas** (medidas DAX del TFG en SQL): `agg_driver_career`, `agg_constructor_career`,
  `agg_driver_season`, `agg_teammate_h2h`.

El catálogo completo con descripciones y linaje se genera con `dbt docs`.

## Calidad de datos

Las fuentes se solapan, así que cada dato se contrasta con al menos otra fuente cuando es posible.
Los contrastes se materializan en el esquema `quality` y `quality.qa_summary` resume cada uno con
su umbral; `dbt build` falla si alguno baja del mínimo (`assert_quality_thresholds`).

| Contraste | Concordancia |
|---|---|
| Totales de pilotos y constructores (títulos, victorias, podios, poles, vueltas rápidas) calculados vs. oficiales de F1DB | 100 % |
| Resultados FastF1 vs. F1DB (posición, puntos) | 100 % |
| Parrilla y Q1/Q2/Q3 FastF1 vs. F1DB (las diferencias restantes son errores de FastF1 contrastados con la FIA) | 99,2 % / 99,9 % |
| Tiempos por vuelta formula1db.com vs. Ergast (1996–2022, 525 000 vueltas) | 99,86 % |
| Tiempos por vuelta formula1db.com vs. FastF1 (2018–2024; FastF1 es la que se desvía) | 99,3 % |
| Vuelta rápida de cada piloto vs. oficial de F1DB | 99,1 – 99,2 % |
| Pilotos con todas sus vueltas oficiales registradas | 99,45 % (formula1db) / 100 % (FastF1) |
| Paradas de F1DB con su entrada a boxes en las vueltas | 99,8 % |

Decisiones y correcciones aplicadas (revisión de divergencias de 2026, con evidencia en
`docs/revision_divergencias/`):

- **Fusión de vueltas** (`int_laptimes`): formula1db.com es la fuente principal y FastF1 la completa.
  Cada vuelta lleva `source`, `validation_status` (`confirmed`, `timing_convention`, `disputed`,
  `corrected`, `single_source`), `confirmed_by` y `corrections`, y conserva los valores originales.
- **Correcciones de F1DB con evidencia** (seed `race_data_overrides`, generado por
  `scripts/generate_override_seed.py`): 72 cifras de vueltas completadas y 97 números de vuelta
  rápida (Stats F1), 5 parrillas, Brasil 2018 y un tiempo de Q3 (documentos de la FIA). Solo se
  aplican si F1DB mantiene el valor revisado; `assert_overrides_still_apply` avisa si cambia.
- **Correcciones de vueltas** (seed `lap_corrections`): la sanción de Russell que formula1db sumó a
  su vuelta 1 en Qatar 2024; las posiciones de la carrera se recalculan con el tiempo corregido.
  Además, si FastF1 y Ergast coinciden entre sí contra formula1db, se toma su valor (49 posiciones).
- **Rondas mal etiquetadas en el scraping**: desde 2023-R7 los datos de formula1db.com estaban
  desplazados una ronda. Cada carrera se asigna por su contenido (`int_formula1db_race_alignment`).
- **Pilotos de formula1db.com**: se identifican por nombre normalizado antes que por dorsal (en los
  coches compartidos de los años 50 el dorsal es del coche).
- **Carreras con resultado a una vuelta anterior** (China 2014, Canadá 2018): se eliminan las vueltas
  corridas después del final oficial.
- **Numeración de vueltas** (`int_lap_numbering`): en San Marino, España y Japón 1994 y Bélgica 2001
  las paradas o vueltas rápidas de F1DB usan otra numeración; se marcan (`lap_numbering_status`).
- **Neumáticos**: se guardan el compuesto real de Pirelli y el relativo de cada carrera
  (`int_tyre_compound_mapping`).
- **Paradas**: `fact_pit_stops` son las paradas reales de F1DB (coinciden con la FIA);
  `fact_pit_lane_passes` tipifica el resto de entradas (Safety Car, bandera roja, retirada...).
- **Vuelta de abandono**: FastF1 registra la vuelta incompleta en la que se retira un piloto; se marca
  con `is_incomplete_lap`.
- **Limitaciones de la fuente** (no corregibles, marcadas en `fact_laptimes.quality_status`):
  coches compartidos de los años 50, carreras en dos mangas (Francia 1981) y gráficos de vueltas
  incompletos anteriores a 1960.
- **Correcciones de `Script-2.sql`**: 28 de 34 ya están en F1DB; de las 6 restantes, 4 se aplican
  desde un seed y 2 se retiraron por falta de evidencia.

## Estructura

```
ingestion/   cargadores Python y CLI `f1-ingest`
transform/   proyecto dbt (staging → intermediate → marts) con seeds y tests
api/         (fase 4) FastAPI sobre data/gold/f1.duckdb
web/         (fase 5) Next.js
tests/       tests unitarios de la ingesta (pytest)
data/        bronze/, gold/, cache/ — no se versiona, se regenera con el pipeline
```
