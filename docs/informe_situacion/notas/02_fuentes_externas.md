# 02 · Fuentes externas para cubrir y contrastar huecos

> Nota de investigación (29-09-2026). Consultas web + peticiones reales pequeñas a las APIs públicas.
> No se ha accedido a formula1db.com (su robots.txt veta explícitamente a ClaudeBot), no se ha
> intentado saltar ninguna protección y no se ha descargado ningún volcado completo.

## 1. Resumen ejecutivo

- **Lo que ya tenemos es más de lo que ofrece casi cualquier fuente abierta**: posiciones vuelta a
  vuelta de las 1 125 carreras 1950–2024 (CSV de formula1db.com), tiempos por vuelta desde 1990,
  neumático por vuelta desde 2011 y paradas de F1DB desde 1994. El problema no es tanto *cubrir*
  como *contrastar*: antes de 1996 formula1db es fuente única.
- **Jolpica-F1** es la integración más rentable: mismo esquema que el volcado Ergast que ya
  cargamos, pero vivo (2023–2026 incluidos), con volcados CSV/SQL de ~14,5 MB. Da una tercera
  fuente independiente de vueltas (1996+) y paradas con duración (2011+) también para 2023–2026.
- **OpenF1** (2023+) y **F1 Live Timing** vía FastF1 (2018+) cubren lo que falta en la era moderna:
  mensajes de dirección de carrera (banderas, SC/VSC, bandera roja, sanciones), meteorología,
  sectores, speed traps, vueltas de sprint y libres, y el **tiempo parado** en boxes (solo ~2024+).
- **Pre-1996 no existe ninguna fuente abierta y descargable de tiempos por vuelta.** Las únicas
  alternativas son Forix/Motorsport Stats (comercial, lap-by-lap desde 1981), StatsF1 (posiciones
  vuelta a vuelta, solo consulta manual) y el proyecto `f1resultsdatabase` (SQLite ODbL construido
  a partir de StatsF1, Motorsport Stats y formula1.com: útil para validar, con riesgo de licencia).
- **Eventos históricos** (SC 1973+, bandera roja 1950+, VSC 2015+) están en listas de Wikipedia y
  su derivado CSV de TracingInsights/Kaggle; la **meteorología** histórica puede aproximarse con el
  reanálisis ERA5 de Open-Meteo (1940+, CC BY 4.0).
- **Licencias:** F1DB es CC BY 4.0; Jolpica y OpenF1 son **CC BY-NC-SA 4.0** (no comercial y
  «compartir igual»). El repositorio no tiene fichero LICENSE ni atribuciones: hay que añadirlos
  antes de integrar nada NC-SA.

## 2. Punto de partida: qué tenemos (bronze medido el 29-09-2026)

| Dato | Cobertura propia | Fuente actual | Observación |
|---|---|---|---|
| Posición vuelta a vuelta (lap chart) | 1950–2024, 1 125/1 125 carreras (1 252 550 filas) | formula1db (CSV TFG) | Fuente única antes de 1996 |
| Tiempo por vuelta | 1950–1989: < 1 % de vueltas con tiempo (505/110 056 en los 50; 3 531/171 428 en los 80); 1990+ casi completo | formula1db; Ergast 1996–2022; FastF1 2018+ | 1990–1995 solo formula1db |
| Sectores por vuelta | 1990+ (formula1db); 2018+ FastF1 | formula1db, FastF1 | — |
| Neumático por vuelta | 2011+ (formula1db, etiquetas S/M/H/SS/US/I/W); 2018+ FastF1 (compuesto, stint, vida) | formula1db, FastF1 | Nada antes de 2011 |
| Paradas | F1DB 1994+ (vuelta + tiempo en pit lane, 22 535 filas); Ergast 2011–2022 (duración) | F1DB, Ergast | Nada antes de 1994; sin tiempo parado |
| Clasificación | F1DB: tiempo 1950+; Q1/Q2/Q3 2006+; Q1/Q2 de días separados 1980–2005 | F1DB | FastF1 toma Q1–Q3 de Ergast (no independiente) |
| Libres / warm-up / precalificación | F1DB: FP1–FP2 1986+, FP3 2003+, warm-up 1984–2003, preclasif. 1977–1992 (solo mejor tiempo) | F1DB | Sin vueltas |
| Sprint | F1DB: resultados 2021+, parrilla, sprint quali 2023+ | F1DB | Sin vueltas de sprint |
| SC/VSC/banderas | FastF1 `TrackStatus` por vuelta 2018+ | FastF1 | Sin mensajes de dirección de carrera ni histórico |
| Meteorología | — | — | FastF1 se carga con `weather=False` |
| Speed traps | FastF1 `SpeedI1/I2/FL/ST` 2018+ | FastF1 | — |

## 3. Pruebas reales realizadas (29-09-2026)

Peticiones pequeñas con `requests` desde `.venv/Scripts/python.exe`, cabecera `User-Agent` propia.

**OpenF1 — `https://api.openf1.org/v1/`**
- `meetings?year=2023` → 24 eventos; `sessions?year=2022` → 404 «No results found»: el histórico
  empieza en 2023. `sessions?year=2026&session_name=Race` → 25 carreras (ya incluye 2026).
- Imola 2024 (`session_key=9515`): `race_control` 100 mensajes (categorías Flag, Drs,
  SessionStatus, Other; banderas GREEN, YELLOW, DOUBLE YELLOW, CLEAR, BLUE ×68, BLACK AND WHITE,
  CHEQUERED; con `lap_number`, `sector`, `scope`); `pit` 27 filas con `lane_duration` pero
  `stop_duration` nulo; `stints` con compuesto y edad del neumático; `weather` 143 muestras
  (aire, pista, lluvia, viento, humedad, presión); `laps` con sectores, mini-sectores e
  `i1/i2/st_speed`; `session_result`; `overtakes` 133 filas; `starting_grid` → 404.
- Japón 2025 (`session_key=10006`): `pit` 21/21 con `stop_duration` (p. ej. 2,6 s) → el tiempo
  parado existe desde ~2024–2025. Bahréin 2023 (`session_key=7953`): `pit` → 404.
- China 2024 sprint (`session_key=9672`): 19 vueltas de Verstappen → vueltas de sprint disponibles.
- Límite: HTTP 429 con `retry-after: 1` al encadenar ~4 peticiones sin pausa (límite publicado
  3 req/s y 30 req/min sin cuenta).

**Jolpica-F1 — `https://api.jolpi.ca/ergast/f1/`**
- `laps` exige temporada y ronda (400 si no). 1995 → 0 vueltas; 1996 R1 → 812.
- `pitstops` 2010 → 0; 2011 R1 → 45 con `duration`.
- `qualifying` 1993 → 0; 1994 R1 → 26. 2024 R6 (Miami): Q1/Q2/Q3 y `sprint` presentes.
- 2026 al día: R5 con 1 206 vueltas y 34 paradas; `2026/results` 330 filas.
- `GET https://api.jolpi.ca/data/dumps/download/` (JSON, sin autenticación): volcados `csv` y `sql`
  de ~14,5 MB; «latest» del 26-09-2026 (solo patrocinadores) y «delayed» (14 días, gratuito no
  comercial). No se descargó.

**F1 Live Timing — `https://livetiming.formula1.com/static/`**
- `2017/Index.json` → 403; `2018/Index.json` → 200 con 20 eventos (falta Australia 2018).
- Feeds de una carrera 2025: TimingData, TimingAppData, RaceControlMessages, TrackStatus,
  WeatherData, PitLaneTimeCollection, PitStopSeries, TyreStintSeries, OvertakeSeries, LapSeries,
  TeamRadio, CarData.z, Position.z, etc.
- `PitStopSeries` (tiempo parado + tiempo en pit lane): 200 en Japón 2025 y Las Vegas 2024; 403 en
  China 2019, Hungría 2020, Portugal 2021 y São Paulo 2023.
- Bahréin 2018: RaceControlMessages, TimingAppData, TrackStatus y WeatherData disponibles.

**Otras**
- statsf1.com: robots.txt permite `*`, pero a peticiones no navegador devuelve una página «Erreur»
  → solo consulta manual (como ya se hizo en `revision_divergencias`).
- formula1.com: robots.txt no bloquea `/en/results`; hay «Pit stop summary» desde 1994 (Pacífico,
  Francia 1994), el mismo inicio que F1DB.
- TracingInsights/RaceData (GitHub): `safety_cars.csv` 375 filas (1973–2026),
  `red_flags.csv` 101 (1950–2026), `virtual_safety_cars.csv` 113 (2015–2026).
- TracingInsights-Archive/PitStops (MIT): un JSON por GP 2018–2026 con el ranking DHL
  (posición, equipo, piloto, tiempo parado, vuelta, puntos).
- Wikidata (`Q171864`, GP de Francia 1975): solo ganador, pole, vuelta rápida, distancia, fecha e
  identificadores externos (Freebase, Racing-Reference).
- Open-Meteo Archive (Monza, 07-09-1975): temperatura, precipitación y viento horarios devueltos.
- f1resultsdatabase: release `v2.10.1+20260921` (`sessionresults.zip`, 74 MB), no descargada.

## 4. Fichas por fuente

Para cada una: **datos y cobertura · acceso/formato · licencia/ToS/robots · fiabilidad ·
integración (bronze → dbt) · uso para contraste**.

### 4.1 APIs y bases abiertas (candidatas a ingesta)

#### Jolpica-F1 (sucesor de Ergast)
- **Datos:** temporadas, carreras, resultados, clasificación (Q1–Q3; desde 1994), sprint, paradas
  con duración (2011+), vueltas con posición y tiempo (1996+), clasificaciones del campeonato,
  estados. Actualizado en la semana del GP. Se nutre en parte de los PDF de la FIA con el parser
  `fia-doc` (2025+).
- **Acceso:** API REST compatible con Ergast (`/ergast/f1/{season}/{round}/laps/`); volcados CSV
  y SQL en `/data/dumps/download/`. Límite: 4 req/s y 500 req/h sin token; se exige un
  `User-Agent` identificativo.
- **Licencia:** datos CC BY-NC-SA 4.0 («freely available for non-commercial use»); código
  Apache-2.0; volcado inmediato solo para patrocinadores; gratuito con 14 días de retraso.
- **Fiabilidad:** alta desde 1996 para vueltas (heredada de Ergast); en `revision_divergencias`
  Ergast nunca discrepó en solitario de formula1db en 2018–2022. Riesgo: proyecto de voluntarios
  sin SLA.
- **Integración:** `ingestion/jolpica_loader.py` que descargue el volcado *delayed* (una petición
  semanal) → `bronze/jolpica/*.parquet` (sustituye a `bronze/ergast`, congelado en 2022). En dbt,
  `stg_jolpica__*` con el mismo mapeo de pilotos que Ergast (fecha de nacimiento + apellido).
- **Contraste:** 3.ª fuente de vueltas 2023–2026 (hoy solo formula1db + FastF1 hasta 2024 y FastF1
  en solitario después); paradas F1DB vs Jolpica (vuelta y duración) 2011+; clasificación Q1–Q3
  (ojo: FastF1 la toma de aquí, no son independientes); resultados de sprint vs F1DB.
- URLs: https://github.com/jolpica/jolpica-f1 · https://github.com/jolpica/jolpica-f1/blob/main/TERMS.md ·
  https://github.com/jolpica/jolpica-f1/blob/main/docs/rate_limits.md ·
  https://github.com/jolpica/jolpica-f1/discussions/261

#### OpenF1
- **Datos (2023+):** `sessions`/`meetings`, `laps` (sectores, mini-sectores, speed traps),
  `stints`, `pit` (pit lane y, desde ~2024–2025, tiempo parado), `race_control` (banderas por
  sector, SC/VSC, bandera roja, investigaciones y sanciones, DRS), `weather`, `position`,
  `intervals`, `overtakes`, `session_result`, `starting_grid`, `car_data` (telemetría ~3,7 Hz),
  `location`, `team_radio`. Incluye libres, clasificación sprint y sprint.
- **Acceso:** REST JSON/CSV sin clave (3 req/s, 30 req/min); tiempo real solo con patrocinio
  (9,90 €/mes).
- **Licencia:** CC BY-NC-SA 4.0; no oficial ni asociado a F1/FIA/FOM.
- **Fiabilidad:** buena (procede del mismo live timing que FastF1); huecos puntuales
  (`pit` 404 en Bahréin 2023; `starting_grid` 404 en Imola 2024).
- **Integración:** loader por sesión (`sessions?year=`, luego endpoints por `session_key`) →
  `bronze/openf1/{endpoint}/season=/session=.parquet`. Primero `race_control`, `weather`, `pit`,
  `stints` y `laps` de sprint. Modelos `fact_race_control_message`, `fact_weather_sample`,
  `fact_pit_stop` (con `stop_duration`).
- **Contraste:** vueltas y stints 2023+ contra FastF1 (misma raíz, pero distinto procesado:
  útil para detectar errores de FastF1 como los 35 neumáticos que violaban reglas); `pit` contra
  F1DB y Jolpica; resultados de sprint contra F1DB.
- URLs: https://openf1.org/ · https://openf1.org/docs/ · https://api.openf1.org/v1/sessions

#### F1 Live Timing vía FastF1 (ya integrado parcialmente)
- **Datos (2018+; falta Australia 2018):** vueltas, sectores, speed traps, compuesto/stint/vida,
  `TrackStatus` por vuelta, `RaceControlMessages`, `WeatherData`, telemetría y posición, todas las
  sesiones (FP1–FP3, Q, sprint shootout/quali, sprint, R). `PitStopSeries` (tiempo parado) solo
  desde ~2024. Antes de 2018 FastF1 solo ofrece lo que da Jolpica.
- **Acceso:** ficheros estáticos JSON/jsonStream sin autenticación; FastF1 (MIT) los cachea.
  Límite propio de FastF1: 500 peticiones/h.
- **Licencia/ToS:** datos propiedad de Formula One World Championship Ltd.; FastF1 se declara no
  oficial. No hay licencia explícita para el feed: uso razonable para análisis, sin redistribuir
  en bruto (la web y la API del proyecto publican derivados).
- **Fiabilidad:** alta en tiempos, pero `revision_divergencias` detectó que FastF1 se desvía en
  solitario en 1 085 tiempos y 1 144 posiciones (2018–2022) y viola reglas de neumáticos en 35
  casos.
- **Integración (bajo esfuerzo, ya hay loader):** activar `messages=True, weather=True` y añadir
  sesiones `S`, `SQ`/`SS`, `FP1–FP3` en `ingestion/fastf1_loader.py`; guardar
  `race_control_messages` y `weather_data` en bronze.
- **Contraste:** SC/VSC de `TrackStatus` contra la lista de Wikipedia/TracingInsights;
  paradas contra F1DB; sanciones contra documentos FIA.
- URLs: https://docs.fastf1.dev/ · https://github.com/theOehrly/Fast-F1 ·
  https://livetiming.formula1.com/static/2018/Index.json

#### F1DB (ya integrado)
- **Datos:** 1950–hoy; resultados, libres (1986+), warm-up, (pre)clasificación, sprint, parrillas,
  vueltas rápidas, paradas (1994+), piloto del día. Sin vueltas ni compuestos.
- **Formatos:** CSV, JSON, SQL (MySQL/PostgreSQL/SQLite) y SQLite; release tras cada GP.
- **Licencia:** CC BY 4.0 → exige atribución visible en web/API.
- **Contraste:** no es independiente de formula1.com para paradas (ambas empiezan en 1994).
- URL: https://github.com/f1db/f1db

### 4.2 Datasets derivados (GitHub, Kaggle, Hugging Face)

#### TracingInsights
- **RaceData** (CC0): tablas estilo Ergast 1950–hoy + `safety_cars` (1973+, causa, vuelta de
  despliegue y retirada), `red_flags` (1950+, vuelta, reanudación, incidente, excluidos),
  `virtual_safety_cars` (2015+), `virtual_safety_car_estimates.json`, accidentes mortales.
  Actualizado por GitHub Actions ≤ 3 h tras la carrera. Origen: Kaggle «Formula 1 Race Data» y
  «Formula 1 Race Events» (jtrotman), que a su vez derivan de Ergast y de listas de Wikipedia
  (CC BY-SA): el CC0 declarado no limpia esa cadena → citar Wikipedia.
- **Repos por temporada 2018–2026** (Apache-2.0): por sesión `session_laptimes.json`,
  `rcm.json` (mensajes de dirección de carrera), `weather.json`, `corners.json`, telemetría. Origen
  FastF1/MultiViewer/Jolpica: es un espejo, no una fuente independiente.
- **PitStops** (MIT): ranking DHL por GP 2018–2026 con tiempo parado y vuelta.
- **Integración:** `safety_cars`, `red_flags`, `virtual_safety_cars` como seeds o bronze
  (≈ 600 filas); resolver `Race` («1973 Canadian Grand Prix») a `race_id` de F1DB. PitStops DHL →
  `fact_pit_stop_stationary_top` para 2018–2023 (donde no hay `PitStopSeries`).
- **Contraste:** validar `TrackStatus` de FastF1 y las vueltas lentas del lap chart de formula1db
  (una SC debería comprimir los intervalos); validar vueltas y paradas en carreras con bandera roja.
- URLs: https://github.com/TracingInsights/RaceData · https://huggingface.co/datasets/tracinginsights/RaceData ·
  https://github.com/TracingInsights/2026 · https://github.com/TracingInsights-Archive/PitStops ·
  https://tracinginsights.com/data/

#### f1resultsdatabase (mclarenmp4-22)
- **Datos:** SQLite de 26 tablas; posiciones vuelta a vuelta 1950+, tiempos 1996+, sectores y
  compuestos 2018+, **paradas desde 1983** (tiempo parado 2018+), `TrackStatus` con SC desde 1973,
  sanciones estructuradas, Q1/Q2 de 1983–2005, warm-up 1984–2003, libres 2000–2003
  (newsonf1.com), meteo (Open-Meteo). Release `v2.10.1+20260921` (74 MB).
- **Origen:** scraping de StatsF1, APIs internas de motorsportstats.com, formula1.com, pitwall.app,
  TracingInsights y Wikipedia.
- **Licencia:** código GPL-3.0, datos ODbL 1.0, pero el origen (StatsF1, Motorsport Stats) no es
  abierto y el propio autor advierte de bloqueos de IP de StatsF1. **Riesgo alto para redistribuir.**
- **Uso recomendado:** solo validación interna (no publicar sus datos): segunda fuente de lap
  chart 1950–1995 (hoy solo formula1db) y de paradas 1983–1993 (hoy ninguna).
- URL: https://github.com/mclarenmp4-22/f1resultsdatabase

#### Kaggle
- «Formula 1 World Championship (1950–2024)» de Rohan Rao: 14 CSV de Ergast, CC0. Redundante con
  Jolpica. https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020
- «Formula 1 Race Data» y «Formula 1 Race Events» (jtrotman): ver TracingInsights.
  https://www.kaggle.com/datasets/jtrotman/formula-1-race-events
- Hay decenas de conjuntos derivados (pit stops, etc.) sin valor añadido y con licencias dudosas.

#### Otros proyectos GitHub revisados
- `ekschallenberg/formula1project`: 589 081 vueltas 1996–2024 desde Ergast (redundante).
- `toUpperCase78/formula1-datasets`: CSV por temporada 2019–2026 (redundante).
- `harningle/fia-doc` (Apache-2.0): parsers de PDF FIA (clasificación, lap chart, history chart,
  lap analysis, paradas; probados en 2025+). Base para automatizar el arbitraje con la FIA.
- `f1dataR`, `LiveF1`: envoltorios de FastF1/Jolpica/live timing (no fuentes nuevas).
- Índice útil: https://github.com/subinium/awesome-f1

### 4.3 Fuentes oficiales (evidencia, no redistribución)

#### FIA — documentos y «Event & Timing Information»
- **Datos:** por GP, PDF de clasificación final/provisional, parrilla, vueltas rápidas,
  **Lap Chart, History Chart, Lap Analysis, Pit Stop Summary**, tiempos de libres y clasificación,
  **mejores sectores, speed trap, velocidades máximas**, decisiones de los comisarios (sanciones),
  notas del director de carrera. Páginas de timing verificadas para 2015; el archivo de
  clasificaciones cubre 2012–2025; el portal de documentos filtra 2019–2026 y 2015.
- **Acceso:** PDF (algunos escaneados → OCR). Sin API.
- **Licencia:** © FIA; términos genéricos. Ya acordado: **solo evidencia, no redistribuir**.
- **Fiabilidad:** máxima (árbitro en `revision_divergencias`).
- **Integración:** no en bronze público. Proceso interno de verificación por muestreo con
  `fia-doc`, guardando solo el veredicto (como `B*_*.csv`).
- URLs: https://www.fia.com/documents/championships/fia-formula-one-world-championship-14 ·
  https://www.fia.com/events/fia-formula-one-world-championship/season-2015/event-timing-information-3 ·
  https://api.fia.com/f1-archives

#### formula1.com — resultados
- **Datos:** resultados 1950+, vuelta rápida, parrilla, libres y clasificación; **Pit stop
  summary desde 1994** (parada, vuelta, hora, duración en pit lane, total). Premio DHL de vuelta
  rápida y de parada más rápida por temporada.
- **ToS:** © Formula One World Championship Ltd.; robots.txt no bloquea `/en/results`, pero los
  términos prohíben el uso automatizado que sobrecargue el servicio. Solo consulta puntual.
- **Contraste:** es el probable origen de las paradas de F1DB → no aporta independencia.
- URL: https://www.formula1.com/en/results/1994/races/606/pacific/pit-stop-summary

#### DHL Fastest Pit Stop Award
- Premio desde 2015; por GP, ranking de tiempos parados (equipo, piloto, vuelta). Sin API ni
  descarga (el espejo reutilizable es TracingInsights-Archive/PitStops 2018+).
- https://inmotion.dhl/en/formula-1/fastest-pit-stop-award ·
  https://en.wikipedia.org/wiki/DHL_Fastest_Pit_Stop_Award

#### Pirelli — press area
- Notas de prensa por GP desde 2011 con los compuestos nominados (C1–C6 desde 2019; nombres
  comerciales 2011–2018). HTML, © Pirelli; se usa como referencia (tabla pequeña hecha a mano).
- **Contraste:** regla «el compuesto usado debe estar entre los nominados» para formula1db (2011+)
  y FastF1 (2018+); completa `int_tyre_compound_mapping` fuera de 2019–2023.
- Antes de 2011 (Bridgestone 1997–2010, Michelin 2001–2006, Goodyear hasta 1998) solo hay notas de
  prensa y artículos dispersos (RaceFans, Autosport); no hay neumático por vuelta en ninguna
  fuente abierta.
- https://press.pirelli.com/?h=1&t=2024+Tyre+Compound+Choices ·
  https://www.racefans.net/2009/02/26/tyre-compounds-for-first-five-races-of-2009/

### 4.4 Sitios estadísticos (consulta manual; no scraping)

| Fuente | Qué ofrece | Cobertura | Acceso / condiciones | Uso propuesto |
|---|---|---|---|---|
| **StatsF1** (statsf1.com) | Inscritos, clasificación, parrilla, resultado, vueltas rápidas, «Tours en tête», **«Tour par tour» (posición por vuelta)** | 1950+ | HTML; robots permite `*`, pero bloquea clientes no navegador (página «Erreur»); datos © | Árbitro manual (ya usado); comprobar lap charts pre-1996 por muestreo |
| **formula1db.com** | Resultados, lap chart, tiempos por vuelta, vueltas rápidas, estadísticas de paradas (1994+) | 1950+ | robots prohíbe todo salvo Google/Seobility y veta ClaudeBot; Cloudflare y login | Ya tenemos el CSV del TFG; **no volver a scrapear** |
| **Forix / 8W** (Autosport) | Resultados con diferencias por vuelta desde 1981 y tiempos completos desde 1982 (según usuarios del foro de Autosport) | 1981+ | Suscripción; hoy parte de Motorsport Stats | Solo si se obtiene licencia |
| **Motorsport Stats** | Resultados, timing points, datos en vivo; 14 000 eventos desde 1911 | 1911+ | Comercial (API bajo contrato, info@motorsportstats.com) | Opción de pago para pre-1996 |
| **ChicaneF1** | Resultados de campeonato 1950+ y 600 carreras no puntuables 1945–1983 | 1945+ | HTML, © Jonathan Davies | Contraste de resultados y de carreras no puntuables |
| **GP Encyclopedia** (grandprix.com) | Crónicas y resultados históricos | 1950+ | HTML, © | Contexto narrativo |
| **F1-Fansite** | Resultados, clasificación, parrillas, libres | 1950+ | HTML, «All rights reserved» | Nada nuevo |
| **Motor Sport Magazine Database** | Carreras desde 1894, crónicas y archivo de la revista | 1894+ | HTML, © | Contexto; lap charts dispersos en crónicas |
| **Racing-Reference** | Resultados, vueltas lideradas; ID enlazado desde Wikidata (P6806) | 1950+ | 403 a clientes automáticos | Contraste de vueltas lideradas |
| **OldRacingCars** | Inscripciones y resultados 1966–1985, archivo McKinney 1949–1953 | 1949–1985 | HTML, «All rights reserved» | Coches compartidos y chasis (A1) |
| **teamdan.com** | Referenciado como web de lap charts; hoy **no responde** (error TLS) | — | — | Descartado |
| **Pitwall, LapF1, BigDataF1, F1TheData, F1 Tempo/GP Tempo** | Visores sobre Ergast/Jolpica/FastF1 (vueltas 1996+, telemetría 2018+) | — | HTML | Sin datos nuevos |
| **F1 Fantasy / F1 TV** | Puntuaciones de juego / vídeo y timing con suscripción | — | Login; ToS restrictivos | Descartado |
| **Sportradar, API-Sports** | APIs comerciales (vueltas, paradas) | Moderna | De pago | Descartado salvo presupuesto |

URLs: https://www.statsf1.com/fr/1962/france.aspx · https://www.statsf1.com/robots.txt ·
https://www.formula1db.com/robots.txt · https://8w.forix.com/ · https://www.forix.com/ ·
https://www.motorsportstats.com/ · https://www.chicanef1.com/ · https://www.grandprix.com/ ·
https://www.f1-fansite.com/f1-results/ · https://www.motorsportmagazine.com/database/series/f1/ ·
https://www.racing-reference.info/ · https://www.oldracingcars.com/f1/ · https://pitwall.app/ ·
https://www.lapf1.com/stats · https://www.bigdataf1.com/ · https://www.f1-tempo.com/ ·
https://developer.sportradar.com/racing/reference/f1-overview ·
https://forums.autosport.com/topic/191857-historical-pitstop-laptime-information-needed-for-exciting-project/

### 4.5 Complementarias

#### Wikipedia / Wikidata
- Wikipedia: artículos por GP (clasificación, parrilla, vueltas lideradas, incidentes), listas
  «List of red-flagged Formula One races» y artículo «Safety car» (despliegues). CC BY-SA 4.0 →
  atribución y «compartir igual» en lo derivado.
- Wikidata: por GP solo ganador (P1346), pole (P3764), vuelta rápida (P5053), distancia (P3157),
  fecha e IDs (Racing-Reference P6806). CC0. Útil como tabla puente de identificadores.
- https://en.wikipedia.org/wiki/List_of_red-flagged_Formula_One_races ·
  https://en.wikipedia.org/wiki/Safety_car · https://www.wikidata.org/wiki/Q171864 ·
  https://query.wikidata.org/

#### Open-Meteo Historical Weather (reanálisis ERA5)
- Temperatura, precipitación, viento… horarios desde 1940 en cualquier coordenada. API gratuita
  no comercial; datos CC BY 4.0. Resolución ~9–25 km: indica «lluvia probable», no estado de pista.
- Integración: `bronze/openmeteo/race_weather.parquet` por carrera (coordenadas de
  `circuit` de F1DB + hora de salida) → columna `weather_reanalysis_*` en `dim_race`, marcada como
  estimación. Contraste con `WeatherData` de FastF1/OpenF1 (2018+) y con el neumático «W/I» de
  formula1db (2011+).
- https://open-meteo.com/en/docs/historical-weather-api

## 5. Matriz hueco × fuente

Leyenda: **C** = cubre (integrable), **V** = sirve para validar/contrastar, **M** = solo consulta
manual o evidencia, **$** = de pago, **—** = no aporta. Entre paréntesis, años.

| Hueco | Jolpica | OpenF1 | FastF1/Live Timing | F1DB | FIA PDF | TracingInsights | f1resultsdatabase | StatsF1 | Forix/MS Stats | Otras |
|---|---|---|---|---|---|---|---|---|---|---|
| Tiempos por vuelta < 1990 | — | — | — | — | — | — | — | — | $ (1981/82+) | Crónicas de época (M) |
| Tiempos 1990–1995 (solo formula1db) | — | — | — | — | — | — | — | — | $ V | — |
| Tiempos 1996–2022 (3.ª fuente) | V (ya con Ergast) | — | V (2018+) | — | M | — | V | — | $ | — |
| Tiempos 2023–2026 | **C/V** | **C/V** | C (ya) | — | M | V (espejo) | V | — | $ | — |
| Lap chart 1950–1995 (solo formula1db) | — | — | — | — | — | — | **V** | **M** (tour par tour) | $ | — |
| Paradas < 1994 | — | — | — | — | — | — | **V** (1983+) | M | $ | — |
| Paradas: duración 2011+ | **C/V** | C (2023+) | C (2018+) | V (pit lane 1994+) | M | — | V | — | — | formula1.com (M) |
| Tiempo parado en boxes | — | C (~2024+) | C (`PitStopSeries` ~2024+) | — | M | C (DHL top, 2018+) | V (2018+) | — | — | DHL (M) |
| Neumáticos < 2011 | — | — | — | — | — | — | — | — | — | Notas de prensa Bridgestone (M, solo nominación) |
| Neumáticos 2011–2017 (solo formula1db) | — | — | — | — | M | — | — | — | — | Pirelli nominaciones (V) |
| Stints 2018+ | — | C/V (2023+) | C (ya) | — | M | V | V | — | — | Pirelli (V) |
| Clasificación Q1–Q3 | V (1994+; no independiente de FastF1) | C/V (2023+) | C (vía Jolpica) | C (ya) | M | — | V | M | — | — |
| Libres (vueltas) | — | C (2023+) | C (2018+) | resultado 1986+ | M | C (espejo) | V | M | — | — |
| Race control (banderas, SC/VSC, rojas) | — | **C** (2023+) | **C** (2018+) | — | M | C (`rcm.json`) | V | — | — | — |
| SC/VSC/bandera roja histórico | — | — | — | — | — | **C** (1950/1973/2015+) | V (SC 1973+) | M | — | Wikipedia (V) |
| Sanciones | — | C (mensajes 2023+) | C (mensajes 2018+) | parcial (penalización de tiempo/parrilla) | **M** (decisiones) | — | V | — | — | — |
| Meteorología | — | C (2023+) | C (2018+) | — | M | C (espejo) | V | — | — | **Open-Meteo C (1940+, estimada)** |
| Sectores y speed traps | — | C (2023+) | C (ya 2018+) | — | M (mejores sectores, speed trap) | — | V | — | — | — |
| Sprint: resultados | V (2021+) | V (2023+) | C | C (ya) | M | — | V | M | — | — |
| Sprint: vueltas | — | **C** (2023+) | **C** (2021+) | — | M | C (espejo) | V | — | — | — |
| Telemetría | — | C (2023+) | C (ya 2024–2026 quali) | — | — | C (espejo) | — | — | — | — |

## 6. Propuesta priorizada

| # | Acción | Cubre / contrasta | Esfuerzo | Riesgos |
|---|---|---|---|---|
| 0 | Añadir `LICENSE` + sección de atribuciones (F1DB CC BY 4.0, Jolpica/OpenF1 CC BY-NC-SA, FastF1 MIT, datos © F1/FIA) en README, web y API | Requisito legal | 0,5 días | Integrar NC-SA obliga a publicar los derivados como no comerciales y con la misma licencia |
| 1 | **FastF1 ampliado**: `messages=True`, `weather=True`, sesiones S/SQ/SS/FP1–FP3 en el loader existente | Race control, meteo, sprint (vueltas), libres 2018+ | 1–2 días (+ tiempo de backfill por el límite de 500 peticiones/h) | Más volumen en bronze; Australia 2018 sin live timing |
| 2 | **Jolpica** sustituye al volcado Ergast congelado: descarga semanal del volcado *delayed* | 3.ª fuente de vueltas y paradas 2023–2026; Q1–Q3; sprint | 1–2 días (mismo esquema que Ergast) | NC-SA; retraso de 14 días; sin SLA |
| 3 | **Eventos históricos** (SC/VSC/rojas) desde TracingInsights RaceData como seed | SC 1973+, rojas 1950+, VSC 2015+; validar `TrackStatus` y vueltas lentas | 1 día (resolver nombres de carrera → `race_id`) | Cadena de licencias desde Wikipedia (CC BY-SA): atribuir |
| 4 | **OpenF1** para 2023+: `race_control`, `pit` (tiempo parado), `stints`, `weather`, `overtakes` | Tiempo parado 2024+, adelantamientos, contraste con FastF1 | 2–3 días (paginación por sesión, 30 req/min) | NC-SA; huecos puntuales (404) |
| 5 | Tiempo parado DHL 2018–2023 desde TracingInsights-Archive/PitStops | Tiempo parado (solo mejores paradas por GP) | 0,5–1 día | Cobertura parcial (ranking, no todas las paradas) |
| 6 | Nominaciones Pirelli 2011+ como seed hecho a mano + test dbt «compuesto ∈ nominados» | Validar neumáticos formula1db 2011–2017 y FastF1 | 2 días (~300 GP) | Trabajo manual; nomenclatura pre-2019 |
| 7 | Meteo estimada con Open-Meteo para 1950–2017 | Condición de carrera histórica | 1 día | Resolución gruesa: etiquetar como estimación |
| 8 | Validación interna del lap chart 1950–1995 y paradas 1983–1993 contra f1resultsdatabase (sin publicar sus datos) | Primer contraste pre-1996 | 2–3 días | Licencia dudosa (StatsF1/Motorsport Stats): solo informes de diferencias; requiere permiso para descargar 74 MB |
| 9 | Verificación por muestreo con PDF FIA + `fia-doc` (2012+) | Árbitro automatizado de discrepancias | 3–5 días | PDF no redistribuibles; OCR en escaneados |
| 10 | Tiempos por vuelta pre-1990 | Sin fuente abierta: solo Forix/Motorsport Stats bajo licencia | — | Coste; fuera del alcance de un TFG |

**Orden recomendado:** 0 → 1 → 2 → 3 (una semana de trabajo cubre race control, meteo,
sprint, eventos históricos y la 3.ª fuente 2023+), después 4–7 y, si interesa la historia
anterior a 1996, 8–9. El punto 10 se documenta como limitación conocida.

### 6.1 Correspondencia con los huecos de la nota 01

Qué fuente verificada aquí resuelve cada hueco de `01_inventario_huecos.md` (sustituye las
«hipótesis» de aquella nota por lo comprobado).

| Hueco (nota 01) | Fuente recomendada (verificada) | Acción de la tabla 6 |
|---|---|---|
| H1 Vueltas de sprint | FastF1 sesión `S` (2021+); OpenF1 `laps` (2023+, probado en China 2024: 19 vueltas) | 1 (y 4 para contraste) |
| H2 Banderas rojas | TracingInsights `red_flags.csv` (1950+, vuelta y reanudación); FastF1/OpenF1 race control (2018+/2023+); Wikipedia | 3 y 1 |
| H3 2025–2026 fuente única | Jolpica `/laps` y `/pitstops` (2026 R5 ya disponible); OpenF1 `laps`/`stints` | 2 y 4 |
| H4 Compuesto C1–C6 2024–2026 | Pirelli press area (nominación por GP) | 6 |
| H6 Tiempos 1990 y Hungría 1993 | Sin fuente abierta (Jolpica empieza en 1996); solo Forix/Motorsport Stats bajo licencia o PDF FOCA/FIA de época | 10 (limitación) |
| H7 Numeración 1994/2001 | Arbitraje manual FIA/StatsF1; f1resultsdatabase como segunda opinión interna | 8 |
| M3 Meteorología | FastF1 `weather=True` (2018+); OpenF1 `weather` (2023+); Open-Meteo ERA5 (1940+, probado) | 1 y 7 |
| M4 Race control y sanciones | FastF1 `messages=True` (2018+); OpenF1 `race_control` (2023+); decisiones FIA (evidencia) | 1, 4 y 9 |
| M5 Neumáticos antes de 2011 | Ninguna fuente abierta con neumático por vuelta; solo nominaciones Bridgestone en prensa | — |
| M7 Validación 1990–1995 | Ninguna fuente abierta de tiempos; posiciones contra f1resultsdatabase/StatsF1 | 8 |
| M9 Paradas Brasil/Mónaco 1994, Italia 1997 | formula1.com «Pit stop summary» existe para 1994 (consulta manual puntual) | manual |
| M10 Tiempo parado | OpenF1 `stop_duration` y `PitStopSeries` (~2024+); DHL vía TracingInsights-Archive/PitStops (2018+, solo mejores) | 4 y 5 |
| B1 Tiempos 1950–1989 | Sin fuente abierta | 10 |
| B2–B5 Lap chart, coches compartidos y vuelta rápida en los 50–70 | StatsF1 (`tour-par-tour`, `meilleur-tour`) manual; f1resultsdatabase para validar | 8 |
| B6 Hora de salida | Wikipedia; `sessions` de Jolpica (hora en carreras recientes) | manual |

## 7. Notas de cumplimiento

- formula1db.com: no se ha accedido (robots.txt veta ClaudeBot; Cloudflare/login). El CSV del TFG
  sigue siendo la única copia y no puede regenerarse: documentarlo como fuente congelada.
- StatsF1, Racing-Reference y los foros de Autosport bloquean clientes automáticos: solo consulta
  manual puntual; no se ha intentado sortear el bloqueo.
- PDF de la FIA: solo como evidencia; no se suben al repositorio ni a releases.
- Volcados (Jolpica 14,5 MB, f1resultsdatabase 74 MB) no descargados: requieren permiso explícito.
