# F1 Data Platform

Evolución del Trabajo Fin de Grado *«Formula 1 Dashboard»* (Antonio Sánchez de la Blanca Romero,
ESI – UCLM, 2024) desde un informe de Power BI hacia una **plataforma de datos completa**:
ingesta automatizada, modelo dimensional versionado y probado, API y web pública accesible.

- **Web:** https://f1-data-platform.vercel.app
- **API:** https://f1-data-api-h7c7.onrender.com (documentación interactiva en
  [`/docs`](https://f1-data-api-h7c7.onrender.com/docs))
- **Datos:** release [`data-latest`](https://github.com/AntonioSchez32/f1-data-platform/releases/tag/data-latest),
  actualizada cada lunes por el pipeline
- **Licencia:** código MIT; los datos conservan la licencia de cada fuente (F1DB, CC BY 4.0; Ergast, CC BY-NC-SA 3.0; cronometraje de la F1, © Formula One) (ver [Licencia y atribuciones](#licencia-y-atribuciones))

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
| 3 | Orquestación con GitHub Actions | ✅ |
| 4 | API FastAPI | ✅ |
| 5 | Web Next.js accesible | ✅ |
| 6 | Despliegue (Render + Vercel) | ✅ |
| 7 | Analítica avanzada (degradación de neumáticos, predicción) | ⏳ |

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

## Pipeline (GitHub Actions)

Dos workflows en `.github/workflows/`:

| Workflow | Cuándo | Qué hace |
|---|---|---|
| `pipeline.yml` | Lunes a las 06:00 UTC (tras cada GP) y a mano (*Run workflow*) | Restaura el último snapshot y la copia de las fuentes estáticas, carga F1DB y la temporada en curso de FastF1, ejecuta `dbt build`, prueba la API contra el resultado y publica el snapshot en una release fechada y en `data-latest`. Si falla una prueba de calidad o la prueba de humo, no se publica nada |
| `ci.yml` | Cada *push* a `main` y cada *pull request* | ruff y pytest; `dbt build` completo y prueba de humo de la API contra el último snapshot; imagen Docker (incluido el arranque sin GitHub); web |

**Snapshot de datos.** Los CSV del TFG (formula1db.com y Ergast) no están en el repositorio y
GitHub Actions no puede regenerarlos, así que cada ejecución parte de los datos publicados por la
anterior. Cada snapshot se publica en dos releases:

- **Fechada e inmutable** (`data-AAAA-MM-DD`; si hay dos ejecuciones el mismo día, la segunda
  lleva el número de ejecución detrás). No se modifica nunca y se conservan las 8 últimas (unas
  8 semanas); el pipeline borra las más antiguas.
- **`data-latest`**, que se sobrescribe en cada ejecución. Su `manifest.json` se sube el último y
  hace de puntero: indica la release fechada (`release_tag`) de la que la API descarga la base de
  datos, así que la API nunca lee ficheros a medio subir.

«Inmutable» es una convención del pipeline, que nunca sube ficheros a una release fechada ya
creada. La opción *Immutable releases* de GitHub (*Settings → General*) **no** debe activarse:
impediría actualizar `data-latest`.

Las dos contienen:

| Fichero | Contenido | Uso |
|---|---|---|
| `bronze.tar.gz` | Capa bronze completa | Entrada de la siguiente ejecución |
| `f1.duckdb` | Esquema `gold` y `quality.qa_summary` | Base de datos de la API (fase 4) |
| `gold-parquet.zip` | Tablas gold en Parquet | Power BI u otras herramientas |
| `manifest.json` | Versión de F1DB, carreras de FastF1, última carrera, calidad, SHA-256, recuento de filas y release fechada | Trazabilidad; puntero de la API |

**Copia de las fuentes estáticas.** formula1db.com y Ergast ya no se pueden volver a obtener, así
que además tienen su propia release, `bronze-static-v1` (`bronze-static.tar.gz`, unos 17 MB), que no
se sobrescribe nunca. El pipeline la crea en su primera ejecución a partir del snapshot y, a partir
de ahí, la restaura siempre encima del snapshot: aunque se publique un `data-latest` dañado, esas
fuentes no se pierden. Si `data-latest` falta o está incompleta, el pipeline parte de la última
release fechada.

**Prueba de humo.** Antes de publicar, `api/tests/smoke` arranca la API contra el `dist/f1.duckdb`
nuevo y comprueba `/health`, `/quality` (ningún control en FAIL), temporadas y clasificaciones, la
última carrera con resultados y vueltas, carreras históricas (Baréin 2024, Mónaco 1950) y que
ninguna tabla haya desaparecido ni perdido más del 2 % de sus filas respecto al snapshot anterior.
Los cambios intencionados (eliminar una tabla, cambiar su grano) se declaran en
`api/tests/smoke/cambios_esperados.json` (`{"removed": [...], "shrink": {"gold.tabla": 0.3}}`) en el
mismo cambio que los introduce, y se vacían cuando la versión nueva ya está publicada. En una
emergencia, el input `allow_shrink` del pipeline omite solo esa comprobación (queda anotado en el
resumen de la ejecución).

```bash
uv run f1-ingest snapshot pack --out dist --tag data-2026-10-05   # genera el snapshot tras dbt build
uv run f1-ingest snapshot pack-static --out dist                  # copia de las fuentes estáticas
uv run f1-ingest snapshot restore bronze.tar.gz                   # restaura bronze en data/
uv run f1-ingest snapshot restore bronze-static.tar.gz --replace  # sustituye formula1db y ergast por la copia
uv run f1-ingest snapshot notes dist/manifest.json
F1_SMOKE_DB=dist/f1.duckdb F1_SMOKE_PREVIOUS_MANIFEST=manifest-anterior.json uv run pytest api/tests/smoke
```

**Volver a una versión anterior.** Si se publica un snapshot malo, se descargan los ficheros de la
release fechada buena y se suben a `data-latest`, con `manifest.json` el último:
`gh release download data-AAAA-MM-DD --dir buena`,
`gh release upload data-latest buena/f1.duckdb buena/gold-parquet.zip buena/bronze.tar.gz --clobber`
y, al final, `gh release upload data-latest buena/manifest.json --clobber`. Después hay que borrar
la release fechada mala (`gh release delete data-AAAA-MM-DD --cleanup-tag`): si no, sería la más
reciente y el pipeline podría partir de ella. La API carga la versión buena en la siguiente
comprobación (6 horas como mucho) y el próximo pipeline parte de ella.

**Puesta en marcha en GitHub (una sola vez, desde el equipo que tiene los datos del TFG):**

1. Crear el repositorio en GitHub y subir el código (`git remote add origin …` y `git push -u origin main`).
2. Generar el snapshot inicial (después de un `dbt build` correcto):
   `uv run f1-ingest snapshot pack --out dist` y
   `uv run f1-ingest snapshot notes dist/manifest.json > dist/notes.md`.
3. Crear la release `data-latest` con los cuatro ficheros de `dist/`: en GitHub, *Releases →
   Draft a new release*, etiqueta `data-latest`, o con la CLI:
   `gh release create data-latest dist/bronze.tar.gz dist/f1.duckdb dist/gold-parquet.zip dist/manifest.json --title "Datos F1" --notes-file dist/notes.md --latest=false`.
   La release `bronze-static-v1` y las fechadas las crea el pipeline.
4. Opcional, documentación de dbt (catálogo y linaje) en GitHub Pages: *Settings → Pages →
   Source: GitHub Actions* y la variable de repositorio `PUBLISH_DOCS = true`.

Si el repositorio es público, las releases también lo son: incluyen los datos de formula1db.com
(con permiso del autor para divulgación). GitHub desactiva los workflows programados de un
repositorio público tras 60 días sin actividad; se reactivan desde la pestaña *Actions*.

## API (FastAPI)

API de solo lectura sobre el modelo gold (`api/`). Documentación interactiva en `/docs`.

```bash
uv run uvicorn api.app.main:app --reload   # desarrollo, en http://localhost:8000/docs
uv run pytest api/tests                 # pruebas sobre datos de ejemplo (api/tests/fixtures)
```

| Grupo | Endpoints |
|---|---|
| Temporadas | `/seasons`, `/seasons/{año}`, `/seasons/{año}/standings/drivers`, `…/constructors`, `…/progression` |
| Carreras | `/races/{id}`, `…/results`, `…/qualifying`, `…/laps`, `…/stints`, `…/pitstops`, `…/pit-lane-passes`, `…/telemetry` |
| Pilotos | `/drivers`, `/drivers/{id}`, `…/seasons`, `…/results`, `…/teammates` |
| Constructores | `/constructors`, `/constructors/{id}`, `…/seasons` |
| Otros | `/records/drivers`, `/records/constructors`, `/circuits`, `/quality`, `/health` |

**Datos.** En local sirve `dist/f1.duckdb` o, si no existe, `data/gold/f1.duckdb`. Desplegada,
lee el `manifest.json` de `data-latest`, descarga `f1.duckdb` de la release fechada que indica,
comprueba su SHA-256 y cada pocas horas mira si hay una versión nueva; si la hay, la carga sin
reiniciar. Las descargas se reintentan tres veces ante fallos transitorios de GitHub.

**Si GitHub no responde al arrancar**, la API sirve la última copia verificada que tenga: una
descargada antes (`F1_API_DATA_DIR`) o la copia de respaldo que la imagen Docker trae desde su
construcción (`F1_API_SEED_DIR`). Lo indica en `/health` (`status: degraded`, `refresh.source:
copy`) y vuelve a intentarlo cada 10 minutos hasta conseguirlo. Sin ninguna copia, no arranca.

**`/health`** consulta la base de datos (503 si no responde) y devuelve la versión de los datos, su
fecha de generación (`data.generated_at`), la release fechada de la que proceden, la última
carrera con resultados y el estado del refresco: origen de los datos (`release`, `copy` o `file`),
arranque, última comprobación, última comprobación correcta y último error.

| Variable | Uso |
|---|---|
| `F1_DATA_REPO` | Repositorio con la release de datos, p. ej. `usuario/f1-data-platform` |
| `F1_GITHUB_TOKEN` | Solo si el repositorio es privado: token de solo lectura (*fine-grained*, *Contents: Read only*). Con el repositorio público se usan los enlaces directos de la release |
| `F1_DATA_TAG` | Release de datos (por defecto `data-latest`) |
| `F1_API_REFRESH_HOURS` | Cada cuántas horas busca datos nuevos (por defecto 6; 0 = nunca) |
| `F1_API_CORS_ORIGINS` | Orígenes web permitidos, separados por comas (por defecto `http://localhost:3000`) |
| `F1_API_CACHE_MAX_AGE` | Segundos de caché HTTP (por defecto 600) |
| `F1_API_DB_PATH` | Servir un fichero concreto (sin actualizaciones) |
| `F1_API_DATA_DIR` | Carpeta de las versiones descargadas (en la imagen, `/data`) |
| `F1_API_SEED_DIR` | Copia de respaldo de solo lectura (en la imagen, `/opt/f1-seed`) |

**Caché.** Cada respuesta lleva una ETag derivada de la versión de los datos y de la URL: los
navegadores y las CDN revalidan con `If-None-Match` y reciben 304 sin repetir la consulta. Al
publicarse datos nuevos cambian todas las ETag.

**Docker.** `docker build -f api/Dockerfile --build-arg F1_DATA_REPO=usuario/f1-data-platform -t f1-api .`
y `docker run -p 8000:8000 -e F1_DATA_REPO=… f1-api`. La imagen solo instala DuckDB, FastAPI y
Uvicorn. Con `F1_DATA_REPO` en la construcción, incluye la copia de respaldo de los datos (si la
descarga falla, se construye sin ella). El token de un repositorio privado no se pasa a la
construcción, para no dejarlo en la imagen: en ese caso no hay copia de respaldo. La CI construye
la imagen, la arranca contra los datos publicados y comprueba que arranca con la copia cuando la
release no está disponible.

## Web (Next.js)

Web pública en español e inglés (`web/`), construida sobre la API. Reproduce las páginas del informe
de Power BI del TFG y añade algunas nuevas:

| Página del TFG | Ruta |
|---|---|
| Inicio: eventos disputados por país (Fig. 5.23) | `/es` (mapa por país o por circuito, con rango de temporadas) |
| Récords de pilotos y constructores (5.24, 5.25) | `/es/records` (títulos y «más laureados», filtrables por temporadas) |
| Resultados de temporada (5.26) | `/es/seasons/{año}` (campeones, clasificaciones, evolución y calendario) |
| Rendimiento en clasificación (5.27) | `/es/races/{id}/qualifying` (pilotos o constructores) |
| Vuelta a vuelta (5.28) | `/es/races/{id}/lap-chart` |
| Neumáticos (5.29) | `/es/races/{id}/tyres` (estrategia y matriz vuelta a vuelta) |
| Tiempos y ritmo de carrera (5.30, 5.31) | `/es/races/{id}/pace` (líneas por vuelta y gráfico de violín) |
| Paradas en boxes (5.32) | `/es/races/{id}/pitstops` (media por constructor y detalle) |
| Detalle de piloto (5.33) | `/es/drivers/{id}` (cifras, puntos por temporada y comparativas con compañeros) |
| Nuevas | telemetría de clasificación (2024+), constructores, calidad de los datos |

```bash
cd web
npm ci
npm run dev                  # http://localhost:3000 (necesita la API en F1_API_URL, por defecto :8000)
npm run build && npm start   # producción
npx playwright test          # pruebas de extremo a extremo y de accesibilidad (axe, WCAG 2.2 AA)
BASE_URL=https://f1-data-platform.vercel.app npx playwright test   # las mismas, contra la web publicada
npm run gen:api              # regenera los tipos TypeScript desde el contrato OpenAPI de la API
```

**Accesibilidad.**
- Cada gráfico lleva un resumen en texto y sus datos en una tabla desplegable.
- Paleta segura para daltonismo; las series también se distinguen por marcador, trazo o letra (los neumáticos, por ejemplo), no solo por color.
- Navegación completa por teclado, con enlace para saltar al contenido y foco visible.
- Tema claro y oscuro según el sistema, y respeto por el movimiento reducido.
- Los filtros son formularios normales, así que funcionan sin JavaScript.
- La CI ejecuta axe sobre todas las páginas, en los dos temas.

## Despliegue

| Pieza | Servicio | Configuración |
|---|---|---|
| Datos | GitHub Releases (`data-latest`, `data-AAAA-MM-DD` y `bronze-static-v1`) | Los publica el pipeline cada lunes |
| API | [Render](https://render.com), plan gratuito | `render.yaml` (Blueprint) con `api/Dockerfile` |
| Web | [Vercel](https://vercel.com), plan Hobby | Proyecto con *Root Directory* `web` y la variable `F1_API_URL` |

Pasos (una sola vez):

1. **API en Render.** *New → Blueprint*, conectar el repositorio de GitHub y aceptar
   `render.yaml`. Al terminar, Render da una dirección `https://f1-data-api-….onrender.com`;
   comprobar que `/health` responde.
2. **Web en Vercel.** *Add New → Project*, importar el repositorio y poner *Root Directory* `web`.
   En *Environment Variables*, `F1_API_URL` con la dirección de la API (sin barra final). *Deploy*.
3. **CORS.** En Render, rellenar `F1_API_CORS_ORIGINS` con la dirección de la web de Vercel.

A partir de ahí todo se actualiza solo:
- Cada `git push` a `main` redespliega la web y, si cambia `api/`, también la API.
- Cada lunes el pipeline publica datos nuevos; la API los carga en menos de 6 horas y la web
  renueva sus páginas cada hora.

El plan gratuito de Render duerme la API tras 15 minutos sin visitas, y su disco se borra en cada
arranque. Render pasa las variables del servicio como argumentos de construcción, así que la imagen
lleva la copia de respaldo de los datos: si sigue siendo la versión publicada, la API arranca sin
descargar nada, y si GitHub falla, arranca con ella. La copia se renueva cada vez que se
redespliega la API; si ya es antigua, al arrancar se descargan los datos publicados (unos 55 MB).
La primera petición tras dormirse tarda lo que tarde el arranque (el log de la API registra su
duración). La web espera hasta 60 segundos y conserva en caché las páginas ya generadas, así que
solo lo nota quien abre una página que nadie ha visitado en la última hora.

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

## Licencia y atribuciones

- **Código**: [MIT](LICENSE).
- **Datos publicados** (releases de datos, API y web): no tienen una licencia única. Cada parte
  conserva la de su origen:

| Parte de los datos | Licencia | Dónde está |
|---|---|---|
| [F1DB](https://github.com/f1db/f1db) y lo derivado de él (resultados, clasificación, paradas, campeonatos, pilotos, equipos y circuitos) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Todo el modelo gold salvo lo indicado abajo |
| Ergast (volcado de 2022) | [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/): no comercial y compartir igual | `bronze/ergast` en `bronze.tar.gz`; vueltas sueltas de relleno (`source = 'ergast'`) y contraste (`validation_status`) |
| Cronometraje de la F1 obtenido con [FastF1](https://github.com/theOehrly/Fast-F1) (la biblioteca es MIT) | © Formula One World Championship Limited (F1 Live Timing); sin licencia abierta | Vueltas, neumáticos, estado de pista y telemetría desde 2018. Se redistribuye con fines académicos y no comerciales |
| formula1db.com | Con permiso de su autor para divulgación; sin licencia abierta | Vueltas históricas recogidas durante el TFG (2024); no se vuelven a extraer |
| Documentos de la FIA | © FIA | Evidencia para resolver discrepancias; no se redistribuyen |

Si se incorporan datos de Jolpica-F1 u OpenF1 (CC BY-NC-SA 4.0), la parte derivada de ellos se
publicará con esa misma licencia, no comercial. Al reutilizar los datos, hay que citar
«F1 Data Platform» y la fuente original de cada parte.

Formula 1, F1 y las marcas relacionadas pertenecen a Formula One Licensing B.V. Este es un proyecto
académico no oficial, sin relación con la Fórmula 1 ni con la FIA.

## Estructura

```
.github/     workflows de GitHub Actions (pipeline semanal y CI)
ingestion/   cargadores Python, snapshots de datos y CLI `f1-ingest`
scripts/     utilidades puntuales (generación de seeds de correcciones)
docs/        revisión de divergencias entre fuentes, informe de situación y plan de acción
transform/   proyecto dbt (staging → intermediate → marts) con seeds y tests
api/         API FastAPI (app/, tests/, Dockerfile)
web/         web Next.js (src/app, componentes de gráficos, diccionarios es/en, pruebas Playwright)
tests/       tests unitarios de la ingesta y los snapshots (pytest)
data/        bronze/, gold/, cache/ — no se versiona, se regenera con el pipeline
```
