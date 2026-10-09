# Revisión de divergencias entre fuentes (28-09-2026)

Revisión de todas las discrepancias entre **F1DB**, **formula1db.com** (scraping del TFG),
**FastF1** y **Ergast**, verificada dos veces y arbitrada con documentos oficiales de la **FIA**
y con **Stats F1**. Prioridad acordada: F1DB y formula1db (si son claramente mejores), después
FastF1 y, por último, Ergast (solo validación).

Las 16 decisiones se tomaron en la página «Conciliación de fuentes F1» (todas según la
recomendación) y **se aplicaron al modelo el 28-09-2026**: ver «Decisiones aplicadas» al final.

## Método

- **Dos pasadas independientes.** La segunda parte de bronze (sin modelos dbt) e identifica a los
  pilotos por nombre (formula1db, FastF1) y por fecha de nacimiento + apellido (Ergast), en vez
  de por dorsal. Ambas dan las mismas cifras en tiempos, posiciones, número de vueltas, vueltas
  rápidas y realineación de carreras.
- **Árbitros.** 24 documentos oficiales de la FIA (lap charts, tiempos de clasificación,
  resúmenes de paradas, parrillas y clasificaciones finales) y Stats F1 (clasificaciones,
  vueltas rápidas, inscritos). Los PDF de la FIA solo se usan como evidencia; no se redistribuyen.

## Resultados clave

| Comprobación | Resultado |
|---|---|
| Tiempos por vuelta, 2018–2022, 3 fuentes (104.248 vueltas) | formula1db y Ergast nunca discrepan solas; FastF1 se desvía en 1.085 |
| Tiempos por vuelta, formula1db vs FastF1, 2023–2024 | 51.747 de 51.755 iguales |
| Posiciones por vuelta, 3 fuentes (108.090) | FastF1 se desvía sola en 1.144; formula1db en 49 (Japón 2022) |
| Paradas de F1DB vs FIA (6 carreras) | 100 % de las paradas reales; F1DB excluye penalizaciones, pasos tras Safety Car y banderas rojas |
| Parrillas F1DB vs FIA (35 casos) | F1DB acierta 30, falla 5 (Estiria 2020 ×4, Qatar 2023) |
| Clasificación F1DB vs FIA (9 casos) | F1DB acierta 8, falla 1 (Verstappen Qatar 2021) |
| Neumáticos en conflicto (43 casos) | FastF1 viola una regla en 35; formula1db en 0 |

## Hallazgos nuevos de la verificación

1. **Fallo del modelo actual:** 447 vueltas de 9 coches compartidos (1950–1955) asignadas al
   piloto equivocado por priorizar el dorsal sobre el nombre (`A1_vueltas_mal_asignadas_coches_compartidos.csv`).
2. **Piloto ausente en formula1db:** Lando Norris en Imola 2024 (se toma de FastF1).
3. **Carreras relanzadas:** en Bélgica 2001 formula1db y Ergast numeran las vueltas desde el
   relanzamiento (desfase 4 respecto a F1DB); indicios similares en San Marino y Japón 1994 y
   Francia 1981.
4. **FastF1 y Ergast no son independientes en clasificación:** FastF1 toma Q1/Q2/Q3 de la API de Ergast.
5. **Correcciones de `Script-2.sql`:** 4 se sostienen y 2 no (`B4_correcciones_Script2.csv`).

## Rectificaciones sobre conclusiones anteriores

- P1: F1DB **no** es incoherente con los pasos por el pit lane (Qatar 2024: 60/60 con la FIA).
- P3: las «paradas omitidas» de Russell (Mónaco 2025) y Tsunoda (Gran Bretaña 2025) fueron penalizaciones.
- B3: la FIA da Vandoorne 14.º y Ocon 15.º; F1DB y Stats F1 se equivocan.
- B5: el caso de 2023 es Qatar, no Singapur.

## Ficheros de evidencia

| Fichero | Contenido |
|---|---|
| `V7_vueltas_completadas_historicas.csv` | 87 casos con F1DB, formula1db, Ergast y Stats F1 |
| `B1_numero_vuelta_rapida.csv` | 112 vueltas rápidas con su veredicto |
| `B2_tiempos_clasificacion.csv` | 9 tiempos de clasificación contrastados con la FIA |
| `B4_correcciones_Script2.csv` | Las 6 correcciones heredadas y su evidencia |
| `B5_parrillas.csv` | 35 parrillas contrastadas con la FIA |
| `A1_vueltas_mal_asignadas_coches_compartidos.csv` | 9 coches y 447 vueltas a reasignar |

## Decisiones aplicadas (28-09-2026)

`dbt build`: 111 de 111 en verde (seeds, modelos, tests unitarios y de datos, umbrales de calidad).

| Decisión | Qué se ha hecho | Resultado |
|---|---|---|
| A1 Fusión de vueltas | `int_laptimes`: formula1db principal; FastF1 completa stint, vida del neumático, speed trap y estado de pista, y aporta las carreras sin formula1db | 1 226 272 vueltas de formula1db y 43 988 de FastF1 (39 carreras + Norris en Imola 2024) |
| A1 Coches compartidos | Piloto por nombre normalizado antes que por dorsal (dorsal+nombre, dorsal+apellido, nombre, apellido único, dorsal) | Las 447 vueltas de `A1_…csv` ya están en su piloto; 0 conflictos con la 2.ª pasada |
| A2 Mayoría o evidencia | Seed `lap_corrections` (Russell, Qatar 2024, −5 s y posiciones recalculadas) y regla de mayoría FastF1 = Ergast ≠ formula1db | Qatar 2024: 939/939 posiciones iguales a FastF1. Mayoría: 49 posiciones (47 Japón 2022, 2 Azerbaiyán 2022) |
| A3 V7 | Seed `race_data_overrides` | 72 cifras corregidas; 2 marcadas como disputadas (`disputed_columns`) |
| A4 B1 | Ídem | 97 números de vuelta rápida corregidos |
| A5 B5 | Ídem (parrilla y posiciones ganadas) | 5 parrillas corregidas; ahora coinciden con la sesión STARTING_GRID_POSITION de la propia F1DB |
| A6 Vueltas tras el final | Se eliminan en las carreras cuyo resultado se tomó antes de la bandera real (alguna fuente registra al ganador más allá de las vueltas oficiales) | 27 vueltas: 13 en China 2014 y 14 en Canadá 2018 |
| N1 Brasil 2018 | Seed | Vandoorne 14.º, Ocon 15.º |
| N2 Clasificación | Seed | Verstappen Qatar 2021 Q3 1:21.282 |
| N3 Script-2.sql | Seed `race_data_corrections` | Quedan 4; retiradas Leoni 1978 y Mónaco 1975 |
| N4 Paradas | `fact_pit_lane_passes` | 24 271 entradas: 22 485 paradas, 351 retiradas, 141 penalización u otra, 114 Safety Car, 62 bandera roja y 1 118 sin tipificar (carreras sin paradas en F1DB: todas las anteriores a 1994, más Brasil 1994, Mónaco 1994 e Italia 1997) |
| N5 Numeración | `int_lap_numbering` | Ninguna carrera se renumera: en las 4 detectadas F1DB se contradice a sí misma y se marcan (ver nota) |
| N6 Neumáticos | `int_tyre_compound_mapping` | `tyre_compound_pirelli` y `tyre_compound_relative`; equivalencia coherente en las 101 carreras de 2019–2023 |
| N7 Ergast | Ya no se corrige nada con Ergast | 305 vueltas `disputed` conservan el valor de formula1db |
| N8 Huecos | Relleno desde Ergast dentro de las vueltas oficiales, marcado `source = ergast` | 0 vueltas (ver nota) |
| N9 Clasificación de Ergast | No se usa | — |
| N10 F1DB | `PROPUESTA_F1DB.md` y `f1db_correcciones_propuestas.csv` | Pendiente de que decidas publicarlo |

**Nota N5.** La regla aprobada era «renumerar con el desfase de las paradas y la vuelta rápida; si
no cuadra, marcar». En las cuatro carreras con desfase es F1DB la que usa dos numeraciones:
- Bélgica 2001: las paradas van desde el relanzamiento (como formula1db) y las vueltas rápidas desde
  la primera salida (+4).
- San Marino 1994 (+4), Japón 1994 (+13) y España 1994 (−1): las paradas van desfasadas y las vueltas
  rápidas coinciden.

La numeración de formula1db cuadra con las vueltas oficiales, así que se conserva. Tras la revisión
final (F1), España 1994 se marca como convención (`pit_lap_convention`), y las otras tres quedan
como `inconsistent`, pendientes de la corrección descrita al final. Las 12 vueltas rápidas de
Bélgica 2001 que se mantuvieron en F1DB (A4) siguen su propia numeración.

**Nota N8.** El caso que se contó como hueco de formula1db era la vuelta 73 del #12 en EE. UU.
2001, posterior a sus 72 vueltas oficiales; es un error de Ergast, que tiene intercambiados a Trulli
y Alesi en varias carreras de 2001. Dentro de las vueltas oficiales no falta ninguna vuelta que Ergast
tenga. La regla queda activa por si aparecen en el futuro.

**Nota A6.** Aplicada de forma general («vuelta > vueltas oficiales de un clasificado») habría borrado
unas 2.000 vueltas reales en 47 carreras, sobre todo de los años 50: relevos y coches compartidos en
Indianápolis, y la numeración de Francia 1981. Por eso se limita a las carreras con resultado
tomado a una vuelta anterior. En Bélgica 2021 formula1db no tiene vueltas de más, así que no hace
falta eliminar nada.

**Otros hallazgos al aplicarlas.**
- 41 de las 21 297 paradas de F1DB (99,8 %) no tienen entrada a boxes en la misma vuelta: 1994–95
  con desfases de ±1 vuelta, y São Paulo 2023, donde F1DB cuenta como parada en la vuelta 1 el cambio
  de neumáticos con bandera roja.
- La vida del neumático de FastF1 y la de formula1db coinciden en el 95–98 % de las vueltas desde 2019
  (67 % en 2018). Se usa la de FastF1, como se decidió, y se conserva la de formula1db en
  `formula1db_tyre_age_laps`.

## Decisiones finales (28-09-2026, segunda ronda)

- **F1:** se mantiene la numeración de formula1db. España 1994 no es un error: F1DB apunta la
  parada en la vuelta siguiente, que es donde se pierde el tiempo (22–78 s), y se marca como
  `pit_lap_convention`.
- **F2:** A6 limitada a China 2014 y Canadá 2018. En ninguna hubo bandera roja: se mostró la
  bandera a cuadros una vuelta antes de tiempo y el resultado se tomó al final de la vuelta anterior
  (54 de 56 y 68 de 70).
- **F3:** la regla de relleno desde Ergast queda activa.
- **F4:** publicarás tú la propuesta a F1DB con el texto de `PROPUESTA_F1DB.md`.

## Pendiente para otra iteración

Propuesta aceptada en principio, pero aplazada: corregir los datos desfasados de F1DB en lugar de
renumerar las vueltas. Con estos arreglos ya no haría falta renumerar nada. La evidencia son los
tiempos por vuelta, porque la vuelta de la parada es entre 10 y 40 s más lenta.

| Carrera | Dato de F1DB | Corrección | Evidencia |
|---|---|---|---|
| Japón 1994 | 14 paradas numeradas desde la segunda manga | +13 (vueltas de la primera manga) | 13 + 37 = 50 vueltas oficiales; las 14 cuadran |
| San Marino 1994 | 31 paradas desplazadas 3–5 vueltas | Poner cada parada en su vuelta de entrada a boxes en formula1db | En la vuelta de F1DB el tiempo es normal; en la de formula1db se pierden 10–44 s |
| Bélgica 2001 | 15 vueltas rápidas contadas desde la primera salida | −4 (revierte 12 casos de la A4) | Tiempo idéntico en la vuelta −4; coherente con las paradas de F1DB y las 36 vueltas oficiales |

Cabos sueltos detectados:
- Brundle, Hill y Wendlinger tienen en San Marino 1994 una parada en las vueltas 17–18 (15–19 s
  perdidos) que solo registra formula1db.
- Las dos paradas de Alboreto en San Marino 1994 solo pueden situarse con la marca de boxes de
  formula1db (+3), sin tiempos que lo confirmen.

## Arreglos de datos rápidos (T3, 30-09-2026)

Bloque T3 del plan de acción (`docs/informe_situacion/plan_accion.tex`). Todos los contrastes de
`quality.qa_summary` siguen en PASS (23 PASS y 17 INFO, como antes). Las cifras que cambian lo hacen
por la carga de Italia 2018 y por los tiempos calculados con sectores.

### Bandera roja en la vuelta que contiene la suspensión

**Problema.** Las fuentes marcan la bandera roja en la vuelta en la que se muestra: el estado
«Red Flag» de formula1db.com hasta 2017 y el código 5 del `TrackStatus` de FastF1 desde 2018. Pero
el tiempo de la suspensión (de 8 a 129 minutos) se suma a la vuelta siguiente, la del relanzamiento,
que se quedaba sin marca. Por eso los gráficos de ritmo mostraban vueltas de 20 o más minutos como
si fueran normales.

**Regla** (`int_laptimes`, paso 6). Se marca la vuelta de un piloto si se cumplen dos condiciones:
- Su tiempo supera max(400 s, 3 veces la mediana de las vueltas de la carrera). El triple de la
  mediana evita confundir las vueltas largas de los circuitos de los años 50: el Nürburgring o
  Pescara pasaban de 9 minutos.
- En esa vuelta o en las tres anteriores hay alguna marca de bandera roja, o al menos tres pilotos
  tienen una vuelta así en la misma vuelta.

Las marcas que ya existían no se tocan: ninguna se pierde (comprobado vuelta a vuelta contra el
build anterior). Las vueltas nuevas llevan `is_red_flag:suspension` en `corrections`. El test
`assert_red_flag_on_suspension_laps` impide que vuelvan a aparecer vueltas así sin marcar. Contra
el build anterior encontraba 24 vueltas.

**Evidencia.** El patrón es el mismo en las 22 carreras de la nota 01 del informe de situación: la
vuelta larga es siempre la inmediatamente posterior a las marcadas. La regla marca exactamente esas
24 vueltas de 22 carreras (384 vueltas de piloto). Además marca 12 vueltas sueltas de pilotos cuya
suspensión cayó una vuelta antes o después que la del resto, porque ya habían cruzado la línea al
salir la bandera, en Europa 2007, Australia 2016 y 2023, Toscana 2020 y São Paulo 2023. No marca
nada antes de 2007 ni en 2025-2026.

| Carrera | Vuelta | Pilotos | Minutos (mediana) | Vueltas ya marcadas |
|---|---|---|---|---|
| Europa 2007 | 4 / 5 | 1 / 16 | 24,2 / 23,1 | 3, 4 |
| Corea 2010 | 4 | 24 | 48,9 | 3 |
| Gran Bretaña 2014 | 2 | 18 | 61,5 | 1 |
| Japón 2014 | 3 | 21 | 21,5 | 2 |
| Australia 2016 | 18 / 19 | 1 / 5 | 8,3 / 20,2 | 17, 18 |
| Bélgica 2016 | 10 | 17 | 19,2 | 9 |
| Brasil 2016 | 21 y 29 | 18 y 18 | 35,3 y 26,6 | 20, 28 |
| Azerbaiyán 2017 | 23 | 15 | 24,5 | 21, 22 |
| Italia 2020 | 27 | 17 | 28,0 | 26 |
| Toscana 2020 | 9 y 46 | 1 y 2 | 27,0 y 24,7 | 8, 44, 45 |
| Baréin 2020 | 2 | 19 | 82,5 | 1 |
| Emilia-Romaña 2021 | 34 | 6 | 28,6 | 31–33 |
| Azerbaiyán 2021 | 49 | 15 | 36,4 | 47, 48 |
| Gran Bretaña 2021 | 3 | 19 | 37,3 | 2 |
| Hungría 2021 | 3 | 15 | 26,4 | 2 |
| Arabia Saudí 2021 | 14 y 16 | 19 y 16 | 19,9 y 21,8 | 13, 15 |
| Gran Bretaña 2022 | 2 | 17 | 53,3 | 1 |
| Japón 2022 | 3 | 18 | 129,1 | 2 |
| Australia 2023 | 9, 56 y 58 | 1, 2 y 2 | 18,2, 17,8 y 33,6 | 8, 54, 55, 57 |
| Países Bajos 2023 | 65 | 5 | 43,0 | 63, 64 |
| México 2023 | 35 | 18 | 22,3 | 34 |
| São Paulo 2023 | 2 / 3 | 2 / 15 | 28,0 / 25,6 | 2 |
| Japón 2024 | 2 | 18 | 28,5 | 1 |
| **São Paulo 2024** | **33** | 15 | 25,6 | 30–32 |

Efectos:
- `fact_laptimes.is_red_flag` pasa de 708 a 1.104 vueltas.
- `fact_pit_lane_passes` sigue tipificando la bandera roja solo en la vuelta en la que se muestra.
  Las entradas en la vuelta del relanzamiento son paradas o retiradas: la de Mazepin en Hungría
  2021 sigue siendo `retirement`.
- La página de ritmo de la web ya excluía las vueltas con bandera roja, así que deja de mostrar las
  suspensiones.

Revisado en D1 con los mensajes de dirección de carrera (`fact_race_control_message`, 2018+):
- En 2025 solo hubo una bandera roja en carrera, la de Bélgica (13:01:58 UTC), mostrada en las
  vueltas de formación detrás del Safety Car, antes de la vuelta 1 cronometrada (FastF1 empieza la
  vuelta 1 en el relanzamiento). Ninguna vuelta la contiene, así que no hay nada que marcar, igual
  que en Bélgica 2021 y Mónaco 2022; en 2025 no hubo ninguna suspensión en carrera. En 2026 las
  rojas de R6, R12 y R13 sí están marcadas, pero sus vueltas de suspensión no tienen tiempo en
  FastF1, así que la regla de la suspensión no tiene nada que marcar.
- El control `red_flag_messages_on_laps` (qa_red_flags) comprueba que cada roja mostrada durante
  la carrera tiene alguna vuelta marcada (2018-2026: todas); las anteriores a la vuelta 1 y las
  posteriores a la última vuelta publicada se excluyen de forma explícita.

Pendiente:
- No hay marcas antes de 2007 (San Marino y Japón 1994, Bélgica 1998, Brasil 2003…).

### Tiempo por vuelta calculado con los sectores

En FastF1, la suma de los tres sectores coincide al milisegundo con el tiempo de la vuelta en más
del 99,99 % de las vueltas que tienen ambos (2018-2026: 17 fallos de más de 5 ms en 198 405
vueltas). Cuando falta el tiempo y están los tres sectores, se usa la suma
(`int_fastf1_laps.is_lap_time_from_sectors`). En `fact_laptimes` esas vueltas llevan
`lap_time_ms:sectors` en `corrections`, `original_lap_time_ms` nulo y siguen como `single_source`.
No hace falta un estado nuevo: el tiempo sigue saliendo de una sola fuente.

- Se recuperan 570 vueltas: 319 de 2025 y 251 de 2026.
- En 2018-2024 hay 2 060 vueltas de FastF1 en la misma situación, y formula1db.com las tiene
  todas. Coinciden al milisegundo 2 030 (98,5 %). De las 30 restantes, 25 son de 2024, casi todas de
  Estados Unidos (vueltas 4 y 5), y difieren menos de 0,1 s. Como la diferencia es menor de 1 s,
  esas vueltas pasan de `single_source` a `timing_convention` (+25). Ninguna cambia el tiempo
  publicado, que en esos años es el de formula1db.com. Las que coinciden quedan confirmadas con
  `confirmed_by = fastf1:sectors`, no `fastf1`, para que se vea que el tiempo de FastF1 era una
  suma de sectores.

### Otros arreglos

- **`dim_race.has_sprint`**: se deriva también de la existencia de un resultado de sprint. F1DB
  solo da `sprint_race_date` desde 2024. Pasan a verdadero los 12 sprints de 2021-2023 (test
  `assert_sprint_races_flagged`). La API añade `has_sprint_qualifying` (hay `SPRINT_SHOOTOUT` desde
  2023). La web solo ofrece la clasificación sprint cuando existe: en 2021-2022 la parrilla del
  sprint salía de la clasificación del viernes.
- **Compuestos sin dato**: `NAN`, `NONE`, `UNKNOWN` y `TEST_UNKNOWN` de FastF1 pasan a nulo (436
  vueltas de 2025-2026 en gold), igual que los compuestos vacíos de formula1db.com (14 vueltas de
  2011-2016). Los compuestos Pirelli y relativos no cambian en ninguna vuelta. Lo comprueba el
  test `assert_tyre_compounds_without_placeholders`.
- **HUGEINT**: las sumas de DuckDB devuelven enteros de 128 bits. Se convierten a BIGINT
  `fact_laptimes.gap_to_leader_ms`, `agg_driver_career.laps_completed` y los recuentos de
  `int_lap_completeness` y `int_tyre_compound_mapping` (test `assert_gold_without_hugeint`).
- **Tabla huérfana `silver.int_formula1db_laps_validated`** (1 226 299 filas): solo existía en la
  base local `data/gold/f1.duckdb`, como resto de una versión anterior del modelo. No estaba en la
  base publicada ni en `gold-parquet.zip`, porque el snapshot solo copia `gold` y
  `quality.qa_summary`. Tampoco se crea en la CI, que parte de cero. Se ha borrado de la base local.
- **Italia 2018 en FastF1**: no era un fallo puntual. FastF1 3.8.3 lanza `IndexError` en
  `Session.__fix_tyre_info` (hay más tramos de neumáticos agrupados al principio que entradas a
  boxes) y se queda sin vueltas, también con la caché vacía. El cargador lo rodea
  (`fastf1_loader.tolerate_tyre_info_errors`): si esa corrección falla, se usan los datos de
  neumáticos sin corregir. Con el rodeo, las 925 vueltas con tiempo coinciden al milisegundo con
  formula1db.com, y los compuestos también en todas las vueltas en las que FastF1 da uno: las 38
  restantes son `NAN` o `NONE`, ahora nulas. Se ha cargado en el bronze local. *Actualización (09/10/2026):* el pipeline ya no descarga FastF1 (livetiming.formula1.com responde 403 a GitHub Actions) ni tiene el input `seasons`; Italia 2018 se publicó el 30/09/2026 con la copia cargada en el equipo del autor (`f1-ingest fastf1-publish`, decisión 12). La telemetría de
  clasificación solo se carga desde 2024 (`TELEMETRY_FIRST_SEASON`), así que no se descarga la de
  2018. El método que se rodea es privado: si una versión nueva de FastF1 lo renombra, el rodeo
  no se instala (con un aviso) y la ingesta sigue. Cada carrera cargada sin la corrección aparece
  en el resumen de la ingesta. El rodeo se puede retirar cuando
  `f1-ingest fastf1 --season 2018 --round 14 --force` funcione sin él.
