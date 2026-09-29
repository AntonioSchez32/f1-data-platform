# 09 · Gráficos propios: inventario, evaluación y propuestas

> Estado: COMPLETA (29/09/2026).

## 0. Resumen

- La web tiene **17 gráficos o mapas** en 16 entradas de inventario (13 ECharts, 1 violín SVG propio, 1 mapa mundial d3, 1 trazado SVG y 1 matriz-tabla), **15 tarjetas KPI** y unas **25 tablas**. Todos los gráficos van dentro de `ChartFigure`, con título, resumen en texto y la tabla de datos desplegable. La base de accesibilidad es buena y mejor que la de la mayoría de webs de F1.
- Réplica del TFG: las páginas de las figuras 5.23-5.33 están todas (mapa, récords de pilotos y constructores, temporada, clasificación, vuelta a vuelta, neumáticos, tiempos, ritmo, boxes y detalle de piloto). Además hay extras: evolución del campeonato, telemetría con trazado, fichas de constructor y calidad de datos.
- Problemas principales:
  1. **Color sin identidad**: la paleta Okabe-Ito de 8 colores se repite en carreras de 20 pilotos. Los compañeros no comparten color de equipo y en el violín dos pilotos distintos salen con el mismo color sin otra diferencia.
  2. **Solapamientos**: stints y matriz de neumáticos cuentan lo mismo. Hay tres gráficos y dos tablas de compañeros con la misma información. Las tarjetas de temporada repiten la tabla.
  3. **Errores de lectura concretos**: la «referencia» de clasificación no es la pole. La duración de parada es el tiempo en el pit lane, no la parada. Las temporadas sin carrera desaparecen del eje. Ferrari tiene barras a 0 en 1950-57. Las etiquetas del final de la evolución del campeonato se solapan. «1,000 m» aparece con el formato inglés.
  4. **Huecos de relato**: no hay página de circuito, ni «gap al líder», ni comparador libre de pilotos, ni fiabilidad o edades. Tampoco se ve cuándo se decidió el título.
- Propongo 26 visualizaciones nuevas (P1-P26, más la P1b), todas comprobadas contra `data/gold/f1.duckdb`, y una navegación con dos entradas nuevas: **Circuitos** y **Comparar**. Además, **Historia** agruparía Récords y las vistas por eras.

Fuentes: código de `web/src/app/[lang]/**` y `web/src/components/**` (sin modificar), la web desplegada (navegada el 29/09/2026 a 640 px y a 375 px de ancho), el TFG (texto de las figuras 5.23-5.33 extraído con `pdftotext`, porque el PDF no deja leerlo directamente) y `data/gold/f1.duckdb` en modo de solo lectura.

Capturas en `docs/informe_situacion/figuras/`:

| Fichero | Contenido |
|---|---|
| `web_lap_chart_bahrain2024.png` | Posiciones vuelta a vuelta, Bahrain 2024 |
| `web_tiempos_vuelta_bahrain2024.png` | Tiempos por vuelta (20 pilotos) |
| `web_violin_bahrain2024.png` | Violines de ritmo |
| `web_stints_bahrain2024.png` | Estrategia de neumáticos |
| `web_quali_gap_bahrain2024.png` | % sobre el mejor tiempo (etiquetas solapadas) |
| `web_telemetria_bahrain2024.png` | Velocidad, acelerador y freno |
| `web_temporada2021_kpi_progresion.png` | Tarjetas KPI y evolución del campeonato de 2021 (etiquetas solapadas) |
| `web_piloto_schumacher_kpi_puntos.png` | KPIs y puntos por temporada (los años 2007-2009 desaparecen del eje) |
| `web_piloto_schumacher_companeros.png` | Gráficos de compañeros |

---

## 1. Método

1. Lectura completa de las 17 páginas y de los 17 componentes visuales: tipos de marca, escalas, colores, datos de entrada y textos alternativos.
2. Navegación por la web desplegada: `/es`, `/es/seasons/2021`, `/es/races/1102` (Bahrain 2024) y sus pestañas, `/es/drivers/michael-schumacher`, `/es/constructors/ferrari` y `/es/records`. Se probó a 640 px y a 375 px de ancho.
3. Consultas de cobertura en DuckDB para saber qué gráficos se pueden dibujar y desde qué año (sección 5.0).

---

## 2. Inventario completo

Leyenda de accesibilidad:
- **F** = `ChartFigure`: título, resumen textual y tabla desplegable.
- **img** = contenedor `role="img"` con `aria-label`.
- **T** = tabla semántica: `caption`, `scope` y región desplazable con el teclado.

### 2.1 Gráficos y mapas

| # | Ruta | Componente | Tipo | Datos (endpoint) | Pregunta que responde | Interacción | Accesibilidad | TFG |
|---|---|---|---|---|---|---|---|---|
| G1 | `/` (#mapa) | `WorldMap` (d3-geo, SVG en servidor, sin JS) | Mapa de símbolos proporcionales (área ∝ √GP), proyección Equal Earth | `/circuits?season_from&season_to`; en la vista por país, centroide ponderado por carreras | ¿Dónde se ha corrido la F1 y cuánto? | Por país o por circuito (enlaces); rango de temporadas (formulario GET); `<title>` en cada círculo | `<title>`/`<desc>`, figcaption y tabla por país o circuito | 5.23 |
| G2 | `/seasons/[year]` | `ProgressionChart` | Líneas de puntos acumulados por ronda (top 10), con etiqueta al final | `/seasons/{y}/standings/progression?top=10` | ¿Cómo se fraguó el campeonato? | Tooltip por eje; resaltado de la serie al pasar | F, img, tabla piloto × ronda | Nuevo |
| G3 | `/races/[id]/qualifying` | `BarChart` vertical | Barras del % sobre el mejor tiempo de la sesión; la mejor en morado | `/races/{id}/qualifying?session=` → `gap_to_pole_pct` | ¿A cuánto quedó cada piloto o equipo del mejor tiempo? | Pilotos o constructores; Q o Q-sprint | F, img | 5.27 |
| G4 | `/races/[id]/lap-chart` | `LapChart` | Bump chart de posición por vuelta, con parrilla en la vuelta 0 y código del piloto al final | `/races/{id}/laps` + `/results` (parrilla) | ¿Cómo evolucionó el orden en carrera? | Resaltado al pasar; tooltip por punto | F, img, tabla salida/llegada/mejor/vueltas lideradas | 5.28 |
| G5 | `/races/[id]/tyres` | `StintChart` | Barras horizontales apiladas por stint; color Pirelli + letra | `/races/{id}/stints` | ¿Qué estrategia hizo cada uno? | Tooltip | F, img, leyenda con letra, tabla | 5.29 |
| G6 | `/races/[id]/tyres` (#matriz) | `CompoundMatrix` | Tabla-mapa de calor piloto × vuelta (compuesto; vuelta de entrada recuadrada) | `/races/{id}/laps` | ¿Qué neumático llevaba en cada vuelta y cuándo paró? | `title` por celda; desplazamiento horizontal | T con texto `sr-only` por celda | 5.29 (matriz) |
| G7 | `/races/[id]/pace` (#tiempos) | `LapTimesChart` | Líneas de tiempo por vuelta; 2 dataZoom (vueltas y tiempos) | `/races/{id}/laps` | ¿Cómo evolucionó el ritmo de cada piloto? | Casillas por piloto, Todos/Ninguno, ocultar vueltas neutralizadas, zoom | F, img, tabla vuelta × piloto | 5.30 |
| G8 | `/races/[id]/pace` (#ritmo) | `ViolinChart` (SVG propio, KDE de Silverman) | Violín + caja P25-P75 + mediana por piloto, ordenado por mediana | Laps filtrados: sin vuelta 1, boxes, SC/VSC/roja ni vueltas >150 % de la mediana; mín. 5 vueltas | ¿Quién tuvo mejor ritmo de verdad y lo mantuvo? | Casillas por piloto; `<title>` por violín | F, img, tabla mediana/mejor/P25-P75/nº | 5.31 |
| G9 | `/races/[id]/pitstops` | `BarChart` vertical | Barras del tiempo medio por equipo (paradas ≤ 60 s); la mejor en morado | `/races/{id}/pitstops` | ¿Qué equipo perdió menos tiempo en boxes? | Tooltip | F, img | 5.32 |
| G10 | `/races/[id]/telemetry` (desde 2024) | `TelemetryChart` | 3 paneles con el eje X compartido: velocidad, acelerador y freno frente a la distancia | `/races/{id}/telemetry?drivers=a,b` (vuelta más rápida de clasificación) | ¿Dónde gana tiempo un piloto frente a otro? | Selector A/B (formulario GET); eje enlazado | F, img, tabla tiempo/v. máx./v. mín./% a fondo | Nuevo |
| G11 | `/races/[id]/telemetry` | `TrackMap` | Trazado x/y coloreado por velocidad (azul→naranja), solo del piloto A | Igual que G10 | ¿Cómo es el circuito y dónde es rápido o lento? | Ninguna | `<title>`/`<desc>`; leyenda con `aria-hidden` | Nuevo |
| G12 | `/drivers/[id]` | `SeasonPointsChart` | Barras de puntos por temporada; título en morado y posición final encima | `/drivers/{id}/seasons` | ¿Cómo fue su carrera deportiva año a año? | Tooltip | F, img, tabla temporada/equipo/pos./pts/V/P/poles | 5.33 (parcial) |
| G13 | `/drivers/[id]` | `TeammatePointsChart` | Barras agrupadas: puntos propios frente a los de sus compañeros (trama diagonal) | `/drivers/{id}/teammates` agregado por temporada | ¿Sumó más que sus compañeros? | Leyenda y tooltip | F, img, textura además del color | 5.33 |
| G14 | `/drivers/[id]` | `TeammateShareChart` ×2 | Barras apiladas al 100 %: % por delante en clasificación y en carrera | Igual | ¿Batió a sus compañeros en clasificación y en carrera? | Leyenda y tooltip | F, img, textura | 5.33 |
| G15 | `/constructors/[id]` | `SeasonPointsChart` | Igual que G12 | `/constructors/{id}/seasons` | Evolución del equipo | Tooltip | F, img | Nuevo |
| G16 | `/records` | `BarChart` horizontal | Títulos por piloto o constructor en el rango de años | `/rankings/{entity}?order_by=championships` | ¿Quién tiene más títulos en esa época? | Entidad y rango de años | F, img | 5.24-5.25 |

### 2.2 Tarjetas KPI

| Ruta | Componente | Contenido | TFG |
|---|---|---|---|
| `/seasons/[year]` | `Highlight` ×3 | Campeón (o líder), equipo campeón (o líder) y victorias del campeón | 5.26 (tarjetas de campeón y equipo) |
| `/drivers/[id]` | `Stat` ×6 | Títulos, victorias, podios, poles, vueltas rápidas y salidas | 5.33 (tarjetas superiores) |
| `/constructors/[id]` | `Stat` ×6 | Títulos, victorias, podios, poles, dobletes y carreras | Nuevo |
| `/quality` | Párrafo resumen | «N controles superados, M fallidos» | Nuevo |

### 2.3 Tablas

| Ruta | Tabla | Observación |
|---|---|---|
| `/` | Top 10 de la última carrera; top 5 de pilotos y de constructores | Puerta de entrada; repite la página de temporada |
| `/seasons` | Tarjetas por década con los campeones | Es una lista de enlaces, sin datos |
| `/seasons/[year]` | Pilotos, constructores y calendario con ganador | Réplica de la figura 5.26 |
| `/races/[id]` | Resultado de carrera o sprint | Pills de vuelta rápida y dato corregido |
| `/races/[id]/qualifying` | Q1/Q2/Q3 con el mejor segmento en morado; % | La columna de % repite G3 |
| `/races/[id]/pitstops` | Lista de paradas; pasos por el pit lane que no son paradas | La segunda tabla es original y valiosa (SC, bandera roja, sanciones) |
| `/drivers`, `/constructors` | Top 50 por victorias o búsqueda | Sin orden por columnas (a diferencia de `/records`) |
| `/drivers/[id]` | Detalle de compañeros (temporada × compañero) | Más la tabla por temporada, repetida en los 3 gráficos |
| `/records` | Ranking ordenable (7 métricas) con rango de años | Réplica de las figuras 5.24-5.25 |
| `/quality` | Controles con umbral y controles informativos | Página original del proyecto |

---

## 3. Evaluación crítica

### 3.1 Problemas transversales

1. **Color y paleta.**
   - `LIGHT_SERIES` tiene 8 colores. A partir del 9.º piloto el color se repite y cambia el trazo (discontinuo o punteado), lo que funciona en líneas finas.
   - En el **violín** (G8) no hay trazo que valga: Hülkenberg y Piastri salen del mismo marrón, y Stroll y Pérez del mismo naranja (captura `web_violin_bahrain2024.png`).
   - No se usa el color del equipo. El aficionado espera Ferrari en rojo y los dos compañeros con el mismo tono. **Dato que falta**: no hay colores de equipo en gold. `stg_fastf1__results.team_color` existe, pero su vista apunta a un bronze que no está disponible (da error al consultarla), y además solo cubre 2018+. Propuesta: seed `constructor_colors.csv` (id, temporada desde/hasta, hex claro y oscuro) y usar variantes claras y oscuras para distinguir a los compañeros, manteniendo el trazo o la forma.
2. **Ejes de temporadas como categorías.** `SeasonPointsChart` y `TeammatePointsChart` usan `type: "category"`, así que las temporadas sin carrera desaparecen. En Schumacher, 2006 va pegado a 2010 y parece que no hubo retirada. Debe ser un eje de valor (años) o marcar los huecos.
3. **Puntos entre eras.** Los gráficos de puntos por temporada (G12, G15) mezclan sistemas de puntuación: 9 puntos por victoria en 1950 frente a 25 hoy, y ahora más carreras. Los 148 puntos de Schumacher en 2004 parecen poco frente a los 575 de Verstappen en 2023. Hace falta una métrica normalizada (sección 5, P14).
4. **Base del eje en cero donde no aporta.**
   - En la media de paradas (G9) las barras van de 24,1 a 27,2 s y el eje de 0 a 30: todas parecen iguales. En barras hay que empezar en 0, así que es mejor un gráfico de puntos o *dot plot* con el eje ajustado, o mostrar la diferencia con el mejor.
   - En telemetría (G10) la velocidad empieza en 0 km/h y la mitad inferior del panel queda vacía.
5. **Formato numérico en ECharts.** Los ejes usan el formato por defecto de ECharts y aparece «1,000 m» en la página española. Los tooltips sí usan `toLocaleString`. Falta un `axisLabel.formatter` con `Intl.NumberFormat(locale)`.
6. **Etiquetas que se solapan.**
   - `ProgressionChart`: `labelLayout.moveOverlap` no se aplica a `endLabel`. En 2021 «Max Verstappen» y «Lewis Hamilton» se pisan, y «Carlos Sainz Jr./Lando Norris/Charles Leclerc» no se leen.
   - Barras verticales de G3 con 20 pilotos: los valores «1,78 %», «1,79 %»… chocan entre sí y los nombres van girados 40°.
7. **Móvil (375 px).**
   - El lap chart se comprime en ~250 px de ancho y los intercambios en boxes forman una madeja ilegible.
   - Las pestañas de carrera y la navegación principal se desplazan en horizontal con una barra visible (se ve «Vuelta a vuelta» y la siguiente pestaña cortada).
   - El violín obliga a desplazarse en horizontal.
   - El mapa del inicio funciona bien porque es un SVG que se escala.
8. **Sin enlaces entre gráficos.** Ningún gráfico enlaza a la ficha del piloto o de la carrera (ECharts permite `on('click')`) ni recuerda la selección de pilotos entre pestañas. Las casillas de G7 y G8 son independientes: el aficionado marca 3 pilotos en tiempos y tiene que volver a marcarlos en el violín.
9. **Accesibilidad.** Lo correcto: figura, resumen, tabla, letras en compuestos, texturas en compañeros y `prefers-reduced-motion`. Mejorable:
   - `aria.enabled: false` es deliberado (la tabla sustituye al gráfico), pero el tooltip no es accesible con el teclado. No hay forma de «recorrer» la serie.
   - El texto del violín es de 10 px dentro de un `viewBox` que se escala hacia abajo: en la práctica queda por debajo de 8 px (captura).
   - El resumen de G16 dice «Lewis Hamilton suma más títulos: 7» cuando empata con Schumacher. Los resúmenes deberían detectar empates.
10. **Rendimiento y carga.** Cada pestaña de carrera vuelve a pedir `/laps` (unas 1 200 filas) y `/results`. Hay `cache` por petición, pero no entre pestañas. Es aceptable, aunque con Render free la primera visita tarda.

### 3.2 Evaluación de cada elemento

| # | Valoración | Puntos fuertes | Problemas concretos | Recomendación |
|---|---|---|---|---|
| G1 Mapa | **Útil** | Sin JS; rango de años; 2 vistas; tabla | Europa es una mancha de círculos que se solapan; el centroide por país sitúa a EE. UU. en medio del país y no en sus circuitos; no muestra el tiempo | Añadir un zoom a Europa (inserto) o una vista de «calendario por país × década» (P9); color por última temporada (vigente o histórico) |
| G2 Evolución campeonato | **Muy útil** | Cuenta la temporada; tabla completa | Etiquetas solapadas; 10 líneas con colores repetidos; los puntos absolutos esconden la diferencia en la lucha por el título | Añadir el modo «diferencia con el líder» (P1), resaltar por defecto los 2-3 aspirantes, marcar la ronda en que se decidió (`drivers_championship_decider`) |
| G3 % sobre el mejor tiempo | **Útil, con un fallo de relato** | Métrica fiel al TFG; modo por constructores | (1) La referencia es el mejor tiempo de cualquier segmento: en Bahrain 2024 la «referencia» es Leclerc (Q2, 1:29.165) y Verstappen, que hizo la pole, aparece a +0,016 %; el resumen dice «Leclerc marcó la referencia», lo que confunde. (2) Mezcla segmentos con distinta evolución de pista: Stroll (eliminado en Q2) queda por delante de Tsunoda porque su Q1 fue mejor. (3) Barras verticales con 20 nombres girados y etiquetas solapadas | Barras horizontales (como G16); nombrar la métrica «mejor vuelta de la sesión»; opción «por segmento» (Q1/Q2/Q3 por separado); marcar la línea de corte de Q1 y Q2 |
| G4 Lap chart | **Muy útil** | Etiqueta directa; parrilla en la vuelta 0; tabla con vueltas lideradas | Madeja en las ventanas de paradas (vueltas 10-17 y 30-38 en Bahrain); con 20 pilotos no se sigue a nadie salvo al que se resalta; no marca SC, abandonos ni paradas; datos desde 1950, pero en los años 50 solo el 56 % de las posiciones por vuelta tienen dato, así que las líneas salen rotas | Resaltar por defecto el top 3 y atenuar al resto; marcar las paradas con puntos y el SC/VSC con bandas; ofrecer al lado un «race trace» (P1b), que responde mejor a la pregunta «quién ganó por estrategia» |
| G5 Stints | **Muy útil** | Claro y fiel a la convención de la TV; letra en cada tramo; el duro con contorno | Eje hasta 60 cuando la carrera tiene 57 vueltas; no distingue neumático nuevo o usado (el 20 % de los stints de 2024 salen con más de 1 vuelta de uso, según `tyre_age_laps`); el primer stint de 1 vuelta (Hülkenberg) sale sin letra | `max = vueltas`; trama o transparencia para los usados; tooltip con la edad inicial |
| G6 Matriz | **Poco útil** (repetida) | Réplica fiel del TFG; accesible | Da la misma información que G5 en 20 × 57 celdas; obliga a desplazarse en horizontal; el recuadro de la vuelta de entrada no añade nada a los cortes de G5 | Fusionarla con G5 como su «tabla de datos», o reutilizar la forma de la matriz para algo nuevo: mapa de calor del **tiempo por vuelta respecto a la mediana** o de la **posición** (P3) |
| G7 Tiempos por vuelta | **Útil** para 2-4 pilotos, **poco útil** con 20 | Zoom doble (fiel al TFG); ocultar neutralizadas activado si hace falta; tabla completa | Con 20 líneas y 8 colores es ilegible (captura); las vueltas de boxes cortan las líneas; el eje de tiempos no es invertido (en F1 «más rápido» se suele dibujar arriba o se dibuja el delta) | Por defecto, solo el top 3 o los dos del mismo equipo; añadir la vista «delta con un piloto de referencia»; opción de corregir el combustible (P2) |
| G8 Violín | **Muy útil** | Filtro de vueltas cuidado (incluye la heurística del 150 %); orden por mediana; tabla | Colores repetidos sin otra diferencia; texto diminuto; ticks con valores extraños (1:41.470, 1:39.698…) en lugar de valores redondos; la cola de VER hasta 1:32.6 (vuelta rápida con blandos nuevos) alarga mucho la escala | Ticks redondos (cada 0,5 s o 1 s); color de equipo; nombres horizontales más grandes; opción de dividir el violín por compuesto (mitad izquierda y derecha, *split violin*) (P4) |
| G9 Media de paradas | **Poco útil tal como está** | Réplica del TFG; umbral de 60 s | La «duración» es el **tiempo en el pit lane** (mediana 2020s: 23,9 s), no la parada estática (unos 2-3 s), y el título no lo aclara; el eje en 0 aplana las diferencias; la media esconde las paradas malas | Renombrarlo a «Tiempo en el pit lane»; usar *strip plot* (una marca por parada) con la mediana; dato que falta: la parada estática (DHL Fastest Pit Stop o documentos de la FIA) |
| G10 Telemetría | **Útil** (con un fallo de relato) | Tres paneles enlazados; selector A/B sin JS | Es la **vuelta rápida de clasificación** dentro de una pestaña de carrera y el título no lo dice; no hay **delta de tiempo acumulado** (lo más informativo en una comparación de telemetría); `rpm`, `gear` y `drs` están al 100 % en gold pero no se usan; velocidad desde 0; el eje Y del freno sin sentido; «1,000 m» | Titular «Vuelta rápida de clasificación»; añadir el panel de delta (se integra con distancia y velocidad) y el de marchas; ajustar el eje de velocidad; ver P6 y P7 |
| G11 Trazado | **Útil** (atractivo) | Proporciones reales; escala continua | Solo el piloto A; no enseña la comparación que se acaba de elegir; la escala azul→naranja no marca dónde está la curva lenta | «Dominio por minisectores» A frente a B (P6) y el número de curva o la marcha en el trazado |
| G12 Puntos por temporada (piloto) | **Útil** | Título en morado; posición encima | Eje de categorías (se pierden los huecos); puntos no comparables entre eras; la barra no dice con qué equipo corrió | Eje temporal; alternar puntos, posición final y % de puntos posibles; color por equipo (P13) |
| G13 Puntos frente a compañeros | **Poco útil** (repetido) | Textura accesible | Repite lo que ya dicen G14 y la tabla; al sumar a varios compañeros en una temporada (1994: Verstappen + Lehto + Herbert) se mezclan duelos distintos | Fusionar con G14 en un solo gráfico de barras divergentes por temporada y compañero (P12) |
| G14 H2H clasificación y carrera (×2) | **Útil** | Porcentajes claros | Dos gráficos casi iguales uno al lado del otro; el apilado al 100 % gasta la mitad de la tinta en el «complemento» | Un único gráfico divergente: clasificación a la izquierda y carrera a la derecha, o 2 puntos por temporada |
| G15 Puntos por temporada (constructor) | **Poco útil** en equipos históricos | — | Ferrari 1950-57: el campeonato de constructores empezó en 1958, así que salen barras a 0 (el `points ?? 0` del código) con 3-7 victorias por temporada; puntos no comparables | Para antes de 1958, mostrar victorias o puntos de sus pilotos o un marcador «sin campeonato»; métrica normalizada |
| G16 Títulos | **Útil** | Horizontal, legible | Repite la columna «Títulos» de la tabla ordenable de al lado; el resumen no detecta el empate | Sustituirlo por algo que la tabla no dé: «títulos a lo largo del tiempo» (línea de tiempo por piloto, P16) |
| KPI temporada | **Poco útil** | Réplica fiel del TFG | El campeón sale 3 veces (tarjeta, pill en la tabla y resumen de G2); «victorias del campeón» es un dato pobre | Sustituirlas por KPIs de relato: margen del título, ronda de la decisión, nº de ganadores distintos, dominio del equipo (% de victorias) |
| KPI piloto y constructor | **Útil** | Resumen rápido | Sin contexto (¿91 victorias es mucho?) | Añadir el percentil o el puesto histórico («2.º de todos los tiempos») o el porcentaje (`win_rate_pct` y `podium_rate_pct` existen en `agg_driver_career`) |
| Tabla de pasos por el pit lane | **Muy útil** y original | Distingue parada, SC, bandera roja y abandono | Poco visible, al final de la pestaña | Integrarla como marcas en G4 y G5 |
| `/quality` | **Útil** para el TFG y la transparencia | — | Solo tablas | Opcional: gráfico de barras de % de coincidencia con la línea del umbral |

### 3.3 Repeticiones y solapamientos (qué fusionar o eliminar)

| Solapamiento | Elementos | Propuesta |
|---|---|---|
| **Estrategia de neumáticos** | G5 stints + G6 matriz + tabla de stints | Dejar G5. La matriz pasa a ser su tabla alternativa o se reutiliza como mapa de calor del ritmo (P3) |
| **Ritmo de carrera** | G4 posiciones + G7 tiempos + G8 violín | Cada uno responde a algo distinto, pero G7 con 20 pilotos no responde a nada. Propuesta: pestaña «Carrera» con G4 y el race trace (P1b); pestaña «Ritmo» con el violín y G7 limitado a 2-4 pilotos o en modo delta |
| **Compañeros de equipo** | G13 + G14 ×2 + tabla por temporada (repetida 3 veces como tabla de cada figura) + tabla de detalle | Un único gráfico divergente (P12) + una tabla de detalle |
| **Campeón de la temporada** | 3 tarjetas + pill de la tabla + resumen de G2 + tarjeta en `/seasons` | Tarjetas de relato (ver KPI temporada) |
| **% en clasificación** | G3 + columna % de la tabla de clasificación | Aceptable (la tabla es la referencia), pero G3 debería aportar algo más (segmentos, cortes) |
| **Títulos** | G16 + columna «Títulos» del ranking | Sustituir G16 (P16) |
| **Inicio frente a temporada** | Top 5 de pilotos y constructores del inicio = tabla de la temporada actual | Aceptable como portada; mejor un «mini G2» (la lucha por el título en una línea) |
| **Puntos por temporada** | G12 (piloto) y G15 (constructor) con el mismo componente | Correcto (reutilización); arreglar los ejes y la normalización |
| **Salida y llegada** | Tabla de G4 (salida, llegada) y tabla de resultado (parrilla, posición) | Aceptable |

### 3.4 Huecos de relato (preguntas típicas de un aficionado sin respuesta)

1. **«¿Por cuánto ganó y cuándo se decidió la carrera?»** No hay diferencias en el tiempo. `gap_to_leader_ms` está al 84-100 % desde 2022, y el tiempo acumulado (Σ `lap_time_ms`) lo reconstruye exactamente desde 1996: en Bahrain 2024, vuelta 30, el cálculo coincide con la fuente al centésimo.
2. **«¿Hubo adelantamientos? ¿Fue una carrera entretenida?»** No hay índice de cambios de posición ni de cambios de líder (calculable: media de cambios de líder por carrera de 4,0 en los 50, 1,8 en los 70 y 2,7 en los 2020).
3. **«¿Qué pasa en este circuito?»** No hay **página de circuito**, aunque `dim_race` tiene 78 circuitos con lat/lon, tipo, sentido, longitud y curvas. No se ven ganadores por circuito, conversión de la pole en victoria (Yas Marina 70,6 %, Catalunya 69,4 %…), probabilidad de SC ni récord de vuelta.
4. **«¿Quién es mejor: X o Y?»** No hay un comparador libre de pilotos. Solo se compara con los compañeros o, en telemetría, en una sesión.
5. **«¿Cuándo se decidió el título y quién podía ganarlo todavía?»** Hay 76 carreras marcadas como `drivers_championship_decider`, pero no se usan. Tampoco se calcula la eliminación matemática.
6. **Fiabilidad y abandonos por época.** `reason_retired` tiene datos de todas las décadas. Los clasificados pasan del 41 % en los 80 al 87 % en los 2020, y la parte mecánica de los abandonos baja del 86 % al 55 %.
7. **Edades y carreras deportivas.** Ganador más joven (Verstappen, 18,6 años) y edad media de la parrilla (35,1 en los 50 frente a 28,4 en los 2020). `date_of_birth` está al 100 %.
8. **Nacionalidades y «victorias en casa».** Hay 95 victorias en casa de 1 167.
9. **Equipos y motores.** No se ve el motor por equipo y temporada, aunque `engine_manufacturer_id` está en los resultados. Tampoco hay una línea de tiempo de las alineaciones.
10. **Sprint.** Hay resultado de sprint, pero no vueltas (ver nota 03).
11. **Datos que no tenemos.** Meteorología, mensajes de dirección de carrera (solo hay banderas por vuelta), parada estática y adelantamientos oficiales.

---
## 5. Propuestas nuevas

### 5.0 Qué se puede dibujar y desde cuándo (comprobado en `data/gold/f1.duckdb`)

| Dato | Tabla y columna | Cobertura |
|---|---|---|
| Posición por vuelta | `fact_laptimes.position` | Las 1 164 carreras disputadas desde 1950 (56 % de las filas con dato en los 50, 95 % en los 60, 100 % desde los 70) |
| Tiempo por vuelta | `fact_laptimes.lap_time_ms` | 0 % antes de 1990, 96,5 % en los 90, ~100 % desde 2000 (desde 1996 en la práctica) |
| Gap al líder | `gap_to_leader_ms` | 60-87 % por temporada desde 1996, 100 % en 2025-26; **reconstruible** exactamente con Σ `lap_time_ms` (comprobado en Bahrain 2024, vuelta 30: Pérez +15,68 s, Sainz +18,20 s en ambos cálculos) |
| Compuesto y edad del neumático | `tyre_compound`, `tyre_age_laps` | Desde 2011 (100 %); compuesto Pirelli C1-C5 desde 2019 |
| Sectores y speed trap | `sector_*_ms`, `speed_trap_kmh` | Desde 2018 (98 %) |
| Banderas por vuelta | `is_safety_car`, `is_yellow_flag`, `is_virtual_safety_car`, `is_red_flag` | SC desde los 90 (1 922 vueltas), VSC desde 2015, bandera roja desde 2000 |
| Paradas | `fact_pit_stops.time_ms` | Desde 1994 (612 carreras); es el tiempo **en el pit lane** (mediana de 30,0 s en los 90 y 23,9 s en los 2020) |
| Pasos por el pit lane | `fact_pit_lane_passes.pass_type` | pit_stop 22 485, unclassified 1 118, retirement 351, penalty_or_other 141, safety_car 114, red_flag 62 |
| Telemetría de clasificación | `fact_quali_telemetry` | 2024-2026 (63 carreras); ~450 puntos por vuelta; velocidad, rpm, marcha, acelerador, freno, DRS y x/y al 100 % |
| Clasificación del campeonato por ronda | `fact_driver_standing`, `fact_constructor_standing` | Todas las rondas desde 1950 (1950: 108/108 filas con posición) |
| Resultado | `fact_race_result` | Parrilla ~90 %; `reason_retired` con 198 valores distintos; `positions_gained`; `is_grand_slam` (71); piloto del día (2016+, 228) |
| Q1/Q2/Q3 | `fact_qualifying_result` | Desde 2006 (40 % de los 2000, ~99 % desde 2010); mejor tiempo desde 1950 (96 %) |
| Carrera | `dim_race` | 78 circuitos con lat/lon, tipo (ROAD/RACE/STREET), sentido, longitud, curvas; `drivers_championship_decider` (76 carreras) |
| Piloto | `dim_driver` | `date_of_birth` 100 % (917 pilotos), nacionalidad alpha2 |
| Compañeros | `agg_teammate_h2h` | 13 530 filas; grafo de 4 componentes conexas, con 810 pilotos en la mayor |

**Datos que faltan** para algunas propuestas:
- **Colores de equipo por temporada**: hace falta un seed. La vista `stg_fastf1__results.team_color` apunta a un bronze que no está disponible y solo cubriría 2018+.
- **Clasificación de `reason_retired`** en mecánico, accidente u otro: seed de unas 200 filas.
- **Parada estática** (solo tenemos el tiempo en el pit lane).
- **Meteorología**.
- **Mensajes de dirección de carrera** (solo hay banderas por vuelta).
- **Vueltas de sprint** (ver nota 03).
- **Adelantamientos oficiales**: los cambios de posición son un proxy.

Esfuerzo: **S** = menos de 1 día (reutiliza un endpoint o componente existente); **M** = 1-3 días (endpoint o modelo dbt nuevo); **L** = más de 3 días.

### 5.1 Carrera (pestañas de `/races/[id]`)

**P1b. Race trace: diferencia con el líder vuelta a vuelta.** *Esfuerzo S-M.*
- Pregunta: ¿por cuánto iba ganando, cuándo se abrió o cerró la carrera y qué hizo el SC con las diferencias?
- Boceto:
  - Eje X: vuelta. Eje Y: segundos detrás del líder, invertido, con el líder en 0 arriba.
  - Una línea por piloto; las vueltas bajo SC/VSC como bandas grises de fondo y las paradas como puntos huecos.
  - Etiqueta directa al final. Por defecto se resalta el top 5 y el resto va en gris al 25 %.
  - Variante: «delta con un piloto elegido» (la referencia horizontal es ese piloto).
- Datos: `fact_laptimes` (Σ `lap_time_ms` por piloto y vuelta; en cada vuelta, referencia = mínimo acumulado), `is_safety_car`/`is_virtual_safety_car`, `is_pit_in_lap`. Desde 1996.
- Dónde: pestaña «Vuelta a vuelta», junto a G4, con un conmutador «posiciones | diferencias».
- Accesibilidad: resumen generado («X abrió N s en M vueltas; el SC de la vuelta K dejó la ventaja en 1 s») y tabla vuelta × piloto.

**P2. Degradación por stint.** *Esfuerzo M.*
- Pregunta: ¿quién cuidó mejor los neumáticos? ¿Cuánto perdía por vuelta cada compuesto?
- Boceto:
  - (a) *Dot plot*: una fila por piloto; cada stint es un punto en X = pendiente en ms/vuelta, con color y letra del compuesto.
  - (b) Al pulsar un piloto, dispersión de tiempo corregido frente a la edad del neumático, con su recta de regresión por stint.
  - Corrección de combustible: restar la tendencia común de la carrera (mediana por vuelta de todos los pilotos) o un coeficiente fijo documentado como estimación.
- Datos: `regr_slope(lap_time_ms, tyre_age_laps)` por (piloto, stint) sobre vueltas limpias (sin vuelta 1, boxes ni SC/VSC; mínimo 8 vueltas). Probado en Bahrain 2024: pendientes de 6 a 123 ms/vuelta (Leclerc: 84 ms/vuelta con blando y 6 con el primer duro). La dispersión muestra que la corrección de combustible es imprescindible antes de publicarlo. Desde 2011.
- Dónde: pestaña «Neumáticos» o «Estrategia», **en lugar de la matriz G6**.
- Accesibilidad: tabla piloto/stint/compuesto/vueltas/pendiente; resumen «el que menos degradó con duro fue X».

**P3. Mapa de calor del ritmo (reutiliza la forma de la matriz).** *Esfuerzo S.*
- Pregunta: ¿en qué fase de la carrera fue rápido cada piloto?
- Boceto:
  - Filas = pilotos (orden de llegada); columnas = vueltas.
  - Color divergente = diferencia con la mediana de la vuelta, con los rápidos en azul y los lentos en naranja (apto para daltonismo).
  - Vueltas neutralizadas rayadas, paradas recuadradas y la letra del compuesto opcional.
- Datos: los mismos `laps` que usa hoy G6.
- Dónde: sustituye a G6.
- Accesibilidad: sigue siendo una `<table>` con el valor en texto `sr-only`, igual que la matriz actual.

**P4. Violín partido por compuesto.** *Esfuerzo S.*
- Pregunta: ¿el ritmo de X era mejor con medio o con duro?
- Boceto: mitad izquierda del violín con el compuesto 1 y mitad derecha con el compuesto 2, en colores Pirelli con contorno; ticks redondos.
- Datos: los de G8 más `tyre_compound`.
- Dónde: opción de G8.
- Accesibilidad: la tabla gana una columna por compuesto.

**P5. Detector de undercut y overcut.** *Esfuerzo M.* No lo he visto como gráfico automático en otras webs de aficionados.
- Pregunta: ¿quién ganó o perdió posiciones por la estrategia de paradas?
- Boceto:
  - Lista de «duelos de estrategia»; cada duelo es un mini *slope chart* con dos puntos (antes y después) y dos líneas (A y B).
  - Etiqueta: «Norris paró 2 vueltas antes que Leclerc → undercut logrado (+1 posición)».
  - Verde u óxido según el resultado, con icono ✓/✗ para no depender del color.
- Datos:
  - Heurística: A y B van consecutivos en pista la vuelta anterior a la parada de A; B para entre 1 y 3 vueltas después; se comparan las posiciones en la vuelta `lb+2`.
  - Resultado en 2024: **204 intentos, 49 undercuts logrados**.
  - Mejora: pedir que la diferencia previa sea menor de 3 s (con `gap_to_leader_ms` o el acumulado) y descartar las paradas bajo SC.
  - Desde 1996 (las paradas empiezan en 1994).
- Dónde: pestaña «Boxes» o «Estrategia» (le da el relato que ahora le falta).
- Accesibilidad: es una lista de frases; el gráfico solo ilustra.

**P6. Delta de tiempo y dominio por minisectores (telemetría).** *Esfuerzo M.*
- Pregunta: ¿en qué curvas gana tiempo A sobre B?
- Boceto:
  - (a) Panel nuevo encima de la velocidad: delta acumulado (s) frente a la distancia, con el cero en el centro; por encima, A es más lento.
  - (b) Trazado dividido en unos 25 minisectores, cada uno con el color del piloto más rápido en él y patrón o letra A/B para no depender del color. Es el gráfico más conocido de FastF1, pero no hay una web en español que lo ofrezca navegable.
- Datos: `fact_quali_telemetry` (distancia, velocidad, x, y). El tiempo acumulado se obtiene con t = Σ Δd/v y se interpola a una rejilla común de distancia. 2024+.
- Dónde: telemetría, que debería pasar a la pestaña Clasificación (sección 6).
- Accesibilidad: tabla por minisector (distancia, piloto más rápido, diferencia).

**P7. Mapa de marchas y DRS en el trazado.** *Esfuerzo S.*
- Pregunta: ¿cómo se conduce este circuito?
- Boceto: trazado coloreado por marcha (paleta ordinal de 8 pasos con el número en las zonas largas), tramos con DRS abierto en trazo grueso y RPM en el tooltip.
- Datos: `gear`, `drs`, `rpm` (100 %, sin usar hoy). 2024+.
- Dónde: telemetría y página de circuito (P24).

**P8. «Ghost race» animada.** *Esfuerzo L.* Inédita en formato accesible.
- Pregunta: ¿cómo se vería la carrera desde arriba?
- Boceto:
  - Un punto por coche (código y color de equipo) sobre la silueta del circuito, o sobre una recta horizontal que representa una vuelta cuando no hay trazado.
  - Posición = fracción de vuelta según el tiempo acumulado interpolado.
  - Controles: play/pausa, velocidad ×10/×30 y deslizador de vuelta. Bandas SC.
- Datos: Σ `lap_time_ms` (desde 1996); silueta de `fact_quali_telemetry` x/y (2024+) o, antes, una línea neutra.
- Accesibilidad:
  - Con `prefers-reduced-motion` se muestra en su lugar una serie estática de mini-gráficos (vueltas 1, 10, 20…).
  - El deslizador es un `<input type="range">` con `aria-valuetext` («Vuelta 23: 1.º VER, 2.º PER a 4,1 s…»).
  - Nunca arranca sola.

**P9. Parrilla → vuelta 1 → llegada (*slope chart*).** *Esfuerzo S.*
- Pregunta: ¿quién ganó posiciones en la salida y quién en la carrera?
- Boceto: 3 columnas (parrilla, fin de la vuelta 1 y llegada); una línea por piloto, verde si gana y óxido si pierde, con grosor o flecha como segunda señal; los abandonos terminan en una columna «Ab.».
- Datos: `grid_position`, `fact_laptimes.position` de la vuelta 1 y `position_number`. **Desde 1950.**
- Dónde: pestaña «Resultado», encima de la tabla.
- Extra histórico: ranking de «mejores salidas» (mínimo de 100 carreras: Jochen Mass +1,56 posiciones de media en la vuelta 1, Brundle +1,52, Stroll +1,34).

### 5.2 Temporada (`/seasons/[year]`)

**P1. Diferencia con el líder del campeonato y eliminación matemática.** *Esfuerzo S-M.*
- Pregunta: ¿cuándo se decidió el título y quién seguía con opciones?
- Boceto:
  - Eje X: ronda. Eje Y: puntos detrás del líder, invertido.
  - Banda sombreada con los «puntos que quedan en juego» (restantes × máximo por carrera; en gold, el máximo es 9 en 1950 y 1990, 25 en 2010 y 2025 y 26 en 2019 por la vuelta rápida, más el sprint).
  - Cuando la línea de un piloto sale de la banda, un ✕ indica que queda eliminado. Una línea vertical marca la carrera `drivers_championship_decider`.
  - Etiquetas directas con separación real (hay que resolver el solape de G2).
- Datos: `fact_driver_standing` (todas las rondas desde 1950), `fact_race_result.points` para el máximo por carrera y `dim_race.drivers_championship_decider`. Aviso: las reglas de «mejores N resultados» anteriores a 1991 hacen que la eliminación sea aproximada y hay que indicarlo.
- Dónde: modo alternativo de G2 (conmutador «puntos | diferencia | posición»).
- Accesibilidad: resumen «El título se decidió en la ronda N (GP de X); Y quedó eliminado en la ronda M».

**P10. Bump chart de posiciones en el campeonato.** *Esfuerzo S.*
- Pregunta: ¿cómo cambió el orden del campeonato ronda a ronda?
- Boceto: como G4, pero por ronda y con `position_number` de la clasificación del campeonato.
- Datos: `fact_driver_standing.position_number`.
- Dónde: tercera opción del conmutador de G2. Reutiliza `LapChart`.

**P11. KPIs de relato de la temporada.** *Esfuerzo S.* Sustituyen a las tarjetas actuales.
- Contenido: margen final del título, ronda en que se decidió, nº de ganadores distintos, % de victorias del mejor equipo y, en temporadas en curso, «carreras restantes / puntos en juego».
- Datos: standings, `is_win` y `drivers_championship_decider`.

### 5.3 Piloto y constructor

**P12. H2H divergente con los compañeros (fusiona G13 y G14).** *Esfuerzo S.*
- Pregunta: ¿batió a sus compañeros, y a cuál?
- Boceto:
  - Una fila por temporada y compañero; barra divergente desde el 50 %: a la derecha, % de clasificaciones ganadas; a la izquierda, perdidas.
  - Un segundo marcador (rombo) con el % en carrera.
  - Etiqueta con el nombre del compañero y color del equipo.
  - Se ve de un vistazo, por ejemplo, el 2010-2012 de Schumacher frente a Rosberg.
- Datos: `agg_teammate_h2h` (ya en `/drivers/{id}/teammates`).
- Accesibilidad: una única tabla (hoy la misma tabla aparece 3 veces).

**P13. «ADN» o carrera deportiva del piloto.** *Esfuerzo M.*
- Pregunta: ¿qué tipo de piloto es: poleman, de domingo, fiable, remontador?
- Boceto:
  - (a) Franja temporal (*swimlane*) sobre un eje de años continuo: las temporadas coloreadas por equipo y un punto con la posición final (eje invertido). Se ven los huecos, como la retirada de Schumacher de 2007 a 2009.
  - (b) «Huella» con 6 barras de percentil frente a los pilotos de su época (no radar, que distorsiona las áreas): % de victorias, % de podios, % de poles, H2H en clasificación, posiciones ganadas de media y % de abandonos. Cada barra lleva la cifra real.
- Datos: `agg_driver_career` (`win_rate_pct`, `podium_rate_pct`, `pole_positions`, `race_starts`), `agg_teammate_h2h`, `fact_race_result.positions_gained` y `reason_retired`. Para los percentiles, pilotos con más de 30 salidas en la misma década.
- Accesibilidad: tabla métrica/valor/percentil.

**P14. Comparación de eras normalizada.** *Esfuerzo S.*
- Pregunta: ¿quién habría sumado más con el sistema de puntos actual?
- Boceto: en `/records` y en la ficha, conmutador «puntos oficiales | sistema 2010 (25-18-15-12-10-8-6-4-2-1) | puntos por carrera».
- Datos: se recalcula desde `fact_race_result.position_number`. Comprobado (mínimo de 50 carreras), en puntos 2010 por carrera: Fangio 15,05, Verstappen 13,86, Hamilton 13,85, M. Schumacher 12,63, Prost 12,26, Clark 11,34, Senna 11,61 y Stewart 11,09.
- Dónde: `/records` (nueva métrica ordenable) y G12 (eje alternativo).
- Accesibilidad: es una columna más de la tabla.

**P15. Red de compañeros y «grados de separación».** *Esfuerzo M.* Inédito.
- Pregunta: ¿cómo se conecta Fangio con Antonelli?
- Boceto:
  - (a) Buscador de dos pilotos → camino mínimo dibujado como cadena horizontal de «fichas» (piloto → equipo y año → piloto…).
  - (b) Grafo de fuerzas opcional del vecindario a 2 saltos (no los 810 nodos a la vez).
- Datos: aristas de `agg_teammate_h2h`. BFS en Python sobre gold: **Fangio → Jo Bonnier → Rolf Stommelen → Riccardo Patrese → Michael Schumacher → Nico Rosberg → Lewis Hamilton → George Russell → Kimi Antonelli** (8 saltos). 4 componentes conexas; la mayor tiene 810 pilotos. Con más de 900 nodos, el BFS se calcula en milisegundos en la API (Python) o se precalcula. La consulta recursiva en SQL explotaba combinatoriamente y no conviene.
- Accesibilidad: el camino es una lista ordenada de texto; el grafo es decorativo, con alternativa textual.

**P16. Línea de tiempo de títulos (sustituye a G16).** *Esfuerzo S.*
- Pregunta: ¿quién dominó cada época?
- Boceto:
  - Eje X: temporada 1950-2026. Una fila por campeón, ordenada por su primer título.
  - Un cuadrado por título con el color del equipo y una línea fina que une su primer y último título.
  - Filtro por rango (el que ya existe).
- Datos: `agg_driver_season.championship_won` (o `/seasons`).
- Accesibilidad: tabla campeón → años.

**P17. Alineación y motor del constructor.** *Esfuerzo S.*
- Pregunta: ¿quién pilotó para el equipo y con qué motor?
- Boceto: *swimlane* por temporada con una fila por piloto (barra por temporada); banda superior coloreada por motor.
- Datos: `/constructors/{id}/seasons` (ya trae los pilotos) y `fact_race_result.engine_manufacturer_id` (22 fabricantes con victorias).
- Arreglo relacionado: en G15, antes de 1958 no dibujar barras a 0, sino un marcador «sin campeonato de constructores» o las victorias.

### 5.4 Historia (vistas agregadas nuevas)

**P18. Streamgraph de victorias por constructor, 1950-2026.** *Esfuerzo S-M.*
- Pregunta: ¿cómo han cambiado las eras de dominio?
- Boceto:
  - Eje X: temporada. El grosor de cada capa es el % de victorias de la temporada (normalizado, para que las temporadas de 7 y de 24 carreras pesen igual).
  - 10 equipos con más victorias en color y el resto en «otros» gris; etiquetas dentro de las capas; conmutador «constructores | motores».
  - Línea superpuesta con el «índice de dominio» (% de victorias del mejor equipo de cada año).
- Datos: `fact_race_result.is_win` × `constructor_id`/`engine_manufacturer_id` (38 constructores y 22 motores con victorias; p. ej., 2025: McLaren 14, Red Bull 8, Mercedes 2).
- Accesibilidad: tabla temporada × equipo y resumen por eras.
- Nota: el streamgraph centrado es difícil de leer con precisión; la alternativa es un área apilada al 100 %.

**P19. Calendario mundial: país × temporada.** *Esfuerzo S.*
- Pregunta: ¿cuándo entró y salió la F1 de cada país?
- Boceto:
  - Rejilla con filas = países, agrupados por continente y ordenados por primer GP, y columnas = temporadas.
  - Celda rellena con el nº de GP de ese año (1, 2 o 3) y el circuito en el tooltip.
  - Parecido a un gráfico de contribuciones de GitHub.
- Datos: `dim_race` (`circuit_country`/`grand_prix_country`, `season`, `circuit_name`). El continente habría que añadirlo a gold: `stg_f1db__countries.continent_id` existe, pero la vista depende del bronze.
- Dónde: inicio, como segunda vista del mapa («mapa | calendario»). Responde a lo que el mapa no muestra: el tiempo.
- Accesibilidad: es una tabla país × década con recuento.

**P20. Fiabilidad a lo largo de la historia.** *Esfuerzo M* (por el seed).
- Pregunta: ¿son los coches más fiables? ¿Se abandona más por accidentes?
- Boceto: área apilada al 100 % por temporada con clasificados, abandono mecánico y abandono por accidente u otro, con anotaciones. Solo se clasificaba el 41 % de los participantes en los 80 y el 87 % en los 2020.
- Datos: `reason_retired` (198 valores) → seed `retirement_categories.csv`. Con una clasificación provisional, la parte mecánica de los abandonos baja del 86 % (años 60) al 55 % (2020s) y la de accidentes sube del 12 % al 44 %.
- Dónde: Historia. Versión por equipo en la ficha del constructor.

**P21. Mapa de calor de posiciones de llegada.** *Esfuerzo S.*
- Pregunta: ¿cómo terminaba de verdad un piloto: siempre en puntos o todo o nada?
- Boceto:
  - En la ficha: filas = temporadas; columnas = posición de llegada 1…20 + «Ab.».
  - Intensidad secuencial = nº de veces; la columna 1 lleva el borde morado.
  - Versión global en Historia: filas = décadas.
- Datos: `fact_race_result.position_number` y `reason_retired`. Desde 1950.
- Accesibilidad: es una `<table>` con los recuentos en texto.

**P22. Edad y relevo generacional.** *Esfuerzo S.*
- Pregunta: ¿los pilotos son cada vez más jóvenes?
- Boceto: *beeswarm* por temporada con la edad de cada ganador el día de la victoria; línea con la edad media de la parrilla (35,1 años en los 50 → 28,4 en los 2020); anotaciones para el más joven (Verstappen, 18,62 años en 2016; le sigue Antonelli con 19,55 en 2026) y el mayor.
- Datos: `dim_driver.date_of_birth` (100 %) y `dim_race.race_date`.

**P23. Margen de victoria e «índice de emoción».** *Esfuerzo M.*
- Pregunta: ¿las carreras son hoy más ajustadas? ¿Cuáles fueron las más disputadas?
- Boceto:
  - (a) *Strip plot* del margen del ganador por carrera (escala logarítmica) con la mediana móvil: 27,6 s en los 50, 11,2 s en los 90 y 6,2 s en los 2020.
  - (b) Tabla «carreras más disputadas» con un índice compuesto de cambios de líder, cambios de posición en pista (sin la vuelta 1 ni vueltas de boxes) y margen final.
  - El índice es un **proxy** y hay que explicarlo: sin datos oficiales de adelantamientos, un cambio de posición no es siempre un adelantamiento.
- Datos: `gap_ms` de P2 y posición por vuelta. Cambios de líder por carrera: media de 4,0 en los 50, 1,8 en los 70, 3,6 en los 2000 y 2,7 en los 2020.
- Accesibilidad: el ranking es una tabla.

### 5.5 Entidades nuevas

**P24. Página de circuito.** *Esfuerzo M.* Es el hueco más grande.
- Pregunta: ¿qué pasa en este circuito?
- Contenido:
  - Ficha: tipo, sentido, longitud, curvas y temporadas.
  - Trazado de P7 si hay telemetría.
  - Ganadores por año (tira de cuadrados con el color del equipo) y conversión de pole en victoria (mínimo de 15 carreras: Yas Marina 70,6 %, Catalunya 69,4 %, Marina Bay 68,8 %, Shanghái 63,2 %).
  - % de vueltas bajo SC desde 2000 (Marina Bay 9,8 %, Baku 9,1 %, Melbourne 8,5 %, Interlagos 7,8 %).
  - Récord de vuelta en carrera por trazado: hay que agrupar por `course_length`, porque los trazados cambian.
- Datos: `dim_race`, `fact_race_result` y `fact_laptimes`. Endpoint nuevo `/circuits/{id}`; la ruta `/circuits` ya existe para el mapa.
- Dónde: los nombres de circuito de las tablas y del mapa pasan a ser enlaces.

**P25. Comparador libre de dos pilotos.** *Esfuerzo M.*
- Pregunta: ¿quién es mejor, X o Y?
- Boceto:
  - (a) Victorias acumuladas frente al nº de carrera, o frente a la edad (dos líneas con etiqueta directa).
  - (b) KPIs enfrentados en espejo (barras a izquierda y derecha).
  - (c) Si coincidieron, H2H en carreras compartidas (quién terminó delante).
  - (d) Normalización de P14.
- Datos: `fact_race_result`, `agg_driver_career` y `dim_driver`.
- Dónde: `/compare?a=&b=`, enlazado desde cada ficha («comparar con…»).
- Accesibilidad: formulario GET sin JS (como la telemetría) y una tabla comparativa.

**P26. Victorias en casa.** *Esfuerzo S.*
- Pregunta: ¿rinden más los pilotos en su país?
- Boceto: barras por nacionalidad con victorias en casa y fuera (95 de 1 167 victorias fueron en casa, comparando `nationality_alpha2` con `circuit_alpha2`).
- Dónde: Historia o la página de circuito.

### 5.6 Prioridad sugerida

| Prioridad | Propuestas | Motivo |
|---|---|---|
| 1 (arreglos baratos) | Ejes temporales en G12, G13 y G15; ticks y texto del violín; formato numérico local; G3 horizontal y con la métrica bien nombrada; seed de colores de equipo; etiquetas de G2; títulos de G9 («tiempo en el pit lane») y G10 («vuelta de clasificación»); barras a 0 de G15; empates en los resúmenes | Errores de lectura con impacto directo y poco coste |
| 2 (relato de carrera) | P1b race trace, P3 en lugar de la matriz, P6 delta y minisectores, P9 parrilla→llegada, P12 H2H divergente | Responden a las preguntas más frecuentes y usan datos que ya sirve la API |
| 3 (entidades) | P24 circuito, P25 comparador, P1 eliminación matemática | Huecos de relato grandes |
| 4 (historia) | P18 streamgraph, P19 calendario, P14 eras, P16 títulos, P20 fiabilidad, P22 edades, P21 mapa de calor | Nueva sección «Historia» |
| 5 (singulares) | P5 undercut, P2 degradación, P15 red de compañeros, P8 ghost race, P23 índice de emoción | Diferenciadores; más esfuerzo o una heurística que hay que validar |

---

## 6. Reorganización de la navegación

**Situación actual**
- Navegación: Temporadas · Pilotos · Constructores · Récords · Calidad.
- Pestañas de carrera: Resultado · Clasificación · Vuelta a vuelta · Neumáticos · Ritmo · Boxes · Telemetría. Son 7 y en móvil se desplazan en horizontal.

**Propuesta**

```
Inicio          última carrera + mini «diferencia con el líder» (P1) + mapa|calendario (G1/P19)
Temporadas      /seasons/[year]: KPIs de relato (P11) · campeonato [puntos | diferencia | posiciones] · clasificaciones · calendario
  └ Carrera     /races/[id], 5 pestañas:
                 1. Resultado       (parrilla→V1→llegada P9 + tabla)
                 2. Clasificación   (G3 horizontal y por segmento + tabla + telemetría G10/G11 con P6 y P7 desde 2024)
                 3. Carrera         (G4 posiciones | P1b diferencias; P8 ghost race opcional)
                 4. Ritmo           (violín G8/P4 + mapa de calor P3 + tiempos G7 limitado a 2-4 pilotos)
                 5. Estrategia      (stints G5 + degradación P2 + undercuts P5 + paradas G9 + pasos por el pit lane)
Pilotos         ficha: KPIs con contexto · ADN P13 · puntos normalizables P14 · H2H divergente P12 · posiciones P21
Constructores   ficha: KPIs · temporadas (arreglo pre-1958) · alineación y motor P17 · fiabilidad del equipo P20
Circuitos       NUEVA (P24)
Comparar        NUEVA (P25 + grados de separación P15)
Historia        Récords (tabla ordenable + P14) · títulos P16 · streamgraph P18 · fiabilidad P20 · edades P22 · margen P23 · en casa P26
Datos           Calidad: enlace en el pie de página (es transparencia, no navegación principal)
```

**Motivos**
1. **La telemetría pasa a Clasificación**, porque es la vuelta de clasificación. Así desaparece el malentendido de verla en una pestaña de carrera.
2. **Neumáticos y Boxes se fusionan en «Estrategia»**: la parada y el compuesto son la misma decisión, y el detector de undercut necesita las dos cosas.
3. **«Ritmo» deja de ser un muro de 20 líneas**: el violín es la vista principal y el detalle vuelta a vuelta es secundario.
4. **5 pestañas en lugar de 7**, que caben en 375 px sin desplazamiento.
5. **Estado compartido entre pestañas**: los pilotos seleccionados en la URL (`?d=VER,NOR`) se mantienen en Carrera, Ritmo y Estrategia. Hoy cada gráfico tiene sus propias casillas.
6. **Récords se convierte en «Historia»**, con subsecciones. Es donde viven las vistas por eras.
7. **Circuitos y Comparar** cubren los dos huecos de entidad más evidentes. Con 7 entradas en la navegación principal hay que revisar el menú en móvil (hoy se desplaza en horizontal).
8. **Enlaces cruzados**: al pulsar una línea o barra (ECharts `on('click')`) se abre la ficha del piloto, del equipo o de la carrera, y los nombres de circuito de las tablas enlazan a P24.

---

## 7. Notas para el informe LaTeX

**Correspondencia con el TFG**

| Figura del TFG | Elemento de la web |
|---|---|
| 5.23 | G1 |
| 5.24-5.25 | G16 y la tabla de récords |
| 5.26 | KPIs de temporada y tablas |
| 5.27 | G3 |
| 5.28 | G4 |
| 5.29 | G5 y G6 |
| 5.30 | G7 |
| 5.31 | G8 |
| 5.32 | G9 |
| 5.33 | KPIs del piloto, G12, G13 y G14 |

Extras sin equivalente en el TFG: G2, G10, G11, G15, la tabla de pasos por el pit lane y `/quality`.

**Mejoras frente al TFG que se pueden defender**
- Accesibilidad: resumen y tabla en cada gráfico.
- Bilingüe.
- Sin licencia ni cuenta de Power BI.
- Filtro de vueltas neutralizadas más riguroso: incluye la bandera roja y la heurística del 150 %.
- Letras en los compuestos y texturas en los compañeros.
- Paleta apta para daltonismo.
- Todas las páginas funcionan sin JS salvo los gráficos, con formularios GET.

**Limitaciones heredadas del TFG que conviene reconocer**
- La métrica de clasificación mezcla segmentos.
- El «tiempo de parada» es en realidad el tiempo en el pit lane.
- Los puntos no están normalizados entre eras.

**Capturas**: tomadas el 29/09/2026 a 640 px de ancho CSS con escala de dispositivo 1,25 (PNG de 480 a 1 280 px de ancho). El recorte de la captura del navegador integrado impedía hacerlas a más ancho.
