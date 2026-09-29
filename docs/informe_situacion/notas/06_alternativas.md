# 06 · Estructuras y arquitecturas alternativas

> Nota de trabajo para el informe de situación (29/09/2026). Recoge qué alternativas existen a la
> estructura y la arquitectura actuales de `f1-data-platform`, con fuentes, y propone qué adoptar,
> qué considerar y qué descartar **para este proyecto en concreto**: una sola persona, coste 0 €,
> fines de portfolio y TFG, datos que cambian una vez por semana.
>
> Leyenda de la recomendación: **ADOPTAR** (merece la pena ya), **CONSIDERAR** (útil si se dan
> ciertas condiciones o como ampliación), **DESCARTAR** (no compensa aquí).
> Leyenda de esfuerzo: S (horas), M (1–3 días), L (una semana o más).

---

## 0. Resumen ejecutivo

1. **La arquitectura actual está bien planteada para su contexto.** Monorepo, uv, dbt-duckdb con
   capas medallion y modelo Kimball, snapshot semanal en GitHub Releases, API de solo lectura y
   web con ISR: es lo que recomiendan las guías de referencia para un proyecto analítico pequeño
   (véanse §2 y §3). No hay razones de peso para una reescritura.
2. **El punto débil es el serving**: la web depende de una API en el plan gratuito de Render
   (se duerme a los 15 min y tarda ~1 min en despertar) para servir datos que **solo cambian los
   lunes**. Es la pieza con más riesgo y la que más alternativas razonables tiene (§5).
3. **La alternativa de más valor por esfuerzo** es publicar desde el pipeline una
   **«API estática»** (JSON precalculado por recurso, o Parquet por tabla) en un CDN gratuito y
   hacer que Next.js lea de ahí; la API FastAPI se mantiene como servicio público y documentación
   (OpenAPI), pero deja de estar en el camino crítico de la web. Detalle en §5.3 y arquitectura B
   en §8.
4. **Mejoras de estructura baratas**: declarar como `sources` de dbt todas las entradas bronze (hoy
   solo F1DB lo está), subcarpetas en `intermediate/`, un `justfile` (o `Taskfile`) en la raíz
   como índice de comandos, y releases de datos inmutables con fecha además de `data-latest`.
5. **Orquestador (Dagster/Prefect/Airflow/Kestra)**: CONSIDERAR solo como ejercicio de portfolio; para
   este volumen, GitHub Actions es suficiente. Hay que tener en cuenta que en julio de 2026
   **Prefect compró Dagster Labs** (§4). Lo que sí se recomienda es disparar el pipeline
   **según el calendario de F1** en vez de un cron fijo de lunes.
6. **Frente**: mantener ECharts (con su módulo `aria` y los *decals*) y el i18n propio, que sigue
   la guía oficial de Next.js; Observable Plot es la alternativa más accesible si se rehace algún
   gráfico sencillo en SVG (§6).
7. **dbt v2** (motor Fusion en Rust, con adaptador DuckDB integrado) acaba de publicarse. El
   adaptador DuckDB figura aún como *beta*: CONSIDERAR la migración más adelante, no ahora (§2.3).

---

## 1. Punto de partida medido en el repositorio (28/09/2026)

| Elemento | Situación actual |
|---|---|
| Repositorio | Monorepo: `ingestion/`, `transform/`, `api/`, `web/`, `scripts/`, `tests/`, `docs/`, `.github/workflows/` (`pipeline.yml`, `ci.yml`), `render.yaml` |
| Python | **Un único** `pyproject.toml` (paquete `f1-data-platform`, wheel con `ingestion` y `api` en *layout* plano) y **grupos de dependencias** `ingest`, `api`, `transform` y `dev`; la imagen Docker de la API instala solo `--group api` |
| dbt | `staging/<fuente>/stg_<fuente>__<entidad>.sql` (f1db, fastf1, formula1db, ergast), `intermediate/int_*.sql` (10 modelos, sin subcarpetas), `marts/core` (5 dimensiones y 8 hechos) y `marts/metrics` (4 `agg_*`), `quality/qa_*` (7 modelos); esquemas `silver`, `gold` y `quality`; seeds de correcciones |
| Fuentes dbt | Solo F1DB está declarada en `_f1db__sources.yml`; los modelos `stg_fastf1__*`, `stg_formula1db__*` y `stg_ergast__*` leen Parquet directamente |
| Artefactos de datos | `f1.duckdb` **54,5 MB**; `gold-parquet.zip` 28 MB (17 tablas; `fact_laptimes` 12,6 MB y 1,27 M filas, `fact_quali_telemetry` 14,1 MB y 0,52 M filas; el resto < 0,4 MB cada una); `bronze.tar.gz` 51,7 MB. Nota: el tamaño real del DuckDB es ~55 MB, no ~200 MB |
| Orquestación | `pipeline.yml`: cron `0 6 * * 1` + `workflow_dispatch` con temporadas y `force_f1db`; restaura bronze de la release, ingesta F1DB y FastF1, `dbt build`, publica en `data-latest` con `--clobber` |
| API | FastAPI + DuckDB solo lectura; descarga `f1.duckdb` de la release al arrancar y cada 6 h; ETag por versión de datos; Render free (Frankfurt) |
| Web | Next.js 16.3, App Router, `src/app/[lang]/…` (16 `page.tsx`), `lib/api/client.ts` con `fetch(..., { next: { revalidate: 3600 } })`, ECharts 6 + d3-geo, diccionarios JSON propios (`getDictionary`), Playwright + axe; 8 páginas usan `searchParams` (filtros como formularios GET) |

---

## 2. Estructura del repositorio

### 2.1 Monorepo frente a multirrepo

| Opción | Ventajas | Inconvenientes | Coste | Esfuerzo | Riesgo | Recomendación |
|---|---|---|---|---|---|---|
| **Monorepo actual** | Un solo sitio para el TFG; cambios atómicos entre contrato OpenAPI, API y web (`npm run gen:api`); una CI; un README que cuenta la historia completa | CI y despliegues deben filtrar por rutas (ya se hace: `buildFilter` en `render.yaml`, *Root Directory* `web` en Vercel) | 0 € | — | Bajo | **ADOPTAR (mantener)** |
| Multirrepo (`f1-data`, `f1-api`, `f1-web`) | Permisos y versiones independientes; cada repo más pequeño | Coordinar versiones del contrato entre repos; tres CI; se diluye la narrativa del portfolio; el cron del repo de datos se desactiva a los 60 días sin *commits* si es público | 0 € | M | Medio | **DESCARTAR** |

Para una persona y un producto con un contrato interno (OpenAPI) que cambia a la vez en API y web,
el monorepo es la opción natural; el problema típico de los monorepos (tiempos de CI, propiedad
de código) no aparece a esta escala.

### 2.2 Layout de Python y uv

Situación: paquetes `ingestion/` y `api/` en la raíz (*flat layout*), un único proyecto uv con
grupos de dependencias. Es una solución deliberada y funciona: la imagen de la API solo instala
`duckdb`, `fastapi` y `uvicorn`.

Alternativas:

- **src-layout** (`src/f1_platform/ingestion`, `src/f1_platform/api`). Evita importar por accidente
  el código del directorio de trabajo en lugar del paquete instalado y es lo que genera
  `uv init --package`. Aquí el beneficio es pequeño porque no se publica en PyPI.
  → **CONSIDERAR** (S) solo si se reorganiza por otro motivo.
- **uv workspaces**: cada componente con su `pyproject.toml` (p. ej. `packages/ingestion`,
  `apps/api`, y quizá un `packages/core` con utilidades comunes), un único `uv.lock` y
  `uv run --package api …`. La documentación de uv lo recomienda para «varios paquetes
  interrelacionados en un mismo repositorio» y lo desaconseja cuando los miembros tienen
  requisitos en conflicto o se quiere un entorno virtual separado por miembro; además impone un
  único `requires-python` para todo el *workspace*
  ([uv: Using workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/)).
  - Ventajas: dependencias declaradas por componente (la API no «ve» pandas ni FastF1 ni por
    error), versiones separadas, Docker más limpio (`uv sync --package api`).
  - Inconvenientes: hoy los grupos ya dan el aislamiento que importa (imagen ligera); hay que
    mover imports, rutas de tests, `Dockerfile`, workflows y README.
  - Coste 0 €; esfuerzo M; riesgo bajo-medio (rotura de rutas).
  - → **CONSIDERAR**. Tiene sentido si entra la fase 7 (analítica avanzada/ML con dependencias
    pesadas como scikit-learn o statsmodels), que merecería su propio miembro.
- **Proyectos uv totalmente independientes** (un lock por carpeta). → **DESCARTAR**: tres locks que
  mantener sin beneficio.

Referencias adicionales sobre *workspaces*: [pydevtools: monorepo con uv workspaces](https://pydevtools.com/handbook/how-to/how-to-set-up-a-python-monorepo-with-uv-workspaces/).

### 2.3 Estructura del proyecto dbt frente a la guía de dbt Labs

Guía de referencia: [How we structure our dbt projects](https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview)
(capas staging → intermediate → marts; de datos «con forma de la fuente» a datos «con forma del
negocio»).

| Recomendación de dbt Labs | Proyecto actual | Valoración |
|---|---|---|
| Staging en carpetas **por sistema de origen**, `stg_[fuente]__[entidad]s` con doble guion bajo ([staging](https://docs.getdbt.com/best-practices/how-we-structure/2-staging)) | Exactamente así (`staging/f1db/stg_f1db__races.sql`…) | Cumple |
| Staging materializado como **vista**, sin *joins* ni agregaciones; *base models* solo si hace falta unir | Vistas; `+materialized: view` | Cumple |
| Un `_[dir]__sources.yml` por carpeta de fuente | Solo `f1db`; FastF1, formula1db y Ergast leen Parquet a mano | **Mejorable** |
| Intermediate agrupado en subcarpetas por área de negocio, nombres `int_[entidad]s_[verbo]s` | 10 modelos planos (`int_laptimes`, `int_lap_numbering`…) | Aceptable; mejorable con subcarpetas |
| Marts por entidad, **anchos y desnormalizados**, en carpetas por área si hay más de ~10 ([marts](https://docs.getdbt.com/best-practices/how-we-structure/4-marts)) | Esquema en constelación Kimball (`dim_*`, `fact_*`) + `agg_*` | Desviación **justificada** (reproduce el modelo del TFG y Power BI necesita estrella); dbt Labs también documenta Kimball ([Building a Kimball dimensional model with dbt](https://docs.getdbt.com/blog/kimball-dimensional-model)) |
| YAML de documentación por carpeta/modelo | `_core__models.yml`, `_quality__models.yml`, `_seeds.yml` | Casi completo (falta `metrics/` e `intermediate/`) |

Propuestas concretas:

1. **Declarar todas las entradas bronze como `sources`** (`_fastf1__sources.yml`,
   `_formula1db__sources.yml`, `_ergast__sources.yml`) con `meta.external_location` apuntando al
   Parquet (patrón soportado por dbt-duckdb, [README de dbt-duckdb](https://github.com/duckdb/dbt-duckdb/blob/master/README.md)).
   Ganancias: linaje completo en `dbt docs` desde el bronze, pruebas de `source freshness`
   (p. ej. «la última carrera cargada no tiene más de 10 días en temporada»), selección
   `dbt build -s source:fastf1+`. Coste 0 €, esfuerzo S, riesgo bajo. → **ADOPTAR**.
2. **Subcarpetas en `intermediate/`**: `laps/` (formula1db, fastf1, ergast, alineación, numeración,
   completitud, fusión), `race_data/` (correcciones, dorsales), `tyres/`. Esfuerzo S. → **ADOPTAR**.
3. **Exportar el gold a Parquet desde dbt** con la materialización `external` de dbt-duckdb en vez
   de hacerlo en `snapshot pack` (mismo README). Así el Parquet es un producto de dbt, con
   contratos y tests. Esfuerzo S–M. → **CONSIDERAR** (sobre todo si se adopta la arquitectura B).
4. **Marts «de servicio» anchos** (OBT) solo para la web, p. ej. `mart_web__race_lap_chart` o
   `mart_web__driver_profile`, sin tocar la estrella del TFG. Permiten que la API o los JSON
   estáticos sean un `select * where race_id = ?`. → **CONSIDERAR** junto con §5.3.
5. **dbt v2 / Fusion.** dbt Labs (ya fusionada con Fivetran desde el 1/6/2026) ha publicado dbt v2
   sobre el motor Fusion en Rust, con Apache 2.0 y con **adaptador DuckDB integrado**
   ([DuckDB: DuckDB now ships inside dbt v2](https://duckdb.org/2026/09/22/dbt-fusion);
   [dbt Core v2 is here](https://docs.getdbt.com/blog/dbt-core-v2-is-here)). La guía de migración
   marca DuckDB como «CLI only, beta» y enumera cambios incompatibles (anclas YAML, claves YAML
   desconocidas que pasan a ser error, `config.get()` sobre `meta`, eliminación de `--models`,
   tests unitarios primero…) ([Upgrading to v2](https://docs.getdbt.com/docs/dbt-versions/core-upgrade/upgrading-to-v2)).
   dbt Labs afirma que v1 seguirá soportado sin fecha de fin. → **CONSIDERAR** a medio plazo:
   primero `dbt parse --use-v2-parser` en 1.12 para ver qué rompe; migrar cuando el adaptador
   DuckDB salga de beta. Esfuerzo M; riesgo medio.
6. **SQLMesh** como alternativa a dbt: Fivetran lo compró (Tobiko, 2025) y lo cedió a la Linux
   Foundation en marzo de 2026 ([The New Stack](https://thenewstack.io/fivetran-donates-sqlmesh-lf/)).
   Aporta planes/entornos virtuales y detección de cambios, pero no compensa reescribir ~50
   modelos y la memoria del TFG ya habla de dbt. → **DESCARTAR**.

### 2.4 Estructura del proyecto Next.js

La documentación oficial ([Project structure](https://nextjs.org/docs/app/getting-started/project-structure),
[carpeta `src`](https://nextjs.org/docs/app/api-reference/file-conventions/src-folder)) admite
tres estrategias: todo fuera de `app/` (en `src/components`, `src/lib`), todo colocado dentro de
cada segmento de ruta, o por funcionalidad; propone carpetas privadas `_carpeta` para lo que no es
ruta. El proyecto sigue la primera: `src/app/[lang]/…`, `src/components/charts`,
`src/lib/api`, `src/dictionaries`. Es válida y coherente.

Mejora opcional: colocar los componentes que solo usa una ruta junto a ella
(`app/[lang]/races/[id]/tyres/_components/stint-chart.tsx`) y dejar en `src/components` solo los
compartidos (`chart-figure`, `echart`). Esfuerzo S; beneficio: localizar rápido el código de cada
página del TFG. → **CONSIDERAR** (cosmético).

### 2.5 Herramientas de monorepo y ejecutores de tareas

Hoy los comandos están repartidos entre `uv run f1-ingest …`, `cd transform && dbt …` con
`DBT_PROFILES_DIR`, `npm` en `web/` y el README.

| Herramienta | Qué aporta | Encaje aquí | Recomendación |
|---|---|---|---|
| **just** (`justfile`) | Ejecutor de comandos (no sistema de *build*), sintaxis sencilla, multiplataforma, recetas con cualquier intérprete ([comparativa Make/Task/just](https://appliedgo.net/spotlight/just-make-a-task/)) | Ideal para `just ingest`, `just build`, `just api`, `just web`, `just e2e`, `just snapshot`; funciona en Windows (el autor trabaja en Windows) | **ADOPTAR** (S) |
| **Taskfile** (go-task) | YAML, dependencias entre tareas y *checksums* de ficheros para saltarse pasos ya hechos; `includes` por paquete ([Taskfile](https://tomharrisonjr.medium.com/taskfile-replaces-make-and-makefiles-abf564708f81)) | Igual de válido que just; más verboso | Alternativa a just |
| **Makefile** | Universal en Linux/macOS | Tabs, peor en Windows | DESCARTAR frente a just/Task |
| **Turborepo** | Caché de tareas y grafo de paquetes; está incorporando Python con uv como lenguaje nativo ([RFC Native Python support](https://github.com/vercel/turborepo/discussions/13625)) | Un solo paquete JS; caché poco útil | **DESCARTAR** |
| **Nx** | Monorepo políglota con *plugins* (Python/uv comunitarios), *affected*, caché distribuida ([Nx vs Turborepo](https://nx.dev/docs/kb/nx-vs-turborepo)) | Sobredimensionado para 4 componentes y una persona | **DESCARTAR** |

---

## 3. Arquitectura de datos

### 3.1 Medallion frente a otras organizaciones y modelos

El proyecto combina dos ideas ortogonales: **medallion** (capas por grado de calidad: bronze
crudo, silver validado, gold enriquecido, según la definición de
[Databricks](https://docs.databricks.com/aws/en/lakehouse/medallion)) y, dentro del gold, un
**modelo dimensional Kimball** (constelación de hechos). Además mapea las capas de dbt:
bronze = Parquet de ingesta, silver = `staging` + `intermediate`, gold = `marts`.

| Alternativa | Ventajas | Inconvenientes | Encaje | Recomendación |
|---|---|---|---|---|
| **Medallion + Kimball (actual)** | Vocabulario conocido; el bronze permite reprocesar; la estrella es lo que espera Power BI y lo que describe la memoria (Fig. 5.7) | Nombres «bronze/silver/gold» y «staging/marts» conviven: hay que explicar el mapeo | Óptimo | **ADOPTAR (mantener)** y documentar el mapeo |
| Kimball «puro» sin capas explícitas | Menos jerga | Se pierde la trazabilidad bronze → gold que justifica las correcciones de fuentes | Peor | DESCARTAR |
| **Data Vault 2.0** (hubs, links, satellites) | Auditoría e historización, pensado para muchas fuentes cambiantes y entornos regulados ([comparativa Kimball vs DV](https://medium.com/@keithbelanger/navigating-the-decision-between-kimballs-dimensional-and-data-vault-2-0-fc50577745bb)) | Duplica el número de modelos; exige una capa dimensional encima para consumir | Excesivo (4 fuentes, 1 persona) | **DESCARTAR** |
| **One Big Table (OBT)** | Consultas sin *joins*, ideal para servir a una web o a DuckDB-WASM; dbt Labs recomienda marts anchos | Redundancia; peor para Power BI; se pierde el paralelismo con el TFG | Útil como **capa de servicio adicional** | **CONSIDERAR** (marts `mart_web__*`, §2.3) |

### 3.2 Formatos de almacenamiento y de tabla

| Formato | Situación en 2026 | Ventajas aquí | Inconvenientes aquí | Recomendación |
|---|---|---|---|---|
| **Fichero DuckDB** (`f1.duckdb`) | Actual; se puede abrir en remoto con `ATTACH 'https://…'` en solo lectura desde DuckDB 1.1 ([DuckDB over HTTPS/S3](https://duckdb.org/docs/lts/guides/network_cloud_storage/duckdb_over_https_or_s3)) | Un solo fichero, 55 MB; la API lo abre directamente | Formato binario ligado a la versión de DuckDB; no es interoperable fuera de DuckDB | **ADOPTAR (mantener)** |
| **Parquet por tabla** | Actual (`gold-parquet.zip`) | Interoperable (Power BI, pandas, Polars, DuckDB-WASM); lectura parcial con peticiones *Range* | Dentro de un zip no se puede leer por *Range*: habría que publicarlos sueltos | **ADOPTAR**: publicar además los Parquet **sin comprimir en zip**, uno por tabla, y particionar `fact_laptimes`/`fact_quali_telemetry` por temporada |
| **DuckLake 1.0** | Estable desde abril de 2026 (DuckDB 1.5.2); catálogo en SQL (SQLite, Postgres o DuckDB), *snapshots* y *time travel*, *data inlining*; admite «un lakehouse de solo lectura sin autenticación» con almacenamiento y un endpoint HTTPS público ([DuckLake 1.0](https://ducklake.select/2026/04/13/ducklake-10/); [extensión](https://duckdb.org/docs/current/core_extensions/ducklake)) | Versionado de datos nativo (cada ejecución semanal sería un *snapshot* consultable); encaja con DuckDB y con dbt v2 | Requiere almacenamiento de objetos con URLs estables (no encaja con `--clobber` en Releases); más piezas que explicar | **CONSIDERAR** (arquitectura C) |
| **Apache Iceberg** | DuckDB ya escribe en Iceberg vía catálogo REST ([Writes in DuckDB-Iceberg](https://duckdb.org/2025/11/28/iceberg-writes-in-duckdb)) | Estándar de la industria, buen punto para el CV | Necesita catálogo (servicio); sin valor práctico con 55 MB | **DESCARTAR** |
| **Delta Lake** | Extensión de DuckDB con escritura y *time travel* desde mayo de 2026 ([Delta grows up](https://duckdb.org/2026/05/07/delta-uc-updates)) | Igual que Iceberg | Igual que Iceberg | **DESCARTAR** |

### 3.3 Dónde publicar los artefactos de datos

| Opción | Límites gratuitos (2026) | Ventajas | Inconvenientes | Recomendación |
|---|---|---|---|---|
| **GitHub Releases** (actual) | Ficheros < 2 GiB, hasta 1000 assets por release, **sin límite de tamaño total ni de ancho de banda** ([About releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)) | Gratis, junto al código, CLI `gh`, notas de release como registro | **No envía cabeceras CORS**: el navegador no puede leer los assets (la descarga es un 302 a `release-assets.githubusercontent.com` sin `Access-Control-Allow-Origin`) ([issue de ejemplo](https://github.com/GlomarGadaffi/pocket-dial/issues/138); [explicación](https://corsfix.com/blog/fetch-github-release)). Sin lecturas parciales útiles para DuckDB-WASM | **ADOPTAR (mantener)** como archivo y entrada del pipeline; añadir releases inmutables con fecha (§3.4) |
| **Cloudflare R2** | 10 GB-mes, 1 M operaciones clase A y 10 M clase B al mes, **egress gratis** ([R2](https://www.cloudflare.com/products/r2/)) | CORS configurable, *Range*, compatible S3 (DuckDB `httpfs`); ideal para Parquet que lea el navegador | Requiere cuenta Cloudflare y tarjeta; el dominio `r2.dev` tiene *rate limiting* y no está pensado para producción: hace falta dominio propio ([límites r2.dev](https://community.cloudflare.com/t/rate-limiting-on-managed-public-buckets-through-r2-dev/605936); [ejemplo DuckDB-WASM + R2](https://andrewpwheeler.com/2025/06/29/using-duckdb-wasm-cloudflare-r2-to-host-and-query-big-data-for-almost-free/)) | **CONSIDERAR** (arquitectura C, o B si se quiere Parquet en el navegador) |
| **Hugging Face Datasets** | Repos públicos generosos (orientativo: hasta 300 GB por repo sin pedir más) ([Storage limits](https://huggingface.co/docs/hub/storage-limits)) | Visibilidad en la comunidad de datos, *dataset viewer* y SQL en la web, `hf://` desde DuckDB ([HF + DuckDB](https://huggingface.co/docs/hub/datasets-duckdb)); versionado git por *commit* | Las descargas redirigen al puente Xet, que **falla el *preflight* CORS con *Range*** y bloquea DuckDB-WASM ([issue #7931](https://github.com/huggingface/datasets/issues/7931)); licencias: los datos de formula1db.com tienen permiso «para divulgación», conviene confirmarlo antes de redistribuir en otra plataforma | **CONSIDERAR** como **escaparate** del dataset gold (no como origen de la web) |
| **MotherDuck** | Plan gratuito: 10 GB, 10 horas de cómputo al mes, 3 usuarios ([pricing](https://motherduck.com/product/pricing/)) | DuckDB gestionado; `dbt` puede escribir directamente; cliente WASM propio | Dependencia de un proveedor y de un *token* en la web/API; el plan gratuito cambió en 2025-2026 (desapareció el plan Lite) | **DESCARTAR** como pieza central; **CONSIDERAR** solo para experimentar |
| **GitHub Pages / Cloudflare Pages** (sitio estático con los datos) | Pages: sitio ≤ 1 GB, ~100 GB/mes de ancho de banda «blando» ([límites](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)); Cloudflare Pages: ancho de banda ilimitado, 500 *builds*/mes, **20 000 ficheros por despliegue** ([resumen de límites](https://dev.to/david_viejo_4d48fdfa7cfff/cloudflare-pages-free-tier-limits-pricing-2026-1f8f)) | CDN, CORS sencillo, sin cuentas nuevas en el caso de GitHub Pages (ya usado para `dbt docs`) | Límite de ficheros en Cloudflare Pages; tamaño en GitHub Pages | **CONSIDERAR** para la «API estática» (§5.3) |

### 3.4 Versionado de datos

Hoy `data-latest` se sobrescribe cada semana (`--clobber`): no se puede volver a la versión de
hace dos lunes ni reproducir un resultado antiguo, aunque `manifest.json` guarda los SHA-256.

| Opción | Esfuerzo | Recomendación |
|---|---|---|
| **Releases inmutables con fecha** (`data-2026-09-28`) + `data-latest` como puntero móvil; conservar las N últimas (p. ej. 12) con un paso de limpieza. La API ya valida el SHA del manifest | S | **ADOPTAR** |
| Registrar en `manifest.json` el SHA del commit de código y la versión de dbt/DuckDB | S | **ADOPTAR** |
| *Snapshots* de DuckLake (versión y *time travel* nativos) | M | CONSIDERAR (arquitectura C) |
| DVC o lakeFS (versionado tipo git para datos) ([comparativa lakeFS](https://lakefs.io/blog/dvc-vs-git-vs-dolt-vs-lakefs/)) | M | **DESCARTAR**: pensado para datasets grandes o ML; aquí basta con releases fechadas |
| Snapshots SCD tipo 2 de dbt (`dbt snapshot`) sobre F1DB para ver cómo cambian los datos oficiales | M | CONSIDERAR: tendría interés analítico (auditar correcciones de F1DB) |

---

## 4. Orquestación y observabilidad

### 4.1 GitHub Actions frente a orquestadores

Limitaciones reales del cron de GitHub Actions, según la documentación oficial: los eventos
`schedule` **pueden retrasarse con carga alta**, sobre todo al principio de cada hora, y **en un
repositorio público los workflows programados se desactivan tras 60 días sin actividad**
([Events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)).
Un análisis práctico concluye que Actions basta para una persona o un equipo pequeño con un
`dbt build` periódico y sin dependencias externas complejas, y que conviene pasar a un orquestador
cuando se necesita observabilidad por modelo, *catch-up* de ejecuciones perdidas, reintentos
finos o mezclar dbt con otras tareas ([comparativa de orquestadores para dbt](https://blog.pmunhoz.com/blog/dbt/dbt-orchestration/dbt-orchestration-tools-comparison/)).

| Opción | Ventajas | Inconvenientes | Coste | Esfuerzo | Riesgo | Recomendación |
|---|---|---|---|---|---|---|
| **GitHub Actions (actual)** | Cero infraestructura, logs y artefactos incluidos, secretos, `workflow_dispatch` con parámetros ya implementado | Sin grafo por activo ni reintento por modelo; cron impreciso; desactivación a los 60 días | 0 € (minutos ilimitados en repos públicos) | — | Bajo | **ADOPTAR (mantener)** |
| **Dagster** (OSS) + `dagster-dbt` | Modelo por activos: cada modelo dbt es un activo con linaje, particiones (temporada/carrera), *sensors*, *backfills* desde la UI; es el que mejor integra dbt ([Dagster & dbt](https://docs.dagster.io/integrations/libraries/dbt)); ejemplo F1 con Dagster + dbt + DuckDB: [frizzleqq/f1-dbt-duckdb](https://github.com/frizzleqq/f1-dbt-duckdb) | Necesita dónde ejecutarse: Dagster+ ya no incluye créditos en Solo/Starter desde mayo de 2026 (Solo: 10 $/mes + 0,04 $/crédito) ([cambios de precios](https://support.dagster.io/articles/3171123463-dagster-solo-and-starter-pricing-updates-may-2026)); autoalojado exige un servidor encendido o ejecutarlo dentro de Actions (`dagster job execute`), lo que anula parte de la ventaja. **Prefect compró Dagster Labs en julio de 2026**; ambos productos siguen, pero hay incertidumbre de hoja de ruta ([anuncio](https://dagster.io/blog/prefect-is-acquiring-dagster)) | 0 € autoalojado en Actions; >0 € gestionado | L | Medio | **CONSIDERAR** solo como ejercicio de portfolio (definir activos y particiones por carrera y ejecutarlos desde Actions) |
| **Prefect** | Python puro, reintentos y mapeo dinámico; bueno para la ingesta (API FastF1 con límite de 500 peticiones/h) | Menos integrado con dbt que Dagster | Plan gratuito limitado | L | Medio | DESCARTAR frente a Dagster para este caso |
| **Apache Airflow** | Estándar de la industria; ejemplo F1 con Airflow + MinIO + Postgres + dbt: [m1nk12/f1-data-pipeline](https://github.com/m1nk12/f1-data-pipeline) | Pesado (planificador, base de datos, workers); sin alojamiento gratuito | >0 € o PC encendido | L | Alto | **DESCARTAR** |
| **Kestra** | Declarativo en YAML, *plugin* dbt, vista Gantt de modelos ([Kestra + dbt](https://kestra.io/docs/use-cases/dbt)) | Servidor Java autoalojado | >0 € o PC encendido | L | Medio | **DESCARTAR** |

### 4.2 Disparar el pipeline según el calendario de F1

El cron fijo del lunes a las 06:00 UTC tiene tres problemas: se ejecuta en semanas sin carrera,
llega tarde cuando hay dos carreras seguidas o una carrera en sábado (Las Vegas, Baréin/Arabia en
algunos años) y no reintenta si FastF1 aún no ha publicado los datos.

Alternativa sin orquestador («sensor de pobre») — **ADOPTAR** (S–M, 0 €, riesgo bajo):

1. Cron **diario** (o cada 6 h) muy barato que solo ejecuta un paso de decisión en Python:
   `fastf1.get_event_schedule(año)` da `Session5DateUtc` (hora de la carrera) de cada evento
   ([FastF1 events](https://docs.fastf1.dev/events.html)). Si hay una carrera terminada hace más
   de N horas (p. ej. 3–6 h) **y** `manifest.json` de `data-latest` no la incluye, lanza el
   pipeline completo (`gh workflow run pipeline.yml` o `repository_dispatch`); si no, termina en
   segundos.
2. Si FastF1 aún no tiene datos, el siguiente disparo lo reintenta solo (la ingesta ya es
   incremental e idempotente).
3. Mantener `workflow_dispatch` con temporadas/rondas como mecanismo de **backfill**; añadir una
   matriz por temporada si alguna vez hay que recargar 2018–2025 (cuidado con el límite de
   500 peticiones/h de FastF1: mejor en serie con `max-parallel: 1`).
4. Contra la desactivación a los 60 días: el propio pipeline podría hacer un *commit* periódico
   (p. ej. actualizar un `docs/data-status.md`), o usar una acción *keepalive*
   ([gh-action-keepalive](https://github.com/efrecon/gh-action-keepalive)). Crear releases **no**
   cuenta como actividad.

Con Dagster esto sería un *sensor* nativo sobre el calendario y una partición por carrera; es la
versión «de libro» del mismo mecanismo.

### 4.3 Observabilidad

| Opción | Qué aporta | Esfuerzo | Recomendación |
|---|---|---|---|
| Publicar `run_results.json` y `manifest.json` de dbt en la release y resumir tiempos/tests en `GITHUB_STEP_SUMMARY` | Historial de ejecuciones y duración por modelo sin herramientas nuevas | S | **ADOPTAR** |
| `dbt source freshness` / `dbt_utils.recency` sobre las fuentes (requiere §2.3.1) | Alerta si FastF1 o F1DB dejan de actualizarse ([recency](https://www.elementary-data.com/dbt-tests/recency)) | S | **ADOPTAR** |
| Aviso por correo/issue automático si falla el pipeline (Actions ya notifica al autor; se puede abrir un *issue* con `gh issue create`) | Visibilidad pública del estado | S | CONSIDERAR |
| **Elementary** OSS (paquete dbt + CLI con informe HTML estático, detección de anomalías) ([repo](https://github.com/elementary-data/elementary)) | Informe de observabilidad publicable en GitHub Pages junto a `dbt docs` | M | **CONSIDERAR**: comprobar primero el soporte del adaptador DuckDB (no confirmado en las fuentes consultadas) |
| `dbt_artifacts` (Brooklyn Data) | Modelos sobre metadatos de ejecución | M | DESCARTAR: no figura soporte DuckDB ([repo](https://github.com/brooklyn-data/dbt_artifacts)) |
| La página `/quality` de la web mostrando también la **historia** de `qa_summary` por release | Observabilidad de cara al público; buen material para el TFG | M | CONSIDERAR (requiere releases fechadas, §3.4) |

---

## 5. Serving: cómo llegan los datos a la web

### 5.1 Situación y problema

Cadena actual: GitHub Release → API FastAPI en Render (descarga el DuckDB al arrancar) → Next.js
en Vercel (ISR de 1 h). Datos de Render free: el servicio **se duerme tras 15 minutos** sin
peticiones, **tarda alrededor de un minuto** en volver, 750 h/mes, disco efímero y
«Render puede reiniciar el servicio en cualquier momento» ([Render: Deploy for free](https://render.com/docs/free)).
El README lo mitiga con la caché de ISR, pero cualquier página no visitada en la última hora
(la mayoría de las ~1 172 carreras × 7 subpáginas × 2 idiomas) paga el arranque en frío. Además,
cada arranque vuelve a descargar 55 MB de GitHub.

Vercel Hobby: 1 M invocaciones de funciones, 4 h de CPU activa, 100 GB de transferencia,
1 M *edge requests*/mes, uso **no comercial** ([Vercel Hobby](https://vercel.com/docs/plans/hobby)).
Es holgado para este tráfico.

### 5.2 Alojar la misma API en otro sitio

| Servicio | Plan gratuito 2026 | Arranque en frío | Encaje | Recomendación |
|---|---|---|---|---|
| **Render** (actual) | 750 h/mes, duerme a los 15 min | ~1 min | Funciona; experiencia lenta en páginas frías | Mantener mientras no se cambie la arquitectura |
| **Google Cloud Run** | 2 M peticiones, 180 000 vCPU-s y 360 000 GiB-s al mes (facturación por petición) ([pricing](https://cloud.google.com/run/pricing)) | Segundos (imagen pequeña); `min-instances=0` gratis, `>0` se cobra | Mejor arranque que Render; la descarga de 55 MB en cada arranque sigue ahí (se puede **meter el DuckDB en la imagen** o leerlo de GCS) | **CONSIDERAR** si se mantiene API en el camino crítico; exige tarjeta y cuenta de facturación |
| **Koyeb** | Instancia gratuita que escala a cero tras **1 h** sin tráfico; *deep sleep* de 1–5 s al despertar ([scale-to-zero](https://www.koyeb.com/docs/run-and-scale/scale-to-zero)) | 1–5 s | Muy buen encaje para una API pequeña | **CONSIDERAR** (la mejor sustitución directa de Render encontrada) |
| **Hugging Face Spaces** (Docker, CPU basic) | Gratis; se duerme tras **48 h** sin actividad, 30–60 s al despertar ([spaces](https://huggingface.co/docs/hub/en/spaces-gpus)) | Raro (48 h) pero lento | Curioso para portfolio de datos; no es su uso previsto | CONSIDERAR solo como réplica |
| **Fly.io** | **Sin plan gratuito** para cuentas nuevas desde oct. 2024 (solo prueba) ([resumen](https://costbench.com/software/cloud-infrastructure/fly-io/free-plan/)) | — | Rompe el requisito de 0 € | **DESCARTAR** |
| **Cloudflare Workers + D1** | Workers: 100 000 peticiones/día, **10 ms de CPU** por petición, 128 MB de memoria ([pricing](https://developers.cloudflare.com/workers/platform/pricing/)); D1 (SQLite): 5 GB, 5 M filas leídas/día, límites diarios aplicados desde el 1/9/2026 ([D1](https://developers.cloudflare.com/d1/platform/pricing/)) | Casi nulo | DuckDB no cabe en ese presupuesto de CPU/memoria; habría que portar la API a SQLite/TypeScript y cargar 1,8 M filas en D1 cada semana | **DESCARTAR** |

### 5.3 Web estática o «API estática» (sin servidor en el camino crítico)

Idea: como los datos cambian una vez por semana, el pipeline puede **precalcular las respuestas**
una vez y publicarlas como ficheros; la web solo lee ficheros de un CDN.

Tres variantes:

**(a) Exportación estática completa de Next.js** (`output: 'export'`). Según la documentación, no
admite ISR, rutas dinámicas sin `generateStaticParams`, `cookies`, *headers*, *redirects*, *proxy*
ni lectura de la petición ([Static exports](https://nextjs.org/docs/app/guides/static-exports)).
Consecuencias aquí: habría que generar **todas** las páginas en cada *build* (≈ 1 172 carreras ×
7 subpáginas × 2 idiomas ≈ 16 400 HTML, más pilotos y constructores: por encima del límite de
20 000 ficheros de Cloudflare Pages y con *builds* largos), y los **8 filtros por `searchParams`
dejarían de funcionar sin JavaScript** (hoy son formularios GET que funcionan sin JS, un punto de
accesibilidad del proyecto). → **DESCARTAR** la exportación completa.

**(b) «API estática» + Next.js con ISR (recomendada).** El pipeline genera, tras `dbt build`, un
árbol de JSON con la **misma forma que las respuestas de la API** (reutilizando las consultas de
los *routers* y los esquemas Pydantic, p. ej. `static-api/v1/races/1100/laps.json`), y lo publica
en un CDN con CORS (GitHub Pages del propio repo, Cloudflare Pages/R2). `lib/api/client.ts` pasa a
leer de `F1_DATA_BASE_URL` en vez de la API; ISR y `revalidate` se mantienen (o se revalida bajo
demanda con un *webhook* de despliegue al acabar el pipeline).
- Ventajas: desaparece el arranque en frío y la dependencia de Render para la web; el contrato
  OpenAPI y los tipos TypeScript no cambian; los filtros siguen siendo formularios en el servidor
  (Vercel); se puede seguir desplegando la API FastAPI para quien quiera consultas libres.
- Inconvenientes: muchos ficheros (del orden de 10 000); parámetros libres (`drivers=…` en
  `/laps`) hay que resolverlos en la web filtrando el JSON completo de la carrera, o precalcular
  solo las combinaciones que usa la web; tamaño total estimado de cientos de MB sin comprimir
  (1,27 M vueltas + 0,52 M puntos de telemetría), que cabe en GitHub Pages (≤ 1 GB) o R2.
- Coste 0 €; esfuerzo M; riesgo bajo (la API sigue como respaldo).
- → **ADOPTAR** (es la base de la arquitectura B).

**(c) Next.js lee Parquet/DuckDB en el servidor durante ISR** (DuckDB para Node en la función de
Vercel). Elimina la API, pero el binario nativo de DuckDB en funciones *serverless* y la descarga
del fichero en cada arranque en frío de la función lo hacen frágil. → **DESCARTAR** frente a (b).

### 5.4 DuckDB-WASM en el navegador

DuckDB-WASM ejecuta DuckDB en el navegador y lee Parquet remoto con peticiones HTTP *Range*
(solo el pie del fichero y las columnas/row groups necesarios) ([artículo VLDB 2022](https://www.vldb.org/pvldb/vol15/p3574-kohn.pdf);
[cliente WASM](https://duckdb.org/docs/current/clients/wasm/overview)). El paquete pesa unos
~3 MB comprimidos más extensiones, con arranque de 150–300 ms en frío
([comparativa 2026](https://kanopylabs.com/blog/pglite-vs-sqlite-wasm-vs-duckdb-wasm)). El servidor
de los datos debe permitir CORS con *Range* ([troubleshooting](https://duckdb.org/docs/current/clients/wasm/troubleshoot)):
**GitHub Releases no sirve** y **Hugging Face tampoco** hoy (§3.3); sí R2 con dominio propio,
Cloudflare Pages o GitHub Pages.

- Ventajas: exploración libre (SQL, filtros arbitrarios, comparar pilotos entre temporadas) sin
  servidor; muy vistoso para portfolio; mismos Parquet que Power BI.
- Inconvenientes: el renderizado pasa al cliente (se pierde parte de RSC, SEO y la robustez sin
  JS que exige el proyecto: los gráficos accesibles con tabla y resumen se generan hoy en el
  servidor); 3+ MB de WASM y decenas de MB de Parquet para móviles; hay que repartir
  `fact_laptimes`/`fact_quali_telemetry` por temporada o carrera para que las lecturas sean
  pequeñas.
- Coste 0 €; esfuerzo M–L; riesgo medio.
- → **CONSIDERAR** como **complemento**: una página «Laboratorio de datos» (consultas SQL y
  descarga) que carga DuckDB-WASM solo en ella, sin sustituir las páginas del TFG.

### 5.5 BI-as-code como alternativa o complemento a Next.js

| Herramienta | Qué es (2026) | Encaje | Recomendación |
|---|---|---|---|
| **Evidence** | SQL + Markdown → sitio estático; históricamente usa DuckDB-WASM en el navegador ([glosario MotherDuck](https://motherduck.com/glossary/evidence/)). En agosto de 2026 publicó **Evidence Core** (nuevo framework abierto, consultas en vivo, métricas en YAML) y la plataforma **Evidence Studio** ([Evidence Core](https://evidence.dev/blog/evidence-core)) | Ideal para un **informe de calidad de datos** o un anexo del TFG con pocas horas de trabajo; referencia de uso con deportes: [mdsinabox / nba-monte-carlo](https://github.com/matsonj/nba-monte-carlo) | **CONSIDERAR** como complemento (p. ej. `reports/` publicado en GitHub Pages); **DESCARTAR** como sustituto de la web (menos control de accesibilidad e i18n, framework en transición) |
| **Observable Framework** | Generador de sitios estáticos con *data loaders* en cualquier lenguaje ejecutados en el *build* y DuckDB en el cliente ([data loaders](https://observablehq.com/framework/data-loaders); [DuckDB](https://observablehq.com/framework/lib/duckdb)) | Encaja con Python + dbt; gráficos con Observable Plot (accesibles) | CONSIDERAR para prototipos de gráficos nuevos; DESCARTAR como sustituto |
| **Rill** | BI sobre DuckDB/ClickHouse con capa semántica en YAML ([repo](https://github.com/rilldata/rill)) | Orientado a *dashboards* de exploración con servidor | DESCARTAR |
| **Streamlit** (Community Cloud) | Apps en Python; se duermen tras 12 h sin tráfico, ~1 GB de RAM ([gestión de apps](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app)) | Rápido para prototipos analíticos (fase 7: degradación de neumáticos) | CONSIDERAR solo para prototipos internos |

La web Next.js ya cubre todas las páginas del TFG con un nivel de accesibilidad (WCAG 2.2 AA,
axe en CI, funcionamiento sin JS) que ninguna de estas herramientas da de serie; sustituirla
sería retroceder.

---

## 6. Frontend

### 6.1 Librería de gráficos

Un análisis comparativo de 2026 resume: ninguna librería es accesible «por defecto»; Vega-Lite
destaca en jerarquía semántica para lectores de pantalla (`description`), Plotly es la única con
navegación por teclado entre marcas de serie, Observable Plot genera etiquetas ARIA por marca y
usa una paleta probada para daltonismo, **ECharts es la de mejor rendimiento con muchos datos**
pero su accesibilidad depende de activar el módulo `aria`, y D3 no trae nada
([Accessible data-visualisation tooling in 2026](https://www.disabilityworld.org/articles/accessible-data-viz-tooling-2026/)).

| Librería | A favor (F1) | En contra | Recomendación |
|---|---|---|---|
| **ECharts 6** (actual) | Canvas rápido para 1 000+ vueltas × 20 pilotos y telemetría; `aria.show` genera descripciones automáticas y `aria.decal` añade texturas además del color ([ECharts ARIA](https://echarts.apache.org/handbook/en/best-practices/aria/)); ya integrada con tabla de datos y resumen textual | Sin navegación por teclado entre puntos ([issue #18585](https://github.com/apache/echarts/issues/18585)); canvas opaco para lectores de pantalla | **ADOPTAR (mantener)**; revisar que `aria` y `decal` estén activos donde el color distingue series; valorar `renderer: 'svg'` en gráficos pequeños |
| **Observable Plot** | SVG, ARIA por marca (`ariaLabel`, `ariaDescription`) ([Plot accessibility](https://observablehq.com/plot/features/accessibility)); gramática concisa; se puede renderizar en el servidor (SVG en RSC, sin JS en el cliente) | Menos interactividad (zoom, *brush*); SVG con 20 000+ puntos es pesado | **CONSIDERAR** para gráficos estáticos sencillos (barras de récords, puntos por temporada, H2H) |
| **Vega-Lite** | Especificación declarativa en JSON (se podría generar desde Python o dbt); `description` para lectores de pantalla | Bundle grande; teclado limitado ([issue de accesibilidad](https://github.com/vega/vega-lite/issues/6603)) | DESCARTAR |
| **D3 / visx** | Control total (ya se usa `d3-geo` para el mapa) | Todo el trabajo de accesibilidad e interacción es propio | Mantener D3 solo para el mapa |
| **Plotly.js** | Navegación por teclado entre marcas de serie | Bundle muy grande, estética menos cuidada | DESCARTAR |

### 6.2 Internacionalización

La web usa diccionarios JSON y `getDictionary(lang)` en `src/lib/i18n.ts`, que es exactamente el
patrón de la guía oficial ([Next.js i18n](https://nextjs.org/docs/app/guides/internationalization)).
La alternativa principal es **next-intl**, que añade plurales e interpolación ICU, formato de
fechas y números y enrutado por idioma con *proxy* ([next-intl App Router](https://next-intl.dev/docs/getting-started/app-router)).
Con dos idiomas y textos mayoritariamente fijos, el patrón actual basta; `Intl.NumberFormat`,
`Intl.DateTimeFormat` e `Intl.PluralRules` nativos cubren el formato. → **Mantener** (ADOPTAR);
**CONSIDERAR** next-intl solo si se añaden idiomas o muchos textos con plurales.

---

## 7. Proyectos de referencia

| Proyecto | Pila | Estructura / idea aprovechable |
|---|---|---|
| [frizzleqq/f1-dbt-duckdb](https://github.com/frizzleqq/f1-dbt-duckdb) | Ergast → Dagster → dbt → DuckDB/MotherDuck | Carpeta `dbt/` + paquete Dagster (`foneplatform/`) + `Makefile`; *staging* como *multi-asset* de Dagster. Referencia directa si se prueba Dagster |
| [memadore/duck-f1](https://github.com/memadore/duck-f1) | FastF1/Ergast → Parquet + DuckDB con dbt | `src/duck_f1/` (src-layout), `tasks/`, `.devcontainer/`, SQLFluff; se distribuye como dataset DuckDB/Parquet |
| [m1nk12/f1-data-pipeline](https://github.com/m1nk12/f1-data-pipeline) | FastF1 + Jolpica → MinIO (bronze) → Postgres (silver/gold) con Airflow y dbt | Medallion «clásico» con almacenamiento de objetos; validación con Pydantic antes de silver. Muestra el coste operativo de Airflow + Docker Compose |
| [matt-ohrenberger/f1-telemetry-platform](https://github.com/matt-ohrenberger/f1-telemetry-platform) | APIs públicas → MotherDuck → dbt | Ejemplo de almacén gestionado en MotherDuck |
| [colin-k-rogers/formula-1-data-analysis](https://github.com/colin-k-rogers/formula-1-data-analysis) | OpenF1 → MotherDuck (Flights) → dbt → Dive | Orquestación y visualización dentro de MotherDuck |
| [matsonj/nba-monte-carlo](https://github.com/matsonj/nba-monte-carlo) («MDS in a box») | dlt → dbt-duckdb → Parquet → Evidence estático en Netlify, `make` + GitHub Actions diario | El referente de «plataforma de datos gratis con DuckDB»: componentes intercambiables (`transform/`, `evidence/`, `dlt/`), Parquet como contrato entre capas, web estática ([artículo de DuckDB](https://duckdb.org/2022/10/12/modern-data-stack-in-a-box)) |
| [Ddscully/dlt-dbt-duckdb-evidence](https://github.com/Ddscully/dlt-dbt-duckdb-evidence) | dlt → DuckDB → dbt → Polars → Evidence, orquestado por Dagster | Almacén reconstruido en cada *push* y publicado mensualmente |
| [InfuseAI/awesome-public-dbt-projects](https://github.com/InfuseAI/awesome-public-dbt-projects) | Lista de proyectos dbt públicos | Para comparar convenciones de carpetas |

Conclusiones: **ningún proyecto F1 público encontrado combina conciliación multifuente con
umbrales de calidad, API documentada y web accesible bilingüe**; el patrón más repetido en
proyectos de bajo coste es «DuckDB + Parquet como contrato + sitio estático». Los que usan
Airflow o Dagster lo hacen sobre todo como demostración de herramientas, no por necesidad.

---

## 8. Arquitecturas objetivo

### A · Evolución mínima (endurecer lo que hay)

- Estructura: `justfile`; *sources* dbt para todo el bronze; subcarpetas en `intermediate/`.
- Datos: releases fechadas inmutables + `data-latest`; Parquet sueltos por tabla (particionados).
- Orquestación: disparo diario ligero guiado por el calendario de FastF1; `source freshness`;
  resumen de dbt en el *step summary*; *keepalive* contra los 60 días.
- Serving: API FastAPI igual; opcionalmente mover de Render a Koyeb (escala a cero tras 1 h,
  1–5 s de arranque) o meter el DuckDB en la imagen para no descargarlo en cada arranque.
- Web: sin cambios.

### B · API estática + web con ISR (recomendada)

- Todo lo de A.
- Nuevo paso del pipeline tras `dbt build`: `f1-ingest export-static` genera JSON con la forma
  de la API (reutilizando consultas y esquemas de `api/app`) y marts `mart_web__*` si hace falta.
- Publicación en un CDN con CORS: **GitHub Pages** del repo (0 cuentas nuevas; ≤ 1 GB) o
  Cloudflare Pages/R2.
- La web lee de `F1_DATA_BASE_URL`; revalidación bajo demanda al acabar el pipeline (o `revalidate`
  semanal) en vez de cada hora.
- La API FastAPI sigue desplegada como servicio público/documentación, fuera del camino crítico.
- Opcional: página «Laboratorio» con DuckDB-WASM sobre los Parquet del mismo CDN.

### C · Orquestador + almacenamiento de objetos (lakehouse ligero)

- Dagster (activos = modelos dbt, particiones por carrera, *sensor* por calendario, *backfills*
  desde la UI) ejecutado dentro de GitHub Actions o en local.
- Almacenamiento en **Cloudflare R2** (bronze y gold en Parquet) con **DuckLake** como catálogo
  (fichero SQLite/DuckDB publicado) → versiones y *time travel* nativos.
- API y web leen de R2 (API: `ATTACH`/`read_parquet` remoto; web: API estática o DuckDB-WASM).
- Posible migración a dbt v2 cuando el adaptador DuckDB sea estable.

### Comparación

| Criterio | Actual | A · Evolución mínima | B · API estática | C · Orquestador + objeto |
|---|---|---|---|---|
| Coste mensual | 0 € | 0 € | 0 € | 0 € (R2 pide tarjeta; Dagster+ gestionado costaría) |
| Esfuerzo de migración | — | S–M (2–3 días) | M (1–2 semanas) | L (3–5 semanas) |
| Arranque en frío visible en la web | Sí (~1 min en páginas frías) | Sí (menor con Koyeb: 1–5 s) | **No** | No (si se sirve estático) |
| Piezas con servidor en el camino crítico | Render + Vercel | Render/Koyeb + Vercel | Solo Vercel | Solo Vercel (+ R2) |
| Versionado de datos | No (se sobrescribe) | Releases fechadas | Releases fechadas | *Snapshots* DuckLake |
| Observabilidad | Logs de Actions | + freshness, resumen dbt | Igual que A | UI de Dagster por activo |
| Riesgo técnico | Bajo | Bajo | Bajo–medio | Medio–alto (más proveedores, Dagster en transición tras la compra) |
| Valor para el TFG / portfolio | Alto | Alto (más robusto) | **Muy alto** (argumento de diseño claro: datos semanales → serving estático) | Alto en CV, pero más difícil de justificar por necesidad real |
| Coherencia con la memoria del TFG | Total | Total | Total (la API sigue existiendo) | Media (nuevas herramientas que explicar) |
| Recomendación | — | **ADOPTAR ya** | **ADOPTAR a continuación** | CONSIDERAR como línea futura |

### Hoja de ruta sugerida

1. **Semana 1 (A, bajo riesgo)**
   - `justfile` en la raíz con las recetas del README (`ingest`, `build`, `test`, `api`, `web`,
     `e2e`, `snapshot`).
   - `_fastf1__sources.yml`, `_formula1db__sources.yml`, `_ergast__sources.yml` con
     `external_location` y `freshness`; subcarpetas en `intermediate/`; YAML de `metrics/`.
   - `pipeline.yml`: publicar también `data-AAAA-MM-DD` inmutable; añadir SHA de commit y
     versiones al `manifest.json`; subir `run_results.json`; resumen en `GITHUB_STEP_SUMMARY`.
   - Parquet gold sueltos (sin zip) y particionados por temporada en las dos tablas grandes.
2. **Semana 2 (A)**
   - Workflow `trigger.yml` diario que consulta el calendario de FastF1 y el manifest y lanza el
     pipeline solo cuando hay una carrera nueva; *keepalive* contra la desactivación a 60 días.
3. **Semanas 3–4 (B)**
   - `export-static` reutilizando las consultas de la API; tests que comparan JSON estático con
     la respuesta de la API para una muestra de recursos.
   - Publicación en GitHub Pages (o Cloudflare Pages) y cambio de `client.ts` a
     `F1_DATA_BASE_URL`, con la API como respaldo configurable.
   - Revalidación bajo demanda desde el pipeline; comprobar con Playwright + axe contra el
     despliegue.
4. **Después (opcional)**
   - Página «Laboratorio» con DuckDB-WASM sobre los Parquet del CDN.
   - Informe de calidad con Evidence u Observable Framework en GitHub Pages.
   - `uv workspaces` si entra la fase 7 (ML) con dependencias pesadas.
   - Prueba de dbt v2 (`dbt parse --use-v2-parser`) y, más adelante, explorar la arquitectura C
     (Dagster + DuckLake en R2) como rama experimental.

---

## Fuentes principales (agrupadas)

- **Estructura**: [dbt: How we structure our dbt projects](https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview) ·
  [staging](https://docs.getdbt.com/best-practices/how-we-structure/2-staging) ·
  [marts](https://docs.getdbt.com/best-practices/how-we-structure/4-marts) ·
  [Kimball con dbt](https://docs.getdbt.com/blog/kimball-dimensional-model) ·
  [uv workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/) ·
  [Next.js project structure](https://nextjs.org/docs/app/getting-started/project-structure) ·
  [just/Task/Make](https://appliedgo.net/spotlight/just-make-a-task/) ·
  [Nx vs Turborepo](https://nx.dev/docs/kb/nx-vs-turborepo) ·
  [Turborepo Python RFC](https://github.com/vercel/turborepo/discussions/13625)
- **dbt y ecosistema**: [dbt Core v2](https://docs.getdbt.com/blog/dbt-core-v2-is-here) ·
  [Upgrading to v2](https://docs.getdbt.com/docs/dbt-versions/core-upgrade/upgrading-to-v2) ·
  [DuckDB en dbt v2](https://duckdb.org/2026/09/22/dbt-fusion) ·
  [dbt-duckdb](https://github.com/duckdb/dbt-duckdb) ·
  [SQLMesh en la Linux Foundation](https://thenewstack.io/fivetran-donates-sqlmesh-lf/)
- **Arquitectura y formatos**: [Medallion (Databricks)](https://docs.databricks.com/aws/en/lakehouse/medallion) ·
  [DuckLake 1.0](https://ducklake.select/2026/04/13/ducklake-10/) ·
  [Iceberg writes](https://duckdb.org/2025/11/28/iceberg-writes-in-duckdb) ·
  [Delta](https://duckdb.org/2026/05/07/delta-uc-updates) ·
  [ATTACH por HTTPS](https://duckdb.org/docs/lts/guides/network_cloud_storage/duckdb_over_https_or_s3)
- **Almacenamiento**: [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases) ·
  [CORS en release assets](https://corsfix.com/blog/fetch-github-release) ·
  [Cloudflare R2](https://www.cloudflare.com/products/r2/) ·
  [HF storage limits](https://huggingface.co/docs/hub/storage-limits) ·
  [HF + DuckDB](https://huggingface.co/docs/hub/datasets-duckdb) ·
  [HF CORS/Range](https://github.com/huggingface/datasets/issues/7931) ·
  [MotherDuck pricing](https://motherduck.com/product/pricing/) ·
  [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)
- **Orquestación**: [GitHub Actions: schedule](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) ·
  [Dagster + dbt](https://docs.dagster.io/integrations/libraries/dbt) ·
  [Prefect compra Dagster](https://dagster.io/blog/prefect-is-acquiring-dagster) ·
  [Precios Dagster+ 2026](https://support.dagster.io/articles/3171123463-dagster-solo-and-starter-pricing-updates-may-2026) ·
  [Kestra + dbt](https://kestra.io/docs/use-cases/dbt) ·
  [Comparativa para dbt](https://blog.pmunhoz.com/blog/dbt/dbt-orchestration/dbt-orchestration-tools-comparison/) ·
  [FastF1 event schedule](https://docs.fastf1.dev/events.html) ·
  [Elementary](https://github.com/elementary-data/elementary)
- **Serving**: [Render free](https://render.com/docs/free) ·
  [Vercel Hobby](https://vercel.com/docs/plans/hobby) ·
  [Cloud Run pricing](https://cloud.google.com/run/pricing) ·
  [Koyeb scale-to-zero](https://www.koyeb.com/docs/run-and-scale/scale-to-zero) ·
  [Cloudflare Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/) ·
  [D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/) ·
  [Next.js static exports](https://nextjs.org/docs/app/guides/static-exports) ·
  [DuckDB-Wasm (VLDB)](https://www.vldb.org/pvldb/vol15/p3574-kohn.pdf) ·
  [Evidence Core](https://evidence.dev/blog/evidence-core) ·
  [Observable Framework](https://observablehq.com/framework/data-loaders) ·
  [Streamlit Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app)
- **Frontend**: [ECharts ARIA](https://echarts.apache.org/handbook/en/best-practices/aria/) ·
  [Observable Plot accessibility](https://observablehq.com/plot/features/accessibility) ·
  [Accesibilidad de librerías 2026](https://www.disabilityworld.org/articles/accessible-data-viz-tooling-2026/) ·
  [Next.js i18n](https://nextjs.org/docs/app/guides/internationalization) ·
  [next-intl](https://next-intl.dev/docs/getting-started/app-router)

> Advertencia sobre las fuentes: varias cifras de planes gratuitos proceden de agregadores
> (costbench, dev.to, blogs) además de la documentación oficial, y cambian con frecuencia; antes
> de decidir conviene verificarlas en la página oficial de cada proveedor. Las noticias muy
> recientes (dbt v2 GA con DuckDB en beta, compra de Dagster por Prefect, Evidence Core) son de
> junio a septiembre de 2026.
