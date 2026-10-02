# Auditoría 5 · Documentación frente a la realidad y cumplimiento de los planes (DOC)

Fecha: 02/10/2026. Auditor de solo lectura (sin cambios en el proyecto salvo esta nota).

## 1. Alcance y método

Revisado: plan original (`~/.claude/plans/esta-carpeta-tiene-mi-kind-owl.md`, fases 0-6 y «Verificación»),
`plan_accion.tex` (tabla de bloques con «Terminado cuando», líneas 103-133), `DECISIONES.md` (1-33),
`SIGUIENTES_PASOS.md`, `PROGRESO.md`, `README.md` completo, `LICENSE`, `docs/revision_divergencias/INFORME.md`,
textos de licencia en API (`api/app/main.py:146-157`), web (`web/src/dictionaries/es.json`) y notas de
release (`ingestion/snapshot.py:712-719`), y comentarios de código relacionados.

Comandos ejecutados (resultados resumidos):
- `pytest -q` → 136 passed, 10 skipped; `ruff check .` → limpio; `transform/target/run_results.json`
  (build del 01/10 21:40) → 223 nodos (147 pass + 76 success). Coincide con `SIGUIENTES_PASOS.md`.
- `gh run list` → CI y pipeline en verde en `852fe06`; anotaciones de la CI sin avisos de Node 20.
  `git status` → `main` va 1 commit por delante de `origin` (`f827372`, solo documentación).
- `gh release view data-latest` → manifiesto `data-2026-10-01-6.1`; descargada la base publicada a
  la carpeta temporal (no al repo).
- Producción: `curl -I` a la web → CSP, HSTS, X-Frame-Options, nosniff, Referrer y Permissions-Policy
  presentes, pero `Cache-Control: private, no-store` y `X-Vercel-Cache: MISS` en `/es` y
  `/es/seasons/2024`. API `/health` → `ok`, `release_tag data-2026-10-01-6.1`;
  `/races/1164/race-control` y `/weather` → 200.
- DuckDB (local y publicada, solo lectura): São Paulo 2024 v.33 con `is_red_flag:suspension`;
  Italia 2018 R14 con 925 vueltas confirmadas por FastF1 (también en la publicada);
  `fact_race_control_message` 17 690 filas / `fact_weather_sample` 28 225, 188 carreras, 2018-2026;
  2025: 498 vueltas `single_source` de 26 689; 0 duplicados en
  `(race_id, driver_id, driver_number, lap_number)`; 12 sprints 2021-2023 con `has_sprint`.
- Cobertura del diccionario de datos: script que cruza `information_schema.columns` de `gold` con
  las descripciones de `transform/models/marts/**/*.yml` → **36 de 299 columnas descritas**.
- Rutas reales de la API (desde `web/src/lib/api/openapi.json`, 30 rutas) frente a la tabla del README.

## 2. Bien hecho

- **Tronco y bloques C1, C2 y D1 cumplen su criterio de terminado** (sección 4) con evidencia
  reproducible: cabeceras en producción, releases fechadas + `bronze-static-v1` + `bronze-openf1`,
  `/health` con `generated_at`, São Paulo 2024 v.33 marcada, grano de vueltas sin duplicados,
  meteo y mensajes 2018+ en gold.
- **Cifras de `SIGUIENTES_PASOS.md` exactas**: 223/223 dbt, 136 pytest, 17 690 / 28 225 filas,
  498 `single_source`, 1 270 260 vueltas: todas reproducidas.
- **Cifras del README verificables**: el seed `race_data_overrides.csv` tiene exactamente 72
  `race_laps`, 97 `fastest_lap_lap` y 5 parrillas, como dice `README.md:419-421`.
- **Licencias y atribución coherentes en las cuatro superficies** (README `:462-482`, OpenAPI
  `api/app/main.py:146-157`, notas de release `ingestion/snapshot.py:712-719`, pie y página de calidad
  de la web): F1DB CC BY 4.0, OpenF1 y Ergast NC-SA, © Formula One, aviso de marcas. Cumple las
  decisiones 2 y la atribución de D1.
- **Seguimiento ordenado** (decisión 19): `PROGRESO.md` lleva el aviso de histórico
  (`PROGRESO.md:3`); decisión 9 cumplida (`git ls-files` incluye fuentes y PDF, no `build/`).
- **Decisiones 15-33 con alternativas y motivo**: material directamente aprovechable en la memoria.
- **Pipeline documentado al detalle** (snapshot, rollback, códigos de salida de `fastf1-publish`,
  prueba de humo y `cambios_esperados.json`), coherente con `pipeline.yml`.

## 3. Hallazgos

| ID | Gravedad | Título | Evidencia | Impacto | Propuesta | Bloque |
|---|---|---|---|---|---|---|
| DOC-01 | alta | Un tercero no puede reproducir el proyecto siguiendo «Puesta en marcha» | `README.md:50-55` manda ejecutar `f1-ingest legacy` y `ergast`, que leen `PROJECT_ROOT.parent / "FORMULA 1 DB"` (`ingestion/config.py:24`) y `PROJECT_ROOT.parent / "ERGAST API" / "f1db_csv.zip"` (`ingestion/ergast_loader.py:20`), carpetas fuera del repositorio que solo existen en el equipo del autor. El README solo explica la puesta en marcha «desde el equipo que tiene los datos del TFG» (`:212`); no hay una ruta para terceros (descargar `bronze-static-v1` o `data-latest` y `snapshot restore`) (lectura) | Sin formula1db no hay vueltas 1950-2024 y el modelo no se construye fuera del PC del autor; la reproducibilidad es un criterio de evaluación del TFG | Añadir «Reproducir desde cero» al README: `gh release download bronze-static-v1` / `data-latest` → `f1-ingest snapshot restore …` → `f1-ingest f1db` → `dbt build`, y marcar `legacy`/`ergast` como «solo el autor» | A1 (el `justfile` puede encapsularlo) |
| DOC-02 | alta | El diccionario de datos prometido no existe: 88 % de las columnas gold sin descripción | Script sobre `gold` frente a los yml de marts: 36/299 columnas descritas. Ejemplos: `dim_race` 3/38, `fact_race_result` 4/32, `agg_driver_career` 0/23, `fact_pit_stops` 0/11 (verificado). El plan original dice que `dbt docs` «sirve de diccionario de datos» y el README, «El catálogo completo con descripciones y linaje se genera con `dbt docs`» (`README.md:384`) | El catálogo sale casi vacío; la memoria y cualquier consumidor de `gold-parquet.zip` no tienen semántica de columnas (unidades, nulos, fuente) | Describir todas las columnas de gold (usar `doc` blocks para las comunes: `race_id`, `*_id`, `position_*`) y, opcionalmente, un test que exija descripción | A1 (o nuevo bloque «documentación») |
| DOC-03 | media | El README promete páginas en caché de una hora; en producción ninguna se cachea | `README.md:345-350` («la web renueva sus páginas cada hora… conserva en caché las páginas ya generadas»). `curl -I` a `/es` y `/es/seasons/2024` → `Cache-Control: private, no-cache, no-store`, `X-Vercel-Cache: MISS` (verificado). `SIGUIENTES_PASOS.md:145` ya lo reconoce («ninguna página de la web se cachea») | Documentación contradictoria entre README y SIGUIENTES; quien lea el README espera arranques en frío solo en páginas no visitadas | Corregir el README (hoy solo se cachean las respuestas de `fetch` con `revalidate`) hasta que A1/A2 lo arregle | A1 |
| DOC-04 | media | Instrucciones con un input del pipeline que no existe (`seasons`) | `pipeline.yml:13-21` solo tiene `force_f1db` y `allow_shrink` (verificado). Siguen diciendo lo contrario: `README.md:451` («lanzar el pipeline a mano con `seasons = 2018`»), `docs/revision_divergencias/INFORME.md:270-272` y `SIGUIENTES_PASOS.md:74` («Deja el campo de temporadas vacío»). Además, el pipeline ya no descarga FastF1 (403) e Italia 2018 ya está publicada (manifiesto: 2018 = 21 carreras; 925 vueltas confirmadas por FastF1) | Instrucciones operativas imposibles de seguir; confunden al autor y a un tercero | README: «publicada con `fastf1-publish` el 01/10»; INFORME: nota de actualización; SIGUIENTES: quitar la frase | Inmediato (documentación), o D2 |
| DOC-05 | media | La decisión 1 se implementó de otra forma y la enmienda no está registrada | `DECISIONES.md` fila 1: «CC BY 4.0 para los datos derivados». README `:466-467`: «no tienen una licencia única. Cada parte conserva la de su origen» (FastF1 © F1, Ergast CC BY-NC-SA 3.0, formula1db con permiso). La implementación es más correcta, pero contradice la decisión registrada (lectura) | Incoherencia legal visible en el documento que la memoria citará como fuente de decisiones | Añadir una decisión (34) o una nota en la fila 1 con el motivo (el cronometraje de la F1 y Ergast no admiten CC BY) | Inmediato (documentación) |
| DOC-06 | media | Las desviaciones del plan original no están registradas en ningún sitio | Plan original fase 5: shadcn/ui, MapLibre, next-intl, Lighthouse CI ≥ 95; `web/package.json` no tiene ninguno (usa `d3-geo`, diccionarios propios) y no hay Lighthouse en `.github` (verificado). Fase 0: sqlfluff en pre-commit; `.pre-commit-config.yaml` solo tiene ruff (lo reconoce DBT-12 en `notas/07_mejoras_codigo.md:199`). Fase 2: `agg_season_standings` → `agg_driver_season`. Fase 3: «avisar a la API» → sondeo cada 6 h (decisión 28 lo cubre). Fase 4: `/drivers/{id}/h2h` → `/teammates`, `/circuits/map` → `/circuits`, `/telemetry/{race}/{driver}` → `/races/{id}/telemetry`. `grep` de «maplibre/shadcn/lighthouse» en `docs/` y README: solo una mención a next-intl como alternativa | La memoria tendrá que justificar cambios de tecnología sin registro de cuándo ni por qué | Tabla «Plan original frente a lo construido» (fase, prometido, hecho, motivo) en `DECISIONES.md` o en un anexo | Nuevo bloque «documentación para la memoria» |
| DOC-07 | media | No hay evidencia de la «paridad con el TFG» que exigía la verificación del plan | Plan original, «Verificación 2»: comparar con el .pbix las victorias, poles y títulos de Hamilton y Verstappen, las victorias de Ferrari y los GP por país. No hay test, nota ni tabla en el repo (`grep -ril "paridad\|pbix\|parity"` sin resultados en docs y modelos). Sí existe la paridad con F1DB (`assert_driver_totals_match_f1db.sql`, `assert_constructor_totals_match_f1db.sql`) (verificado) | Es el argumento central de «se conserva el modelo del TFG»; sin él la memoria no puede afirmarlo con evidencia | Tabla de KPIs (gold frente a las cifras del .pbix o de la memoria del TFG, con las diferencias explicadas por correcciones posteriores) en `docs/` | Nuevo bloque «documentación para la memoria» |
| DOC-08 | baja | `DECISIONES.md`: decisiones 31-33 fuera de su tabla | `DECISIONES.md:39-41`: filas `\| 31 \|…` pegadas tras la lista de «Consecuencias para el plan» (`:34-38`), sin cabecera; en GitHub no se muestran como tabla. Además el orden queda 1-19, 31-33, 20-30 (lectura) | Registro de decisiones difícil de leer y citar | Mover 31-33 a la tabla de «Forma de trabajar» (`:24-30`) | Inmediato |
| DOC-09 | baja | Restos desfasados en `SIGUIENTES_PASOS.md` | `:47` «Hasta entonces, `/race-control` y `/weather` dan error» (hoy 200 en producción, verificado); `:62` y `:76` «tras cada GP hasta D1» (D1 ya hecho); «Estado al cerrar el 01/10» repite lo de «D1 publicado» | Ruido en la única fuente de estado | Podar en el siguiente commit de seguimiento | Inmediato |
| DOC-10 | baja | Docstring de Ergast desfasado y «solo validación» impreciso | `ingestion/ergast_loader.py:3-5`: «no alimenta el modelo… entre 1996 y 2017». En realidad valida 1996-2022 (`README.md:398`), decide 49 posiciones por mayoría con FastF1 (`README.md:426`) y puede rellenar vueltas con `source = 'ergast'` (`int_laptimes.sql:416`; hoy 0 filas, verificado). El README dice «Solo validación» en `:362` y «vueltas sueltas de relleno» en `:470` | Contradicción interna; afecta al ámbito de la licencia NC-SA de Ergast | Alinear docstring y README: «valida y corrige por mayoría; rellena vueltas sueltas (hoy ninguna)» | Inmediato o D2 (Jolpica sustituye a Ergast) |
| DOC-11 | baja | El diagrama del README no muestra la arquitectura desplegada | `README.md:15-28` solo dibuja fuentes → bronze → dbt → API → web; faltan GitHub Actions, las releases (`data-latest`, fechadas, `bronze-*`), Render y Vercel, el sondeo de 6 h y la carga de FastF1 en el PC del autor, que el plan original sí incluía (lectura) | La memoria y un tercero no ven el flujo de publicación, que es la parte más original del proyecto | Añadir un segundo diagrama (publicación y despliegue) | A1 |
| DOC-12 | baja | Pequeñas inexactitudes del README | `:377` «y dos nuevos:» seguido de cuatro tablas; la tabla de la API (`:239-245`) omite `/rankings/drivers` y `/rankings/constructors` (están en el OpenAPI); la lista de comandos de snapshot omite `restore-openf1`/`pack-openf1` (`ingestion/cli.py:127-138`); la tabla «Estado» (`:30-41`) no remite al plan de acción ni a `SIGUIENTES_PASOS.md` (lectura) | Menor | Corregir en el siguiente commit de documentación | Inmediato |
| DOC-13 | baja | Las sesiones de FastF1 que el D1 original incluía no se han cargado ni reasignado | `plan_accion.tex:125` (D1: «sesiones S/SQ/SS/FP»). La decisión 22 lleva el sprint a OpenF1 (2023+) y S1, pero `fastf1_loader.py` solo pide `R` y `Q` (`:126`, `:203`, `:229`). Los sprints de 2021-2022 (anteriores a OpenF1) necesitarán FastF1 en S1, y nadie recoge FP/SQ/SS (lectura) | S1 depende de D1 y su estimación (4-6 días) suponía la ingesta hecha; habrá carga local de FastF1 extra | Anotarlo en la fila de S1 de `SIGUIENTES_PASOS.md` (ingesta FastF1 `S`/`SQ`/`SS` 2021-2022 en el PC del autor) y decidir si FP se descarta | S1 |
| DOC-14 | baja | Erratas de dependencias en la tabla de bloques | `plan_accion.tex:120`: T1 «Depende: D1» (T1 va antes que D1 y no lo necesita; parece D0, la licencia). `:126`: D2 depende de «D0», que no es un bloque de la tabla (lectura) | Confunde al leer el plan; el PDF lo arrastra | Corregir en el .tex si se regenera el PDF | Inmediato (opcional) |

## 4. Promesas de los planes: estado

### Plan original (fases 0-6)

| Fase | Estado | Evidencia y desviaciones |
|---|---|---|
| 0 Organización | Hecho con desviación | Git, `.gitignore`, uv, pre-commit con ruff (`.pre-commit-config.yaml`, versión igual a `uv.lock` 0.16.9), README. **Sin sqlfluff** (DOC-06) |
| 1 Ingesta | Hecho con desviación | Cargadores F1DB, FastF1 (incremental, un Parquet por carrera), legacy y Ergast; además OpenF1. CLI con subcomandos (`f1-ingest fastf1`) en vez de `--source`. Los CSV históricos están fuera del repo (DOC-01) |
| 2 dbt | Hecho con desviación | Staging, intermedios, marts de la Fig. 5.7 + 4 hechos nuevos, métricas (`agg_driver_season` en lugar de `agg_season_standings`), seeds de correcciones, tests propios (`assert_one_winning_car_per_race`, `assert_standings_points_match_results`). **El diccionario de datos no está** (DOC-02). PR a F1DB aplazado (decisión 11) |
| 3 Orquestación | Hecho con desviación | Cron lunes 06:00 UTC y `workflow_dispatch`; publicación en releases. «Avisar a la API» → sondeo cada 6 h (decisión 28). CI con `dbt build` completo (mejor que la muestra prevista). FastF1 fuera del pipeline por el 403 (decisión 12) |
| 4 API | Hecho con desviación | 30 rutas, ETag y `Cache-Control`, CORS, OpenAPI, pytest, Docker en Render. Nombres de endpoints distintos (DOC-06) |
| 5 Web | Hecho con desviación | Todas las páginas del TFG + telemetría, constructores y calidad; Playwright + axe en la CI. **Sin shadcn, MapLibre, next-intl ni Lighthouse CI** (DOC-06); las páginas no se cachean (DOC-03) |
| 6 Despliegue | Hecho (la analítica, en la fase 7) | Vercel + Render en marcha; Parquet gold para Power BI (`gold-parquet.zip`) |
| Verificación | Parcial | 1, 3, 4 y 5 cubiertas por la CI y el pipeline. **2 (paridad con el .pbix) sin evidencia** (DOC-07); Lighthouse no se ejecuta |

### Plan de acción (bloques hechos)

| Bloque | Criterio de terminado (`plan_accion.tex`) | Estado |
|---|---|---|
| T1 | CI sin avisos de Node 20; cabeceras en producción | **Hecho**, con `fra1` aplazado (decisión 6). Acciones fijadas a SHA, Dependabot, `fetch` con timeout y reintento (`web/src/lib/api/client.ts:39-47`), ruff alineado. Verificado |
| T2 | Un pipeline con datos rotos no publica; la API arranca sin GitHub | **Hecho** (prueba de humo y job Docker con arranque desde la copia, en verde; `/health` con `generated_at`). Lectura + CI verde |
| T3 | QA sin regresiones; São Paulo 2024 v.33 marcada | **Hecho**. Verificado (v.33 `is_red_flag:suspension`; 12 sprints; Italia 2018 publicada). Su instrucción de publicación quedó desfasada (DOC-04) |
| C1 | Ningún duplicado de grano; Schumacher M./R. distinguibles | **Hecho**. 0 duplicados con `driver_number` (los 85 sin él son coches compartidos de 1951-1964, por diseño); `api/app/codes.py:27` (MSC/RSC). Verificado / lectura |
| C2 | Los tests fallan si se rompe la fusión | **Hecho** según el revisor (30/30 roturas detectadas); hay 3 ficheros de unit tests. Lectura, no reproducido |
| D1 | Meteo y mensajes 2018+ en gold | **Hecho con desviación registrada** (redefinido por las decisiones 20-30: OpenF1 en lugar de las sesiones S/SQ/SS/FP de FastF1). Verificado; ver DOC-13 |

Decisiones 1-33: implementadas como se registraron, salvo la 1 (DOC-05). Las 6, 10 y 11 siguen
aplazadas, como estaba previsto. Las 15-19 y 31-33 son de método y no tienen reflejo en el código,
salvo `.claude/agents/` (9 definiciones) y `.claude/skills/grill-me`, que existen.

## 5. Útil para la memoria del TFG y no documentado

- Tabla «plan original frente a lo construido» con el motivo de cada desviación (DOC-06).
- Paridad de KPIs con el .pbix (DOC-07).
- Diagrama de publicación y despliegue (DOC-11) y guía de reproducción para terceros (DOC-01).
- Diccionario de datos de gold (DOC-02).
- Correspondencia entre bloques y commits (está repartida entre `SIGUIENTES_PASOS.md` y `git log`)
  y la evolución de los recuentos de pruebas (115 → 173 → 223 nodos dbt): hoy solo en `PROGRESO.md`
  y `SIGUIENTES_PASOS.md`.
- Las decisiones 1-14 no tienen alternativas ni motivo (solo desde la 15): si la memoria las cita,
  conviene completarlas.

## 6. Dudas

- No pude comparar con el .pbix (binario fuera del repo), así que DOC-07 señala la falta de
  evidencia, no una discrepancia.
- No ejecuté `dbt build` (escribe en la base local); usé el `run_results.json` del 01/10, que coincide
  con lo declarado.
- No probé la reproducción en un clon limpio: DOC-01 se deduce de las rutas de `config.py` y
  `ergast_loader.py`. Tampoco comprobé si `dbt build` falla o solo avisa con el bronze de formula1db vacío.
- C2 (30/30 roturas detectadas) no se ha reproducido.
- Al principio, la carpeta temporal compartida tenía otra copia de `f1.duckdb` (manifiesto
  `data-2026-09-29`), dejada por otro auditor; usé una descarga propia de `data-latest`
  (`data-2026-10-01-6.1`). Conviene que las otras áreas comprueben qué copia usaron.
