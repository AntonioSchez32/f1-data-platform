# Paridad con el informe de Power BI del TFG

Fecha: 09/10/2026. Decisión 38 (cierra DOC-07 de `docs/auditoria/AUDITORIA.md`). El catálogo de
gráficos está en [`catalogo_informe_tfg.md`](catalogo_informe_tfg.md).

## Resumen

- **Fecha de corte:** GP de Abu Dabi 2024 (`race_id` 1125, 08/12/2024), la última carrera presente en
  el `.pbix` final. Las figuras de la memoria son anteriores: corresponden al GP de São Paulo 2024
  (`race_id` 1122, ronda 21), y también se han comprobado a esa fecha.
- **Resultado:** de 7 357 comparaciones con la definición de cada lado, **7 342 cuadran (99,8 %)**.
  Las 15 diferencias tienen causa identificada: 3 son correcciones de datos posteriores al TFG
  (nuestras o de F1DB), 9 son definiciones distintas y 3 son un error del TFG. **No queda ninguna
  diferencia sin explicar** y no hace falta ejecutar ninguna medida en Power BI Desktop.
- Las clasificaciones del campeonato cuadran fila a fila (20 717 de 20 717 filas de pilotos en todas
  las carreras), igual que los GP por país (34 de 34 países, 1 125 carreras).
- **Hallazgo nuevo (no está en la auditoría):** en la comparativa de puntos frente al compañero, la
  plataforma suma los puntos del piloto una vez por cada compañero con el que coincidió en la
  carrera. En los equipos de tres o más coches (1950–1981) eso infla la barra «Puntos del piloto»:
  473 temporadas de piloto y 13 883 puntos duplicados (por ejemplo, Fangio suma 1 043,6 en lugar de
  277,6 y Clark, 1 179 en lugar de 274). Afecta a `agg_teammate_h2h.points` y a la web
  (`/drivers/[id]`, gráfico «Puntos frente al compañero»). Ver la sección 5.

## 1. Método

1. **Fuente.** Solo el `.pbix` final, «Trabajo de fin de grado - Only F1 DB - Modificado.pbix»
   (08/12/2024). Los demás `.pbix` (Ergast, Fast F1, Only F1 DB, «Modificado - Dimensiones») son
   versiones anteriores del mismo informe y no aportan nada a esta comparación.
2. **Diseño del informe.** El `.pbix` es un zip. `Report/Layout` (JSON en UTF-16 LE) se ha leído con
   Python estándar: 8 páginas, 80 objetos visuales, 5 grupos de marcadores y los filtros de página,
   de objeto visual y de segmentación. Las «11 páginas» del plan original son las 11 figuras de la
   memoria (5.23–5.33): 8 páginas, cinco de ellas con dos vistas por marcador.
3. **Modelo y datos.** `pbixray` 0.15.5 (con DuckDB 1.5.6) en un entorno virtual aparte, en la carpeta temporal de la
   sesión (ni en el repositorio ni en su `.venv`). Lee sin problema las 29 medidas DAX, las 2
   columnas calculadas, las 14 consultas de Power Query, las 25 relaciones y **los datos de las
   tablas** (VertiPaq): `dim_race` (1 125 carreras), `fact_race_result` (27 171 filas),
   las clasificaciones, `fact_qualifying_result`, `fact_pit_stops` y `fact_gp_laptimes`
   (1,2 millones de vueltas). Las tablas se volcaron a Parquet en la carpeta temporal.
4. **Cálculo.** Cada medida DAX se ha reescrito en SQL sobre las tablas del `.pbix` (con DuckDB) y se
   ha comparado con la misma métrica calculada sobre `data/gold/f1.duckdb` (en solo lectura,
   filtrada a `season <= 2024`) con las definiciones de la plataforma (las de
   `agg_driver_career`, `agg_constructor_career` y `agg_teammate_h2h`, pero recalculadas desde los
   hechos para poder cortar en 2024). Los identificadores de F1DB coinciden en los dos lados (todos
   los constructores; de los pilotos falta solo `andrea-kimi-antonelli`, renombrado después y sin
   carreras antes del corte).
5. **Validación de la reescritura DAX → SQL.** Con el corte de São Paulo 2024, el SQL reproduce las
   cifras visibles en las figuras 5.24, 5.25, 5.26 y 5.33 de la memoria (sección 4), salvo las
   diferencias explicadas allí. Eso confirma que la reescritura es fiel sin abrir Power BI.
6. **Comparación exhaustiva.** No se ha limitado a una muestra: se comparan todos los pilotos
   (856 con carreras), todos los constructores (183) y todas las temporadas (75). Las tablas de
   muestra de abajo son un extracto.

Las equivalencias DAX → SQL usadas están en el anexo.

## 2. KPIs comparados (corte: Abu Dabi 2024)

### 2.1 Recuento global

| KPI (medida DAX) | Universo | Cuadran | Diferencias | Causa |
|---|---|---|---|---|
| Carreras (`Carreras`) | 856 pilotos | 854 | Trintignant 84/83, Behra 53/54 | Corrección nuestra: Italia 1951, el #50 lo llevó Behra (`race_data_corrections.csv`, fila de `race_id` 14) |
| Victorias (`Victorias`) | 856 | 856 | — | — |
| Podios (`Podios`) | 856 | 854 | Farina 20/19, Trintignant 10/9 | Definición: el TFG cuenta filas y en Argentina 1955 los dos compartieron dos coches que acabaron 2.º y 3.º; nosotros contamos carreras |
| Poles (`Pole Position`) | 856 | 852 | Schumacher 67/68, Leclerc 25/26, Russell 6/5, Magnussen 0/1 | Definición: el TFG cuenta **salidas desde la posición 1 de la parrilla** (`race_grid_position_text = "1"`); la plataforma, la pole oficial de F1DB. Con la definición del TFG cuadran los 856 |
| Vueltas rápidas (`Fastest Laps`) | 856 | 855 | Pescarolo 0/1 | Cambio de F1DB: Italia 1971 (`race_id` 206), la vuelta rápida es de Pescarolo; en nuestra base no hay corrección propia (`is_corrected = false`) |
| Puntos (`Total Puntos Acumulados`) | 856 | 856 | — | Los dos suman carrera y sprint |
| Títulos (`Campeones mundiales`) | 856 | 856 | — | — |
| Carreras por equipo | 183 constructores | 183 | — | — |
| Victorias por equipo | 183 | 183 | — | El TFG excluye coches compartidos y cuenta filas; da lo mismo que nuestras victorias por carrera |
| Podios por equipo | 183 | 183 | — | — |
| Vueltas rápidas por equipo | 183 | 180 | Ferrari 263/265, Maserati 15/17, Brabham 41/42 | Definición: el TFG cuenta carreras; la plataforma, pilotos acreditados (en los años 50 varios compartían la vuelta rápida), como F1DB |
| Títulos de constructores | 183 | 183 | — | — |
| Piloto campeón | 75 temporadas | 75 | — | — |
| Victorias del piloto campeón | 75 | 75 | — | — |
| Equipo del piloto campeón | 75 | 72 | 1961, 1970, 1977 | Error del TFG: la medida toma el equipo de la **última carrera** y Phil Hill (1961), Rindt (1970) y Lauda (1977) no la corrieron; la tarjeta sale vacía |
| Equipo campeón | 75 | 75 | — | Desde 1958 en los dos |
| Victorias del equipo campeón | 75 | 75 | — | — |
| Motorista campeón | 75 | 75 | — | — |
| Clasificación final de pilotos (posición y puntos) | 1 637 filas | 1 637 | — | — |
| Clasificación final de constructores | 698 filas | 698 | — | — |
| Clasificación tras cada carrera (pilotos, puntos) | 20 717 filas | 20 717 | — | — |
| GP por país (`Eventos`, mapa) | 34 países | 34 | — | 1 125 carreras en los dos, Indianápolis 500 incluidas (Estados Unidos, 79) |

Total: 5 992 comparaciones de pilotos (5 983 cuadran), 915 de constructores (912), 450 de temporadas
(447). En las poles se cuenta la comparación con la definición de la plataforma; con la del TFG
cuadran todas.

### 2.2 Muestra de pilotos (TFG / plataforma)

| Piloto | Carreras | Victorias | Podios | Poles (TFG = parrilla 1 / oficial) | V. rápidas | Puntos | Títulos |
|---|---|---|---|---|---|---|---|
| Hamilton | 356 / 356 | 105 / 105 | 202 / 202 | 104 / 104 | 67 / 67 | 4 862,5 / 4 862,5 | 7 / 7 |
| Schumacher | 308 / 308 | 91 / 91 | 155 / 155 | **67 / 68** | 77 / 77 | 1 566 / 1 566 | 7 / 7 |
| Verstappen | 209 / 209 | 63 / 63 | 112 / 112 | 40 / 40 | 33 / 33 | 3 023,5 / 3 023,5 | 4 / 4 |
| Vettel | 300 / 300 | 53 / 53 | 122 / 122 | 57 / 57 | 38 / 38 | 3 098 / 3 098 | 4 / 4 |
| Prost | 202 / 202 | 51 / 51 | 106 / 106 | 33 / 33 | 41 / 41 | 798,5 / 798,5 | 4 / 4 |
| Senna | 162 / 162 | 41 / 41 | 80 / 80 | 65 / 65 | 19 / 19 | 614 / 614 | 3 / 3 |
| Alonso | 404 / 404 | 32 / 32 | 106 / 106 | 22 / 22 | 26 / 26 | 2 337 / 2 337 | 2 / 2 |
| Leclerc | 149 / 149 | 8 / 8 | 43 / 43 | **25 / 26** | 10 / 10 | 1 430 / 1 430 | 0 / 0 |
| Fangio | 51 / 51 | 24 / 24 | 35 / 35 | 29 / 29 | 23 / 23 | 277,64 / 277,64 | 5 / 5 |
| Farina | 34 / 34 | 5 / 5 | **20 / 19** | 5 / 5 | 5 / 5 | 127,33 / 127,33 | 1 / 1 |

Los cuatro casos de poles: Schumacher (Francia 1996) y Leclerc (Mónaco 2021) hicieron la pole pero
no tomaron la salida; en São Paulo 2022 la pole fue de Magnussen, pero salió primero Russell, que
ganó el sprint.

### 2.3 Muestra de constructores (TFG / plataforma)

| Constructor | Carreras | Victorias | Podios | V. rápidas (TFG por carrera / plataforma por piloto) | Títulos |
|---|---|---|---|---|---|
| Ferrari | 1 100 / 1 100 | 248 / 248 | 829 / 829 | **263 / 265** | 16 / 16 |
| McLaren | 974 / 974 | 189 / 189 | 524 / 524 | 172 / 172 | 9 / 9 |
| Mercedes | 317 / 317 | 129 / 129 | 298 / 298 | 109 / 109 | 8 / 8 |
| Red Bull | 394 / 394 | 122 / 122 | 282 / 282 | 99 / 99 | 6 / 6 |
| Williams | 827 / 827 | 114 / 114 | 312 / 312 | 133 / 133 | 9 / 9 |
| Lotus (`lotus`) | 493 / 493 | 79 / 79 | 172 / 172 | 71 / 71 | 7 / 7 |
| Maserati | 73 / 73 | 9 / 9 | 37 / 37 | **15 / 17** | 0 / 0 |

Los puntos de constructor no salen en el informe salvo en la clasificación de cada temporada (que
cuadra fila a fila). Por eso las dos métricas de puntos de C4 (decisión 37) no tienen equivalente
en el TFG y no se comparan aquí. Tampoco hay en el informe temporadas ni años de pilotos o
constructores (DAT-01/02/03): C4 no cambia ningún KPI de esta tabla.

### 2.4 Comparativa con el compañero (página «Detalle de rendimiento piloto»)

Las definiciones son distintas a propósito, así que aquí no se espera igualdad:

| Aspecto | TFG (medidas `H2H …`) | Plataforma (`agg_teammate_h2h`) |
|---|---|---|
| Carreras que cuentan | Solo las que **los dos** terminan clasificados (`position_number` no nulo) | Todas las compartidas, ordenadas por `position_display_order` (incluye abandonos) |
| % por delante | por delante / (por delante + por detrás) | por delante / carreras juntas |
| Coches compartidos | Cuentan | Se excluyen |
| Clasificación | `position_number` de `QUALIFYING_RESULT` | `position_display_order` de `QUALIFYING` |
| Puntos del piloto | Todos sus puntos (carrera y sprint) | Solo carrera (DAT-04, lo arregla C4) y **duplicados por compañero** (hallazgo nuevo) |
| Puntos del compañero | Suma de todos los compañeros, carrera y sprint | Igual, sin sprint ni coches compartidos |

Resultado para 14 pilotos (carrera completa hasta 2024):

| Piloto | % carrera TFG / nuestro | % clasificación TFG / nuestro | Puntos compañero TFG / nuestro |
|---|---|---|---|
| Hamilton | 61,8 / 60,7 | 62,1 / 61,2 | 4 069 / 4 012 |
| Verstappen | 80,1 / 73,7 | 79,1 / 78,4 | 1 788 / 1 735 |
| Schumacher | 73,8 / 64,3 | 75,7 / 75,3 | 1 060,5 / 1 060,5 |
| Alonso | 75,4 / 68,1 | 73,9 / 73,6 | 1 214 / 1 205 |
| Senna | 77,8 / 64,8 | 88,6 / 88,6 | 382 / 382 |
| Prost | 61,4 / 61,9 | 67,2 / 67,2 | 483 / 483 |
| Vettel | 62,8 / 61,0 | 64,3 / 63,8 | 2 398,5 / 2 398,5 |
| Leclerc | 62,3 / 58,4 | 66,9 / 67,1 | 1 188,5 / 1 119,5 |

- **Clasificación:** prácticamente igual (≤ 1 punto porcentual); la diferencia viene de los pocos
  pilotos sin `position_number` en clasificación.
- **Carrera:** la plataforma da porcentajes más bajos para los pilotos dominantes, porque cuenta
  también las carreras en que ellos abandonan. Es una definición distinta, no un error.
- **Puntos del compañero:** cuadran en todas las temporadas sin sprint ni coches compartidos; la
  diferencia de 2021 en adelante es el sprint (DAT-04).

### 2.5 Páginas de carrera (selección por defecto del informe: Abu Dabi 2024)

| Página | Comprobación | Resultado |
|---|---|---|
| Rendimiento en clasificación | % respecto al mejor tiempo, por piloto | 20 de 20 (diferencia máxima 0,0005 puntos) |
| Paradas en boxes | Media por constructor (paradas de menos de 70 s) | 10 de 10 |
| Ritmo en carrera | Suma de tiempos por vuelta por piloto | 20 de 20 |
| Situación de carrera | Posición en cada vuelta (las 1 125 carreras) | 1 173 851 de 1 175 086 vueltas comunes (99,9 %) |

Diferencias de vueltas, de menor importancia:

- El TFG guarda una fila «vuelta 0» (parrilla) por piloto; la plataforma no. Sin ella, 1 106 de 1 125
  carreras tienen el mismo número de vueltas.
- De las otras 19, 14 son Indianápolis 500 de 1950–1960, de las que el TFG solo tenía unas pocas
  vueltas y la plataforma tiene la tabla completa. En 3 (1967 R7, 1969 R7, Imola 2024) la plataforma
  añade 1–2 pilotos que faltaban (en Imola 2024, con FastF1). En 2 (China 2014, Canadá 2018,
  carreras con la bandera a cuadros adelantada) tiene 13–14 filas menos. Causa: datos de vueltas
  completados y depurados después del TFG (fusión de fuentes de C1/C2). Es una hipótesis
  verosímil, no comprobada vuelta a vuelta.
- Paradas: 21 262 en el TFG frente a 21 297 en la plataforma hasta 2024 (+35, actualizaciones de F1DB;
  no investigado en detalle).
- **Umbral de las paradas:** el TFG excluye las de 70 s o más; la web excluye las de más de 60 s y su
  texto dice «como en el TFG». Hasta 2024 hay 62 paradas entre 60 y 70 s, repartidas en 51 carreras.

## 3. Causas de las diferencias, agrupadas

| Causa | Casos | Detalle |
|---|---|---|
| Corrección de datos posterior (nuestra) | 2 | Italia 1951, Trintignant → Behra |
| Cambio de F1DB | 1 | Vuelta rápida de Pescarolo en Italia 1971, que el TFG no tenía |
| Definición distinta | 9 | Poles = parrilla 1 (4), podios por fila (2), vueltas rápidas por carrera (3) |
| Error del TFG | 3 | Equipo del piloto campeón vacío en 1961, 1970 y 1977 |
| Error nuestro | 0 en los KPIs | El hallazgo de la sección 5 afecta a un gráfico, no a un KPI de la tabla |

## 4. Figuras de la memoria (corte: São Paulo 2024)

- **Fig. 5.24 (récords de pilotos, 16 filas × 4 valores):** victorias, podios y puntos cuadran en las
  16 filas. «Carreras» cuadra en 14: Fangio sale con 58 (51) y Clark con 74 (73). La medida que se
  usó para la figura contaba filas, no carreras (Fangio compartió coches; Clark tiene una carrera con
  dos filas). El `.pbix` final ya usa `SUMMARIZE` (driver, race) y da 51 y 73, como la plataforma.
- **Fig. 5.25 (récords de constructores):** cuadra salvo la fila «Lotus» (570 carreras, 81 victorias,
  197 podios, 76 vueltas rápidas). La tabla agrupa por **nombre**, y en F1DB hay dos constructores
  llamados «Lotus»: `lotus` (Team Lotus, 493/79/172/71) y `lotus-f1` (2012–2015, 77/2/25/5). La suma
  da exactamente la fila de la figura. Pasa lo mismo con los dos «ATS». La web los muestra por
  separado, que es lo correcto.
- **Fig. 5.26 (temporada 2023):** Verstappen 575, Pérez 285, Hamilton 234; 19 victorias; Red Bull.
  Cuadra.
- **Fig. 5.33 (Schumacher):** 7 títulos, 308 carreras, 91 victorias, 155 podios, 77 vueltas
  rápidas, 67 poles. Cuadra; la plataforma da 68 poles (pole oficial, sección 2.1).

## 5. Hallazgo nuevo: puntos duplicados en «Puntos frente al compañero»

`agg_teammate_h2h` tiene una fila por pareja (piloto, compañero, temporada, constructor), y
`points` es la suma de los puntos del piloto **en las carreras con ese compañero**. La web
(`web/src/app/[lang]/drivers/[id]/page.tsx`, `bySeason`) suma `points` de todas las parejas de la
temporada. Si en una carrera el piloto tuvo dos o más compañeros (equipos de tres o más coches, muy
habitual hasta 1981), sus puntos de esa carrera se cuentan una vez por compañero.

- Alcance: 473 temporadas de piloto entre 1950 y 1981, 13 883 puntos duplicados en total. De 1982 en
  adelante no hay casos con puntos.
- Ejemplos (suma de toda la carrera deportiva): Fangio 1 043,6 frente a 277,6; Clark 1 179 frente a
  274; Lauda 425,5 frente a 420,5.
- `teammate_points` no tiene el problema: sumar a todos los compañeros es lo que se quiere mostrar.
- No está en `AUDITORIA.md` (DAT-04 trata solo el sprint). Encaja en C4 porque toca el mismo modelo y
  la misma página que DAT-04: calcular los puntos del piloto por temporada una sola vez, por
  ejemplo con `count(distinct race_id)` o desde `agg_driver_season`, en lugar de sumarlos por
  pareja.

## 6. Conclusiones

1. **Paridad demostrada.** Con la misma definición, la plataforma reproduce todos los KPIs del
   informe a la fecha de corte del TFG, para todos los pilotos, constructores y temporadas, no solo
   para una muestra. La verificación de paridad del plan original (DOC-07) queda cubierta con
   evidencia.
2. **Las diferencias son mejoras o cambios documentados de definición:** pole oficial frente a
   «salida desde la pole», podios por carrera frente a por fila, vueltas rápidas por piloto
   acreditado (como F1DB), dos correcciones de datos y la separación de los dos «Lotus».
3. **Errores del TFG detectados:** la tarjeta «Equipo del piloto campeón» queda vacía cuando el
   campeón no corre la última carrera (1961, 1970, 1977). En la figura 5.24, «Carreras» contaba filas
   (Fangio 58), algo ya corregido en el `.pbix` final. En la 5.25, la fila «Lotus» mezcla dos
   constructores.
4. **Un error nuestro** que no es un KPI: los puntos duplicados en el gráfico de puntos frente al
   compañero (sección 5).

## 7. Preguntas para el autor (`/grill-me`)

1. **Puntos duplicados frente al compañero (sección 5):** ¿se añade a C4 junto a DAT-04
   (recomendado, porque es el mismo modelo y la misma página) o se registra como hallazgo nuevo en
   la auditoría?
2. **Umbral de paradas:** ¿70 s, como el `.pbix` final, o 60 s como ahora? Si se queda en 60 s, hay
   que quitar «como en el TFG» de `pitAvgLede`. Recomendación: 60 s y corregir el texto; la
   diferencia es pequeña (62 paradas hasta 2024).
3. **Definición del duelo en carrera:** el TFG solo contaba las carreras con los dos clasificados y
   la plataforma cuenta todas. ¿Se mantiene la de la plataforma (recomendado: es más estricta y
   coherente con la clasificación) y se explica en la web y en la defensa?
4. **Poles:** ¿se menciona en la defensa que el TFG medía salidas desde la posición 1 y no poles
   oficiales (4 pilotos cambian, entre ellos Schumacher 67 → 68)?
5. **Opcional, sin necesidad técnica:** si el tribunal pide comprobarlo en vivo, basta con abrir el
   `.pbix` en Power BI Desktop, ir a «Detalle de rendimiento piloto» (Hamilton por defecto) y ver
   que las tarjetas dan 7 / 356 / 105 / 202 / 67 / 104, como la tabla 2.2.

## 8. Puntos para la defensa

Respuestas breves por si el tribunal compara el informe de Power BI del TFG con la plataforma (decisión 48).

- **«¿La plataforma reproduce el TFG?»** Sí. A la fecha de corte del TFG (Abu Dabi 2024) cuadran 7 342 de 7 357 cifras, recalculando las 29 medidas DAX del `.pbix` sobre la nueva base. Las clasificaciones cuadran fila a fila (20 717 de 20 717) y los GP por país, todos (34 de 34). Las 15 diferencias tienen causa conocida.
- **Poles.** El TFG contaba las salidas desde la posición 1 de la parrilla (`race_grid_position_text = "1"`); la plataforma cuenta la pole oficial de F1DB. Difieren cuando el poleman sale penalizado o desde el pit lane. Por eso cambian 4 pilotos: Schumacher pasa de 67 a 68, Leclerc de 25 a 26, Russell de 6 a 5 y Magnussen de 0 a 1. La plataforma usa la definición oficial.
- **Duelo con el compañero.** Se mantiene el criterio del TFG: solo cuentan las carreras en que acaban los dos, para quitar averías y accidentes ajenos al piloto (decisión 46).
- **Puntos frente al compañero, una mejora sobre el TFG.**
  - El TFG sumaba los puntos de todos los compañeros de cada carrera. Con los 3 o 4 coches por equipo de los años 50, eso descompensaba la comparación.
  - La plataforma compara, carrera a carrera, los puntos del piloto con los del mejor compañero de esa carrera (decisión 45).
  - Además se corrigió un fallo propio de la primera versión de la web, que sumaba los puntos del piloto una vez por cada compañero (Fangio 1955: 106 en vez de 40).
- **Correcciones de datos posteriores al TFG.**
  - En Italia 1951, el coche #50 lo llevó Behra y no Trintignant: es una corrección propia con evidencia, en la seed `race_data_corrections.csv`.
  - La vuelta rápida de Italia 1971 es de Pescarolo: la corrigió F1DB después del TFG.
- **Definiciones de recuento.** El TFG contaba los podios por fila (Farina y Trintignant compartieron coche en Argentina 1955) y las vueltas rápidas de equipo por carrera. La plataforma cuenta por carrera y por piloto acreditado, como F1DB.
- **Errores del TFG que corrige la plataforma.**
  - «Equipo del piloto campeón» salía vacío en 1961 (Phil Hill), 1970 (Rindt) y 1977 (Lauda), porque la medida tomaba el equipo de la última carrera y ellos no la corrieron.
  - En la Fig. 5.25, «Lotus» mezclaba Team Lotus y Lotus F1 (2012–2015) porque agrupaba por nombre. La web los separa.
- **Comprobación en vivo, si la piden.** Abrir el `.pbix` final en Power BI Desktop, ir a «Detalle de rendimiento piloto» (Hamilton por defecto) y comparar sus tarjetas, 7 / 356 / 105 / 202 / 67 / 104, con la ficha de Hamilton en la web. Coinciden; la única diferencia esperable sería la de las poles, explicada arriba.
- **Método, por si preguntan cómo se hizo.** El `.pbix` se leyó sin abrir Power BI (`pbixray`, diseño y modelo VertiPaq). Cada medida DAX se reescribió en SQL y se comparó con la base gold limitada a las temporadas hasta 2024. Las equivalencias están en el anexo.

## Anexo: equivalencias DAX → SQL

Sobre las tablas del `.pbix` (nombres de columna de F1DB):

| Medida | SQL equivalente |
|---|---|
| `Carreras` | `count(distinct race_id) filter (where type = 'RACE_RESULT')` por piloto |
| `Victorias` / `Podios` | `count(*) filter (where position_text = '1' / in ('1','2','3') and type = 'RACE_RESULT')` |
| `Pole Position` | `count(*) filter (where race_grid_position_text = '1' and type = 'RACE_RESULT')` |
| `Fastest Laps` | `count(*) filter (where race_fastest_lap and type = 'RACE_RESULT')` |
| `Total Puntos Acumulados` | `sum(coalesce(race_points, 0))`, carrera y sprint |
| `Campeones mundiales` | filas con `position_text = '1'` en `fact_race_driver_standing` en la carrera con `season_last_race` (última ronda del año) |
| `Carreras Por Equipo` | `count(distinct race_id)` por constructor, sin filtrar tipo |
| `Victorias` / `Podios por Equipo` | como las de piloto, con `not race_shared_car` |
| `Vueltas Rápidas por Equipo` | `count(distinct race_id) filter (where race_fastest_lap_rank = 1 and type = 'RACE_RESULT')` |
| `H2H Piloto` / `H2H Teammate` | autounión de `fact_race_result` por carrera y constructor, otro piloto, los dos `RACE_RESULT` con `position_number` no nulo; cuenta compañeros detrás / delante |
| `H2H … Qualy` | lo mismo sobre `fact_qualifying_result` con `type = 'QUALIFYING_RESULT'` |
| `Total Puntos Acumulados Compañero` | suma de `race_points` de los compañeros de la misma carrera, constructor y tipo |
| `Eventos` | `count(*)` de `dim_race` por `circuit_country` |
| `qualifying_best_percentage_gap` (columna) | `100 * (best - min(best) over carrera y tipo) / min(best)` |
