# 03 · Vueltas de las carreras al sprint (2021 → 2026)

> Estudio de viabilidad con pruebas reales (29 sprints con FastF1, 7 con OpenF1, Jolpica, FIA).
> Fecha: 2026-09-29. No se ha modificado código del repo; prototipos en el scratchpad.

## Conclusiones

1. **Viable y barato**: FastF1 (`get_session(año, ronda, 'Sprint')`) tiene el 100 % de las
   vueltas oficiales de los 29 sprints disputados (11 319 vueltas; 568/590 pilotos exactos y el
   resto son la vuelta de abandono, 1 DNS y 1 DSQ), con posición, compuesto, stint, boxes y
   estado de pista (SC/VSC/roja). Cubre los tres formatos (2021-22, 2023 Shootout, 2024+).
2. **Hueco sistemático: la vuelta 1** no tiene tiempo en FastF1 para los sprints (sí en las
   carreras largas). Se reconstruye con exactitud (verificada contra la FIA) desde el total
   oficial de F1DB, o con un desfase de salida constante por sesión para el resto de pilotos.
3. **OpenF1** (solo 2023+) coincide al milisegundo con FastF1 y rellena la v1 y las vueltas
   bajo SC sin tiempo, pero no es validación independiente (misma fuente Live Timing).
   **Jolpica** da la vuelta rápida por piloto de los 29 sprints: es la evidencia independiente
   (F1DB no tiene ni vuelta rápida ni paradas de sprint). formula1db.com no sirve (el TFG solo
   extrajo carreras largas y el sitio bloquea).
4. **Defecto actual** (independiente de las vueltas): `dim_race.has_sprint` es falso en
   2021-2023 porque F1DB no trae fechas de sesión; la web oculta 12 sprints ya cargados
   (6 de 2021-2022 y 6 de 2023) en el selector.
5. Diseño recomendado: tipo bronze `sprint_laps`, `int_sprint_laptimes` separado de
   `int_laptimes` y `session_type` en `fact_laptimes`/`fact_pit_lane_passes`; parámetro
   `?session=sprint` en `/laps`, `/stints`, `/pit-lane-passes`, y `SessionSwitch` en las pestañas
   vuelta a vuelta, neumáticos y ritmo. Esfuerzo: 6-8,5 días (mínimo viable ~4).

## Situación actual (revisión de código)

- F1DB ya aporta resultados de sprint (`SPRINT_RACE_RESULT`) y de clasificación sprint
  (`SPRINT_QUALIFYING_RESULT`): `fact_race_result.session_type in ('RACE','SPRINT')`,
  `fact_qualifying_result` con `SPRINT_QUALIFYING`, `dim_race.has_sprint`,
  `dim_race.sprint_qualifying_format`, `agg_driver_career.sprint_wins`.
- API: `/races/{id}/results?session=race|sprint` y `/races/{id}/qualifying?session=qualifying|sprint_qualifying`.
  Web: `session-switch.tsx` en resultados y clasificación.
- Vueltas: `ingestion/fastf1_loader.py` solo carga `get_session("R")` y `"Q"`; ningún
  sprint en bronze ni en la caché `data/cache/fastf1` (0 carpetas de sesión Sprint).
- `ergast_loader.py` usa el volcado CSV de oct-2022 (incluye `sprint_results.csv`, sin vueltas
  de sprint); no se ingiere `sprint_results`.
- `int_laptimes`, `int_lap_completeness`, `fact_laptimes`, `fact_pit_lane_passes` filtran
  `session_type = 'RACE_RESULT'` y claves (race_id, driver, lap): sin dimensión de sesión.

## F1DB (release v2026.15.1) — medido en bronze

- 29 fines de semana con `SPRINT_RACE_RESULT` (2021: 3, 2022: 3, 2023: 6, 2024: 6, 2025: 6,
  2026: 5 disputados + Singapur 10-oct pendiente, ya en el calendario sin resultados).
- `SPRINT_QUALIFYING_RESULT` solo 2023+ (23 fines de semana): en 2021-2022 la parrilla del
  sprint salía de la clasificación del viernes (`QUALIFYING_RESULT`).
- `SPRINT_STARTING_GRID_POSITION` 29. NO hay `FASTEST_LAP` ni `PIT_STOP` de sprint: la validación
  de numeración (`int_lap_numbering`) y el tipado de pasos por boxes no tienen referencia F1DB.
- `race_laps` del sprint = vueltas oficiales por piloto (referencia de completitud).
- **Defecto detectado**: `stg_f1db__races.has_sprint = sprint_race_date is not null`, pero F1DB no
  trae fechas de sesión en 2021-2023 → `dim_race.has_sprint` = 0 en 2021-2023 (12 sprints con
  resultados en `fact_race_result` que la web no ofrece en el selector). Arreglo: derivar
  `has_sprint` de la existencia de `SPRINT_RACE_RESULT`.

## FastF1 3.8.3 — prueba real (caché propia en el scratchpad)

Calendario (`get_event_schedule`, `EventFormat`): 30 fines de semana con sprint 2021-2026.
- 2021-2022 `sprint`: sesiones FP1 | Qualifying | FP2 | **Sprint** | Race (FastF1 normaliza el
  nombre oficial de 2021 «Sprint Qualifying» a `Sprint`).
- 2023 `sprint_shootout`: FP1 | Qualifying | **Sprint Shootout** | Sprint | Race.
- 2024+ `sprint_qualifying`: FP1 | **Sprint Qualifying** | Sprint | Qualifying | Race.
- `get_session(año, ronda, 'Sprint')` funciona para todos; la carrera sigue en `Session5`.

Primeras mediciones (vueltas FastF1 vs `race_laps` de `SPRINT_RACE_RESULT`):

### Completitud FastF1 (29 sprints disputados, 2021-R10 → 2026-R12; medido)

| Sprint | F1DB vueltas | FastF1 vueltas | Pilotos OK/total | Vuelta abandono (+1) | Tiempos nulos (v1 / resto) | SC / VSC / roja (vueltas-piloto) | Pit-in |
|---|---:|---:|---:|---:|---:|---|---:|
| 2021 Gran Bretaña | 339 | 339 | 20/20 | 0 | 20 / 0 | 0/0/0 | 1 |
| 2021 Italia | 342 | 343 | 19/20 | 1 | 20 / 21 | 58/0/0 | 1 |
| 2021 São Paulo | 480 | 480 | 20/20 | 0 | 20 / 0 | 0/0/0 | 0 |
| 2022 Emilia-Romaña | 399 | 400 | 19/20 | 1 | 20 / 0 | 77/0/0 | 1 |
| 2022 Austria | 435 | 436 | 19/20 | 0 (Alonso DNS con 1 vuelta en FastF1) | 20 / 0 | 0/0/0 | 1 |
| 2022 São Paulo | 468 | 469 | 19/20 | 1 | 20 / 1 | 0/0/0 | 1 |
| 2023 Azerbaiyán | 308 | 308 | 20/20 | 0 | 19 / 54 | 55/38/0 | 5 |
| 2023 Austria | 480 | 480 | 20/20 | 0 | 20 / 0 | 0/0/0 | 11 |
| 2023 Bélgica | 208 | 209 | 19/20 | 1 | 20 / 39 | 58/0/0 | 11 |
| 2023 Qatar | 318 | 322 | 16/20 | 4 | 20 / 16 | 175/0/0 | 4 |
| 2023 EE. UU. | 377 | 377 | 20/20 | 0 | 20 / 0 | 0/0/0 | 1 |
| 2023 São Paulo | 480 | 480 | 20/20 | 0 | 20 / 0 | 0/0/0 | 0 |
| 2024 China | 378 | 378 | 20/20 | 0 | 20 / 0 | 0/0/0 | 2 |
| 2024 Miami | 343 | 344 | 19/20 | 1 | 20 / 23 | 56/0/0 | 38 |
| 2024 Austria | 460 | 460 | 20/20 | 0 | 20 / 0 | 0/0/0 | 0 |
| 2024 EE. UU. | 380 | 380 | 20/20 | 0 | 20 / 0 | 0/0/0 | 0 |
| 2024 São Paulo | 475 | 476 | 19/20 | 1 | 20 / 1 | 0/46/0 | 0 |
| 2024 Qatar | 380 | 380 | 20/20 | 0 | 20 / 0 (12 vueltas sin compuesto) | 0/0/0 | 2 |
| 2025 China | 380 | 380 | 20/20 | 0 | 20 / 0 | 0/0/0 | 1 |
| 2025 Miami | 331 | 331 | 20/20 | 0 | 19 / 32 | 84/0/0 | 21 |
| 2025 Bélgica | 297 | 297 | 20/20 | 0 | 20 / 0 | 0/0/0 | 1 |
| 2025 EE. UU. | 315 | 320 | 15/20 | 5 | 20 / 40 | 150/0/0 | 3 |
| 2025 São Paulo | 441 | 444 | 17/20 | 3 | 20 / 23 | 37/0/19 | 20 |
| 2025 Qatar | 380 | 380 | 20/20 | 0 | 20 / 0 | 0/0/0 | 3 |
| 2026 China | 396 | 397 | 21/22 | 1 | 22 / 13 | 78/0/0 | 14 |
| 2026 Miami | 361 | 380 | 21/22 | 0 (Bortoleto DSQ: 19 vueltas, F1DB `race_laps` nulo) | 20 / 0 | 0/0/0 | 1 |
| 2026 Canadá | 490 | 491 | 21/22 | 1 | 22 / 2 | 0/0/0 | 7 |
| 2026 Gran Bretaña | 372 | 372 | 22/22 | 0 | 22 / 0 | 0/0/0 | 2 |
| 2026 Países Bajos | 506 | 506 | 22/22 | 0 | 22 / 1 | 0/0/0 | 2 |
| **Total** | **11 319** | **11 359** | **568/590 exactos** | 22 | | | |

Lectura:
- **Cobertura 100 %**: en los 29 sprints cada piloto tiene todas sus vueltas oficiales, sin huecos
  (`count = max(lap)`). Las 22 diferencias son la vuelta de abandono (+1, mismo criterio que
  `int_lap_completeness`), un DNS con vuelta registrada y un DSQ sin `race_laps` en F1DB.
- **Vuelta 1 sin tiempo SIEMPRE** en sprint (FastF1 no la calcula en sprints; en carreras largas
  2023-26 solo 31 de ~95 000 vueltas tienen la v1 nula). Tampoco sectores de la v1.
- Tiempos nulos adicionales bajo SC/VSC/bandera roja (igual que en carreras largas: 1 013 de las
  1 363 nulas de 2023-26 son con SC).
- Compuestos: nombres relativos (SOFT/MEDIUM/HARD/INTERMEDIATE/WET); 1 sprint con 12 vueltas sin
  compuesto (2024 Qatar). Posición nula solo en la vuelta de abandono. `TrackStatus` completo.
- F1DB no trae paradas del sprint, pero FastF1 sí registra entradas a boxes (p. ej. 2023 Austria:
  11 cambios de intermedios a secos; 2024 Miami: 38 pasos bajo SC).

### Vuelta 1 del sprint: reconstruible con exactitud

FastF1 no calcula la v1 en sprints, pero conserva `LapStartTime` y `Time` de la v1. Medido:
- `race_time_millis` (F1DB) − Σ vueltas 2..n (FastF1) reproduce **exactamente** la v1 oficial de
  la FIA *Sprint History Chart* (Imola 2022: LEC 1:31.400, VER 1:34.500, NOR 1:38.060).
- `(Time − LapStartTime)` de la v1 excede la oficial en un **desfase constante dentro de cada
  sesión** (160-286 ms según el sprint). Restando `race_time_penalty_millis` (las penalizaciones
  de 5/10 s van incluidas en `race_time_millis`), el rango intra-sesión es 0 ms en 22 de los 24
  sprints calibrables; 38 ms en 2026 China y 5 000 ms en 2026 Miami (una penalización de 5 s que
  F1DB no refleja en `race_time_penalty_millis`: la mediana lo absorbe, y el caso sirve de alerta). Así se reconstruye la v1 de todos los pilotos,
  incluidos doblados y abandonos. En 5 sprints con SC y tiempos nulos (2021 Italia, 2023 Bakú y
  Bélgica, 2025 Miami y São Paulo) no hay pilotos calibradores: usar la v1 de OpenF1/FIA o
  el desfase típico (~260 ms) marcando `timing_convention`.

## OpenF1 (api.openf1.org, sin clave) — prueba real

- Sesiones: `session_name` = `Sprint` (type `Race`) y `Sprint Qualifying` (type `Qualifying`;
  normaliza el «Sprint Shootout» de 2023). **Solo 2023+**: 6 sprints/año 2023-2026 (24 sesiones,
  Singapur 2026 incluida con `session_key` 11383 aún sin datos). No cubre 2021-2022.
- Endpoints probados por sesión: `laps`, `stints`, `pit`, `race_control`, `position`,
  `session_result` (todos responden; ~6 peticiones/sprint, limitar a ~2 req/s).

Validación cruzada FastF1 ↔ OpenF1 (7 sprints: 2023 Austria y Qatar, 2024 China, 2025 Bélgica y
EE. UU., 2026 China y Gran Bretaña):

| Sprint | Vueltas FastF1 | Emparejadas | Con tiempo en ambas | Iguales ±1 ms | Distintas | Solo OpenF1 tiene tiempo (de ellas v1) | Compuesto igual* |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2023 Austria | 480 | 480 | 460 | 460 | 0 | 20 (20) | 480/480 |
| 2023 Qatar | 322 | 322 | 286 | 286 | 0 | 32 (19) | 318/318 |
| 2024 China | 378 | 378 | 358 | 358 | 0 | 20 (20) | 378/378 |
| 2025 Bélgica | 297 | 297 | 277 | 277 | 0 | 19 (19) | 297/297 |
| 2025 EE. UU. | 320 | 320 | 260 | 260 | 0 | 55 (17) | 317/318 |
| 2026 China | 397 | 397 | 362 | 362 | 0 | 34 (22) | 240/240 |
| 2026 Gran Bretaña | 372 | 372 | 350 | 350 | 0 | 22 (22) | 356/356 |

\* sobre las vueltas cubiertas por algún stint de OpenF1: **0 contradicciones de compuesto**, pero
OpenF1 omite stints (2026 China: le faltan los primeros stints de 157 vueltas) y numera algún stint
distinto (2025 Bélgica, 11 vueltas).

Conclusiones OpenF1: mismos datos de cronometraje que FastF1 (100 % idénticos cuando ambos tienen
tiempo) → sirve para **rellenar** la v1 y las vueltas bajo SC que FastF1 deja sin tiempo, no como
validación independiente (misma fuente F1 Live Timing). Su v1 es ~0,35-0,44 s más larga que la
oficial (mide desde otra referencia): marcarla `timing_convention`, preferir la reconstrucción.

## Jolpica-F1 / Ergast

- `https://api.jolpi.ca/ergast/f1/{año}/sprint/` → resultados de los 29 sprints (2021-2026),
  y **por piloto `FastestLap` (vuelta y tiempo)**. No existen `/{año}/{ronda}/sprint/laps` ni
  `/sprint/pitstops` (404); `/{año}/{ronda}/laps` son solo de la carrera larga.
- Volcado CSV Ergast (oct-2022) del repo: `sprint_results.csv` (100 filas = 5 sprints 2021-22)
  con `fastestLap`/`fastestLapTime`; sin vueltas de sprint.
- Uso propuesto: la vuelta rápida por piloto de Jolpica es la **evidencia independiente** para
  validar tiempo y numeración (sustituye a `FASTEST_LAP` de F1DB, que no existe para sprints).

## FIA, formula1.com y formula1db.com

- FIA publica por sprint PDFs con patrón `fia.com/sites/default/files/{año}_{ronda}_{gp}_f1_s0_timing_sprint{historychart|lapchart|...}_v01.pdf`
  (comprobados: 2022_04_ita *Sprint History Chart*, 5 páginas con vuelta, piloto, gap, tiempo
  y PIT; 2026_05_can *Sprint Lap Chart*). Es la **referencia oficial** (incluye la v1), pero son
  PDF de maquetación variable y con aviso de copyright restrictivo: útil para verificar
  casos puntuales (seed de correcciones con evidencia), no como fuente masiva.
- formula1.com: resultados, parrilla y clasificación sprint; sin vuelta a vuelta del sprint.
- formula1db.com: el scraping del TFG solo recorrió `/results/race` (no hay vueltas de sprint en
  `f1_lap_times.csv`); la web responde 403 y robots.txt lo prohíbe → **no es fuente para sprints**.

## Clasificación sprint (Shootout 2023 / Sprint Qualifying 2024+)

- FastF1: `get_session(a, r, 'Sprint Shootout')` (2023) y `'Sprint Qualifying'` (2024+) cargan
  vueltas (2023 Austria 355, 2024 China 218, 2025 Bélgica 185), pero `results` llega **sin
  posición ni SQ1/SQ2/SQ3** (FastF1 los toma de Ergast/Jolpica, que no los tiene) → los
  resultados siguen viniendo de F1DB (`SPRINT_QUALIFYING_RESULT`, ya en `fact_qualifying_result`).
- **Trampa de alias**: `'SQ'` en 2021-2022 devuelve la *carrera* sprint (se llamaba «Sprint
  Qualifying») y en 2023 falla (allí es `'SS'`). Usar el nombre completo según `EventFormat`.
- Aporte útil: telemetría de la vuelta rápida de SQ (como `quali_telemetry`), no vueltas de carrera.

## Catálogo de sprints y cobertura esperada por fuente

Formatos: **A** = 2021-2022 (la clasificación del viernes fija la parrilla del sprint; el sprint
se llamó «Sprint Qualifying» en 2021 y «Sprint» en 2022); **B** = 2023 (Qualifying del viernes
para el GP + *Sprint Shootout* el sábado); **C** = 2024+ (*Sprint Qualifying* el viernes; sprint y
Qualifying el sábado). En 2021-2026 no se canceló ningún sprint ya disputable (Imola 2023, que iba
a tener sprint, se canceló entero por las inundaciones y no figura en F1DB).

| Año | Ronda / GP (F1DB `race_id`) | Fmt | F1DB res. | FastF1 vueltas | OpenF1 | Jolpica res. + VR | Ergast CSV | FIA PDF |
|---|---|---|---|---|---|---|---|---|
| 2021 | 10 Gran Bretaña (1045), 14 Italia (1049), 19 São Paulo (1054) | A | ✓ | ✓ medido | ✗ | ✓ | ✓ | ✓ |
| 2022 | 4 Emilia-Romaña (1061), 11 Austria (1068), 21 São Paulo (1078) | A | ✓ | ✓ medido | ✗ | ✓ | ✓ (Imola, Austria) | ✓ (Imola comprobado) |
| 2023 | 4 Azerbaiyán (1083), 9 Austria (1088), 12 Bélgica (1091), 17 Qatar (1096), 18 EE. UU. (1097), 20 São Paulo (1099) | B | ✓ + SQ | ✓ medido | ✓ | ✓ | ✗ | ✓ |
| 2024 | 5 China (1106), 6 Miami (1107), 11 Austria (1112), 19 EE. UU. (1120), 21 São Paulo (1122), 23 Qatar (1124) | C | ✓ + SQ | ✓ medido | ✓ | ✓ | ✗ | ✓ |
| 2025 | 2 China (1127), 6 Miami (1131), 13 Bélgica (1138), 19 EE. UU. (1144), 21 São Paulo (1146), 23 Qatar (1148) | C | ✓ + SQ | ✓ medido | ✓ | ✓ | ✗ | ✓ |
| 2026 | 2 China (1151), 4 Miami (1153), 5 Canadá (1154), 9 Gran Bretaña (1158), 12 Países Bajos (1161) | C | ✓ + SQ | ✓ medido | ✓ | ✓ | ✗ | ✓ (Canadá comprobado) |
| 2026 | 17 Singapur (1166), 10-oct | C | pendiente | pendiente | sesión creada | pendiente | ✗ | pendiente |

Totales: 29 sprints disputados = **11 319 vueltas oficiales** (F1DB) / 11 359 registros FastF1
(≈ +1 % de filas sobre `fact_laptimes`). OpenF1 medido en 7 de sus 23 sprints disputados;
Jolpica, resultados de los 29.

Problemas identificados:
1. Nombres de sesión cambiantes: resolver siempre por `EventFormat` + nombre completo, nunca
   por alias (`SQ` es ambiguo entre años).
2. v1 sin tiempo en FastF1 (reconstruible) y tiempos nulos bajo SC (rellenables con OpenF1 2023+).
3. F1DB no tiene paradas ni vuelta rápida del sprint → `int_lap_numbering`, `fact_pit_stops`,
   `fact_pit_lane_passes` (`pass_type='pit_stop'`) y `qa_fastest_laps` no tienen referencia;
   usar la VR de Jolpica y tipificar los pasos por boxes por SC/retirada/otros.
4. `dim_race.has_sprint` falso en 2021-2023 (defecto actual, independiente de las vueltas).
5. DSQ con `race_laps` nulo (Bortoleto, 2026 Miami) y DNS con 1 vuelta en FastF1 (Alonso,
   2022 Austria): conciliarlos como hace `int_lap_completeness` (`disqualified`, DNS excluidos).
6. Compuesto Pirelli (C1-C6): `int_tyre_compound_mapping` depende de formula1db (carreras
   largas hasta 2023); para el sprint se reutiliza el mapeo de la carrera del mismo fin de semana
   (misma asignación de neumáticos). En 2024+ tampoco existe para la carrera: sin cambio.
7. Carga incremental: `completed_races` mira `Session5DateUtc` (carrera); el sprint está
   disponible un día antes (Singapur 2026 el 10-oct). Usar la fecha de la sesión «Sprint».

## Diseño propuesto

### Ingesta
- `fastf1_loader.py`: nuevo tipo `sprint_laps` (`bronze/fastf1/sprint_laps/season=YYYY/round=RR.parquet`,
  con columna `session='SPRINT'`) para los eventos con `'sprint' in EventFormat`, sesión `'Sprint'`.
  Se prefiere un tipo propio a `laps/season=YYYY/session=S/…` porque la fuente dbt actual lee
  `fastf1/laps/*/*.parquet`: hoy no lo recogería, pero un cambio futuro del patrón a `**`
  mezclaría sprint y carrera sin avisar. Opcional: `sprint_quali_telemetry` (sesiones
  «Sprint Shootout»/«Sprint Qualifying», mismo patrón que `quali_telemetry`).
- Nuevo `openf1_loader.py` (2023+): `laps`, `stints`, `pit`, `race_control` de las sesiones
  `Sprint` → `bronze/openf1/{tipo}/season=YYYY/round=RR.parquet`; `session_key` resuelto con
  `/sessions?year=…` (filtrar `session_name == 'Sprint'`) y casado con F1DB por fecha y país.
- Jolpica: `jolpica_loader.py` con `/{año}/sprint/` (resultados + `FastestLap`), paginando
  (`limit=100`, `offset`). Sirve además para contrastar los resultados de sprint de F1DB.

### dbt
- Staging: `stg_fastf1__sprint_laps` (igual que `stg_fastf1__laps` + `lap_start_time_ms`),
  `stg_openf1__laps`, `stg_jolpica__sprint_results`.
- `int_fastf1_sprint_laps` (prototipo en el scratchpad): claves F1DB + reconstrucción de la v1.
- `int_sprint_laptimes`: FastF1 principal; OpenF1 rellena tiempos nulos (`source='openf1'`);
  `validation_status` con la misma semántica que `int_laptimes`, más un valor nuevo:
  - `confirmed`: FastF1 = OpenF1 ±1 ms (documentar que comparten la fuente primaria) o = VR de Jolpica;
  - `derived` (**nuevo**): v1 reconstruida desde el total oficial de F1DB;
  - `timing_convention`: v1 de OpenF1 o por desfase de sesión;
  - `disputed`: la VR de Jolpica no coincide con ninguna vuelta del piloto;
  - `single_source`: resto.
  Numeración: evidencia = VR de Jolpica (±1 ms) en lugar de `FASTEST_LAP` de F1DB.
- **Hecho**: añadir `session_type` (`RACE`/`SPRINT`) a `fact_laptimes` (union de
  `int_laptimes`, sin tocar, + `int_sprint_laptimes`) y a `fact_pit_lane_passes`; clave única
  `(race_id, session_type, driver_id, driver_number, lap_number)`. Se elige columna en vez de
  hecho separado porque la API y la web ya tratan la sesión como parámetro (`fact_race_result`
  hace lo mismo) y las consultas de vueltas, stints y ritmo se reutilizan tal cual.
  Contrapartida: todo consumidor debe filtrar la sesión: 3 consultas de `api/app/routers/races.py`
  (`laps`, `stints`, `pit-lane-passes`), `qa_fastest_laps`, `qa_pit_stops`, `qa_summary` e
  `int_lap_completeness`. Alternativa de menor riesgo: `fact_sprint_laptimes` separado.
- `int_lap_completeness` parametrizado por sesión (`SPRINT_RACE_RESULT`) → `quality_status`.
- `stg_f1db__races.has_sprint`: derivarlo de la existencia de `SPRINT_RACE_RESULT` (arreglo
  inmediato, útil aunque no se haga lo demás).
- Tests: `unique_combination` con `session_type`; `accepted_values` de `session_type`;
  singular `assert_sprint_laps_match_f1db` (máx. vuelta = `race_laps` salvo vuelta de
  abandono/DSQ/DNS); `assert_sprint_lap_sum_matches_total` (Σ vueltas = `race_time −
  penalización` ±1 ms para los clasificados en la vuelta del líder); umbral de sprint en
  `assert_quality_thresholds`; `qa_sprint_fastest_laps` (VR Jolpica frente a vueltas).

### API
- `GET /races/{id}/laps?session=race|sprint`, `/stints?session=…`, `/pit-lane-passes?session=…`
  (`Literal["race","sprint"] = "race"`, como `/results`); lista vacía si no hay sprint.
  `/pitstops` sigue siendo solo de carrera (F1DB no tiene paradas de sprint). Regenerar
  `web/src/lib/api/openapi.json` y `schema.d.ts`; fixtures de `api/tests` con un sprint.

### Web
- Pestañas `lap-chart`, `tyres`, `pace` (y `pitstops` para los pasos por boxes): `SessionSwitch`
  carrera/sprint cuando `race.has_sprint`, con `?session=sprint` (sin JS, como en resultados).
  `getDriverNames(raceId, session)` debe usar `getResults(raceId, "sprint")` para el orden.
  Textos en `dictionaries/{es,en}.json` y aviso de «vuelta 1 derivada».

### Esfuerzo estimado

| Bloque | Días |
|---|---:|
| Loader FastF1 sprint + backfill de 29 sprints (~1-2 min/sprint con caché fría) | 0,5-1 |
| Loaders OpenF1 (2023+) y Jolpica sprint | 1 |
| dbt: staging, `int_fastf1_sprint_laps` (v1), `int_sprint_laptimes`, `session_type` en hechos, `has_sprint` | 2-3 |
| Tests dbt + QA | 1 |
| API (3 endpoints + tests + OpenAPI) | 0,5-1 |
| Web (selector en 3-4 pestañas, i18n, e2e Playwright) | 1-1,5 |
| **Total** | **6-8,5 (≈ 1,5 semanas)** |

Versión mínima (solo FastF1 + v1 derivada + `session_type` + API/web, sin OpenF1/Jolpica): ~4 días.

## Riesgos
- **Regresión por cambio de grano** de `fact_laptimes`: una consulta sin filtro de sesión
  mezcla sprint y carrera (vueltas 1..24 duplicadas, ritmo sesgado). Mitigar con test de grano y
  revisando los consumidores listados.
- **Validación poco independiente**: FastF1 y OpenF1 salen del mismo F1 Live Timing; lo
  independiente es la VR de Jolpica y el total de F1DB. La FIA (PDF), solo para casos puntuales.
- Dependencia de APIs de terceros (Live Timing vía FastF1, límites de OpenF1, Jolpica ~200
  peticiones/hora). Mitigan la caché y el bronze por sprint.
- v1 no calibrable en 5 sprints con SC y tiempos nulos → `timing_convention`.
- F1DB puede no reflejar la penalización en `race_time_penalty_millis` (2026 Miami): la v1
  derivada saldría 5 s desplazada. Mitigar con la mediana del desfase y un test de rango
  (v1 entre 0,9× y 1,6× la v2 del piloto) que dispare el uso del desfase.
- Licencia: los PDF de la FIA prohíben la reproducción sin permiso; no redistribuirlos.

## Prototipo (scratchpad `…/730e2b1e-…/scratchpad/sprint/`)
- `schedule.py` → `sprint_schedule_fastf1.csv` (30 fines de semana con sprint 2021-2026).
- `ff1_sprint_probe.py` → carga `get_session(a, r, 'Sprint')`, escribe
  `bronze_proto/fastf1/laps/season=YYYY/session=S/round=RR.parquet` y mide frente a F1DB.
- `measure_all.py` → `coverage_fastf1_sprint.csv` (tabla de completitud); `anomalies.py`.
- `openf1_sessions.py`, `openf1_probe.py` → `openf1_sprint_sessions.csv` y bronze OpenF1.
- `compare_ff1_openf1.py` (validación cruzada), `jolpica_probe.py`, `sq_probe.py`,
  `lap1_derivation.py` (calibración de la v1), `fia_2022_04_ita_sprinthistorychart.txt`.
- `proposal/fastf1_loader_sprint.py` y `proposal/int_fastf1_sprint_laps.sql` (código propuesto).

Código clave (reconstrucción de la v1, del prototipo dbt):

```sql
session_offset as (
    select race_id, median(lap1_from_start_ms - (race_time_ms - rest_ms)) as start_offset_ms
    from per_driver                 -- race_time_ms = race_time_millis - race_time_penalty_millis
    where race_time_ms is not null and rest_laps = race_laps - 1
    group by race_id
)
-- v1 = race_time_ms - suma(v2..n)   si el piloto tiene total oficial y vueltas 2..n completas
--    = (Time - LapStartTime de la v1) - start_offset_ms   en otro caso
```

Carga de la sesión (loader propuesto):

```python
def _load_sprint(event, season):
    session = event.get_session("Sprint")  # válido en los tres formatos 2021+
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    laps = _with_keys(timedeltas_to_millis(pd.DataFrame(session.laps)), event, season)
    laps.insert(3, "session", "SPRINT")
    write_parquet(laps, race_path("sprint_laps", season, int(event["RoundNumber"])))
```
