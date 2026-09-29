# 08 · Gráficos, visualizaciones y récords en webs y proyectos externos de F1

Fecha de la investigación: 2026-09-29. Objetivo: catalogar qué gráficos, estadísticas y récords ofrecen otras webs, apps y proyectos de F1, contrastarlos con los datos que ya tiene `f1-data-platform` y proponer una lista priorizada de ideas para la web (https://f1-data-platform.vercel.app/es).

## 0. Metodología y limitaciones

- Búsquedas web y lectura de páginas públicas. Las descripciones de gráficos están redactadas con palabras propias; no se reproducen textos.
- **formula1db.com** responde 403 (Cloudflare) y su robots.txt prohíbe el scraping: **no se ha accedido a su contenido**. Lo que se dice de ella procede solo de los **títulos y URL indexados por el buscador** (que revelan su estructura de secciones y récords).
- **statsf1.com** devuelve error 500 a los clientes automáticos; su catálogo se reconstruye igualmente a partir de títulos indexados.
- Kaggle, Reddit, X/Instagram y Tableau Public requieren JS o sesión: se usan resultados de búsqueda y páginas de descripción, no el contenido interactivo.
- La disponibilidad de datos se ha comprobado con consultas `read_only` sobre `data/gold/f1.duckdb` (ver §1). Consultas de prueba: vueltas lideradas por piloto (Hamilton 5 529, Schumacher 5 111), victoria desde la posición de parrilla más retrasada (Watson, Long Beach 1983, desde la 22.ª), ganador más joven (Verstappen, 18,6 años) y grand slams (Clark 8). Es decir, los récords de este tipo **se pueden calcular ya**.

## 1. Qué datos tenemos (gold)

| Dato | Tabla | Cobertura |
|---|---|---|
| Resultados de carrera y sprint: posición, parrilla, puntos, pole, vuelta rápida (VR), piloto del día, grand slam, posiciones ganadas, motivo de abandono, número de paradas | `fact_race_result` | 1950–2026 |
| Clasificación: Q1/Q2/Q3, mejor tiempo, % sobre la pole | `fact_qualifying_result` | 1950–2026 (Q1–Q3 desde 2006) |
| Posición y tiempo de cada vuelta, gap al líder | `fact_laptimes` | 1950–2026 (1 164 de 1 172 carreras; gap en 1 141) |
| Sectores S1/S2/S3 y speed trap por vuelta | `fact_laptimes` | 2018–2026 (187 carreras) |
| Compuesto, stint y edad del neumático | `fact_laptimes` | 2011–2026 (325 carreras) |
| Banderas por vuelta (SC, VSC, amarilla, roja), vuelta borrada | `fact_laptimes` | SC desde 1993 (268 carreras con SC) |
| Paradas con duración | `fact_pit_stops` | 1994–2026 (612 carreras) |
| Entradas y salidas del pit lane | `fact_pit_lane_passes` | parcial |
| Telemetría de la vuelta rápida de clasificación (velocidad, rpm, marcha, acelerador, freno, DRS, x/y) | `fact_quali_telemetry` | 2024–2026 (63 carreras) |
| Clasificación del campeonato tras cada carrera (pilotos y constructores) | `fact_driver_standing`, `fact_constructor_standing` | 1950–2026 |
| Agregados de carrera deportiva, temporada y duelos entre compañeros | `agg_*` | completo |
| Dimensiones: piloto (nacimiento, fallecimiento, nacionalidad), circuito (coordenadas, tipo, sentido, longitud, curvas), GP, motor, neumático | `dim_*` | completo |

**No tenemos**: telemetría de carrera (solo la vuelta de clasificación), clima y temperatura de pista, adelantamientos oficiales en pista (solo se pueden **aproximar** con cambios de posición vuelta a vuelta), minisectores, posiciones GPS en carrera, libres, radio, mensajes de dirección de carrera, penalizaciones como entidad, puntos del carné de la FIA, presupuestos o costes de daños.

---

## 2. Catálogo por fuente

Leyenda de la columna «¿Tenemos?»: ✅ sí, con los datos actuales · 🟡 parcial (solo algunas temporadas o con aproximación) · ❌ no.
Originalidad y valor para el público general: escala de 1 a 3.

### 2.1 formula1db.com (solo estructura indexada)
URL: https://www.formula1db.com/record · https://www.formula1db.com/races · https://www.formula1db.com/seasons

Los títulos indexados muestran una **matriz de récords muy sistemática**: `record/{driver|team|constructor}/{estadística}/{race}/{tipo}/{ámbito}`, donde:
- estadística: win, podium, point, pole-to-win, lead (vueltas lideradas), finish, start, hat-trick, grand-slam, combined-grand-slam (equipo)…
- tipo: `most` (total), `ratio` (porcentaje), `consecutive` (racha), `age/youngest|oldest`, `chronicle` (evolución histórica de quién tenía el récord);
- ámbito: `all` (carrera deportiva), `season`, `circuit`, `team`.

Por carrera: resultado, lap chart, tiempos por vuelta, VR, estadísticas de neumáticos y de paradas. Por temporada: vueltas lideradas y paradas.

| Elemento | Pregunta | ¿Tenemos? | Orig. | Valor |
|---|---|---|---|---|
| Récords con filtro de ámbito (total, temporada, circuito, equipo) y de tipo (total, %, racha, edad) | ¿Quién es el mejor en X, en una temporada o en un circuito? | ✅ | 2 | 3 |
| «Chronicle»: evolución del poseedor de cada récord | ¿Cómo ha pasado el récord de victorias de Fangio a Hamilton? | ✅ | 3 | 3 |
| % de puntos obtenidos sobre el máximo posible | ¿Quién aprovechó más su coche? | ✅ | 2 | 2 |
| Pole-to-win por circuito | ¿Dónde es más decisiva la pole? | ✅ | 2 | 2 |
| Vueltas lideradas por temporada o carrera y su % | ¿Quién dominó realmente la carrera? | ✅ | 1 | 3 |
| Estadísticas de neumáticos y paradas por carrera y temporada | ¿Qué compuesto funcionó? ¿Qué equipo para más rápido? | ✅ (2011+/1994+) | 1 | 2 |

### 2.2 statsf1.com
URL: https://www.statsf1.com/en/statistiques/pilote.aspx · https://www.statsf1.com/en/statistiques/constructeur.aspx · https://www.statsf1.com/en/statistiques/moteur.aspx

Estadísticas para **pilotos, constructores, motores, neumáticos, naciones y circuitos**, con subcategorías: número de GP, cronología, edad, parrilla, victorias, poles, VR, puntos (incluido «con más constructores distintos»), podios, **vueltas en cabeza** (total, por GP, en un año, consecutivas, GP liderados en un año), **km en cabeza**, y un bloque «misc» con **hat trick** y **grand chelem**. En cada GP hay «lap by lap» y resúmenes de vueltas en cabeza por temporada.

| Elemento | Pregunta | ¿Tenemos? | Orig. | Valor |
|---|---|---|---|---|
| Km en cabeza (vueltas lideradas × longitud del circuito) | ¿Quién ha liderado más distancia? | ✅ (`course_length`) | 3 | 2 |
| Estadísticas por motor y por marca de neumáticos | ¿Qué motor ha ganado más? | ✅ (`engine_manufacturer_id`, `tyre_manufacturer_id`) | 2 | 2 |
| Estadísticas por nación (pilotos y GP) | ¿Qué país tiene más victorias? | ✅ | 1 | 3 |
| Tabla «vuelta a vuelta» con el orden en cada vuelta | ¿Quién iba delante en la vuelta N? | ✅ | 1 | 2 |
| Puntos con más constructores distintos | ¿Quién ha puntuado con más equipos? | ✅ | 3 | 1 |

### 2.3 FIA: documentos de cronometraje (PDF)
URL: https://www.fia.com/eventtiming-information · ejemplos: [Race Lap Chart](https://www.fia.com/sites/default/files/2023_09_can_f1_r0_timing_racelapchart_v01.pdf), [Race History Chart](https://www.fia.com/sites/default/files/2024_01_brn_f1_r0_timing_racehistorychart_v01.pdf), [Race Lap Analysis](https://www.fia.com/sites/default/files/2023_08_esp_f1_r0_timing_racelapanalysis_v01.pdf)

| Documento | Qué muestra | ¿Tenemos? | Valor para la web |
|---|---|---|---|
| Lap Chart | Matriz posición × vuelta con el número de coche | ✅ (ya lo tenemos como lap chart de posiciones) | ya cubierto |
| History Chart | Por vuelta: coche, gap al líder y tiempo de vuelta, y «PIT» cuando para | ✅ (`gap_to_leader_ms`, `is_pit_in_lap`) | base del **race trace** (gráfico de huecos), que nos falta |
| Lap Analysis | Tiempos de cada piloto vuelta a vuelta, con las vueltas de parada marcadas | ✅ | cubierto por los tiempos por vuelta |
| Pit Stop Summary | Parada, vuelta, hora, duración en el pit lane y total acumulado | ✅ (1994+) | ya tenemos la media por constructor; falta la **tabla y el ranking de paradas** |
| Best Sector Times | Mejor S1/S2/S3 de cada piloto y **vuelta ideal** (suma de los mejores sectores) | ✅ (2018+) | nuevo: **vuelta ideal frente a vuelta real** |
| Maximum Speeds / Speed Trap | Velocidad punta en la trampa y en los puntos intermedios | 🟡 (solo speed trap, 2018+) | nuevo: **ranking de velocidad punta** |
| Classification | Resultado oficial | ✅ | cubierto |

### 2.4 formula1.com y F1 Insights powered by AWS
URL: https://www.formula1.com/en/results/awards · https://aws.amazon.com/sports/f1/ · https://corp.formula1.com/new-f1-insights-powered-by-aws-will-help-formula-1-fans-make-sense-of-split-second-decisions-on-the-track/

Archivo de resultados de formula1.com: resultado de la carrera, parrilla de salida, clasificación, sprint, **vueltas rápidas** (ranking de la VR de cada piloto), **resumen de paradas**, y premios (**DHL Fastest Lap** y **DHL Fastest Pit Stop**, piloto del día).

F1 Insights (unos 22 gráficos de TV):

| Gráfico | Qué responde | ¿Tenemos? | Comentario |
|---|---|---|---|
| Track Dominance | ¿Quién es más rápido en cada tramo del circuito? | 🟡 (telemetría de clasificación 2024+, x/y) | factible: trazado coloreado por el piloto más rápido en cada tramo |
| Car Performance Scores | Rendimiento en curva, en recta y de manejo por equipo | 🟡 (aproximable con el speed trap y los sectores 2018+) | una versión simplificada, «velocidad punta frente a tiempo en curva», es factible |
| Driver Season Performance (7 métricas: ritmo de clasificación, salidas, vuelta 1, ritmo de carrera, gestión de neumáticos, paradas, adelantamientos) | Perfil del piloto en una temporada | 🟡 (salidas y vuelta 1 con posiciones; ritmo con tiempos; neumáticos 2011+) | **radar del piloto**, muy vistoso |
| Battle Forecast | ¿En cuántas vueltas alcanzará al de delante? | 🟡 (se puede reconstruir a posteriori con gaps) | es un gráfico en directo; poco sentido en un histórico |
| Pit Window, Predicted Pit Strategy, Undercut Threat, Pit Strategy Battle | Estrategia en directo | 🟡 | se puede hacer un **análisis a posteriori de undercut y overcut** con posiciones antes y después de la parada |
| Tyre Performance | Degradación y vida útil del neumático | ✅ (2011+) | **curva de degradación por compuesto** |
| Time Lost, Pit Lane Performance | Tiempo perdido en la parada | ✅ (1994+) | cubierto en parte |
| Braking Performance, Corner Analysis, Exit Speed | Frenada y curvas | 🟡 (telemetría de clasificación 2024+) | análisis de curva en la vuelta de pole |
| Close to the Wall, Car Development, Alternative Strategy, Projected Knockout Time | Varios | ❌ | sin datos |
| Fastest Driver (ranking desde 1983) | ¿Quién es el más rápido de la historia a igualdad de coche? | ✅ (clasificación frente al compañero, desde 1950) | **ranking «a igualdad de coche»**, de gran valor |

### 2.5 F1 TV / Live Timing, MultiViewer y apps de cronometraje (Undercut, F1Dash, Formula Live Pulse, formula1dashboard)
URL: https://multiviewer.app/ · https://github.com/JustAman62/undercut-f1 · https://f1dash.net/ · https://www.f1livepulse.com/en/features/ · https://app.formula1dashboard.com/

Elementos comunes: torre de tiempos, driver tracker (mapa en vivo), página de stints de neumáticos, historial de tiempos por vuelta, **modo de comparación de gaps entre dos pilotos**, radio, dirección de carrera, gap al líder, delta frente a la media, calculadora de campeonato, **tracker de adelantamientos**, box plots de ritmo por equipo, «track DNA» y consistencia (formula1dashboard), costes de daños y elementos de unidad de potencia usados.

| Elemento | ¿Tenemos? | Valor |
|---|---|---|
| Gap entre dos pilotos elegidos, vuelta a vuelta | ✅ (1950+) | 3 |
| **Repetición animada** de la carrera (posiciones o gaps vuelta a vuelta con play/pause) | ✅ | 3 |
| Tracker de adelantamientos (aproximado por cambios de posición fuera de las paradas) | 🟡 | 2 |
| Calculadora de «¿quién puede ganar aún el título?» | ✅ (clasificación por carrera y calendario) | 3 |
| Consistencia (dispersión de las vueltas limpias) | ✅ | 2 |
| Radio, dirección de carrera, clima, elementos de la PU, costes de daños | ❌ | — |

### 2.6 f1-tempo.com y GP Tempo
URL: https://www.f1-tempo.com/ · https://www.gp-tempo.com/ · [hilo en F1technical](https://www.f1technical.net/forum/viewtopic.php?t=30189)

Superposición de telemetría de varias vueltas (velocidad, acelerador, freno, rpm, marcha, DRS), **mapa del circuito coloreado por el piloto más rápido en cada punto**, tiempos por vuelta por stint, dominio por sectores a lo largo de la temporada y **estado completo en la URL para compartir** cualquier comparativa.
- ¿Tenemos? 🟡: telemetría solo de la vuelta rápida de clasificación 2024–2026; sectores 2018+.
- Ideas: comparar la telemetría de 2 pilotos con una curva de **delta acumulado**; **mapa de dominio**; **«quién gana cada sector» a lo largo de la temporada**; compartir el estado mediante la URL, que es barato en Next.js con query params.

### 2.7 TracingInsights (web, GitHub, redes y Substack)
URL: https://tracinginsights.com/ · https://tracinginsights.com/analysis/lap-chart/ · https://github.com/TracingInsights/2026 · https://tracinginsights.substack.com

El catálogo más amplio: ritmo de carrera, **ritmo en tandas largas**, **degradación de neumáticos** (con corrección de combustible), **race trace**, lap chart, cambios de posición, **tiempo en tráfico** («drivers in traffic»), **vueltas en el top 10**, **valoración de la salida**, vuelta ideal, **mapa de calor de tiempos por vuelta**, velocidad punta en la trampa, diagrama g-g y aceleraciones lateral y longitudinal, % de acelerador a fondo, adelantamientos, **contendientes al título**, puntos del carné, temperatura de pista. Herramientas: corrección de combustible, ocultar outliers y mostrar el estado de pista (SC/VSC) sobre los gráficos.

| Elemento | ¿Tenemos? | Valor |
|---|---|---|
| Race trace (gap a un ritmo de referencia) | ✅ | 3 |
| Degradación con corrección de combustible | ✅ (2011+) | 2 |
| Mapa de calor de tiempos (piloto × vuelta) | ✅ | 2 |
| Vueltas en el top 10 y tiempo en tráfico (gap < 1 s al de delante) | ✅ (con gaps) | 2 |
| Valoración de la salida (posiciones ganadas en la vuelta 1) | ✅ (parrilla y posición en la vuelta 1) | 3 |
| Vuelta ideal | ✅ (2018+) | 2 |
| Franjas SC/VSC sobre los gráficos de la carrera | ✅ (1993+) | 3 |
| Diagrama g-g, aceleraciones, temperatura | ❌/🟡 | 1 |

### 2.8 Galería de ejemplos de FastF1
URL: https://docs.fastf1.dev/gen_modules/examples_gallery/index.html

16 ejemplos: estilo por piloto, **trazado con curvas numeradas**, dispersión de tiempos por vuelta coloreada por compuesto, distribución de tiempos (violines), cambios de posición, **comparativa de ritmo por equipo** (box plot), estrategias de neumáticos, resumen de clasificación (barras de gap a la pole), **«¿quién puede ganar aún el mundial?»**, **mapa de calor de posiciones del campeonato** (piloto × ronda), **resumen de temporada**, velocidades superpuestas, **marchas sobre el trazado**, velocidad con curvas anotadas, **velocidad sobre el mapa** y trazado medio de velocidad entre temporadas.
- Casi todo es ✅ con nuestros datos (la telemetría, 🟡). Lo que nos falta: mapa de calor del campeonato, «¿quién puede ganar aún?», box plot por equipo, marchas y velocidad sobre el trazado, curvas numeradas y resumen de clasificación con barras de gap.

### 2.9 OpenF1
URL: https://openf1.org/

API con 18 endpoints: telemetría a unos 3,7 Hz, posición GPS, intervalos, vueltas con minisectores, paradas, stints, radio, clima, dirección de carrera, **adelantamientos**, parrilla y clasificación del campeonato. Proyectos de la comunidad: circuito de LED, visualización en VR y generador de comentarios con IA.
- Interesante como **fuente futura**: clima, adelantamientos y dirección de carrera desde 2023. Hoy ❌ para nosotros.

### 2.10 formula1points.com
URL: https://www.formula1points.com/

Simulador de campeonato, **conversor de sistemas de puntuación** («¿quién habría ganado con los puntos de 1991?»), comparativa de pilotos y de compañeros, estadísticas de todos los tiempos, rachas, outliers, **animaciones** (carreras de barras), juegos (tipo Wordle: Driverle, Teammatle…), creador de tier lists.
| Elemento | ¿Tenemos? | Orig. | Valor |
|---|---|---|---|
| **Campeonatos recalculados con otros sistemas de puntos** | ✅ (resultados completos) | 3 | 3 |
| Bar chart race de victorias o puntos históricos | ✅ | 2 | 3 |
| Juego tipo Wordle de pilotos | ✅ (dimensiones) | 3 | 2 (engagement) |

### 2.11 RaceFans (datos interactivos de cada GP)
URL: [2026 Azerbaijan GP interactive data](https://www.racefans.net/2026/09/26/2026-azerbaijan-grand-prix-interactive-data-lap-charts-times-and-tyres/)

Por carrera: lap chart con resaltado del piloto al hacer clic, **gráfico de huecos respecto al tiempo medio de vuelta del ganador** (race history clásico), tiempos por vuelta sin las vueltas muy lentas, tablas de vueltas rápidas (tiempo, gap, **velocidad media** y vuelta), estrategias de neumáticos y **tabla de paradas con gap a la más rápida**.
- Todo ✅. Lo único que nos falta es el **race history/gaps**, más la velocidad media de la VR (derivable de `course_length` y del tiempo).

### 2.12 The Race / F1MATHS / laptime.me (análisis de ritmo)
URL: https://www.f1technical.net/news/28301 · https://laptime.me/laptime-me-f1-2026-fuel-adjusted-pace-analysis-miami/

Ranking de ritmo de carrera por **mediana de vueltas limpias** y corrección de combustible, **pecking order** por equipos a lo largo de la temporada (gap medio al más rápido, en %).
- ✅ Con los tiempos por vuelta (filtrando SC, entradas y salidas de boxes y la vuelta 1). **Pecking order de temporada** (gap de clasificación % por equipo y carrera): ✅ con `gap_to_pole_pct`, que ya existe.

### 2.13 Autosport Forix / Motorsport Stats
URL: https://www.forix.com/ · http://www.forix.com/8w/6thgear/index.html

Base de datos profesional: **gap charts desde 2012**, tiempos de vuelta con gráficos por piloto, «gap analysis». Da servicio de datos a medios.
- ✅ Ya lo cubrimos con más años (gaps desde 1950).

### 2.14 fermanpre/f1-stats (estilo Atlas F1) y otros «gap charts»
URL: https://github.com/fermanpre/f1-stats · https://github.com/izmishi/f1-lap-chart · https://davidor.github.io/formula1-lap-charts/ · https://f1-visualization.vercel.app/

- **Gap chart en tiempo absoluto que incluye a los doblados**, ranking de vueltas de todo el campo (todas las vueltas ordenadas de la más rápida a la más lenta) y resúmenes por piloto.
- izmishi: gap respecto a un **coche imaginario a ritmo constante**, lo que evita que la línea del líder sea plana.
- f1-visualization: **repetición animada** del gap al líder con play/pause y selección de vuelta.
- Todo ✅.

### 2.15 ChicaneF1 y grandprix.com (enciclopedias)
URL: https://www.chicanef1.com/ · https://www.grandprix.com/encyclopedia

Gráficos de puntos de la temporada, **matrices de participación** (piloto × carrera), perfiles de chasis, motores, diseñadores, patrocinadores y dorsales, carreras no puntuables (1945–1983) y buscador de récords.
- ✅ Matriz de participación y gráfico de puntos. ❌ Chasis, diseñadores y patrocinadores.

### 2.16 Wikipedia
URL: https://en.wikipedia.org/wiki/List_of_Formula_One_driver_records · https://en.wikipedia.org/wiki/List_of_Formula_One_race_records · https://en.wikipedia.org/wiki/Grand_Slam_(Formula_One)

- **Matriz de resultados del campeonato** (piloto × GP) con el color de cada celda según el resultado: oro para la victoria, plata, bronce, verde si puntúa, azul si termina sin puntos, morado si no se clasifica, negro si es descalificado… con superíndices para la pole, la VR y la posición en el sprint. Es el formato más reconocible por el aficionado. ✅ con nuestros datos.
- Lista de récords de pilotos organizada en 12 bloques (ver §3); récords de carrera: abandonos, paradas, adelantamientos, **márgenes de victoria**, velocidades medias, duración, **safety cars**, **banderas rojas**, calendario, temperatura y asistencia.

### 2.17 Kaggle, Tableau Public, comunidad de Power BI, Observable
URL: https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020 · https://public.tableau.com/app/profile/sports.chord/viz/VisualHistoryofF1Tableau/VisualHistoryofFormula1Tableau · https://community.fabric.microsoft.com/t5/Data-Stories-Gallery/Formula-1-analysis-1950-2021/m-p/2052947 · https://community.fabric.microsoft.com/t5/Data-Stories-Gallery/Power-BI-Animated-Bar-Chart-Race-for-Formula-1-season-2021/m-p/2256794 · https://observablehq.com/@dis-2025-fall/f1-top-15-bump-chart

Patrones repetidos: gantt de la historia de cada GP (qué años se celebró), mapa de circuitos (ya lo tenemos), distribución de carreras por mes, nacionalidades en gráfico de círculos, barras apiladas de motivos de abandono, **bar chart race**, **bump chart** (ranking a lo largo del tiempo, p. ej. ranking ELO de pilotos) y dashboard con 4 vistas (pilotos, equipos, temporadas y circuitos).
- ✅ Todo. De más valor: **gantt de la historia de los GP y los circuitos**, **evolución de los motivos de abandono (fiabilidad)**, **bump chart del campeonato** y ranking ELO.

### 2.18 Redes (F1Visualized, F1_charts, r/formula1, r/F1Technical)
URL: https://x.com/f1visualized · https://x.com/F1_charts · https://f1bythenumbers.com/r-formula1-or-r-f1art/

- F1Visualized (~120 mil seguidores en Instagram): resultados y estadísticas en **pixel art**; demuestra que la estética atrae más que el dato.
- En r/formula1 lo que más triunfa es el contenido visual; entre lo estadístico, las comparativas históricas simples (p. ej. «líder del campeonato tras N carreras en los últimos 10 años»).
- En r/F1Technical dominan la **degradación con corrección de combustible** (vida del neumático frente a tiempo corregido) y los cruces entre compuestos.

### 2.19 Modelos de valoración de pilotos (f1metrics, F1 Mathematical Model, F1-analysis)
URL: https://f1metrics.wordpress.com/2019/11/22/the-f1metrics-top-100/ · https://f1mathematicalmodel.com/2026/08/17/2026-mid-season-f1-driver-ratings/ · https://f1-analysis.com/2025/12/09/f1-2025-mathematical-driver-rankings/

Aíslan el efecto del coche comparando solo con el compañero de equipo y encadenan esos duelos entre temporadas para obtener un ranking histórico; corrigen por edad y experiencia.
- ✅ Tenemos `agg_teammate_h2h` (desde 1950). Un **ranking «a igualdad de coche»** sencillo (red de duelos entre compañeros) es muy original para una web pública.

### 2.20 Proyectos de GitHub parecidos
URL: https://github.com/hugoogb/f1-tracker · https://github.com/gaurab6969/F1-ErgastEra-Archive · https://github.com/PeterCollavino7/f1-analysis · https://github.com/smit-sms/Formula-One-Data-Visualization-Dashboard

f1-tracker (Next.js, FastAPI y PostgreSQL, desde 1950) es el más parecido a nuestro proyecto: progresión del campeonato, perfiles, comparativa de pilotos con **radar**, H2H de clasificación, posiciones vuelta a vuelta, estrategia de neumáticos, páginas de circuito con trazado SVG e historial, récords, **buscador universal** y colores de equipo.
- Nuestro diferencial: calidad de datos y validación entre fuentes, telemetría, violines de ritmo y matriz de compuestos. Nos falta: **páginas de circuito**, **radar**, **buscador** y **comparador libre entre dos pilotos cualesquiera**.

### 2.21 Prensa (FT, NYT, Guardian, Datawrapper)
No se han encontrado gráficos interactivos de F1 destacables de estos medios en la búsqueda. Lo que aparece son piezas sobre el dominio de una era (p. ej. el % de victorias de Mercedes en 2014 o de Red Bull en 2023; [Statista](https://www.statista.com/chart/18556/mercedes-f1-win-ratio)) y rankings de temporadas más dominantes. Idea derivada: el **«índice de dominio» por temporada** (% de victorias o de puntos del mejor equipo), que ✅ podemos calcular.

---

## 3. Catálogo de récords y estadísticas curiosas

Todas se calculan con `fact_race_result`, `fact_laptimes`, `fact_qualifying_result`, `fact_*_standing`, `agg_*` y `dim_driver`/`dim_race`. «Ámbito» indica en qué variantes merece la pena ofrecerlas (C = carrera deportiva, T = temporada, Ci = circuito, E = equipo).

| # | Récord / estadística | Definición | Fuente de inspiración | ¿Calculable hoy? | Ámbito |
|---|---|---|---|---|---|
| 1 | Victorias, poles, VR, podios, puntos, salidas | totales | todas | ✅ (ya en la web) | C/T/Ci/E |
| 2 | **Porcentajes** (victorias, poles, podios, puntos sobre el máximo posible) | con un mínimo de salidas | formula1db, Wikipedia | ✅ (`win_rate_pct` ya existe) | C/T |
| 3 | **Rachas**: victorias, podios, poles, VR, carreras en los puntos, carreras terminadas y salidas consecutivas | secuencias | formula1db, Wikipedia | ✅ | C/Ci |
| 4 | **Hat trick** (pole, victoria y VR) | | statsf1, formula1db | ✅ | C/T/E |
| 5 | **Grand chelem** (hat trick y liderar todas las vueltas) | | statsf1, Wikipedia | ✅ (`grand_slams`) | C/T/Ci |
| 6 | **Victorias desde la pole** y % de conversión de la pole | | Wikipedia, formula1db | ✅ | C/T/Ci |
| 7 | **Vueltas lideradas**, % de vueltas lideradas, carreras lideradas, **km en cabeza** | con `position = 1` | statsf1, formula1db | ✅ (1 164 carreras con vueltas) | C/T/Ci |
| 8 | Vueltas consecutivas en cabeza | secuencia a lo largo de varias carreras | statsf1 | ✅ | C |
| 9 | Liderar vueltas sin ganar nunca / más vueltas lideradas sin victoria | | Wikipedia | ✅ | C |
| 10 | **Edad**: más joven y más veterano en debutar, puntuar, subir al podio, ganar, lograr la pole o ser campeón | con `date_of_birth` | Wikipedia, formula1db | ✅ | C |
| 11 | **Remontada máxima**: victoria o podio desde la parrilla más retrasada; más posiciones ganadas en una carrera | `grid_position`, `positions_gained` | Wikipedia | ✅ | C/Ci |
| 12 | Carreras hasta la primera victoria, pole o podio; más carreras sin ganar | | Wikipedia | ✅ | C |
| 13 | Más podios sin ganar; más puntos sin ser campeón | | Wikipedia | ✅ | C |
| 14 | **Compañeros derrotados**: número de compañeros a los que se ganó en la temporada | con `agg_teammate_h2h` | f1metrics, formula1points | ✅ | C |
| 15 | **Duelos en clasificación y carrera contra el compañero** (% y rachas) | | formula1points, f1-tracker | ✅ (ya en la web) | T |
| 16 | Victorias con más equipos distintos, puntos con más constructores distintos | | statsf1 | ✅ | C |
| 17 | **Márgenes de victoria**: el más ajustado y el más amplio (tiempo y vueltas) | `gap_ms` y `gap_laps` del 2.º | Wikipedia (race records) | ✅ | Ci/T |
| 18 | Mayor diferencia en la pole (en %) | `gap_to_pole_pct` | Wikipedia | ✅ | T |
| 19 | Carreras con más y menos coches clasificados; motivos de abandono | `reason_retired` | Wikipedia | ✅ | T |
| 20 | Carreras con más **safety cars** o vueltas bajo SC; banderas rojas | con las banderas por vuelta | Wikipedia | 🟡 (1993+) | T/Ci |
| 21 | Parada más rápida por temporada y equipo; más paradas en una carrera | `fact_pit_stops` | DHL Fastest Pit Stop | ✅ (1994+; la duración total en el pit lane no es el tiempo parado) | T/E |
| 22 | Más cambios de líder en una carrera | cambios de `position = 1` | the-race, statsf1 | ✅ | Ci/T |
| 23 | **Adelantamientos aproximados** por carrera o piloto (cambios de posición fuera de las vueltas de parada, sin contar abandonos) | en `fact_laptimes` | OpenF1, TracingInsights | 🟡 (es aproximación: no cuenta adelantamientos intermedios) | Ci/T |
| 24 | Mejor salida (posiciones ganadas en la vuelta 1) | comparando la parrilla con la posición en la vuelta 1 | AWS, TracingInsights | ✅ | C/T |
| 25 | **Campeón decidido en la última carrera**, en qué ronda se decidió y el título más ajustado | `drivers_championship_decider`, standings | Wikipedia | ✅ | T |
| 26 | **Líder del campeonato tras la carrera N** frente al campeón final («¿el líder tras N carreras gana el título?») | con los standings | r/formula1 | ✅ | T |
| 27 | Índice de dominio (% de victorias o puntos del mejor equipo) | | Statista, prensa | ✅ | T |
| 28 | Porcentaje de dobletes (1-2) por equipo | `one_two_finishes` | formula1db (equipo) | ✅ | C/T |
| 29 | Victorias en casa (piloto que gana su GP nacional) | nacionalidad del piloto = país del GP | statsf1 (naciones) | ✅ | C |
| 30 | Estadísticas por motor y por neumático | | statsf1 | ✅ | C/T |
| 31 | Vuelta rápida más rápida por circuito y velocidad media | `course_length` / tiempo | RaceFans, Wikipedia | ✅ (ojo: trazados distintos del mismo circuito) | Ci |
| 32 | Victorias distintas: más GP distintos o más circuitos distintos ganados | | statsf1 | ✅ | C |
| 33 | Temporadas consecutivas con victoria o con pole | | Wikipedia | ✅ | C |
| 34 | Pilotos del día (desde 2016) | `is_driver_of_the_day` | formula1.com | ✅ | C/T |
| 35 | Récords de sprint (victorias, poles, puntos) | `session_type = 'SPRINT'` | Wikipedia | ✅ | C |
| 36 | «Chronicle»: cronología del poseedor de un récord | cálculo acumulado | formula1db | ✅ | C |
| 37 | Temperatura de pista, asistencia | | Wikipedia | ❌ | — |

---

## 4. Lista consolidada y deduplicada de ideas (ordenada por valor/esfuerzo)

Valor: interés para el público general y para la defensa del TFG (1 a 5). Esfuerzo: S = horas, M = 1–2 días, L = más de 3 días. «Hoy» indica si es factible con los datos actuales.

| # | Idea | Tipo | Inspiración | Valor | Esfuerzo | Hoy |
|---|---|---|---|---|---|---|
| 1 | **Race trace / gráfico de huecos** (gap de cada piloto respecto al ritmo medio del ganador, con marcas de parada, SC/VSC y VR) | carrera | FIA History Chart, RaceFans, TracingInsights, izmishi | 5 | S | ✅ 1950+ |
| 2 | **Franjas SC/VSC/bandera roja** sombreadas en todos los gráficos por vuelta que ya existen | carrera | TracingInsights, The Field | 4 | S | ✅ 1993+ |
| 3 | **Matriz de resultados de temporada estilo Wikipedia** (piloto × GP coloreada por resultado, con superíndices de pole y VR) | temporada | Wikipedia, ChicaneF1 | 5 | S | ✅ |
| 4 | **Récords ampliados**: rachas, hat tricks, victorias desde la pole y % de conversión, vueltas y km lideradas, edad (más joven y más veterano), remontadas, carreras hasta la primera victoria, márgenes de victoria. Con filtros de ámbito (carrera deportiva, temporada, circuito, equipo) y de tipo (total, %, racha, edad) | récords | formula1db, statsf1, Wikipedia | 5 | M | ✅ |
| 5 | **Mapa de calor o bump chart del campeonato** (posición en la clasificación × ronda) y **«¿quién puede ganar aún?»** | temporada | FastF1, Observable | 4 | S | ✅ |
| 6 | **Tabla de paradas y ranking de la parada más rápida** (por carrera y temporada, con gap a la más rápida) | carrera/temporada | FIA Pit Stop Summary, RaceFans, DHL | 4 | S | ✅ 1994+ |
| 7 | **Valoración de la salida** (posiciones ganadas o perdidas en la vuelta 1, por carrera y temporada) | carrera/piloto | AWS, TracingInsights | 4 | S | ✅ |
| 8 | **Vueltas lideradas por carrera** (barra o anillo del % de vueltas en cabeza de cada piloto) y cambios de líder | carrera | statsf1, formula1db | 4 | S | ✅ |
| 9 | **Comparador libre de dos pilotos** (en una carrera: gap entre ambos vuelta a vuelta; en su carrera deportiva: estadísticas enfrentadas y radar) | pilotos | Pitwall, f1-tracker, Undercut | 5 | M | ✅ |
| 10 | **Campeonatos con otros sistemas de puntos** («¿quién habría ganado en 2008 con los puntos de 2010?») | temporada | formula1points | 5 | M | ✅ |
| 11 | **Mejores sectores y vuelta ideal** frente a la vuelta real; **ranking de speed trap** | carrera | FIA Best Sector Times y Speed Trap | 3 | S | ✅ 2018+ |
| 12 | **Mapa de dominio del circuito** (trazado coloreado por el piloto más rápido en cada tramo) y **delta acumulado** entre dos vueltas de clasificación | carrera | AWS Track Dominance, F1 Tempo, GP Tempo | 4 | M | 🟡 2024+ |
| 13 | **Curva de degradación por compuesto** (edad del neumático frente al tiempo con corrección de combustible) | carrera | r/F1Technical, TracingInsights | 3 | M | ✅ 2011+ |
| 14 | **Pecking order de la temporada** (gap % a la pole o ritmo mediano por equipo y carrera, en líneas) | temporada | The Race, F1MATHS | 4 | S | ✅ |
| 15 | **Páginas de circuito** (historial de ganadores, récord de vuelta, % de victorias desde la pole, SC por edición, trazado) | circuito | f1-tracker, statsf1 | 4 | M | ✅ |
| 16 | **Repetición animada** (play/pause) del lap chart o del race trace | carrera | f1-visualization, F1 TV | 4 | M | ✅ |
| 17 | **Bar chart race histórico** (victorias o títulos acumulados por piloto, equipo, motor o nación) | récords | Power BI, Tableau, formula1points | 4 | M | ✅ |
| 18 | **Mapa de calor de tiempos por vuelta** (piloto × vuelta) y **consistencia** (dispersión de las vueltas limpias) | carrera | TracingInsights, formula1dashboard | 3 | S | ✅ |
| 19 | **«Chronicle» de récords** (línea escalonada con quién tuvo el récord de victorias o poles en cada momento) | récords | formula1db | 4 | M | ✅ |
| 20 | **Ranking «a igualdad de coche»** (red de duelos entre compañeros, al estilo ELO o f1metrics simplificado) | pilotos | f1metrics, AWS Fastest Driver | 5 | L | ✅ |
| 21 | **Radar de temporada del piloto** (clasificación frente al compañero, salidas, ritmo de carrera, consistencia, paradas del equipo, adelantamientos aproximados) | pilotos | AWS Driver Season Performance, f1-tracker | 4 | M | 🟡 |
| 22 | Estadísticas por **motor, neumático y nación**, y **victorias en casa** | récords | statsf1 | 3 | S | ✅ |
| 23 | **Fiabilidad**: evolución de los motivos de abandono por década o equipo | histórico | Tableau, Wikipedia | 3 | S | ✅ |
| 24 | **Índice de dominio** por temporada y ranking de las temporadas más dominantes | histórico | prensa, Statista | 3 | S | ✅ |
| 25 | **Gantt de la historia de los GP y circuitos** (qué años se celebró cada GP) | mapa/histórico | Tableau | 3 | S | ✅ |
| 26 | **Undercut/overcut a posteriori** (posiciones antes y después del ciclo de paradas entre rivales directos) | carrera | AWS Undercut Threat | 3 | M | ✅ 1994+ |
| 27 | **Adelantamientos aproximados** y tiempo en tráfico | carrera | OpenF1, TracingInsights | 3 | M | 🟡 |
| 28 | Estado de la vista en la URL para compartir cualquier comparativa | UX | GP Tempo | 3 | S | ✅ |
| 29 | Buscador universal (pilotos, equipos, circuitos) | UX | f1-tracker | 3 | S | ✅ |
| 30 | Juego tipo Wordle o quiz de pilotos | engagement | formula1points | 2 | M | ✅ |
| 31 | Clima, temperatura de pista, radio, dirección de carrera, adelantamientos oficiales | varios | OpenF1, F1 TV | 3 | L | ❌ (requeriría ingerir OpenF1, 2023+) |
| 32 | Diagrama g-g, telemetría de carrera, minisectores, Close to the Wall | telemetría | TracingInsights, AWS | 2 | L | ❌ |

**Top 5 recomendado a corto plazo** (máximo valor y mínimo esfuerzo, todo factible hoy): (1) race trace, (2) franjas SC/VSC en los gráficos existentes, (3) matriz de resultados estilo Wikipedia, (4) récords ampliados (rachas, hat trick, vueltas lideradas, edad, remontadas), (5) mapa de calor del campeonato y «¿quién puede ganar aún?». Después: el comparador libre de pilotos y los campeonatos con otros sistemas de puntos, que son los más «virales».

**Diferencial frente a la competencia**: pocas webs gratuitas ofrecen **gaps y posiciones vuelta a vuelta desde 1950** (Pitwall compara desde 1996, f1-visualization desde 1996, Forix desde 2012 y TracingInsights desde 2018). Un race trace y una repetición animada para carreras de los años 50 a 90 serían una rareza atractiva, siempre avisando de la calidad del dato con la página de calidad que ya existe.

---

## 5. Fuentes consultadas

- formula1db.com (solo títulos indexados): https://www.formula1db.com/record · https://www.formula1db.com/record/driver/lead/race/ratio/all/lap · https://www.formula1db.com/record/driver/hat-trick/race/chronicle · https://www.formula1db.com/record/driver/start/race/age/youngest · https://www.formula1db.com/races/2025-italian-grand-prix/stats/race/tyres · https://www.formula1db.com/seasons/2025/results?section=lead
- statsf1.com (títulos indexados): https://www.statsf1.com/en/statistiques/pilote.aspx · https://www.statsf1.com/en/statistiques/pilote/divers/hattrick.aspx · https://www.statsf1.com/fr/statistiques/pilote/divers/chelem.aspx · https://www.statsf1.com/fr/statistiques/pilote/entete/tour-consecutif.aspx · https://www.statsf1.com/en/statistiques/pilote/point/constructeur-different.aspx
- FIA: https://www.fia.com/eventtiming-information y los PDF enlazados en §2.3
- formula1.com: https://www.formula1.com/en/results/awards · https://www.formula1.com/en/results/2026/awards/fastest-pit-stops
- AWS F1 Insights: https://aws.amazon.com/sports/f1/ · https://aws.amazon.com/blogs/machine-learning/accelerating-innovation-how-serverless-machine-learning-on-aws-powers-f1-insights/
- F1 Tempo: https://www.f1-tempo.com/ · GP Tempo: https://www.gp-tempo.com/
- TracingInsights: https://tracinginsights.com/ · https://tracinginsights.substack.com/p/ferrari-disaster-class-is-hard-compound
- FastF1: https://docs.fastf1.dev/gen_modules/examples_gallery/index.html
- OpenF1: https://openf1.org/
- formula1points: https://www.formula1points.com/
- RaceFans: https://www.racefans.net/2026/09/26/2026-azerbaijan-grand-prix-interactive-data-lap-charts-times-and-tyres/
- The Field (guía de gráficos): https://www.thefieldf1.com/charts
- Pitwall: https://pitwall.app/
- Forix: https://www.forix.com/
- ChicaneF1: https://www.chicanef1.com/ · grandprix.com: https://www.grandprix.com/encyclopedia
- Wikipedia: https://en.wikipedia.org/wiki/List_of_Formula_One_driver_records · https://en.wikipedia.org/wiki/List_of_Formula_One_race_records
- Apps: https://github.com/JustAman62/undercut-f1 · https://f1dash.net/ · https://multiviewer.app/ · https://www.f1livepulse.com/en/features/ · https://app.formula1dashboard.com/
- Proyectos: https://github.com/hugoogb/f1-tracker · https://github.com/fermanpre/f1-stats · https://github.com/izmishi/f1-lap-chart · https://davidor.github.io/formula1-lap-charts/ · https://f1-visualization.vercel.app/ · https://github.com/PeterCollavino7/f1-analysis
- Comunidades: https://public.tableau.com/app/profile/sports.chord/viz/VisualHistoryofF1Tableau/VisualHistoryofFormula1Tableau · https://community.fabric.microsoft.com/t5/Data-Stories-Gallery/Formula-1-analysis-1950-2021/m-p/2052947 · https://observablehq.com/@dis-2025-fall/f1-top-15-bump-chart · https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020 · https://f1bythenumbers.com/r-formula1-or-r-f1art/ · https://x.com/f1visualized · https://x.com/F1_charts
- Modelos de pilotos: https://f1metrics.wordpress.com/2019/11/22/the-f1metrics-top-100/ · https://f1mathematicalmodel.com/2026/08/17/2026-mid-season-f1-driver-ratings/
- Ritmo: https://www.f1technical.net/news/28301 · https://laptime.me/laptime-me-f1-2026-fuel-adjusted-pace-analysis-miami/ · Statista: https://www.statista.com/chart/18556/mercedes-f1-win-ratio
