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
