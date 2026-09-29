# 04 — Arquitectura de datos de «f1-data-platform»

> Nota de trabajo para el informe de situación. Estado verificado el 29/09/2026 sobre el
> repositorio (`HEAD = cceddd3`), el almacén local `data/gold/f1.duckdb` (último `dbt build`
> correcto el 28/09/2026 a las 19:18 UTC, 21,7 s) y el snapshot `dist/` (manifiesto del
> 28/09/2026 19:23 UTC). Todas las cifras proceden de consultas de solo lectura sobre esos
> ficheros. Los bloques `diagrama` están pensados para convertirse después en TikZ.

## 0. Visión general

La plataforma sigue una **arquitectura medallón** (bronze → silver → gold) implementada con
Python (ingesta), **DuckDB** como motor y almacén analítico y **dbt-core 1.12.5 + dbt-duckdb**
como herramienta de transformación y pruebas. Sobre la capa gold se añaden un esquema `quality`
(conciliación entre fuentes) y un proceso de exportación («snapshot») que publica los datos en
la GitHub Release `data-latest`, de la que se alimenta la API FastAPI (y, a través de ella, la web
Next.js).

| Capa | Ubicación física | Formato | Quién la escribe | Contenido |
|---|---|---|---|---|
| raw | `data/raw/f1db/<tag>/f1db.db` | SQLite | `f1db_loader.download_sqlite` | Base de datos F1DB descargada (73,7 MB, `v2026.15.1`) |
| caché | `data/cache/fastf1/` | caché HTTP de FastF1 | biblioteca `fastf1` | Respuestas de la API de F1 Live Timing (≈4,5 GB, no se publica) |
| bronze | `data/bronze/{f1db,fastf1,formula1db,ergast}/` | Parquet + `_metadata.json` | `f1-ingest` | Copia fiel de cada fuente, sin reglas de negocio (≈68 MB) |
| silver | esquema `silver` de `data/gold/f1.duckdb` | vistas (staging) y tablas (intermediate, seeds) | dbt | Tipado, renombrado, claves comunes, fusión y corrección de fuentes |
| gold | esquema `gold` del mismo fichero | tablas | dbt | Modelo dimensional en constelación (5 dimensiones, 8 hechos, 4 agregados) |
| quality | esquema `quality` | tablas | dbt | 6 modelos de contraste entre fuentes + `qa_summary` (40 comprobaciones) |
| distribución | `dist/` → Release `data-latest` | `.tar.gz`, `.duckdb`, `.zip`, `.json` | `f1-ingest snapshot pack` | Entrada de la próxima ejecución y datos que sirve la API |

El almacén de trabajo (`data/gold/f1.duckdb`, 238 MB) contiene los tres esquemas: `silver`
(20 vistas + 14 tablas), `gold` (17 tablas) y `quality` (7 tablas). La base que se publica
(`dist/f1.duckdb`, 54,5 MB) solo contiene `gold.*` y `quality.qa_summary`.

### 0.1 Inventario del proyecto dbt (según `transform/target/manifest.json`)

| Tipo de nodo | Nº | Detalle |
|---|---|---|
| Sources | 22 tablas | f1db (13), fastf1 (4), formula1db (2), ergast (3) |
| Modelos staging | 20 | 14 f1db, 4 fastf1, 1 formula1db, 1 ergast (vistas en `silver`) |
| Modelos intermediate | 10 | `int_*` |
| Modelos marts | 17 | 13 en `marts/core` (5 dim + 8 fact) y 4 en `marts/metrics` (`agg_*`) |
| Modelos quality | 7 | 6 `qa_*` + `qa_summary` |
| Seeds | 3 | `race_data_overrides`, `race_data_corrections`, `lap_corrections` |
| Tests de datos | 50 | 13 `not_null`, 10 `relationships`, 9 `accepted_values`, 6 `unique`, 5 `unique_combination` (genérico propio), 7 singulares |
| Unit tests | 4 | en `models/quality/_quality__models.yml` |
| Macros | 3 | `generate_schema_name`, `normalize_name`, `parse_duration_ms` |

> Nota de recuento: en `silver` hay exactamente 20 vistas `stg_*` (14 de F1DB, 4 de FastF1,
> 1 de formula1db y 1 de Ergast); el total de modelos es 20 + 10 + 17 + 7 = **54**, que coincide
> con los 54 `model: success` de `run_results.json`.

Resultado del último `dbt build` (`transform/target/run_results.json`): 54 modelos `success`,
3 seeds `success`, 50 tests `pass` (incluidos los 3 de severidad `warn`, sin avisos) y 4 unit tests
`pass`.

---

## 1. Datos en bruto y capa BRONZE (`ingestion/`)

El paquete `ingestion` sustituye a los scripts manuales del TFG (descarga manual de F1DB, Selenium
contra formula1db.com, `fastf1-main.py` y `fastf1-telemetry.py` que escribían CSV en modo
*append*). Se instala como *script* de consola `f1-ingest = "ingestion.cli:main"`
(`pyproject.toml`) y sus dependencias van en el grupo `ingest` (`fastf1>=3.4`, `pandas>=2.2`,
`pyarrow>=17`, `requests>=2.32`); la base común del proyecto es solo `duckdb>=1.1`.

Principios comunes a todos los cargadores:

- **Bronze = copia fiel**: no se aplican reglas de negocio; solo cambios de formato (SQLite/CSV →
  Parquet, `timedelta` → milisegundos enteros, nombres de columna en `snake_case` para los CSV del
  TFG, eliminación de duplicados exactos).
- **Idempotencia**: volver a ejecutar una carga reemplaza ficheros, nunca añade filas.
- **Escritura atómica**: se escribe en un temporal (`*.tmp`) y se renombra (`os.replace` o
  renombrado de directorio), de modo que bronze nunca queda a medio escribir.
- **Metadatos**: cada fuente de carga completa deja un `_metadata.json` con `loaded_at` (UTC) y el
  recuento de filas por tabla.

### 1.1 `config.py` — rutas y constantes

| Constante | Valor | Uso |
|---|---|---|
| `PROJECT_ROOT` | raíz del repositorio | base de rutas |
| `DATA_DIR` | `$F1_DATA_DIR` o `<raíz>/data` | permite redirigir los datos (tests, CI) |
| `RAW_DIR`, `BRONZE_DIR`, `CACHE_DIR` | `data/raw`, `data/bronze`, `data/cache` | capas físicas |
| `F1DB_REPO`, `F1DB_ASSET` | `f1db/f1db`, `f1db-sqlite.zip` | release de GitHub que se descarga |
| `FASTF1_FIRST_SEASON` | `2018` | primera temporada con cronometraje completo en FastF1 |
| `LEGACY_CSV_DIR` | `<raíz>/../FORMULA 1 DB` | CSV del scraping del TFG (fuera del repo) |

### 1.2 `io.py` — utilidades de escritura

| Función | Qué hace |
|---|---|
| `write_parquet(df, path)` | Crea el directorio, escribe `path.parquet.tmp` con `df.to_parquet(index=False)` y lo mueve con `os.replace` (atómico). Garantiza que recargar una carrera sobrescribe su fichero. |
| `write_metadata(directory, **fields)` | Escribe `_metadata.json` con `loaded_at` (ISO, UTC, precisión de segundos) más los campos recibidos (release, origen, recuentos). |
| `read_metadata(directory)` | Lee `_metadata.json` o devuelve `{}` si no existe (lo usa `f1db_loader` para decidir si hay release nueva y `snapshot` para el manifiesto). |

### 1.3 `f1db_loader.py` — F1DB (fuente principal de resultados)

F1DB es una base de datos abierta (CC BY 4.0) que se publica en releases de GitHub tras cada Gran
Premio.

| Función | Qué hace |
|---|---|
| `latest_release()` | `GET https://api.github.com/repos/f1db/f1db/releases/latest` (con `Authorization: Bearer $GITHUB_TOKEN` si existe, para no agotar el límite anónimo). Devuelve `tag`, `published_at` y la URL del asset `f1db-sqlite.zip`. |
| `download_sqlite(release)` | Si `data/raw/f1db/<tag>/f1db.db` ya existe no descarga nada (idempotencia por versión). Si no, descarga el zip en *streaming* (bloques de 1 MiB, timeout 120 s), extrae `f1db.db` y borra el zip. |
| `export_tables(db_path, out_dir)` | Abre DuckDB en memoria, `INSTALL/LOAD sqlite`, adjunta la base en `READ_ONLY` y, para cada **tabla** (no las vistas, que F1DB deriva de `race_data`), ejecuta `COPY (SELECT * FROM src.<tabla>) TO '<tabla>.parquet' (FORMAT parquet)`, respetando los tipos declarados en SQLite. Escribe en `f1db.tmp/` y después sustituye el directorio completo (reemplazo atómico). Devuelve el recuento de filas por tabla. |
| `load(force=False)` | Orquesta: si el `release` de `_metadata.json` coincide con el último tag y no hay `--force`, termina sin hacer nada; si no, descarga, exporta y escribe los metadatos (`release`, `published_at`, `tables`). |

Ficheros producidos: `data/raw/f1db/v2026.15.1/f1db.db` (73,7 MB) y
`data/bronze/f1db/*.parquet` (31 tablas, 5,1 MB en total) + `_metadata.json`
(`release = v2026.15.1`, publicada el 27/09/2026). Tablas y filas:

| Tabla | Filas | Tabla | Filas |
|---|---:|---|---:|
| `race_data` (71 columnas, 4,4 MB) | 187 675 | `season_entrant_driver` | 3 882 |
| `race_driver_standing` | 21 541 | `season_driver` | 3 416 |
| `race_constructor_standing` | 10 654 | `season_entrant_chassis` | 2 292 |
| `race` (47 columnas) | 1 172 | `season_entrant_engine` | 2 027 |
| `driver` (32 columnas) | 917 | `season_entrant_tyre_manufacturer` | 1 955 |
| `constructor` (22 columnas) | 187 | `season_entrant_constructor` | 1 925 |
| `season_driver_standing` | 1 681 | `season_entrant` | 1 799 |
| `season_constructor_standing` | 721 | `chassis` | 1 153 |
| `country` | 249 | `season_constructor` | 1 079 |
| `circuit` | 78 | `entrant` | 830 |
| `engine_manufacturer` | 78 | `season_engine_manufacturer` | 560 |
| `grand_prix` | 54 | `engine` | 424 |
| `tyre_manufacturer` | 9 | `constructor_chronology` | 217 |
| `season` | 77 | `circuit_layout` | 160 |
| `continent` | 7 | `season_tyre_manufacturer` | 160 |
| `driver_family_relationship` | 86 | | |

Solo 13 de las 31 tablas se declaran como *sources* de dbt (§2.2); el resto se conserva en bronze
por completitud (p. ej. chasis, inscripciones por temporada), pero hoy no alimenta el modelo.

### 1.4 `fastf1_loader.py` — FastF1 (cronometraje 2018+ y telemetría)

Carga **incremental por carrera** desde la API de F1 Live Timing a través de la biblioteca
`fastf1` (con caché local en `data/cache/fastf1`).

| Elemento | Qué hace |
|---|---|
| `LoadSummary` | *Dataclass* con listas `loaded`, `skipped`, `failed` y la marca `rate_limited`. |
| `race_path(kind, season, round)` | Ruta de partición estilo Hive: `data/bronze/fastf1/<kind>/season=YYYY/round=RR.parquet` (`kind` ∈ `laps`, `results`, `quali_results`, `quali_telemetry`). **Un fichero por carrera**. |
| `timedeltas_to_millis(df)` | Convierte cada columna `timedelta64` en `<col>_ms` (`Int64`, redondeado) y elimina la original (Parquet/DuckDB-friendly). |
| `downsample_by_distance(tel, step=10)` | Conserva la primera muestra de cada tramo de 10 m (`Distance // 10`), para no repetir los 364 MB del `quali_laps.csv` del TFG. |
| `_with_keys(df, event, season)` | Inserta al principio `season`, `round` y `event_name`. |
| `_load_race(event, season)` | Sesión `R`: `session.load(laps=True, telemetry=False, weather=False, messages=False)`; escribe `laps` y `results`. |
| `_load_qualifying(event, season, telemetry)` | Sesión `Q`: escribe `quali_results` (Q1/Q2/Q3). Con telemetría, para cada piloto toma `pick_fastest()`, obtiene `get_telemetry()`, submuestrea y guarda `Distance, Speed, RPM, nGear, Throttle, Brake, DRS, X, Y, Z` + `Driver`, `DriverNumber`, `Compound`, `LapTime_ms`. Un piloto sin datos solo genera un *warning*. |
| `completed_races(season)` | Calendario sin tests (`get_event_schedule`) filtrado a carreras cuya hora de inicio (`Session5DateUtc`) + **6 h** ya ha pasado (margen para que el cronometraje oficial esté publicado). |
| `load_season(season, rounds, telemetry, force)` | Rechaza temporadas < 2018; habilita la caché; por cada carrera calcula qué `kinds` faltan (o todos con `force`) y **solo descarga lo pendiente**; captura `RateLimitExceededError` (límite de 500 peticiones/hora) y marca `rate_limited` para que la próxima ejecución continúe donde se quedó; cualquier otro error se anota en `failed` sin detener la temporada. |

Ficheros producidos (45 MB en total):

| Directorio | Ficheros | Cobertura | Filas | Columnas |
|---|---:|---|---:|---:|
| `fastf1/laps/` | 187 | 2018 (20) · 2019 (21) · 2020 (17) · 2021–2023 (22 c/u) · 2024 (24) · 2025 (24) · 2026 (15) | 205 718 | 34 |
| `fastf1/results/` | 187 | ídem | 3 768 | 25 |
| `fastf1/quali_results/` | 187 | ídem | 3 769 | 25 |
| `fastf1/quali_telemetry/` | 63 | 2024 (24) · 2025 (24) · 2026 (15) | 518 699 | 17 |

FastF1 no escribe `_metadata.json`: la cobertura se deduce de las particiones (así lo hace
`snapshot.summarize`).

### 1.5 `legacy_loader.py` — formula1db.com (scraping del TFG, carga única)

Los scripts Selenium del TFG se retiran, pero sus CSV (tiempos por vuelta 1950–2024, que ninguna
otra fuente abierta cubre antes de 1996) se conservan.

| Función | Qué hace |
|---|---|
| `snake_case(name)` | Aplica `RENAMES` (`"+-" → positions_change`, `"No." → car_number`) y normaliza a minúsculas con `_`. |
| `clean(df)` | Renombra columnas y elimina **duplicados exactos** (los CSV se generaron con `mode="a"`); devuelve cuántos se quitaron. |
| `load(source_dir)` | Lee `f1_lap_times.csv`, `f1_race_entries.csv` y `f1_drivers.csv` **todo como texto** (`dtype=str`, `keep_default_na=False`) para no perder formatos como `1:39.019` o `-`; escribe `lap_times`, `race_entries`, `drivers` y `_metadata.json`. |

| Fichero bronze | Filas | Columnas | Tamaño | Duplicados eliminados |
|---|---:|---:|---:|---:|
| `formula1db/lap_times.parquet` | 1 252 550 | 17 (`season, round, car_number, driver_name, lap, rank, positions_change, time, gap, interval, tyre, tyre_age, status, lap_time, sector_1..3`) | 14,8 MB | 0 |
| `formula1db/race_entries.parquet` | 28 558 | 11 | 0,18 MB | 0 |
| `formula1db/drivers.parquet` | 1 051 | 6 | 0,06 MB | 0 |

Cobertura de `lap_times`: 1950–2024, 1 125 carreras (etiquetadas por temporada y ronda).

### 1.6 `ergast_loader.py` — Ergast (volcado de octubre de 2022, solo validación)

Ergast dejó de actualizarse; se usa como **tercera fuente independiente** de vueltas (1996–2022).
`load(zip_path)` abre `../ERGAST API/f1db_csv.zip`, lee `races, results, drivers, lap_times,
pit_stops, qualifying` con `na_values=["\\N"]`, escribe un Parquet por tabla y el
`_metadata.json`.

| Fichero | Filas | Columnas |
|---|---:|---:|
| `ergast/lap_times.parquet` | 535 748 | 6 |
| `ergast/results.parquet` | 25 800 | 18 |
| `ergast/races.parquet` | 1 079 | 18 |
| `ergast/pit_stops.parquet` | 9 559 | 7 |
| `ergast/qualifying.parquet` | 9 535 | 9 |
| `ergast/drivers.parquet` | 855 | 9 |

Solo `races`, `results` y `lap_times` se declaran como sources.

### 1.7 `snapshot.py` — empaquetado y restauración

Resuelve un problema de despliegue: GitHub Actions no tiene los CSV del TFG ni el histórico de
FastF1, así que cada ejecución **parte del último snapshot publicado** y publica el siguiente.

| Función | Qué hace |
|---|---|
| `sha256(path)` | Hash por bloques de 1 MiB (integridad en el manifiesto). |
| `pack_bronze(bronze_dir, out)` | Exige que existan las fuentes estáticas (`STATIC_SOURCES = ("formula1db", "ergast")`; sin ellas `dbt build` no puede ejecutarse) y crea `bronze.tar.gz` con rutas `bronze/...`, omitiendo `*.tmp`; escritura atómica. |
| `restore_bronze(archive, data_dir)` | Verifica que todos los miembros empiezan por `bronze/`, extrae con `filter="data"` (rechaza rutas absolutas, enlaces y escapes del directorio) y crea `data/gold/` (dbt crea la base pero no su carpeta). Devuelve las fuentes restauradas. |
| `build_api_database(warehouse, out)` | Crea una DuckDB nueva, adjunta el almacén en `read_only` y copia **todas las tablas de `gold`** y **`quality.qa_summary`** con `CREATE TABLE … AS SELECT`; `CHECKPOINT` final. Resultado compacto (54,5 MB frente a 238 MB). |
| `export_gold_parquet(database, out)` | Exporta cada tabla gold a Parquet con compresión ZSTD y las mete en `gold-parquet.zip` (modo `ZIP_STORED`, porque Parquet ya va comprimido). Pensado para Power BI u otras herramientas. |
| `summarize(database, bronze_dir)` | Datos del manifiesto: release de F1DB, carreras de FastF1 por temporada (recuento de particiones), última carrera completada (`gold.dim_race where is_completed order by race_date desc`) y recuento de estados de `quality.qa_summary`. |
| `pack(out_dir, …)` | Genera los tres ficheros y `manifest.json` (fecha, resumen, filas por tabla, bytes y SHA-256 de cada fichero). Falla si no existe `data/gold/f1.duckdb`. |
| `release_notes(manifest)` | Texto Markdown de la release (última carrera, versión F1DB, cobertura FastF1, estados de calidad, licencias). |

Snapshot actual (`dist/`, 28/09/2026): `bronze.tar.gz` 51,7 MB, `f1.duckdb` 54,5 MB,
`gold-parquet.zip` 28,1 MB, `manifest.json` 1,6 KB; última carrera 2026 R15 (Azerbaiyán);
calidad: 23 PASS y 17 INFO.

### 1.8 `cli.py` — la CLI `f1-ingest`

`argparse` con subcomandos; las importaciones son diferidas (FastF1 tarda en importarse) y la
salida se fuerza a UTF-8 (la consola de Windows usa cp1252).

| Comando | Efecto | Código de salida |
|---|---|---|
| `f1-ingest f1db [--force]` | `f1db_loader.load`; imprime los metadatos | 0 |
| `f1-ingest fastf1 --season 2025 2026 [--round 3 4] [--telemetry] [--force]` | `load_season` por temporada; resumen «cargadas / ya existentes / con error»; si hay *rate limit* se detiene y avisa de que la carga es reanudable | 1 si alguna carrera falla |
| `f1-ingest legacy [--path DIR]` | `legacy_loader.load` (carga única) | 0 |
| `f1-ingest ergast [--path ZIP]` | `ergast_loader.load` (carga única) | 0 |
| `f1-ingest snapshot pack [--out dist]` | `snapshot.pack`; imprime tamaños y hashes | 0 |
| `f1-ingest snapshot restore <bronze.tar.gz>` | `restore_bronze` | 0 |
| `f1-ingest snapshot notes <manifest.json>` | `release_notes` a stdout | 0 |

Pruebas unitarias en `tests/test_ingestion.py` (conversión de `timedelta`, submuestreo,
particionado, idempotencia de `write_parquet`, limpieza de duplicados) y `tests/test_snapshot.py`
(ida y vuelta pack/restore, contenido de la base de la API, fuentes estáticas obligatorias,
rechazo de archivos ajenos, notas de la release).

### 1.9 Resumen de fuentes

| Fuente | Tipo de acceso | Frecuencia | Cobertura | Papel en el modelo |
|---|---|---|---|---|
| F1DB | Release GitHub (SQLite) | tras cada GP | 1950–2026 | Fuente de verdad de resultados, clasificaciones, campeonatos, paradas y dimensiones |
| FastF1 | API Live Timing (biblioteca) | semanal, incremental | 2018–2026 | Vueltas 2025–2026 y pilotos ausentes; enriquece vueltas (stint, vida del neumático, speed trap, estado de pista); telemetría de clasificación (2024+); validación |
| formula1db.com | CSV del scraping del TFG | carga única | 1950–2024 | Fuente principal de tiempos por vuelta |
| Ergast | Volcado CSV oct. 2022 | carga única | 1996–2022 | Validación de vueltas y relleno puntual marcado |

---

## 2. Proyecto dbt (`transform/`) y capa SILVER

### 2.1 Configuración

- **`dbt_project.yml`**: proyecto `f1`, perfil `f1`. Materializaciones y esquemas por carpeta:

| Carpeta | Materialización | Esquema |
|---|---|---|
| `models/staging` | `view` | `silver` |
| `models/intermediate` | `table` | `silver` |
| `models/marts` | `table` | `gold` |
| `models/quality` | `table` | `quality` |
| `seeds` | tabla (seed) | `silver` |

- **`profiles.yml`**: un único target `dev`, `type: duckdb`,
  `path: {{ env_var('F1_DUCKDB_PATH', '../data/gold/f1.duckdb') }}`, `threads: 4`. Se invoca
  siempre con `--profiles-dir .` desde `transform/`.
- **Rutas de bronze**: las *sources* usan `meta.external_location` (funcionalidad de dbt-duckdb)
  con `{{ env_var('F1_BRONZE_DIR', '../data/bronze') }}`; así las vistas de staging leen los Parquet
  directamente, sin copiarlos al almacén. Consecuencia práctica: las vistas `stg_*` guardan rutas
  relativas y **solo se pueden consultar con el directorio de trabajo en `transform/`** (fuera de
  él fallan con «No files found»).

### 2.2 Sources (`models/staging/f1db/_f1db__sources.yml`)

| Source | Tablas declaradas | Ubicación |
|---|---|---|
| `f1db` | `race`, `race_data`, `race_driver_standing`, `race_constructor_standing`, `season_driver_standing`, `season_constructor_standing`, `driver`, `constructor`, `engine_manufacturer`, `tyre_manufacturer`, `grand_prix`, `circuit`, `country` | `…/f1db/{name}.parquet` |
| `fastf1` | `laps`, `results`, `quali_results`, `quali_telemetry` | `read_parquet('…/fastf1/<t>/*/*.parquet', hive_partitioning = false, union_by_name = true)` |
| `formula1db` | `lap_times`, `race_entries` | `…/formula1db/{name}.parquet` |
| `ergast` | `races`, `results`, `lap_times` | `…/ergast/{name}.parquet` |

En FastF1 se desactiva `hive_partitioning` porque `season` y `round` ya van dentro del fichero, y
`union_by_name` tolera cambios de esquema entre temporadas. `formula1db.race_entries` está
declarada pero ningún modelo la usa.

### 2.3 Macros (`transform/macros/`)

| Macro | Propósito | Implementación |
|---|---|---|
| `generate_schema_name` | Usar el esquema personalizado tal cual (`silver`, `gold`, `quality`) en lugar del prefijo por defecto `<target>_<schema>` | devuelve `custom_schema_name` o `target.schema` |
| `normalize_name(column)` | Nombre de persona comparable entre fuentes (p. ej. «José Froilán González» → «jose froilan gonzalez») | quita « Jr.», cambia `-` por espacio, `strip_accents`, `lower`, elimina todo lo que no sea `[a-z ]`, `trim` |
| `parse_duration_ms(column)` | Tiempos en texto (`1:39.019`, `42.414`, `1:02:03.5`) → milisegundos `bigint`; `NULL` para `-` o vacío | valida con `regexp_full_match('\d+(:\d{1,2})*(\.\d+)?')`, divide por `:` y acumula en base 60 con `list_reduce` |

### 2.4 Seeds (`transform/seeds/`, esquema `silver`)

Las seeds son el mecanismo de **corrección manual auditable**: cada fila lleva la decisión de la
revisión de divergencias de 2026 (`docs/revision_divergencias/INFORME.md`) y su evidencia, y solo
se aplica si el dato de origen sigue siendo el revisado (autodesactivación cuando la fuente lo
corrige).

| Seed | Filas | Columnas | Para qué sirve |
|---|---:|---|---|
| `race_data_corrections` | 4 | `race_id, session_type, match_driver_id, match_driver_number, match_position_display_order, set_driver_id, set_driver_number, note` | Correcciones heredadas de `Script-2.sql` del TFG sobre `race_data` (piloto o dorsal erróneo) que F1DB aún no ha corregido y que Stats F1 sostiene (se retiraron Leoni 1978 y Mónaco 1975, decisión N3). Las columnas `match_*` son condiciones (NULL = comodín); `set_*` son los valores nuevos. Ej.: GP 331, Lammers #9 → #10; GP 14, el #50 de Trintignant → Jean Behra. |
| `race_data_overrides` | 195 | `race_id, session_type, position_display_order, driver_id, column_name, f1db_value, corrected_value, action, decision, evidence` | Correcciones **celda a celda** con evidencia (FIA, Stats F1, formula1db, Ergast). `action = set` sustituye el valor; `action = flag` lo conserva y lo marca como disputado. Generada por `scripts/generate_override_seed.py` a partir de las hojas CSV de `docs/revision_divergencias`. Tests: `accepted_values` en `column_name` (10 columnas permitidas) y `action`, y `unique_combination(race_id, session_type, position_display_order, column_name)`. |
| `lap_corrections` | 1 | `race_id, driver_id, lap_number, column_name, original_value, corrected_value, decision, evidence` | Correcciones de vueltas concretas de formula1db.com (decisión A2). Hoy: GP 1124, Russell, vuelta 1: 120 631 → 115 631 ms (formula1db sumó a la vuelta 1 la sanción de 5 s). Si una carrera tiene alguna corrección, sus posiciones por vuelta se recalculan. |

Desglose de `race_data_overrides` por decisión:

| Decisión | Acción | Columna | Celdas |
|---|---|---|---:|
| A3 (vueltas completadas históricas) | set / flag | `race_laps` | 72 / 2 |
| A4 (vuelta de la vuelta rápida) | set | `fastest_lap_lap` | 97 |
| A5 (parrillas) | set | `race_grid_position_number` (5), `race_grid_position_text` (5), `race_positions_gained` (4) | 14 |
| N1 (orden de clasificación) | set | `position_display_order`, `position_number`, `position_text`, `race_positions_gained` | 8 |
| N2 (tiempo de Q3) | set | `qualifying_q3_millis`, `qualifying_gap_millis` | 2 |

No existe una seed de «mapeos» (compuestos, pilotos…): esas equivalencias se **calculan** en
modelos (`int_tyre_compound_mapping`, `int_driver_race_numbers`, `int_formula1db_race_alignment`).

### 2.5 Staging (`models/staging/<fuente>/stg_<fuente>__<entidad>.sql`, vistas en `silver`)

Función: una vista por tabla de origen, con **renombrado a `snake_case` y a claves comunes**
(`id → driver_id`, `year → season`, `type → session_type`), **casts** (`::integer`, `::boolean`)
y decodificación de formatos, sin joins de negocio (salvo el de Ergast para obtener temporada,
ronda y dorsal).

| Modelo | Filas | Col. | Origen | Transformación relevante |
|---|---:|---:|---|---|
| `stg_f1db__races` | 1 172 | 21 | `race` | `id→race_id`, `year→season`, `date→race_date`, `time→race_time_utc`; `has_sprint = sprint_race_date is not null`; booleanos de «decider» |
| `stg_f1db__race_data` | 187 675 | 42 | `race_data` | Tabla ancha de F1DB (una fila por piloto × sesión × carrera, distinguida por `type → session_type`); selecciona 42 de 71 columnas; casts booleanos (`race_shared_car`, `race_pole_position`, `race_fastest_lap`, `race_driver_of_the_day`, `race_grand_slam`) |
| `stg_f1db__drivers` | 917 | 13 | `driver` | datos personales + claves de país |
| `stg_f1db__constructors` | 187 | 4 | `constructor` | |
| `stg_f1db__engine_manufacturers` | 78 | 3 | `engine_manufacturer` | |
| `stg_f1db__tyre_manufacturers` | 9 | 3 | `tyre_manufacturer` | |
| `stg_f1db__circuits` | 78 | 10 | `circuit` | `length → circuit_length_km`, `type → circuit_type` |
| `stg_f1db__grands_prix` | 54 | 6 | `grand_prix` | |
| `stg_f1db__countries` | 249 | 6 | `country` | `alpha2_code`, `alpha3_code`, `demonym`, `continent_id` |
| `stg_f1db__race_driver_standings` | 21 541 | 8 | `race_driver_standing` | |
| `stg_f1db__race_constructor_standings` | 10 654 | 9 | `race_constructor_standing` | |
| `stg_f1db__season_driver_standings` | 1 681 | 7 | `season_driver_standing` | `year → season` |
| `stg_f1db__season_constructor_standings` | 721 | 8 | `season_constructor_standing` | |
| `stg_f1db__official_totals` | 1 104 | 10 | `driver` ∪ `constructor` | Totales precalculados por F1DB (`total_race_wins`, `total_podiums`…) con `entity_type`; **solo se usan en tests de paridad**, nunca como métrica |
| `stg_fastf1__laps` | 205 718 | 24 | `fastf1.laps` | `upper(Compound)`; `is_pit_in_lap/out` desde `PitInTime_ms/PitOutTime_ms`; decodifica `TrackStatus` (2 = amarilla, 4 = SC, 5 = roja, 6/7 = VSC); `is_deleted`, `is_accurate`, `speed_trap_kmh` |
| `stg_fastf1__results` | 3 768 | 12 | `fastf1.results` | `team_color = '#' || TeamColor`, `headshot_url`, `status`, `points` |
| `stg_fastf1__quali_results` | 3 769 | 8 | `fastf1.quali_results` | `q1_ms, q2_ms, q3_ms` |
| `stg_fastf1__quali_telemetry` | 518 699 | 15 | `fastf1.quali_telemetry` | `distance_m, speed_kmh, rpm, gear, throttle_pct, is_braking, drs, x, y` (descarta `Z`) |
| `stg_formula1db__lap_times` | 1 226 299 | 23 | `formula1db.lap_times` | Descarta filas que no son vueltas (`Grid`, `Start`, `A`; 26 251 filas); `parse_duration_ms` para `lap_time`, `time`, `gap`, `interval`, sectores; `gap_to_leader_laps` con regex `\+(\d+) Lap`; decodifica neumático (`H/M/S/SS/US/HS/I/W` → `HARD`…`WET`; `C0–C6` se conservan) y `status` (`Pit`, `Out Lap`, `Yellow Flag`, `Safety Car`, `Virtual Safety Car`, `Red Flag`, `Lap Time Deleted`) en booleanos |
| `stg_ergast__lap_times` | 535 748 | 6 | `ergast.lap_times` ⋈ `races` ⋈ `results` | Añade `season`, `round` y el `driver_number` de la carrera (Ergast identifica al piloto por su id interno) |

### 2.6 Intermediate (`models/intermediate/int_*.sql`, tablas en `silver`)

Es la capa donde vive la **lógica de conciliación de fuentes**. Orden de dependencias:

```diagrama
# Grafo de dependencias de intermediate (arista = "alimenta a")
stg_f1db__race_data + seed race_data_corrections + seed race_data_overrides -> int_race_data_corrected
int_race_data_corrected + stg_f1db__drivers -> int_driver_race_numbers
stg_formula1db__lap_times + int_race_data_corrected + stg_f1db__races -> int_formula1db_race_alignment
stg_formula1db__lap_times + int_formula1db_race_alignment + int_driver_race_numbers -> int_formula1db_laps
stg_fastf1__laps + stg_f1db__races + int_driver_race_numbers -> int_fastf1_laps
stg_ergast__lap_times + stg_f1db__races -> int_ergast_laps
int_formula1db_laps + int_race_data_corrected -> int_lap_numbering
int_formula1db_laps + int_fastf1_laps -> int_tyre_compound_mapping
int_formula1db_laps + int_fastf1_laps + int_ergast_laps + int_lap_numbering + int_tyre_compound_mapping
  + int_race_data_corrected + int_driver_race_numbers + seed lap_corrections -> int_laptimes
int_laptimes + int_race_data_corrected -> int_lap_completeness
```

#### `int_race_data_corrected` — 187 675 filas × 46 columnas
Granularidad: la de `race_data` (carrera × sesión × `position_display_order`). Es la **única
entrada de F1DB para los hechos** de resultados, clasificación y paradas.
1. **Correcciones heredadas** (`legacy_corrected`): `LEFT JOIN race_data_corrections` con
   condiciones comodín (`match_* is null or match_* = valor`); sustituye `driver_id` y
   `driver_number` con `SELECT * REPLACE (coalesce(set_…, original))`, conserva
   `original_driver_id` y marca `is_corrected` (7 filas afectadas).
2. **Overrides con evidencia**: `applicable_overrides` une la seed con las filas por
   `(race_id, session_type, position_display_order, driver_id)` y **solo acepta la celda si el
   valor actual de F1DB (casteado a texto) coincide con `f1db_value`**; la comparación se genera con
   un bucle Jinja sobre el diccionario `override_columns` (10 columnas con su tipo).
3. `pivoted` agrupa por fila y obtiene `override_<col>` (valor `set`), `overridden_columns`
   (lista de columnas con `set`) y `disputed_columns` (lista con `flag`).
4. Resultado final: `REPLACE (coalesce(override_<col>::<tipo>, <col>) as <col>)` para las 10
   columnas y las listas `overridden_columns` / `disputed_columns` (vacías por defecto). Filas
   con override: 177; con columnas disputadas: 2.

Tipos de sesión presentes: `RACE_RESULT` 27 621, `QUALIFYING_RESULT` 27 040,
`STARTING_GRID_POSITION` 25 858, `PIT_STOP` 22 535, `FASTEST_LAP` 17 170, entrenamientos libres
(FP1–FP4) 41 334, `QUALIFYING_1/2_RESULT` 15 248, `WARMING_UP_RESULT` 7 683,
`DRIVER_OF_THE_DAY_RESULT` 894, `PRE_QUALIFYING_RESULT` 647, `SPRINT_RACE_RESULT` 590,
`SPRINT_STARTING_GRID_POSITION` 589, `SPRINT_QUALIFYING_RESULT` 466. Gold solo usa seis de ellas.

#### `int_driver_race_numbers` — 28 332 × 6
`SELECT DISTINCT race_id, driver_number, driver_id` de `int_race_data_corrected` (dorsal no nulo)
con `driver_name`, `normalized_name` y `normalized_last_name` (macro `normalize_name`). Es la
**tabla puente** que traduce el dorsal de FastF1/formula1db/Ergast al `driver_id` de F1DB.

#### `int_formula1db_race_alignment` — 1 125 × 8
Asigna cada carrera de formula1db.com a una carrera de F1DB **por su contenido** y no por la ronda
etiquetada (el script de actualización del TFG fijaba `round_race` a mano y desde 2023-R7 los
datos quedaron desplazados una ronda). Firma de una carrera = vueltas completadas por dorsal
(`max(lap_number)`); se cuenta cuántos dorsales coinciden con `race_laps` oficiales para cada
carrera candidata de la misma temporada y se elige la de más coincidencias (`QUALIFY
row_number() … order by matching_drivers desc, (candidate_round = labelled_round) desc`); en empate
se conserva la ronda etiquetada. Salidas: `labelled_round`, `aligned_round`, `race_id`,
`is_realigned`, `legacy_drivers`, `matching_drivers`, `match_pct`. Resultado: **17 carreras
realineadas**, todas en 2023 (rondas etiquetadas 7–23 → 6–22).

#### `int_formula1db_laps` — 1 226 299 × 24
Vueltas de formula1db con `race_id` (vía la realineación) y `driver_id`. El piloto se resuelve
**una vez por (carrera, dorsal, nombre)** con candidatos por dorsal, nombre normalizado o apellido,
y un nivel de coincidencia (`driver_match_level`): 1 = dorsal y nombre (1 213 900 vueltas),
2 = dorsal y apellido (8 314), 3 = nombre (1 885), 4 = apellido único en la carrera (0),
5 = solo dorsal (2 200). Se queda el mejor nivel con `QUALIFY row_number()`. Esto resuelve los
**coches compartidos de los años 50**, donde el dorsal es del coche y no del piloto (unit test
`test_shared_car_laps_follow_driver_name`). Añade `stint = NULL` y `source = 'formula1db'`.

#### `int_fastf1_laps` — 205 718 × 24
Vueltas FastF1 con `race_id` (join por `season, round`) y `driver_id` (por dorsal).
Calcula `gap_to_leader_ms = session_time_ms − min(session_time_ms) over (partition by race_id,
lap_number)`. `source = 'fastf1'`.

#### `int_ergast_laps` — 535 748 × 5
Vueltas de Ergast con `race_id` de F1DB (join por `season, round`): `race_id, driver_number,
lap_number, position, lap_time_ms`.

#### `int_lap_numbering` — 638 × 7 (decisión N5)
Detecta, por carrera, si formula1db.com numera las vueltas igual que F1DB (problema típico en
carreras relanzadas o en dos partes). Estima el desfase (vuelta formula1db − vuelta F1DB) con dos
evidencias independientes:
- `fastest_lap_offsets`: para cada vuelta rápida oficial (`session_type = 'FASTEST_LAP'`), la
  vuelta de formula1db del mismo piloto con el mismo tiempo (±1 ms) más cercana (`arg_min`).
- `pit_stop_offsets`: para cada parada de F1DB (`PIT_STOP`), la vuelta de entrada a boxes de
  formula1db más cercana.

Cada evidencia necesita ≥ 3 casos (`HAVING sum(cases) >= 3`); se toma el desfase dominante y su
proporción. Estados (`numbering_status`):

| Estado | Regla | Carreras |
|---|---|---:|
| `consistent` | todas las evidencias dan desfase 0 | 634 |
| `pit_lap_convention` | vuelta rápida con desfase 0 y paradas de F1DB una vuelta después que la entrada a boxes (≥ 80 %): convención, no error (España 1994) | 1 |
| `renumbered` | un único desfase ≠ 0 en todas las evidencias con ≥ 80 % de los casos y sin superar las vueltas oficiales → se aplica `applied_lap_shift = −desfase` | 0 |
| `inconsistent` | las evidencias no cuadran (San Marino 1994 y Japón 1994 por las paradas de F1DB, con desfases de +4 y +13; Bélgica 2001 por sus vueltas rápidas, desfase −4) → se conserva la numeración y se marca | 3 |

Las carreras sin evidencia suficiente no aparecen (en `int_laptimes` se etiquetan `no_evidence`).

#### `int_tyre_compound_mapping` — 288 × 6 (decisión N6)
Equivalencia por carrera entre el compuesto real de Pirelli `C0–C6` (formula1db, 2019–2023) y el
relativo `HARD/MEDIUM/SOFT` (FastF1). Cuenta pares de vueltas comunes, toma el relativo más
frecuente (`arg_max`) por compuesto real y valida la coherencia con ventanas: cada compuesto real
tiene un relativo distinto (`count(*) over (partition by race_id, relative_compound) = 1`) y, al
ordenar por compuesto real, la «blandura» nunca retrocede (`lag`). `is_consistent` se evalúa por
carrera con `bool_and(...) over (partition by race_id)`. Resultado: 101 carreras, todas
coherentes.

#### `int_laptimes` — 1 270 260 × 33 (decisiones A1, A2, A6, N5, N6, N8)
Modelo central de vueltas fusionadas. Pasos (CTE):
1. `official`: vueltas oficiales, clasificado, ganador y coche compartido por (carrera, piloto).
2. `count_back_races` (**A6**): carreras en las que alguna fuente registra al ganador más allá de
   las vueltas oficiales (bandera a cuadros anticipada o resultado tomado una vuelta antes: China
   2014, Canadá 2018, Japón 2019, Bélgica 2021, Japón 2022), excluyendo coches compartidos.
3. `formula1db`: aplica `applied_lap_shift` (conserva `original_lap_number` y
   `lap_numbering_status`, `no_evidence` si no hay fila) y une `lap_corrections` **solo si el
   valor original coincide**.
4. `formula1db_corrected_time` / `formula1db_repositioned`: en carreras con corrección, recalcula
   el tiempo acumulado (`sum(...) over (partition by race_id, driver_number order by lap_number
   rows between unbounded preceding and current row)`), la diferencia con el líder y la posición
   (`rank() over (partition by race_id, lap_number order by corrected_race_time_ms)`).
5. `compared` / `resolved`: `LEFT JOIN` con FastF1 y Ergast por `(race_id, driver_number,
   lap_number)`; regla de **mayoría** (A2): si FastF1 y Ergast coinciden entre sí (±1 ms) y ambos
   discrepan de formula1db (vuelta > 1), se toma el tiempo de FastF1; igual para la posición.
6. `formula1db_final`: tiempo y posición resueltos; enriquecimiento con FastF1 (`stint`,
   `tyre_age_laps` con prioridad FastF1, `speed_trap_kmh`, `is_accurate`, banderas de pista);
   `validation_status`, `confirmed_by` (lista `ergast`/`fastf1`), `corrections` (lista
   `lap_time_ms:seed`, `lap_time_ms:majority`, `position:recalculated`, `position:majority`) y
   valores originales.
7. `fastf1_fill`: vueltas FastF1 de carreras sin formula1db o de pilotos ausentes en ella (con
   vueltas oficiales > 0); `validation_status = 'single_source'`, `lap_numbering_status =
   'not_applicable'`.
8. `ergast_fill` (**N8**): vueltas sueltas que faltan en formula1db dentro de las vueltas
   oficiales, `source = 'ergast'` (hoy 0 filas: no hay huecos que rellenar).
9. `UNION ALL BY NAME` de las tres ramas, cálculo de `tyre_compound_pirelli` (C0–C6, o nombre
   comercial hasta 2018, o INTERMEDIATE/WET) y `tyre_compound_relative` (vía el mapeo coherente de
   2019–2023, o directamente HARD/MEDIUM/SOFT desde 2019) y **borrado A6** de las vueltas de
   clasificados posteriores al final oficial en las `count_back_races`.

Estados de `validation_status`:

| Estado | Regla | Vueltas |
|---|---|---:|
| `confirmed` | Ergast o FastF1 dan el mismo tiempo (±1 ms) | 587 453 |
| `timing_convention` | diferencia < 1 s, vuelta 1 o vuelta > 300 s (bandera roja): cada fuente reparte el tiempo distinto | 443 |
| `disputed` | otra fuente discrepa ≥ 1 s sin mayoría: se conserva formula1db | 305 |
| `corrected` | seed con evidencia o mayoría de las otras dos fuentes | 1 |
| `single_source` | sin otra fuente con la que contrastar (antes de 1996, o fuente FastF1) | 682 058 |

Correcciones aplicadas: `position:recalculated` 185 vueltas (carrera de Russell), `position:majority`
49, `lap_time_ms:seed` 1. Fuente final: `formula1db` 1 226 272 vueltas (1 125 carreras,
1950–2024), `fastf1` 43 988 (40 carreras: 2025–2026 completas y un piloto suelto de 2024).

#### `int_lap_completeness` — 25 752 × 12
Concilia, por (carrera, piloto), las vueltas registradas con las oficiales de F1DB. Excluye a
quien no tomó la salida (`DNQ`, `DNPQ`, `DNP`, `EX`, `DNS` sin vueltas); `FULL OUTER JOIN` entre
oficial y registrado; fuente principal de la carrera con `mode(source)`. Calcula
`missing_laps`, `laps_beyond_official` y `status`:

| Estado | Significado | Pilotos-carrera |
|---|---|---:|
| `ok` | todas las vueltas oficiales, sin huecos (se tolera una vuelta extra: la de abandono) | 25 339 |
| `disqualified` | DSQ: F1DB no computa sus vueltas | 160 |
| `shared_car` | coche compartido: la fuente no separa vueltas por piloto | 117 |
| `missing_laps` | faltan vueltas o hay huecos | 116 |
| `no_laps` | la carrera tiene vueltas pero el piloto no | 11 |
| `extra_laps` | más de una vuelta por encima de las oficiales | 9 |

> Observación: en `silver` existe además la tabla `int_formula1db_laps_validated`
> (1 226 299 × 22) **sin modelo en el proyecto**: es un residuo de una versión anterior que dbt no
> elimina. Conviene borrarla (ver §7).

---

## 3. Capa GOLD: modelo dimensional

### 3.1 Enfoque

Gold mantiene el diseño del TFG (Kimball, **esquema de constelación**: varias tablas de hechos que
comparten dimensiones conformadas) y lo amplía. Rasgos de diseño:

- **Claves naturales** de F1DB como claves de dimensión: `driver_id`, `constructor_id`,
  `engine_manufacturer_id`, `tyre_manufacturer_id` (texto tipo *slug*, p. ej. `lewis-hamilton`) y
  `race_id` (entero). No hay claves sustitutas.
- **Dimensiones desnormalizadas** (sin copo de nieve), como en el TFG: el país se incrusta en cada
  dimensión; temporada, circuito y Gran Premio se incrustan en `dim_race`.
- **Dimensiones tipo 1** (sobrescritura completa en cada `dbt build`); no hay historización.
- **Atributos degenerados** en los hechos (`session_type`, `position_text`, `reason_retired`,
  `driver_number`, `source`, `validation_status`…), como decidió el TFG para no crear hasta seis
  dimensiones de una sola columna.
- Hechos con **metadatos de linaje y calidad por fila**: `is_corrected`, `overridden_columns`,
  `disputed_columns`, `source`, `validation_status`, `confirmed_by`, `corrections`, `original_*`,
  `lap_numbering_status`, `quality_status`.
- Capa de **métricas precalculadas** (`agg_*`) que sustituye a parte de las medidas DAX del TFG.

### 3.2 Inventario de tablas gold (DuckDB, 28/09/2026)

| Tabla | Tipo | Filas | Col. | Granularidad | Clave (natural / compuesta) |
|---|---|---:|---:|---|---|
| `dim_driver` | dimensión | 917 | 15 | piloto | `driver_id` |
| `dim_constructor` | dimensión | 187 | 6 | constructor | `constructor_id` |
| `dim_engine_manufacturer` | dimensión | 78 | 5 | motorista | `engine_manufacturer_id` |
| `dim_tyre_manufacturer` | dimensión | 9 | 5 | proveedor de neumáticos | `tyre_manufacturer_id` |
| `dim_race` | dimensión | 1 172 | 38 | Gran Premio (1950–2026; 8 aún sin disputar) | `race_id` |
| `fact_race_result` | hecho transaccional | 28 211 | 32 | piloto × carrera × sesión (`RACE` 27 621, `SPRINT` 590) | `(race_id, session_type, position_display_order)` |
| `fact_qualifying_result` | hecho transaccional | 27 506 | 19 | piloto × carrera × sesión (`QUALIFYING` 27 040, `SPRINT_QUALIFYING` 466) | `(race_id, session_type, position_display_order)` |
| `fact_pit_stops` | hecho transaccional | 22 535 | 11 | parada real (F1DB; 1994–2026, 612 carreras) | `(race_id, driver_id, stop_number)` (no testeada) |
| `fact_pit_lane_passes` | hecho transaccional | 24 271 | 7 | entrada al pit lane registrada en las vueltas | `(race_id, driver_id, driver_number, lap_number)` |
| `fact_laptimes` | hecho transaccional | 1 270 260 | 35 | vuelta × piloto × carrera (1 164 carreras) | `(race_id, driver_id, driver_number, lap_number)` |
| `fact_quali_telemetry` | hecho transaccional | 518 699 | 15 | muestra cada 10 m de la vuelta rápida de clasificación (63 carreras, 2024–2026) | sin clave declarada (de facto `race_id, driver_id, distance_m`) |
| `fact_driver_standing` | hecho *snapshot* periódico | 21 541 | 8 | piloto × carrera (clasificación tras cada GP) | `(race_id, driver_id)` (no testeada) |
| `fact_constructor_standing` | hecho *snapshot* periódico | 10 654 | 9 | constructor (+motor) × carrera | `(race_id, position_display_order)` (no testeada) |
| `agg_driver_career` | agregado | 917 | 23 | piloto | `driver_id` |
| `agg_constructor_career` | agregado | 187 | 16 | constructor | `constructor_id` |
| `agg_driver_season` | agregado | 1 681 | 15 | piloto × temporada | `(season, driver_id)` |
| `agg_teammate_h2h` | agregado | 13 530 | 13 | piloto × compañero × constructor × temporada | `(season, constructor_id, driver_id, teammate_id)` |

### 3.3 Dimensiones

| Dimensión | Construcción |
|---|---|
| `dim_driver` | `stg_f1db__drivers` con dos `LEFT JOIN` a `stg_f1db__countries`: rol «país de nacimiento» (`country_of_birth_name`) y rol «nacionalidad» (`nationality_country`, `nationality_demonym`, `nationality_alpha2`). Es un *role-playing* de la dimensión país resuelto por desnormalización. |
| `dim_constructor` | `stg_f1db__constructors` ⟕ países → `country_constructor`, `demonym_constructor`, `alpha2_constructor`. |
| `dim_engine_manufacturer` | Ídem con sufijo `_engine_manufacturer`. |
| `dim_tyre_manufacturer` | Ídem con sufijo `_tyre_manufacturer`. |
| `dim_race` | `stg_f1db__races` ⟕ circuitos ⟕ país del circuito ⟕ Grandes Premios ⟕ país del GP. Añade `is_completed` (existe algún `RACE_RESULT`: 1 164 de 1 172) e `is_season_final_race` (`round = max(round) over (partition by season)`). Como contiene `season` y `race_date`, hace también de dimensión temporal de grano carrera. |

### 3.4 Hechos

- **`fact_race_result`**: `int_race_data_corrected` filtrado a `RACE_RESULT` y
  `SPRINT_RACE_RESULT` (renombrados `RACE`/`SPRINT`). Medidas: `laps`, `time_ms`,
  `time_penalty_ms`, `gap_ms`, `gap_laps`, `interval_ms`, `points` (`coalesce(…, 0)`),
  `grid_position`, `positions_gained`, `pit_stops`. Indicadores: `is_win` (`position_number = 1`),
  `is_podium` (`<= 3`), `is_pole_position`, `is_fastest_lap`, `is_driver_of_the_day`,
  `is_grand_slam`, `is_shared_car`. Linaje: `is_corrected`, `overridden_columns`,
  `disputed_columns`. A diferencia del TFG, la parrilla y la vuelta rápida ya vienen en la fila
  `RACE_RESULT` de F1DB, así que desaparecen los *merges* de Power Query con
  `fact_starting_grid_position` y `fact_fastest_lap`.
- **`fact_qualifying_result`**: `QUALIFYING_RESULT` y `SPRINT_QUALIFYING_RESULT`;
  `best_time_ms = coalesce(least(q1, q2, q3), qualifying_time_millis)` (cubre los formatos
  antiguos de sesión única); `gap_to_pole_pct = round(100 · (best / min(best) over (partition by
  race_id, session_type) − 1), 3)`; `is_pole`; `overridden_columns`.
- **`fact_pit_stops`**: `session_type = 'PIT_STOP'`; `stop_number`, `lap_number`, `time_ms` y
  `time_seconds` (medida derivada del TFG). Solo paradas reales.
- **`fact_pit_lane_passes`** (nuevo, decisión N4): todas las vueltas con `is_pit_in_lap` de
  `int_laptimes` emparejadas con la parada de F1DB de la misma vuelta (corrigiendo
  `pit_stop_offset` en carreras `inconsistent`/`pit_lap_convention` y quedándose con una parada por
  vuelta con `QUALIFY row_number()`). Tipificación `pass_type`, en orden de evaluación:

  | `pass_type` | Regla | Filas |
  |---|---|---:|
  | `pit_stop` | coincide con una parada de F1DB | 22 485 |
  | `unclassified` | carrera sin paradas en F1DB (antes de 1994) | 1 118 |
  | `red_flag` | entrada con bandera roja | 62 |
  | `retirement` | no clasificado y entra en su última vuelta | 351 |
  | `safety_car` | bajo SC/VSC sin parada registrada | 114 |
  | `penalty_or_other` | resto (drive-through, stop-and-go…) | 141 |

- **`fact_laptimes`** (el `fact_gp_laptimes` del TFG): `int_laptimes` ⟕ `int_lap_completeness`.
  Añade `is_incomplete_lap` (vuelta posterior a las oficiales: la de abandono) y `quality_status`
  (`ok` 1 249 767 vueltas, `disqualified` 6 860, `shared_car` 6 831, `missing_laps` 6 229,
  `extra_laps` 573; `unmatched_driver` si no hay conciliación, hoy 0). Distribución de
  `lap_numbering_status`: `consistent` 693 360, `no_evidence` 529 556, `not_applicable` 43 988,
  `inconsistent` 2 269, `pit_lap_convention` 1 087. Compuesto relativo conocido en 191 209 vueltas
  (HARD 77 192, MEDIUM 67 713, SOFT 28 696, INTERMEDIATE 13 935, WET 3 673).
- **`fact_quali_telemetry`** (nuevo): `stg_fastf1__quali_telemetry` con `race_id` y `driver_id`
  (vía `int_driver_race_numbers`; 0 filas sin piloto).
- **`fact_driver_standing`** y **`fact_constructor_standing`**: `SELECT *` de las vistas de
  staging de clasificaciones tras cada carrera (puntos y posición acumulados,
  `positions_gained`, `championship_won`).

### 3.5 Métricas (`marts/metrics`)

| Modelo | Entradas | Lógica | Métricas |
|---|---|---|---|
| `agg_driver_career` | `fact_race_result`, `stg_f1db__season_driver_standings`, `dim_driver` | Agregados por piloto con `count(distinct race_id) filter (where …)` (evita dobles conteos en coches compartidos); sprints aparte; campeonatos desde la clasificación final | `championships`, `best_championship_position`, `first/last_season`, `race_entries`, `race_starts` (excluye DNQ/DNPQ/DNP/EX/DNS), `wins`, `podiums`, `pole_positions`, `fastest_laps`, `grand_slams`, `driver_of_the_day`, `sprint_wins`, `points` (carrera + sprint), `championship_points`, `best_race_result`, `laps_completed`, `win_rate_pct`, `podium_rate_pct` |
| `agg_constructor_career` | `fact_race_result`, `stg_f1db__season_constructor_standings`, `dim_constructor`, `dim_race` | Criterios de F1DB: victorias por carrera, **podios por coche** (`count(distinct (race_id, position_number))`), vueltas rápidas por piloto acreditado | `championships`, `best_championship_position`, `first/last_season`, `race_entries`, `wins`, `podiums`, `podium_races`, `one_two_finishes`, `pole_positions`, `fastest_laps`, `race_points` |
| `agg_driver_season` | `stg_f1db__season_driver_standings`, `fact_race_result`, `dim_race`, `dim_driver`, `dim_constructor` | Posición y puntos finales de F1DB + recuentos de la temporada; equipo principal = `mode(constructor_id)` | `championship_position(_text)`, `points`, `championship_won`, `races`, `wins`, `podiums`, `pole_positions`, `fastest_laps`, `best_result` |
| `agg_teammate_h2h` | `fact_race_result`, `fact_qualifying_result`, `dim_race` | *Self-join* por carrera y constructor (sin coches compartidos); «por delante» según `position_display_order` en carrera y en clasificación | `races_together`, `race_ahead(_pct)`, `qualifyings_together`, `quali_ahead(_pct)`, `points`, `teammate_points`, `points_difference` |

La paridad de `agg_driver_career` y `agg_constructor_career` con los totales oficiales de F1DB se
verifica con tests singulares (§4.3).

### 3.6 Diagramas del modelo (para TikZ)

Constelación completa (cada hecho forma una estrella; las dimensiones son compartidas):

```diagrama
# Esquema de constelación gold. Aristas = FK -> PK, cardinalidad N:1
dimensiones: dim_race[race_id], dim_driver[driver_id], dim_constructor[constructor_id],
             dim_engine_manufacturer[engine_manufacturer_id], dim_tyre_manufacturer[tyre_manufacturer_id]
hechos: fact_race_result, fact_qualifying_result, fact_pit_stops, fact_pit_lane_passes,
        fact_laptimes, fact_quali_telemetry, fact_driver_standing, fact_constructor_standing
aristas:
  fact_race_result       -> dim_race, dim_driver, dim_constructor, dim_engine_manufacturer, dim_tyre_manufacturer
  fact_qualifying_result -> dim_race, dim_driver, dim_constructor, dim_engine_manufacturer, dim_tyre_manufacturer
  fact_pit_stops         -> dim_race, dim_driver, dim_constructor, dim_engine_manufacturer, dim_tyre_manufacturer
  fact_pit_lane_passes   -> dim_race, dim_driver
  fact_laptimes          -> dim_race, dim_driver
  fact_quali_telemetry   -> dim_race, dim_driver
  fact_driver_standing   -> dim_race, dim_driver
  fact_constructor_standing -> dim_race, dim_constructor, dim_engine_manufacturer
relaciones entre hechos (misma clave de grano, sin FK; línea discontinua):
  fact_pit_lane_passes (race_id, driver_id, stop_number) ~ fact_pit_stops (race_id, driver_id, stop_number)
  fact_pit_lane_passes (race_id, driver_id, driver_number, lap_number) ~ fact_laptimes (misma clave)
disposición sugerida: dim_race en el centro; dim_driver a la derecha; dim_constructor,
  dim_engine_manufacturer y dim_tyre_manufacturer a la izquierda; hechos de resultados arriba,
  hechos de vueltas y boxes abajo, standings a los lados.
```

Estrella principal (resultados):

```diagrama
centro: fact_race_result
  clave: race_id, session_type, position_display_order
  medidas: points, laps, time_ms, gap_ms, grid_position, positions_gained, pit_stops
  indicadores: is_win, is_podium, is_pole_position, is_fastest_lap, is_grand_slam
  linaje: is_corrected, overridden_columns, disputed_columns
radios (N:1): dim_race, dim_driver, dim_constructor, dim_engine_manufacturer, dim_tyre_manufacturer
```

Estrella de vueltas:

```diagrama
centro: fact_laptimes
  clave: race_id, driver_id, driver_number, lap_number
  medidas: lap_time_ms, position, gap_to_leader_ms, sector_1_ms, sector_2_ms, sector_3_ms, tyre_age_laps, speed_trap_kmh
  atributos: stint, tyre_compound, tyre_compound_pirelli, tyre_compound_relative, is_pit_in_lap,
             is_pit_out_lap, is_yellow_flag, is_safety_car, is_virtual_safety_car, is_red_flag
  calidad: source, validation_status, confirmed_by, corrections, lap_numbering_status, quality_status
radios (N:1): dim_race, dim_driver
satélites: fact_pit_lane_passes (misma clave de vuelta), fact_quali_telemetry (race_id, driver_id)
```

Capa de métricas (dependencias de construcción, no FK):

```diagrama
fact_race_result + stg_f1db__season_driver_standings + dim_driver -> agg_driver_career
fact_race_result + stg_f1db__season_constructor_standings + dim_constructor + dim_race -> agg_constructor_career
stg_f1db__season_driver_standings + fact_race_result + dim_race + dim_driver + dim_constructor -> agg_driver_season
fact_race_result + fact_qualifying_result + dim_race -> agg_teammate_h2h
```

### 3.7 Comparación con el modelo del TFG (Fig. 5.7, secciones 5.1–5.3)

En el TFG las dimensiones de análisis eran Carreras (agregado: temporada), Pilotos,
Constructores, Fabricantes de motores y Fabricantes de neumáticos (Tabla 5.1). La Fig. 5.7
(«Diseño final esquema de constelación») tenía 5 dimensiones y 6 hechos. La ETL se hacía en Power
Query (ODBC contra la SQLite de F1DB y CSV de formula1db.com en SharePoint), las medidas en DAX y
la actualización era manual (nueva descarga de F1DB, scripts Selenium y republicación o puerta de
enlace local).

| Aspecto | TFG (Power BI) | f1-data-platform |
|---|---|---|
| Dimensiones | `dim_driver`, `dim_constructor`, `dim_engine_manufacturer`, `dim_tyre_manufacturer`, `dim_race` (temporada, GP y circuito desnormalizados; Figs. 5.5–5.6) | Las mismas 5, con los mismos nombres y el mismo criterio de desnormalización; se añaden `alpha2/alpha3` (banderas en la web), `is_completed`, `is_season_final_race`, `has_sprint` y los booleanos de «decider» |
| Hechos | `fact_race_result`, `fact_qualifying_result`, `fact_pit_stops`, `fact_race_driver_standing`, `fact_race_constructor_standing`, `fact_gp_laptimes` (6) | 8: se renombran `fact_driver_standing`, `fact_constructor_standing` y `fact_laptimes`; se añaden `fact_pit_lane_passes` y `fact_quali_telemetry` |
| Tiempos por vuelta | Solo formula1db.com | Fusión formula1db + FastF1 + Ergast con estado de validación, correcciones y linaje por fila |
| Resultados | Merges con `fact_starting_grid_position` y `fact_fastest_lap` en Power Query; columnas condicionales de penalización | Directamente de `race_data` (fila `RACE_RESULT`), con correcciones auditables (seeds) |
| Medidas | DAX (victorias, podios, compañeros…, §5.3.3) | Columnas derivadas en los hechos (`is_win`, `is_podium`, `gap_to_pole_pct`, `time_seconds`) + tablas `agg_*` precalculadas y verificadas contra F1DB |
| Tipos | Conversión manual en Power Query (puntos → comas, enteros/decimales) | Tipos de SQLite preservados en Parquet; casts en staging |
| Atributos de texto | En los hechos (`status`, `tyre`, `position_text`, `type`…) | Mismo criterio (dimensiones degeneradas) |
| Calidad | Revisión manual (`Script-2.sql`) | Esquema `quality` (40 comprobaciones con umbral), 50 tests y 4 unit tests |
| Actualización | Manual | Semanal con GitHub Actions, incremental y reproducible |

---

## 4. Capa de CALIDAD

La calidad se trabaja en tres niveles: (1) **modelos de contraste** entre fuentes (esquema
`quality`), resumidos en `qa_summary`; (2) **tests de datos de dbt** (genéricos y singulares) que
se ejecutan en cada `dbt build` e impiden publicar si fallan; (3) **unit tests de dbt** sobre la
lógica de conciliación más delicada.

### 4.1 Modelos `qa_*` (esquema `quality`, tablas)

| Modelo | Filas | Qué compara | Emparejamiento | Indicadores |
|---|---:|---|---|---|
| `qa_formula1db_vs_fastf1_laps` | 161 475 | Vueltas de formula1db frente a FastF1 en las carreras que cubren ambas | `(race_id, driver_number, lap_number)` | `is_matched`, `is_time_match` (±1 ms, excluye la vuelta 1: cada fuente la cronometra desde un punto distinto), `is_position_match`, `is_tyre_match` (solo compuestos comparables SOFT/MEDIUM/HARD/INTERMEDIATE/WET) |
| `qa_formula1db_vs_ergast_laps` | 535 760 | formula1db frente a Ergast (1996–2022) | ídem | `is_matched`, `is_time_match`, `is_position_match` |
| `qa_fastf1_vs_f1db_results` | 3 768 | Resultados de carrera FastF1 frente a F1DB | `(race_id, driver_number)` | `is_position_match` (solo clasificados), `is_points_match`, `is_grid_match` (excluye salidas desde el pit lane) |
| `qa_fastf1_vs_f1db_qualifying` | 8 326 | Q1/Q2/Q3 FastF1 frente a F1DB | `(race_id, driver_number)` + `CROSS JOIN LATERAL (VALUES …)` para desplegar las tres sesiones | `is_matched`, `is_time_match` |
| `qa_pit_stops` | 22 535 | Cada parada de F1DB frente a las entradas a boxes de las vueltas | `fact_pit_stops` ⟕ `fact_pit_lane_passes (pass_type = 'pit_stop')` por `(race_id, driver_id, stop_number)` | `is_match`, fuente dominante de la carrera |
| `qa_fastest_laps` | 14 005 | Mejor vuelta calculada (sin vueltas borradas) frente a la vuelta rápida oficial de F1DB | `(race_id, driver_id)` | `difference_ms`, `is_match` (±1 ms) |

### 4.2 `qa_summary` (40 comprobaciones)

Una fila por comprobación con `check_id`, `description`, `compared`, `matched`, `min_match_pct`,
`match_pct` y `status`: `INFO` si no tiene umbral, `NO_DATA` si no hay casos, `PASS` si
`match_pct ≥ min_match_pct` y `FAIL` en otro caso. Tests: `unique` y `not_null` en `check_id`,
`accepted_values` en `status`. Resultado actual: **23 PASS, 17 INFO, 0 FAIL, 0 NO_DATA**.

| `check_id` | Comparados | Coinciden | % | Umbral | Estado |
|---|---:|---:|---:|---:|---|
| `formula1db_vs_fastf1_lap_time` | 156 003 | 154 910 | 99,30 | 98 | PASS |
| `formula1db_vs_fastf1_position` | 161 367 | 159 817 | 99,04 | 98 | PASS |
| `formula1db_vs_fastf1_tyre` | 43 019 | 42 611 | 99,05 | 98 | PASS |
| `formula1db_vs_ergast_coverage` | 535 760 | 535 542 | 99,96 | 98 | PASS |
| `formula1db_vs_ergast_lap_time` | 525 436 | 524 725 | 99,86 | 98 | PASS |
| `formula1db_vs_ergast_position` | 535 542 | 534 945 | 99,89 | 98 | PASS |
| `fastf1_vs_f1db_race_position` | 3 260 | 3 260 | 100,00 | 100 | PASS |
| `fastf1_vs_f1db_points` | 3 768 | 3 768 | 100,00 | 100 | PASS |
| `fastf1_vs_f1db_grid` | 3 646 | 3 616 | 99,18 | 99 | PASS |
| `fastf1_vs_f1db_qualifying` | 8 263 | 8 255 | 99,90 | 99 | PASS |
| `f1db_pit_stops_in_laps_fastf1` | 1 238 | 1 238 | 100,00 | 99 | PASS |
| `f1db_pit_stops_in_laps_formula1db` | 21 297 | 21 256 | 99,81 | 99 | PASS |
| `fastest_lap_fastf1` | 779 | 772 | 99,10 | 99 | PASS |
| `fastest_lap_formula1db` | 13 226 | 13 123 | 99,22 | 95 | PASS |
| `lap_completeness_fastf1` | 794 | 794 | 100,00 | 99 | PASS |
| `lap_completeness_formula1db` | 24 681 | 24 545 | 99,45 | 97 | PASS |
| `lap_driver_attribution` | 1 270 260 | 1 270 260 | 100,00 | 99,9 | PASS |
| `tyre_mapping_consistent` | 101 | 101 | 100,00 | 100 | PASS |
| `f1db_overrides_A3` / `A4` / `A5` / `N1` / `N2` | 74 / 97 / 14 / 8 / 2 | todas | 100,00 | 100 | PASS (5) |
| `formula1db_race_alignment` | 1 125 | 1 108 | 98,49 | — | INFO |
| `lap_numbering_consistent` / `inconsistent` / `pit_lap_convention` | 638 | 634 / 3 / 1 | — | — | INFO (3) |
| `lap_source_formula1db` / `fastf1` | 1 270 260 | 1 226 272 / 43 988 | 96,54 / 3,46 | — | INFO (2) |
| `lap_time_confirmed` / `single_source` / `timing_convention` / `disputed` / `corrected` | 1 270 260 | 587 453 / 682 058 / 443 / 305 / 1 | — | — | INFO (5) |
| `pit_lane_pass_<tipo>` (6 tipos) | 24 271 | ver §3.4 | — | — | INFO (6) |

Los umbrales se fijaron por tipo de comparación: 100 % donde la semántica es idéntica (puntos,
posición de clasificados, overrides aplicados, mapeo de neumáticos), 98–99 % en vueltas y tiempos,
y 95–97 % donde el histórico tiene limitaciones conocidas (vuelta rápida y completitud en
formula1db).

### 4.3 Tests de dbt

**Genéricos** (declarados en `_core__models.yml`, `_quality__models.yml` y `_seeds.yml`; 43 en
total):

| Test | Nº | Dónde |
|---|---:|---|
| `unique` | 6 | PK de las 5 dimensiones; `qa_summary.check_id` |
| `not_null` | 13 | PK de dimensiones, `dim_race.season`, `driver_id` de `fact_race_result`, `fact_qualifying_result`, `fact_laptimes`, `fact_quali_telemetry`, `pass_type`, `validation_status`, `check_id` |
| `relationships` | 10 | Integridad referencial de `fact_race_result` con las 5 dimensiones; `driver_id` de `fact_qualifying_result`, `fact_pit_stops`, `fact_laptimes`, `fact_driver_standing`; `constructor_id` de `fact_constructor_standing` |
| `accepted_values` | 9 | `fact_race_result.session_type` (`RACE`, `SPRINT`), `fact_pit_lane_passes.pass_type`, `fact_laptimes.source`, `.quality_status`, `.validation_status`, `qa_summary.status`, seed `race_data_overrides.column_name` y `.action`, seed `lap_corrections.column_name` |
| `unique_combination` (propio, `tests/generic/unique_combination.sql`) | 5 | Clave compuesta de `fact_race_result`, `fact_qualifying_result`, `fact_pit_lane_passes`, `fact_laptimes` y de la seed `race_data_overrides` |

**Singulares** (`transform/tests/`, 7):

| Test | Severidad | Qué valida |
|---|---|---|
| `assert_driver_totals_match_f1db` | error | Paridad de `agg_driver_career` con los totales oficiales de F1DB (campeonatos, inscripciones, salidas, victorias, podios, poles, vueltas rápidas, grand slams), excluyendo los pilotos afectados por `race_data_corrections` |
| `assert_constructor_totals_match_f1db` | error | Ídem para `agg_constructor_career` |
| `assert_one_winning_car_per_race` | error | Exactamente un coche ganador (`count(distinct driver_number) = 1`) por carrera y sesión (los coches compartidos pueden repartir la victoria entre pilotos) |
| `assert_quality_thresholds` | error | Ninguna fila de `qa_summary` en `FAIL` (es el «interruptor» que bloquea la publicación) |
| `assert_standings_points_match_results` | warn | Desde 1991, suma de puntos de carrera + sprint = puntos de la clasificación final |
| `assert_corrections_still_apply` | warn | Cada fila de `race_data_corrections` sigue encajando con F1DB (si no, F1DB lo corrigió y puede retirarse) |
| `assert_overrides_still_apply` | warn | Cada override sigue aplicándose (piloto y valor original sin cambios) |

**Unit tests** (4, en `_quality__models.yml`, con datos de entrada simulados con `given`/`expect`):
`test_shared_car_laps_follow_driver_name` (`int_formula1db_laps`: Farina/Bonetto 1951),
`test_realigns_race_labelled_with_wrong_round` y `test_keeps_labelled_round_on_tie`
(`int_formula1db_race_alignment`: Mónaco 2023 etiquetado como R7; empate) y
`test_lap_completeness_statuses` (`int_lap_completeness`: vuelta de abandono, abandono en la
vuelta 1, descalificado y huecos).

**Resultado actual**: 50/50 tests `pass` (ningún aviso de los 3 `warn`) y 4/4 unit tests `pass`.
Además, las pruebas de Python (`pytest`) cubren la ingesta y el snapshot, y la CI ejecuta
`dbt parse` y `dbt build` completos contra el último snapshot publicado.

---

## 5. Linaje completo y pipeline

### 5.1 Linaje de extremo a extremo

```diagrama
# Linaje (izquierda -> derecha). Agrupar por columnas: Fuente | Raw | Bronze | Staging | Intermediate | Gold | Quality | Distribución | Consumo
Fuente:  GitHub f1db/f1db (release)  |  API F1 Live Timing (FastF1)  |  CSV scraping formula1db.com (TFG)  |  f1db_csv.zip Ergast 2022
Raw:     data/raw/f1db/<tag>/f1db.db (SQLite)      [solo F1DB; FastF1 usa data/cache/fastf1]
Bronze:  bronze/f1db/*.parquet (31) | bronze/fastf1/{laps,results,quali_results,quali_telemetry}/season=YYYY/round=RR.parquet
         | bronze/formula1db/{lap_times,race_entries,drivers}.parquet | bronze/ergast/*.parquet (6)
Staging (vistas silver): stg_f1db__* (14) | stg_fastf1__* (4) | stg_formula1db__lap_times | stg_ergast__lap_times
Seeds (silver): race_data_corrections, race_data_overrides, lap_corrections
Intermediate (tablas silver): int_race_data_corrected -> int_driver_race_numbers -> {int_formula1db_race_alignment -> int_formula1db_laps, int_fastf1_laps, int_ergast_laps}
         -> {int_lap_numbering, int_tyre_compound_mapping} -> int_laptimes -> int_lap_completeness
Gold: dim_* (desde stg_f1db__*) ; fact_race_result/fact_qualifying_result/fact_pit_stops (desde int_race_data_corrected)
      ; fact_laptimes (int_laptimes + int_lap_completeness) ; fact_pit_lane_passes (int_laptimes + int_lap_numbering + int_race_data_corrected)
      ; fact_quali_telemetry (stg_fastf1__quali_telemetry + int_driver_race_numbers) ; fact_*_standing (stg_f1db__race_*_standings)
      ; agg_* (hechos + dims + stg_f1db__season_*_standings)
Quality: qa_* (int_* y fact_*) -> qa_summary -> test assert_quality_thresholds
Distribución (f1-ingest snapshot pack): bronze.tar.gz ; f1.duckdb (gold.* + quality.qa_summary) ; gold-parquet.zip ; manifest.json -> GitHub Release data-latest
Consumo: API FastAPI (Render) descarga f1.duckdb de la release y lo sirve en solo lectura -> web Next.js (Vercel)
         ; Power BI / otras herramientas -> gold-parquet.zip
Ciclo: bronze.tar.gz de la release -> (restore) -> bronze de la siguiente ejecución
```

Qué ocurre en cada fase:

| Fase | Operaciones | Artefacto |
|---|---|---|
| Fuente → raw | Descarga versionada por tag (F1DB); caché HTTP (FastF1) | `f1db.db`, `data/cache` |
| raw/fuente → bronze | Conversión a Parquet sin reglas de negocio, `timedelta` → ms, `snake_case`, deduplicación exacta, partición por temporada/ronda, escritura atómica, `_metadata.json` | `data/bronze/**` |
| bronze → staging | Lectura directa de Parquet (`external_location`), renombrado, casts, parseo de tiempos y códigos (neumático, estado de pista) | vistas `silver.stg_*` |
| staging → intermediate | Correcciones (seeds), claves comunes (dorsal → `driver_id`, temporada/ronda → `race_id`), realineación de carreras, numeración de vueltas, mapeo de compuestos, fusión de vueltas con validación y linaje, conciliación de completitud | tablas `silver.int_*` |
| intermediate → gold | Modelo dimensional (dimensiones desnormalizadas, hechos por tipo de sesión), indicadores derivados, métricas agregadas | tablas `gold.*` |
| gold/intermediate → quality | Contrastes entre fuentes y resumen con umbrales; tests | tablas `quality.*`, `run_results.json` |
| gold → distribución | Base compacta para la API, Parquet ZSTD, manifiesto con hashes, notas de release | `dist/*` → Release `data-latest` |
| distribución → API | La API (config `F1_DATA_REPO`) descarga `manifest.json` y `f1.duckdb`, guarda cada versión como `f1-<sha256[:12]>.duckdb`, la abre `read_only` y comprueba cada 6 h (`F1_API_REFRESH_HOURS`) si hay una nueva | `data/api` o `/data` en el contenedor |

La API consulta 16 de las 17 tablas gold (todas salvo `dim_tyre_manufacturer`) y
`quality.qa_summary` (endpoint de estado de calidad).

### 5.2 Pipeline `.github/workflows/pipeline.yml` paso a paso

Disparadores: `schedule` los **lunes a las 06:00 UTC** (los datos de cronometraje del GP del
domingo ya están publicados) y `workflow_dispatch` con entradas `seasons` (temporadas de FastF1)
y `force_f1db`. `permissions: contents: write`; `concurrency: data-pipeline` sin cancelación
(nunca dos ejecuciones escribiendo la release a la vez); variables `DATA_TAG = data-latest` y
`GH_TOKEN`. Job `pipeline` en `ubuntu-latest`, `timeout-minutes: 120`:

| # | Paso | Comando / lógica | Propósito |
|---|---|---|---|
| 1 | Checkout | `actions/checkout@v5` | Código |
| 2 | uv | `astral-sh/setup-uv@v6` con caché | Gestor de entornos |
| 3 | Dependencias | `uv sync --locked` | Entorno reproducible (`uv.lock`) |
| 4 | Restaurar snapshot | `gh release download data-latest --pattern bronze.tar.gz` → `f1-ingest snapshot restore`; si no existe la release, error explicativo (el snapshot inicial debe publicarse desde el equipo del autor, que tiene los CSV del TFG) | Recuperar el bronze completo (incluidas las fuentes estáticas) |
| 5 | Ingesta F1DB | `f1-ingest f1db [--force]` | Nueva release de F1DB si la hay (idempotente) |
| 6 | Ingesta FastF1 | temporadas = entrada o año actual (en enero también el anterior); validación con regex `^[0-9]{4}( [0-9]{4})*$`; `f1-ingest fastf1 --season $SEASONS --telemetry`; `continue-on-error: true` | Carga incremental de las carreras nuevas; una carrera sin datos no bloquea la publicación |
| 7 | dbt build | `uv run dbt build --profiles-dir .` en `transform/` | Seeds, modelos, tests y unit tests en orden de DAG; si falla un test de severidad `error` (p. ej. `assert_quality_thresholds`) el pipeline se detiene y **no publica** |
| 8 | Snapshot | `f1-ingest snapshot pack --out dist`; `snapshot notes` → `dist/notes.md` y al `GITHUB_STEP_SUMMARY` | Generar artefactos y resumen |
| 9 | Publicar | crea la release si no existe (`--latest=false`); sube `f1.duckdb`, `gold-parquet.zip`, `manifest.json` con `--clobber` y **`bronze.tar.gz` el último** (es la entrada de la próxima ejecución); actualiza las notas | Distribución |
| 10 | Aviso FastF1 | si el paso 6 falló: `::warning::` | Visibilidad de carreras pendientes |
| 11–12 | Docs dbt (opcional, `vars.PUBLISH_DOCS == 'true'`) | `dbt docs generate --static` → `site/index.html` → `upload-pages-artifact` | Catálogo y linaje navegables |
| 13 | Logs (si falla) | `upload-artifact` de `transform/logs/` y `run_results.json` | Diagnóstico |
| job `docs` | `needs: pipeline`, `deploy-pages@v4` | Publicación en GitHub Pages |

El workflow `ci.yml` complementa al pipeline en cada *push*/PR: ruff + pytest, `dbt parse` y
`dbt build` sobre el último snapshot, construcción y prueba de humo de la imagen Docker de la API
y pruebas de la web (tipos OpenAPI, Playwright + axe).

```diagrama
# Flujo del pipeline semanal (nodos = pasos; aristas = orden)
cron lunes 06:00 UTC | workflow_dispatch -> checkout + uv sync
-> restaurar bronze.tar.gz (release data-latest)
-> f1-ingest f1db -> f1-ingest fastf1 --telemetry (continue-on-error)
-> dbt build (seeds, modelos, tests) --[fallo]--> subir logs, fin sin publicar
-> snapshot pack + notes
-> gh release upload (f1.duckdb, gold-parquet.zip, manifest.json, bronze.tar.gz al final)
-> [opcional] dbt docs -> GitHub Pages
release data-latest -> API (Render, refresco cada 6 h) -> web (Vercel)
release data-latest (bronze.tar.gz) -> siguiente ejecución (ciclo)
```

---

## 6. Diccionario de datos de la capa gold (resumen)

Convenciones: `*_id` = clave natural de F1DB; `*_ms` = milisegundos (`BIGINT`); `is_*` =
booleano; listas `VARCHAR[]`. Tipos tal como están en DuckDB.

### 6.1 Dimensiones

**`dim_driver`** (917 × 15) — PK `driver_id`.
`driver_id` VARCHAR · `name`, `first_name`, `last_name`, `full_name` VARCHAR · `abbreviation`
VARCHAR (código de 3 letras) · `permanent_number` VARCHAR · `gender` VARCHAR · `date_of_birth`,
`date_of_death` DATE · `place_of_birth` VARCHAR · `country_of_birth_name` VARCHAR ·
`nationality_country`, `nationality_demonym`, `nationality_alpha2` VARCHAR.

**`dim_constructor`** (187 × 6) — PK `constructor_id`.
`constructor_id`, `name`, `full_name`, `country_constructor`, `demonym_constructor`,
`alpha2_constructor` (todas VARCHAR).

**`dim_engine_manufacturer`** (78 × 5) — PK `engine_manufacturer_id`.
`engine_manufacturer_id`, `name`, `country_engine_manufacturer`, `demonym_engine_manufacturer`,
`alpha2_engine_manufacturer`.

**`dim_tyre_manufacturer`** (9 × 5) — PK `tyre_manufacturer_id`.
`tyre_manufacturer_id`, `name`, `country_tyre_manufacturer`, `demonym_tyre_manufacturer`,
`alpha2_tyre_manufacturer`.

**`dim_race`** (1 172 × 38) — PK `race_id`.
Carrera: `race_id` BIGINT, `season` BIGINT, `round` BIGINT, `race_date` DATE, `race_time_utc`
VARCHAR, `official_name`, `qualifying_format`, `sprint_qualifying_format` VARCHAR, `has_sprint`
BOOLEAN, `circuit_type`, `direction` VARCHAR, `course_length` DOUBLE, `turns` BIGINT, `laps` BIGINT,
`distance` DOUBLE, `scheduled_laps` BIGINT, `scheduled_distance` DOUBLE,
`drivers_championship_decider`, `constructors_championship_decider`, `is_completed`,
`is_season_final_race` BOOLEAN. Circuito: `circuit_id`, `circuit_name`, `circuit_full_name`,
`circuit_place_name`, `circuit_latitude`/`circuit_longitude` DOUBLE, `circuit_country`,
`circuit_demonym`, `circuit_alpha2`, `circuit_alpha3`. Gran Premio: `grand_prix_id`,
`grand_prix_name`, `grand_prix_full_name`, `grand_prix_short_name`, `grand_prix_abbreviation`,
`grand_prix_country`, `grand_prix_demonym`.

### 6.2 Hechos

**`fact_race_result`** (28 211 × 32) — clave `(race_id, session_type, position_display_order)`.
| Columna | Tipo | Descripción |
|---|---|---|
| `race_id` | BIGINT | FK `dim_race` |
| `session_type` | VARCHAR | `RACE` / `SPRINT` |
| `position_display_order` | BIGINT | orden de presentación (incluye no clasificados) |
| `position_number` / `position_text` | BIGINT / VARCHAR | posición o motivo (DNF, DSQ, DNQ, NC…) |
| `driver_number` | VARCHAR | dorsal |
| `driver_id`, `constructor_id`, `engine_manufacturer_id`, `tyre_manufacturer_id` | VARCHAR | FK a dimensiones |
| `is_shared_car` | BOOLEAN | coche compartido (años 50) |
| `laps`, `time_ms`, `time_penalty_ms`, `gap_ms`, `gap_laps`, `interval_ms` | BIGINT | vueltas y tiempos |
| `reason_retired` | VARCHAR | motivo de abandono |
| `points` | DOUBLE | puntos (0 si nulo) |
| `grid_position` / `grid_position_text` / `positions_gained` / `pit_stops` | BIGINT / VARCHAR / BIGINT / BIGINT | parrilla, ganancia y nº de paradas |
| `is_pole_position`, `is_fastest_lap`, `is_driver_of_the_day`, `is_grand_slam`, `is_win`, `is_podium` | BOOLEAN | indicadores |
| `is_corrected` | BOOLEAN | fila corregida por `race_data_corrections` |
| `overridden_columns`, `disputed_columns` | VARCHAR[] | columnas corregidas / disputadas (`race_data_overrides`) |

**`fact_qualifying_result`** (27 506 × 19) — clave `(race_id, session_type, position_display_order)`.
`session_type` (`QUALIFYING`/`SPRINT_QUALIFYING`), posición (`position_display_order`,
`position_number`, `position_text`), `driver_number`, 4 FK, `time_ms`, `q1_ms`, `q2_ms`, `q3_ms`,
`laps`, `best_time_ms`, `gap_to_pole_pct` DOUBLE, `is_pole`, `overridden_columns`.

**`fact_pit_stops`** (22 535 × 11) — grano: parada.
`race_id`, `position_display_order`, `driver_number`, 4 FK, `stop_number`, `lap_number`,
`time_ms` BIGINT, `time_seconds` DOUBLE.

**`fact_pit_lane_passes`** (24 271 × 7) — clave `(race_id, driver_id, driver_number, lap_number)`.
`race_id`, `driver_id`, `driver_number`, `lap_number`, `stop_number` (si `pass_type =
pit_stop`), `pass_type` (6 valores, §3.4), `source`.

**`fact_laptimes`** (1 270 260 × 35) — clave `(race_id, driver_id, driver_number, lap_number)`.
| Grupo | Columnas |
|---|---|
| Claves | `race_id` BIGINT, `driver_id` VARCHAR, `driver_number` VARCHAR, `lap_number` BIGINT |
| Medidas | `position` BIGINT, `lap_time_ms` BIGINT, `gap_to_leader_ms` HUGEINT, `sector_1_ms`/`sector_2_ms`/`sector_3_ms` BIGINT, `speed_trap_kmh` DOUBLE |
| Neumático | `stint` INTEGER, `tyre_compound` (tal como lo publica la fuente), `tyre_compound_pirelli` (C0–C6 o comercial), `tyre_compound_relative` (HARD/MEDIUM/SOFT/INTERMEDIATE/WET desde 2019), `tyre_age_laps` (FastF1 si existe), `formula1db_tyre_age_laps` |
| Estado de pista | `is_pit_in_lap`, `is_pit_out_lap`, `is_yellow_flag`, `is_safety_car`, `is_virtual_safety_car`, `is_red_flag`, `is_deleted`, `is_accurate` |
| Linaje y calidad | `source` (`formula1db`/`fastf1`/`ergast`), `validation_status` (5 valores), `confirmed_by` VARCHAR[], `corrections` VARCHAR[], `original_lap_time_ms`, `original_position`, `original_lap_number`, `lap_numbering_status` (5 valores), `is_incomplete_lap`, `quality_status` (5 valores + `unmatched_driver`) |

**`fact_quali_telemetry`** (518 699 × 15) — grano: muestra cada 10 m.
`race_id`, `driver_id`, `driver_code`, `driver_number`, `tyre_compound`, `lap_time_ms`,
`distance_m`, `speed_kmh`, `rpm` DOUBLE, `gear` BIGINT, `throttle_pct` DOUBLE, `is_braking`
BOOLEAN, `drs` BIGINT, `x`, `y` DOUBLE.

**`fact_driver_standing`** (21 541 × 8) — grano: piloto tras cada carrera.
`race_id`, `position_display_order`, `position_number`, `position_text`, `driver_id`, `points`
DOUBLE, `positions_gained`, `championship_won`.

**`fact_constructor_standing`** (10 654 × 9) — grano: constructor (+motor) tras cada carrera.
Ídem con `constructor_id` y `engine_manufacturer_id`.

### 6.3 Agregados

**`agg_driver_career`** (917 × 23): `driver_id`, `name`, `nationality_country`,
`nationality_alpha2`, `championships`, `best_championship_position`, `first_season`,
`last_season`, `race_entries`, `race_starts`, `wins`, `podiums`, `pole_positions`,
`fastest_laps`, `grand_slams`, `driver_of_the_day`, `sprint_wins`, `points` DOUBLE,
`championship_points` DOUBLE, `best_race_result`, `laps_completed` HUGEINT, `win_rate_pct`,
`podium_rate_pct` DOUBLE.

**`agg_constructor_career`** (187 × 16): `constructor_id`, `name`, `country_constructor`,
`alpha2_constructor`, `championships`, `best_championship_position`, `first_season`,
`last_season`, `race_entries`, `wins`, `podiums`, `podium_races`, `one_two_finishes`,
`pole_positions`, `fastest_laps`, `race_points` DOUBLE.

**`agg_driver_season`** (1 681 × 15): `season`, `driver_id`, `driver_name`, `constructor_id`,
`constructor_name`, `championship_position`, `championship_position_text`, `points`,
`championship_won`, `races`, `wins`, `podiums`, `pole_positions`, `fastest_laps`, `best_result`.

**`agg_teammate_h2h`** (13 530 × 13): `season`, `constructor_id`, `driver_id`, `teammate_id`,
`races_together`, `race_ahead`, `race_ahead_pct`, `qualifyings_together`, `quali_ahead`,
`quali_ahead_pct`, `points`, `teammate_points`, `points_difference`.

---

## 7. Propuestas de mejora

Ordenadas por relación beneficio/esfuerzo. Cada una indica el problema observado y la
justificación.

### 7.1 Higiene y robustez inmediata (esfuerzo bajo)

1. **Eliminar la tabla huérfana `silver.int_formula1db_laps_validated`** (1,2 M filas, sin modelo).
   dbt no borra relaciones que ya no gestiona; ocupa espacio en el almacén y confunde al explorar.
   Añadir un `on-run-end` o una macro de limpieza de relaciones no gestionadas.
2. **Rutas absolutas o `PRAGMA`/`dbt-duckdb` `external_root` en las sources**: las vistas `stg_*`
   guardan `../data/bronze/...` y solo funcionan si el directorio de trabajo es `transform/`
   (comprobado: fuera de él fallan). Resolver la ruta con `env_var` absoluta o materializar las
   vistas que se consulten fuera de dbt.
3. **Tests de clave que faltan**: `unique_combination` para `fact_pit_stops (race_id, driver_id,
   stop_number)`, `fact_driver_standing (race_id, driver_id)`,
   `fact_constructor_standing (race_id, constructor_id, engine_manufacturer_id)`, las cuatro
   tablas `agg_*` y `fact_quali_telemetry`; `relationships` para `race_id` de todos los hechos (hoy
   solo se prueba en `fact_race_result`) y para `constructor_id`/`engine_manufacturer_id` de
   `fact_qualifying_result` y `fact_pit_stops`. `accepted_values` para
   `fact_qualifying_result.session_type` y `fact_laptimes.lap_numbering_status`.
4. **Documentar `marts/metrics` y `staging`** en YAML (hoy no tienen `.yml`): descripciones de
   columnas para que `dbt docs` y la API tengan un catálogo completo.
5. **Tipos**: `gap_to_leader_ms` y `laps_completed` salen como `HUGEINT` (efecto de sumas y
   restas de ventanas); convertir a `BIGINT`. `race_time_utc` es VARCHAR; `points` DOUBLE podría ser
   `DECIMAL(6,2)` (medios puntos históricos).
6. **Declarar fuentes no usadas o retirarlas**: `formula1db.race_entries` está declarada y no se
   usa; 18 tablas de F1DB y 3 de Ergast están en bronze sin source. O se modelan (chasis,
   inscripciones) o se documenta que se conservan solo por completitud.

### 7.2 Gobierno del modelo (esfuerzo medio)

7. **Contratos de modelo dbt** (`config: contract: {enforced: true}`) en los 17 modelos gold, con
   `data_type` y `constraints` (`primary_key`, `not_null`). Gold es la interfaz pública de la API y
   del zip de Parquet: un contrato impide que un cambio de tipo o el borrado de una columna llegue a
   producción sin que falle el build. Complementar con **versiones de modelo** (`versions:`) si se
   rompe la interfaz.
8. **Freshness de sources**: `loaded_at_field` a partir de `_metadata.json` (o una columna
   `_loaded_at` que la ingesta añada al Parquet) y `freshness: warn_after: 8 days` para F1DB y
   FastF1; así el pipeline avisa si la ingesta lleva una semana sin datos nuevos.
9. **Nomenclatura según la guía de estilo de dbt Labs**:
   - Separar los YAML por carpeta y tipo (`_f1db__models.yml`, `_fastf1__sources.yml`…): hoy todas
     las sources están en `staging/f1db/_f1db__sources.yml`.
   - Prefijo por fuente también en los intermediate (`int_formula1db__laps_aligned`,
     `int_laps__merged`) y verbo en el nombre (`int_race_data__corrected`).
   - Plural consistente en marts (`fact_pit_stops` frente a `fact_race_result`); dbt Labs recomienda
     nombres de entidad en plural (`fct_race_results`, `dim_drivers`) o, si se mantiene la
     convención del TFG, aplicarla sin excepciones.
   - Mover los unit tests de `_quality__models.yml` al YAML del modelo que prueban.
10. **Exposures** (`exposures:`) para la API, la web y el zip de Parquet: el DAG de `dbt docs`
    mostraría qué endpoints dependen de cada tabla y el análisis de impacto sería automático.
11. **Tests de rango y consistencia adicionales** (paquete `dbt_utils`/`dbt_expectations`):
    `lap_time_ms` entre 30 s y 3 h salvo bandera roja; `sector_1+2+3 ≈ lap_time_ms` (±5 ms);
    `points ≥ 0`; `gap_to_pole_pct ≥ 0`; recuento de vueltas por carrera ≤ `dim_race.laps` + 1;
    monotonía de `race_time_ms`; `expression_is_true` para `is_podium → position_number ≤ 3`.
    Pasar `assert_standings_points_match_results` a `error` si lleva tiempo sin avisos.
12. **Seed de mapeos explícita** para códigos de neumático de formula1db (`H`, `SS`, `US`…) y
    códigos de `TrackStatus`, hoy embebidos en `CASE` dentro del staging: una seed documentada es
    más fácil de revisar y de testear (`accepted_values` sobre el compuesto).

### 7.3 Evolución del modelo dimensional (esfuerzo medio-alto)

13. **Dimensión de sesión (`dim_session`)**: hoy `session_type` es un atributo degenerado con
    vocabularios distintos por hecho (`RACE`/`SPRINT`, `QUALIFYING`/`SPRINT_QUALIFYING`) y la
    telemetría/vueltas no indican sesión. Una dimensión `(race_id, session_type)` con fecha y hora
    de sesión, formato (Q1-Q3, sesión única, sprint shootout) y estado permitiría unir hechos de
    distintas sesiones y preparar la ingesta de libres y sprint de FastF1.
14. **Dimensión de fecha/temporada (`dim_date` / `dim_season`)**: `dim_race` hace de dimensión
    temporal de grano carrera, pero no hay atributos de temporada (reglamento de puntos, nº de
    carreras, era técnica, campeón) ni calendario. `dim_season` (77 filas en F1DB `season`)
    facilitaría análisis por eras y normalizar puntos entre sistemas de puntuación.
15. **Dimensión de estado/resultado** (`dim_result_status`) a partir de `position_text` y
    `reason_retired`: agrupar DNF mecánico/accidente/DSQ permite análisis de fiabilidad sin
    expresiones regulares en la web. Revisa la decisión del TFG de mantenerlos degenerados, que
    tenía sentido en Power BI (tamaño del modelo) pero no en DuckDB.
16. **SCD tipo 2 para pertenencia a equipo y datos cambiantes**: la afiliación piloto-equipo ya está
    en los hechos (correcto), pero atributos como el nombre comercial del constructor
    (`constructor_chronology` de F1DB), el motor por temporada o los datos del piloto cambian con el
    tiempo y hoy se sobrescriben. Opciones: `dbt snapshot` (estrategia `check`) sobre las
    dimensiones para conservar el historial entre releases de F1DB, o construir SCD2 a partir de
    las tablas `season_entrant_*` y `constructor_chronology` que ya están en bronze.
17. **Claves sustitutas** (`dbt_utils.generate_surrogate_key`) para los hechos con clave
    compuesta (`race_result_sk`, `lap_sk`…) y, si se adopta SCD2, para las dimensiones
    (`driver_sk` + `valid_from/valid_to`). Mejora los joins en herramientas BI (Power BI necesita
    relaciones de una columna) y desacopla el modelo de los *slugs* de F1DB, que pueden cambiar.
18. **Hecho de puente / factless para coches compartidos** (`bridge_shared_car`): hoy se resuelven
    con `is_shared_car` y `count(distinct …)`; una tabla puente coche–pilotos haría explícita la
    semántica.
19. **Hecho de clasificación final de temporada** (`fact_season_driver_standing`,
    `fact_season_constructor_standing`): los agregados leen `stg_f1db__season_*_standings`
    directamente desde staging, lo que rompe la regla de dbt de que marts dependan de
    intermediate/marts y deja esos datos fuera de gold (la API no puede exponerlos sin pasar por
    `agg_driver_season`).

### 7.4 Rendimiento y operación

20. **Materialización incremental** de `int_laptimes`, `fact_laptimes`, `fact_quali_telemetry` y
    `stg_fastf1__*` (estrategia `delete+insert` por `race_id`): el histórico 1950–2024 de
    formula1db y Ergast no cambia; solo cambian las carreras nuevas de FastF1 y las correcciones.
    Con `is_incremental()` y un `--full-refresh` periódico (o cuando cambien seeds), el build
    semanal dejaría de reprocesar 1,27 M de vueltas. Hoy el build completo tarda ≈22 s, así que el
    beneficio es más de escalabilidad (p. ej. si se incorporan libres o telemetría de carrera) que
    inmediato.
21. **Particionado en la exportación**: `gold-parquet.zip` contiene un fichero por tabla; para
    `fact_laptimes` y `fact_quali_telemetry` convendría `PARTITION_BY (season)` (Hive), lo que
    permite a Power BI/DuckDB/Polars leer solo las temporadas necesarias y hacer cargas
    incrementales. Aplicar lo mismo en bronze a FastF1 ya se hace (temporada/ronda).
22. **Metadatos de carga en bronze**: añadir `_loaded_at`, `_source_file` y `_source_version` como
    columnas en cada Parquet (hoy solo en `_metadata.json`, y FastF1 no tiene), para trazabilidad
    fila a fila y para la *freshness* de dbt.
23. **Snapshot incremental de bronze**: `bronze.tar.gz` (51,7 MB) se reconstruye y sube entero
    cada semana; separar las fuentes estáticas (formula1db, Ergast: nunca cambian) de las dinámicas
    reduciría transferencia y riesgo.
24. **Validación del esquema de FastF1** en la ingesta: `union_by_name = true` tolera cambios de
    columnas entre versiones de la biblioteca sin avisar; un test de columnas esperadas
    (`dbt_expectations.expect_table_columns_to_contain_set`) sobre las sources detectaría cambios
    de la API.
25. **Semantic layer / métricas dbt**: las métricas de `agg_*` (victorias, podios, % por delante)
    podrían declararse como `metrics` de MetricFlow sobre los hechos para servirlas con distintos
    cortes (por temporada, circuito, equipo) sin multiplicar tablas agregadas; el proyecto ya genera
    `semantic_manifest.json` vacío.

### 7.5 Resumen de prioridades

| Prioridad | Propuestas |
|---|---|
| Alta (rápidas, reducen riesgo) | 1, 2, 3, 5, 7 |
| Media (gobierno y documentación) | 4, 8, 9, 10, 11, 12, 19, 22 |
| Evolución funcional | 13, 14, 15, 16, 17, 18, 25 |
| Escalabilidad | 20, 21, 23, 24 |
