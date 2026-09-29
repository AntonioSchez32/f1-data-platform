# 01 · Inventario cuantificado de datos que faltan o están incompletos

Nota de trabajo para el informe de situación de `f1-data-platform` (29-09-2026).
Base medida: `data/gold/f1.duckdb` construido el 28-09-2026 (F1DB `v2026.15.1`, publicada el
27-09-2026; 1 172 carreras en el calendario, 1 164 disputadas hasta Azerbaiyán 2026, ronda 15).
Todas las cifras salen de consultas de solo lectura sobre esa base y sobre la capa bronze.

---

## 1. Resumen ejecutivo

1. **Resultados, parrillas, clasificaciones y campeonatos están completos 1950→2026** (1 164 de 1 164
   carreras). Lo que falta es el **detalle dentro de cada carrera**, y crece hacia atrás en el tiempo.
2. **Vueltas: todas las carreras tienen lap chart, pero no todas tienen tiempos.** Hay tiempo por vuelta
   solo desde 1990 (y no completo: faltan 4 carreras de 1990 y Hungría 1993). De 1950 a 1989 solo hay
   posiciones (y en los años 50 el 43,6 % de ellas son desconocidas, «?» en formula1db.com). Excepción:
   Mónaco 1984 y Monza 1988 tienen tiempos.
3. **Faltan 3 223 vueltas de 116 pilotos** frente a las vueltas oficiales, más 39 de 11 pilotos sin
   ninguna vuelta; el 96 % son de 1950–1959 (Indianápolis 1953–1955, relevos y coches compartidos).
   Desde 1970 solo faltan 28 vueltas sueltas (10 de ellas en Francia 1981).
4. **Validación de tiempos:** el 53,7 % de las vueltas (682 058) son `single_source`. Esto afecta a
   todo lo anterior a 1996 (Ergast empieza en 1996) y a todo 2025–2026, que solo tiene FastF1
   (formula1db termina en Abu Dabi 2024).
5. **2025–2026 (FastF1 como única fuente):** 734 vueltas sin tiempo (570 de ellas tienen los tres
   sectores, así que el tiempo se puede calcular), 436 vueltas con compuesto `NAN`/`NONE` (354 en Miami
   2025, 15 pilotos), y ninguna vuelta con compuesto Pirelli real (C1–C6).
6. **Banderas rojas mal marcadas.** Solo hay marcas desde 2007 (31 carreras). En 22 carreras (24 vueltas),
   la vuelta cuyo tiempo contiene la suspensión (20–130 min) no lleva `is_red_flag`. La marca, tanto
   de formula1db como de FastF1, cae en la vuelta en que se muestra la bandera, que es la anterior
   (São Paulo 2024, v. 33, es uno de estos casos). Además faltan todas las rojas
   anteriores a 2007 y Bélgica 2021.
7. **Paradas:** hay duración (tiempo en el pit lane) desde 1994, en 612 carreras. Faltan Brasil y
   Mónaco 1994 e Italia 1997. Desde 1990 hay entradas a boxes sin tipificar, y antes de 1990 no hay
   nada. En ninguna época está el tiempo parado.
8. **Neumáticos:** el compuesto está desde 2011 y los stints desde 2018 (con FastF1). No hay nada
   antes de 2011, y falta el compuesto Pirelli real en 2024–2026.
9. **Sesiones que F1DB ya tiene y el modelo no expone:** libres FP1–FP4 (1986+), warm-up (1984–2003),
   precalificación (1977–1992), clasificaciones de viernes y sábado (1980–2005), porcentaje del
   piloto del día y tiempo de parrilla.
10. **Sesiones que no carga ninguna fuente:** vueltas y paradas de las **carreras al sprint** (hay 29
    sprints con resultado y 0 vueltas), vueltas de clasificación y libres, meteorología, mensajes de
    dirección de carrera y sanciones estructuradas. FastF1 las tiene todas desde 2018 (y los sprints
    desde 2021), pero el cargador las desactiva (`weather=False, messages=False`, solo sesiones R y Q).
11. **Telemetría:** solo la vuelta rápida de clasificación de cada piloto en 2024–2026 (63 carreras).
    No hay telemetría de 2018–2023 ni de carrera.
12. **Incoherencias de modelo:** `dim_race.has_sprint` vale falso en los 12 sprints de 2021–2023.
    FastF1 no tiene Italia 2018 en bronze, así que esa carrera no tiene stint, speed trap ni estado
    de pista. Queda una tabla huérfana, `silver.int_formula1db_laps_validated`. Siguen abiertos los 3
    casos de numeración de vueltas (San Marino y Japón 1994, Bélgica 2001).

---

## 2. Metodología

### 2.1 Fuentes y qué cubre cada una (según `ingestion/` y `transform/`)

| Fuente | Cargador | Qué aporta | Periodo | Estado |
|---|---|---|---|---|
| F1DB (SQLite, release GitHub) | `f1db_loader.py` (todas las tablas) | Resultados, clasificación, parrillas, vuelta rápida, paradas, libres, campeonatos, dimensiones | 1950→actual | Semanal |
| formula1db.com (scraping del TFG) | `legacy_loader.py` (solo `lap_times` y `drivers`; `race_entries` no está en bronze) | Vuelta a vuelta: posición, tiempo, diferencias, sectores, neumático, estado | 1950 → Abu Dabi 2024 | Congelado (web bloquea bots) |
| FastF1 | `fastf1_loader.py`: sesión **R** (laps, results) y **Q** (results; telemetría opcional) | Vueltas 2025+; stint, vida del neumático, speed trap, estado de pista 2018+; Q1–Q3; telemetría de la vuelta rápida de clasificación | 2018→actual (telemetría 2024+) | Semanal (temporada en curso) |
| Ergast (volcado CSV oct-2022) | `ergast_loader.py` | Solo validación de tiempos (1996–2022) y relleno N8 (0 vueltas) | 1996–2022 (vueltas), 2011–2022 (paradas) | Congelado |

Columnas de FastF1 que llegan a bronze y no se usan: `SpeedI1`, `SpeedI2`, `SpeedFL`,
`FreshTyre` (está en staging pero no en `fact_laptimes`), `DeletedReason`, `PitInTime`/`PitOutTime`,
`LapStartDate`, `TeamColor` y `HeadshotUrl`. De F1DB no se usan `driver_of_the_day_percentage`,
`starting_grid_position_time`, `practice_*` ni las tablas de chasis, motor, inscritos, trazados y
relaciones familiares.

### 2.2 Consultas principales

Todas se lanzan desde `transform/` (las vistas de staging leen `../data/bronze/...`) con
`duckdb.connect('../data/gold/f1.duckdb', read_only=True)`.

**Cobertura de vueltas frente a las oficiales por temporada.** Las vueltas oficiales salen de
`RACE_RESULT.race_laps` (con correcciones).

```sql
with off as (
  select race_id, driver_id, sum(race_laps) official_laps, bool_or(race_shared_car) shared
  from silver.int_race_data_corrected where session_type = 'RACE_RESULT' group by all),
lp as (select race_id, driver_id, count(distinct lap_number) rec from gold.fact_laptimes group by all)
select r.season, count(distinct r.race_id) races,
       sum(official_laps) oficiales, sum(least(coalesce(rec,0), official_laps)) cubiertas
from gold.dim_race r left join off using (race_id) left join lp using (race_id, driver_id)
where r.is_completed group by 1 order by 1;
```

**Estado por piloto y carrera.** Se usa el modelo `silver.int_lap_completeness`, que ya concilia
las vueltas registradas con las oficiales:

```sql
select r.season, r.round, r.grand_prix_name, c.status, count(*) pilotos, sum(missing_laps) faltan
from silver.int_lap_completeness c join gold.dim_race r using (race_id)
where status in ('missing_laps', 'no_laps', 'extra_laps') group by all order by 1, 2;
```

**Rellenado de cada campo de `fact_laptimes` por temporada** (resultado en la §3.3):

```sql
select r.season, count(*) vueltas,
  round(100.0*count(lap_time_ms)/count(*),1) tiempo, round(100.0*count(position)/count(*),1) pos,
  round(100.0*count(sector_1_ms)/count(*),1) s1, round(100.0*count(nullif(tyre_compound,''))/count(*),1) comp,
  round(100.0*count(tyre_compound_pirelli)/count(*),1) pirelli, round(100.0*count(stint)/count(*),1) stint,
  sum(is_pit_in_lap::int) boxes, sum(is_safety_car::int) sc, sum(is_red_flag::int) roja,
  round(100.0*count(speed_trap_kmh)/count(*),1) speed_trap
from gold.fact_laptimes join gold.dim_race r using (race_id) group by 1 order by 1;
```

**Suspensiones sin marca de bandera roja.** Una vuelta de más de 400 s que registran al menos 3 pilotos
contiene la suspensión:

```sql
select r.season, r.round, r.grand_prix_name, lap_number, count(*) n,
       median(lap_time_ms)/60000 min_mediana, bool_or(is_red_flag) marcada
from gold.fact_laptimes join gold.dim_race r using (race_id)
where lap_time_ms > 400000 group by all having count(*) >= 3 order by 1, 2, 4;
```

**Sesiones de F1DB por década** (incluidas las que no se exponen):

```sql
select r.season//10*10 decada,
  count(distinct d.race_id) filter (where type = 'FREE_PRACTICE_1_RESULT') fp1, ...
from gold.dim_race r left join read_parquet('../data/bronze/f1db/race_data.parquet') d
  on r.race_id = d.race_id group by 1;
```

Además se consultaron `quality.qa_summary`, `silver.int_lap_numbering`,
`silver.int_formula1db_race_alignment`, `gold.fact_pit_stops`, `gold.fact_pit_lane_passes`,
`gold.fact_qualifying_result`, `gold.fact_race_result`, `gold.fact_quali_telemetry` y el
`TrackStatus` de bronze de FastF1.

---

## 3. Tablas de cobertura

### 3.1 Matriz de cobertura por tipo de dato

✅ completo · 🟡 parcial · ❌ no hay · ⚪ la fuente existe pero no se expone en gold

| Dato | 1950–59 | 60–69 | 70–79 | 80–89 | 90–95 | 96–2005 | 06–10 | 11–17 | 18–24 | 25–26 | Origen |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Resultado de carrera | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | F1DB |
| Parrilla | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | F1DB |
| Penalización de parrilla (texto) | ❌ | ❌ | ❌ | ❌ | 🟡 | 🟡 | 🟡 | ✅ | ✅ | ✅ | F1DB (⚪ solo en silver) |
| Clasificación: mejor tiempo | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | – | – | – | – | F1DB |
| Clasificación: Q1/Q2/Q3 | – | – | – | – | – | – | ✅ | ✅ | ✅ | ✅ | F1DB (+FastF1 QA) |
| Clasificaciones de viernes y sábado | ❌ | ❌ | ❌ | ⚪ | ⚪ | ⚪ (hasta 2002) | – | – | – | – | F1DB `QUALIFYING_1/2_RESULT` |
| Nº de vueltas de clasificación | ❌ | ❌ | ❌ | ❌ | 🟡 (1994+) | ✅ | ✅ | ✅ | ✅ | ✅ | F1DB |
| Precalificación | – | – | ⚪ | ⚪ | ⚪ | – | – | – | – | – | F1DB (1977–1992) |
| Libres (mejor tiempo y vueltas) | ❌ | ❌ | ❌ | ⚪ (1986+) | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | F1DB |
| Warm-up | ❌ | ❌ | ❌ | ⚪ (1984+) | ⚪ | ⚪ (hasta 2003) | – | – | – | – | F1DB |
| Vuelta rápida de cada piloto | 🟡 (solo la absoluta) | 🟡 | 🟡 | 🟡 (74 %) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | F1DB `FASTEST_LAP` (⚪ solo QA) |
| Posición vuelta a vuelta | 🟡 (56 %) | 🟡 (95 %) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | formula1db / FastF1 |
| Tiempo por vuelta | ❌ | ❌ | ❌ | ❌* | 🟡 (4 carreras sin tiempos) | ✅ | ✅ | ✅ | ✅ | 🟡 (97,8–98,7 %) | formula1db / FastF1 |
| Validación con otra fuente | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Ergast | ✅ | ✅ | ✅ Ergast+FastF1 | ❌ | — |
| Sectores | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (~98 %) | ✅ | formula1db 2018+ / FastF1 |
| Entradas y salidas de boxes por vuelta | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | formula1db / FastF1 |
| Paradas (vuelta y duración) | ❌ | ❌ | ❌ | ❌ | 🟡 (1994–95) | ✅ | ✅ | ✅ | ✅ | ✅ | F1DB |
| Tiempo parado | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — |
| Compuesto por vuelta | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ (C1–C5 solo 2019–23) | 🟡 (sin Cx; Miami 2025 `NAN`) | formula1db / FastF1 |
| Vida del neumático | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 🟡 (2014–15) | ✅ | ✅ | formula1db / FastF1 |
| Stint | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (menos Italia 2018) | ✅ | FastF1 |
| Speed trap | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (menos Italia 2018) | ✅ | FastF1 (I1, I2 y FL sin usar) |
| Amarilla / SC / VSC por vuelta | ❌ | ❌ | ❌ | ❌ | 🟡 (SC 1993+) | ✅ (amarilla 1996+) | ✅ | ✅ (VSC 2015+) | ✅ | ✅ | formula1db / FastF1 |
| Bandera roja por vuelta | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 🟡 (2007+) | 🟡 | 🟡 (desfase de 1 vuelta) | 🟡 | formula1db / FastF1 |
| Telemetría | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 🟡 (Q 2024) | 🟡 (Q) | FastF1 |
| Meteorología | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | (FastF1 2018+, sin cargar) |
| Dirección de carrera y sanciones | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | (FastF1 2018+, sin cargar) |
| Sprint: resultado y parrilla | – | – | – | – | – | – | – | – | ✅ (2021+) | ✅ | F1DB |
| Sprint: clasificación SQ1–SQ3 | – | – | – | – | – | – | – | – | ✅ (2023+) | ✅ | F1DB |
| Sprint: vueltas, paradas y vuelta rápida | – | – | – | – | – | – | – | – | ❌ | ❌ | (FastF1 sesión S, sin cargar) |
| Piloto del día | – | – | – | – | – | – | – | 🟡 (2016+) | ✅ | ✅ | F1DB (sin el porcentaje) |
| Hora de salida (UTC) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 🟡 | ✅ | F1DB (71 carreras) |

\* De 1950 a 1989 solo tienen tiempos Mónaco 1984 (396 vueltas), Monza 1988 (927) y 33 vueltas de
Mónaco 1989.

### 3.2 Vueltas oficiales cubiertas por década

Vueltas oficiales = suma de `race_laps` por piloto. Cubiertas = vueltas registradas dentro del rango
oficial (`int_lap_completeness.recorded_in_range`, sin contar las que pasan de las oficiales).
Parcial = al menos un piloto con `missing_laps` o `no_laps`. La última columna excluye los coches
compartidos y los descalificados.

| Década | Carreras | Completas | Parciales | Sin vueltas | Vueltas oficiales | Cubiertas | % | % sin compartidos ni DSQ |
|---|---|---|---|---|---|---|---|---|
| 1950 | 84 | 44 | 40 | 0 | 108 257 | 104 650 | 96,67 | 97,01 |
| 1960 | 100 | 89 | 11 | 0 | 92 875 | 92 700 | 99,81 | 99,89 |
| 1970 | 144 | 142 | 2 | 0 | 157 646 | 157 641 | 100,00 | 100,00 |
| 1980 | 156 | 151 | 5 | 0 | 166 476 | 166 446 | 99,98 | 99,98 |
| 1990 | 162 | 161 | 1 | 0 | 174 640 | 174 639 | 100,00 | 100,00 |
| 2000 | 174 | 174 | 0 | 0 | 182 660 | 182 660 | 100,00 | 100,00 |
| 2010 | 198 | 198 | 0 | 0 | 226 213 | 226 213 | 100,00 | 100,00 |
| 2020 | 146 | 146 | 0 | 0 | 160 245 | 160 244 | 100,00 | 100,00 |

Hay además vueltas registradas por encima de las oficiales: 1 027 de los Tyrrell descalificados en
1984 (F1DB les pone 0 vueltas), 7 716 de coches compartidos y vueltas de abandono de FastF1.

**Estado por piloto (`int_lap_completeness`, 25 752 pares carrera-piloto):**

| Estado | Pilotos | Vueltas que faltan | Comentario |
|---|---|---|---|
| ok | 25 339 | 0 | |
| missing_laps | 116 | 3 223 | 95 de ellos en los años 50 (3 097 vueltas) |
| no_laps | 11 | 39 | Abandonos en la vuelta 1 no registrados (años 50–80) y Behra, Italia 1951 (29) |
| extra_laps | 9 | 7 | Francia 1981 (numeración tras el relanzamiento), Marimón 1954, Daywalt 1954, Russo 1960, Trintignant 1951, Gasly GB 2024 (1 vuelta sin estar en el resultado) |
| shared_car | 117 | 531 | Coche compartido: la fuente no separa las vueltas de cada piloto |
| disqualified | 160 | 19 | F1DB no computa sus vueltas |

### 3.3 Rellenado de campos de `fact_laptimes` (% de vueltas con valor)

| Periodo | Vueltas | Tiempo | Posición | Sectores | Compuesto | Pirelli (Cx) | Relativo | Vida | Stint | Speed trap | Boxes marcados |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1950–1959 | 108 201 | 0 % | 56 % | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 1960–1969 | 92 874 | 0 % | 95 % | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 1970–1989 | 325 148 | 0,4 % | 100 % | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 5 |
| 1990 | 19 165 | 75,3 % | 100 % | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 163 |
| 1991–1995 | 91 880 | 98,5 % | 100 % | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 109 |
| 1996–2010 | 268 832 | 100 % | 100 % | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 8 850 |
| 2011–2017 | 157 786 | 100 % | 100 % | 0 | 100 % | 100 %† | 0–9 % | 85–100 % | 0 | 0 | 6 410 |
| 2018 | 22 246 | 100 % | 100 % | 98,2 % | 100 % | 100 %† | 0,1 % | 100 % | 94,5 % | 95,8 % | 557 |
| 2019–2023 | 113 629 | 100 % | 100 % | ~98 % | 100 % | 100 % | 100 % | 100 % | ~100 % | ~100 % | 3 867 |
| 2024 | 26 574 | 100 % | 100 % | 98,1 % | 100 % | **8,3 %** | 100 % | 100 % | 100 % | 100 % | 844 |
| 2025 | 26 689 | **98,7 %** | 99,9 % | 98,1 % | 100 %‡ | **6,0 %** | 98,5 % | 98,4 % | 98,7 % | 99,9 % | 841 |
| 2026 | 17 236 | **97,8 %** | 99,8 % | 97,5 % | 100 %‡ | **0,1 %** | 99,9 % | 99,7 % | 100 % | 99,8 % | 625 |

† Hasta 2018 `tyre_compound_pirelli` es el nombre comercial (SOFT, SUPERSOFT…), no Cx.
‡ Incluye 354 vueltas `NAN` (Miami 2025, 15 pilotos), 57 `NONE` (Bélgica 2025) y 25 `NONE` (Hungría 2026).
El % de Pirelli en 2024–2026 corresponde solo a INTERMEDIATE/WET: **no hay compuesto Cx desde 2024**
(formula1db 2024 y FastF1 dan HARD/MEDIUM/SOFT, y `int_tyre_compound_mapping` solo cubre 2019–2023).

### 3.4 Tiempo por vuelta: carreras sin tiempos o con tiempos parciales desde 1990

| Carrera | Vueltas | Con tiempo | Comentario |
|---|---|---|---|
| EE. UU. 1990 (R1) | 1 341 | 0 | Solo lap chart |
| Brasil 1990 (R2) | 1 271 | 0 | Solo lap chart |
| San Marino 1990 (R3) | 1 026 | 0 | Solo lap chart |
| Mónaco 1990 (R4) | 1 084 | 0 | Solo lap chart |
| Alemania 1990 (R9) | 744 | 728 | 97,8 % |
| Hungría 1993 (R11) | 1 333 | 0 | Solo lap chart |
| San Marino 1994 (R3) | 1 000 | 957 | 95,7 %; además, numeración `inconsistent` |
| 2025: 18 carreras | — | −352 | FastF1 sin `LapTime`: 341 bajo SC/VSC, 83 de boxes. 319 con los tres sectores. Destacan Gran Bretaña (−91), Bélgica (−60) y Azerbaiyán (−58) |
| 2026: 15 carreras | — | −382 | Ídem (251 con sectores). Italia −62, Azerbaiyán −91, Bélgica −62, Países Bajos −47, Mónaco −37 |

### 3.5 Estado de validación de los tiempos (`validation_status`)

| Periodo | Vueltas | confirmed | single_source | (de ellas con tiempo) | timing_convention | disputed | corrected | Fuentes |
|---|---|---|---|---|---|---|---|---|
| 1950–1989 | 526 223 | 0 | 526 223 | 1 356 | 0 | 0 | 0 | formula1db |
| 1990–1995 | 111 045 | 0 | 111 045 | 104 931 | 0 | 0 | 0 | formula1db |
| 1996–2017 | 426 618 | 425 731 | 204 | 204 | 380 | 303 | 0 | formula1db (+Ergast) |
| 2018–2022 | 111 488 | 111 450 | 0 | 0 | 38 | 0 | 0 | formula1db (+Ergast, FastF1) |
| 2023–2024 | 50 961 | 50 272 | 661 | 661 | 25 | 2 | 1 | formula1db (+FastF1); Norris Imola 2024 solo FastF1 |
| 2025–2026 | 43 925 | 0 | 43 925 | 43 191 | 0 | 0 | 0 | FastF1 |

Hay 106 287 tiempos anteriores a 1996 sin contrastar. En 2023–2024 FastF1 no es independiente de
formula1db (las dos salen del cronometraje en directo de la F1), y FastF1 toma Q1/Q2/Q3 de Ergast.

### 3.6 Paradas y entradas al pit lane por temporada

| Temporada | Carreras | Con paradas F1DB | Paradas (todas con vuelta y duración) | Entradas al pit lane (vueltas) |
|---|---|---|---|---|
| 1950–1989 | 481 | 0 | 0 | 3 (Mónaco 1984, Monza 1988) |
| 1990–1993 | 64 | 0 | 0 | 1 038 (58 carreras, sin tipificar) |
| 1994 | 16 | 14 (sin Brasil y Mónaco) | 476 (475 con duración) | 552 |
| 1995–2020 | 471 | 470 (sin Italia 1997) | 17 481 | 17 787 |
| 2021 | 22 | 21 (Bélgica 2021 no tuvo paradas) | 798 | 823 |
| 2022–2026 | 107 | 107 | 3 780 | 4 066 |

Tipos de paso (`fact_pit_lane_passes`, 24 271): 22 485 paradas, 1 118 sin tipificar, 351 retiradas,
141 penalización u otra, 114 Safety Car y 62 bandera roja. La **duración** de F1DB es el tiempo en el
pit lane de la FIA. En ninguna época hay **tiempo parado**.

### 3.7 Clasificación

| Periodo | Formato F1DB | Tiempo expuesto | Q1 / Q2 / Q3 | Vueltas | Sin exponer |
|---|---|---|---|---|---|
| 1950–1960 | FOUR_LAPS / TWO_SESSION | Mejor tiempo (86–100 %) | — | — | — |
| 1961–1979 | TWO_SESSION | Mejor tiempo (99–100 %) | — | — | Precalificación 1977+ (9 carreras) |
| 1980–1995 | TWO_SESSION | Mejor tiempo (99–100 %) | — | 1994+ | **Clasificaciones de viernes y sábado** (`QUALIFYING_1/2_RESULT`, 15 248 filas en 292–293 carreras hasta 2005) y precalificación hasta 1992 |
| 1996–2002 | ONE_SESSION | 99–100 % | — | ✅ | — |
| 2003–2005 | ONE_LAP / AGGREGATE | 94–97 % | — | ✅ | Tandas 1 y 2 de 2003–2005 |
| 2006–2026 | KNOCKOUT | — | 98–100 % / ~72 % / ~47 % (lo esperable por las eliminaciones) | ✅ | — |

Lo que no hay: vuelta a vuelta de clasificación (FastF1 lo tiene desde 2018, sin cargar), sectores y
speed trap de clasificación, y telemetría anterior a 2024.

### 3.8 Carreras al sprint

| Temporada | Sprints con resultado | `has_sprint` | Clasificación sprint | Vueltas | Paradas | Vuelta rápida |
|---|---|---|---|---|---|---|
| 2021 | 3 | **falso** | (Q del viernes) | 0 | 0 | 0 |
| 2022 | 3 | **falso** | (Q del viernes) | 0 | 0 | 0 |
| 2023 | 6 | **falso** | 6 (SQ1–SQ3) | 0 | 0 | 0 |
| 2024 | 6 | verdadero | 6 | 0 | 0 | 0 |
| 2025 | 6 | verdadero | 6 | 0 | 0 | 0 |
| 2026 | 5 (+Singapur, pendiente) | verdadero | 5 | 0 | 0 | 0 |

Causa del error de `has_sprint`: `stg_f1db__races` lo deriva de `sprint_race_date`, que F1DB solo
rellena desde 2024. Debería derivarse de la existencia de `SPRINT_RACE_RESULT` o de `qualifying_format`
/ `sprint_qualifying_format`.

### 3.9 Telemetría (`fact_quali_telemetry`, 518 699 muestras cada 10 m)

| Temporada | Carreras | Pilotos-carrera | Muestras |
|---|---|---|---|
| 2018–2023 | 0 | 0 | 0 (FastF1 la tiene y no se carga) |
| 2024 | 24 | 475 | 195 334 |
| 2025 | 24 | 475 | 191 381 |
| 2026 | 15 | 325 | 131 984 |

Solo hay la vuelta más rápida de clasificación de cada piloto: nada de carrera, libres ni sprint.
Se guardan X e Y, pero no Z.

### 3.10 Banderas rojas (vueltas con `is_red_flag`)

Hay marcas en 31 carreras de 2007–2026. Entre 1990 y 2006 no hay ninguna carrera marcada, aunque
hubo varias suspendidas (San Marino y Japón 1994, Bélgica 1998, Brasil 2003…).

**Vueltas que contienen la suspensión** (más de 400 s, al menos 3 pilotos) y **no** llevan la marca:

| Carrera | Vuelta con la suspensión | Minutos (mediana) | Vueltas marcadas |
|---|---|---|---|
| Europa 2007 | 5 | 23,1 | 3–4 |
| Corea 2010 | 4 | 48,9 | 3 |
| Gran Bretaña 2014 | 2 | 61,5 | 1 |
| Japón 2014 | 3 | 21,5 | 2 |
| Australia 2016 | 19 | 20,2 | 17–18 (la 18 sí) |
| Bélgica 2016 | 10 | 19,2 | 9 |
| Brasil 2016 | 21 y 29 | 35,3 / 26,6 | 20, 28 |
| Azerbaiyán 2017 | 23 | 24,5 | 21–22 |
| Italia 2020 | 27 | 28,0 | 26 |
| Baréin 2020 | 2 | 82,5 | 1 |
| Emilia-Romaña 2021 | 34 | 28,6 | 31–33 |
| Azerbaiyán 2021 | 49 | 36,4 | 47–48 |
| Gran Bretaña 2021 | 3 | 37,3 | 2 |
| Hungría 2021 | 3 | 26,4 | 2 |
| Arabia Saudí 2021 | 14 y 16 | 19,9 / 21,8 | 13, 15 |
| Gran Bretaña 2022 | 2 | 53,3 | 1 |
| Japón 2022 | 3 | 129,1 | 2 |
| Países Bajos 2023 | 65 | 43,0 | 63–64 |
| México 2023 | 35 | 22,3 | 34 |
| São Paulo 2023 | 3 | 25,6 | 2 |
| Japón 2024 | 2 | 28,5 | 1 |
| **São Paulo 2024** | **33** | 25,6 | 30–32 |

El patrón es sistemático. La marca de roja (el estado «Red Flag» de formula1db, que se usa hasta
2017, y el código 5 del `TrackStatus` de FastF1, desde 2018) se asigna a la vuelta en la que se
muestra la bandera, mientras que el tiempo de la suspensión se suma a la vuelta siguiente, la del
relanzamiento. Los datos sí marcan bien Mónaco 2011, Canadá 2011, Malasia 2012, Mónaco 2013 y 2022,
Toscana 2020 y Australia 2023. Faltan además:
- **Bélgica 2021.** FastF1 marca la vuelta 3, pero en gold solo queda la vuelta 1 de formula1db, sin
  marca.
- **Japón y Mónaco 2024.** Faltan las vueltas de los pilotos que abandonaron en la vuelta 1 (FastF1
  tiene 20 filas y el modelo 16–18).
- **2025.** No hay ninguna bandera roja marcada, ni en FastF1 ni en el modelo. Hay que comprobarlo.

En 2025–2026 la vuelta de la suspensión no tiene tiempo en FastF1 (Italia 2026: 62 vueltas sin tiempo).

### 3.11 Otras sesiones y datos de F1DB que no se exponen

| Sesión o dato | Carreras | Periodo | Filas |
|---|---|---|---|
| FREE_PRACTICE_1_RESULT | 713 | 1986–2026 | 16 164 (97 % con tiempo) |
| FREE_PRACTICE_2_RESULT | 687 | 1986–2026 | 15 575 |
| FREE_PRACTICE_3_RESULT | 424 | 2003–2026 | 8 889 |
| FREE_PRACTICE_4_RESULT | 36 | 2004–2005 | 706 |
| WARMING_UP_RESULT | 324 | 1984–2003 | 7 683 |
| PRE_QUALIFYING_RESULT | 79 | 1977–1992 | 647 (636 con tiempo) |
| QUALIFYING_1/2_RESULT | 292/293 | 1980–2005 | 15 248 |
| DRIVER_OF_THE_DAY (porcentaje) | 228 | 2016–2026 | 832 porcentajes |
| FASTEST_LAP por piloto | 1 163 | 1950–2026 | 17 170 (solo la absoluta hasta 1979) |
| SPRINT_STARTING_GRID_POSITION | 29 | 2021–2026 | 589 (se usa dentro del resultado) |
| Tablas `chassis`, `engine`, `entrant`, `season_entrant_*`, `circuit_layout`, `driver_family_relationship` | — | — | Sin modelo gold |

---

## 4. Lista priorizada de huecos

Prioridad: **alta** = error visible en la web o dato básico que falta en una época cubierta; **media** =
amplía análisis relevantes; **baja** = histórico marginal o complemento.

### 4.1 Prioridad alta

| # | Hueco | Magnitud | Impacto en la web o el análisis | Fuentes posibles (hipótesis) |
|---|---|---|---|---|
| H1 | **Vueltas de las carreras al sprint** | 29 sprints (2021–2026), 0 vueltas | La página de la carrera no tiene lap chart, ritmo ni estrategia del sprint. `agg_driver_career.sprint_wins` sí existe | FastF1 sesión `S` (2021+) desde la misma API; Jolpica `/sprint` (resultados); formula1db.com (si tiene páginas de sprint; lo estudia la nota 03) |
| H2 | **Banderas rojas mal situadas o ausentes** | 24 vueltas de suspensión sin marca en 22 carreras (2007–2024); 0 marcas antes de 2007; Bélgica 2021 | Los gráficos de ritmo muestran vueltas de 20–130 min como si fueran normales, y el lap chart no sombrea la suspensión. Los tipos `red_flag` de pit lane están infracontados | Regla derivada: marcar la vuelta siguiente a la del código 5 si su tiempo supera X; mensajes de dirección de carrera de FastF1 (`messages=True`, 2018+); lista de carreras con bandera roja de Wikipedia; Stats F1 e informes FIA para 1990–2006 |
| H3 | **2025–2026 sin segunda fuente y con huecos** | 43 925 vueltas `single_source`; 734 sin tiempo (570 recuperables sumando sectores); 436 con compuesto `NAN`/`NONE` | Ritmo con huecos; la estrategia de Miami 2025 sale vacía; el semáforo de calidad no cubre la temporada en curso | Calcular el tiempo con S1+S2+S3 o con la diferencia de `Time`; Jolpica `/laps` y `/pitstops` (2023+, sucesor de Ergast); formula1db.com en la sesión del usuario (ver restricciones); el livetiming de F1 para el compuesto (FastF1 `session.laps` con `livedata`) |
| H4 | **Compuesto Pirelli real (C1–C6) en 2024–2026** | 0 % de vueltas secas con Cx | La web solo puede mostrar SOFT/MEDIUM/HARD; no se puede comparar el desgaste real entre carreras | Notas de prensa de Pirelli con los compuestos elegidos para cada GP (una fila por carrera; se extiende el seed de `int_tyre_compound_mapping`); Wikipedia («Pirelli tyre allocation»); racingnews365 y f1technical |
| H5 | **`dim_race.has_sprint` falso en 2021–2023** | 12 carreras | Filtros y etiquetas «fin de semana sprint» incorrectos; afecta a la API `/seasons` y a los agregados | Corrección interna (derivar de `SPRINT_RACE_RESULT`) |
| H6 | **Tiempos por vuelta 1990 (4 carreras) y Hungría 1993** | 5 carreras sin tiempos; Alemania 1990 y San Marino 1994 parciales | Página de ritmo vacía justo en la primera temporada con tiempos | Scraping de formula1db.com en la sesión del usuario (quizás ahora tenga esas carreras); lap charts de la FIA/FOCA; Forix/Autosport; revistas de la época (hipótesis) |
| H7 | **Numeración inconsistente pendiente** | San Marino 1994 (31 paradas desfasadas), Japón 1994 (14 paradas +13), Bélgica 2001 (15 vueltas rápidas −4) y Alboreto/Brundle/Hill/Wendlinger 1994 | Paradas y vuelta rápida en una vuelta equivocada en la web; `fact_pit_lane_passes` las cuenta como `penalty_or_other` | Ya documentado en `INFORME.md` («Pendiente para otra iteración»): seed de correcciones con los tiempos por vuelta como evidencia y propuesta a F1DB |

### 4.2 Prioridad media

| # | Hueco | Magnitud | Impacto | Fuentes posibles |
|---|---|---|---|---|
| M1 | Datos de sesión que F1DB ya tiene y no se exponen: **libres, warm-up, precalificación, clasificaciones de viernes y sábado** | ~64 000 filas en 713 carreras | Faltan las pestañas de libres y de clasificación histórica (antes de 2006 solo hay el mejor tiempo, cuando F1DB tiene las dos sesiones de 1980–2005) | F1DB (ya en bronze): basta con modelos gold nuevos |
| M2 | **Vuelta rápida de cada piloto** (`FASTEST_LAP`) | 17 170 filas; solo en QA | Sin ranking de vueltas rápidas por carrera ni evolución histórica fuera de las vueltas; antes de 1990 es el único dato de ritmo | F1DB (ya en bronze) |
| M3 | **Meteorología** | 0 carreras | No se puede explicar el ritmo, el uso de intermedios o el desgaste; es clave para la fase 7 (degradación) | FastF1 `weather=True` (2018+, temperatura de aire y pista, lluvia por minuto); Open-Meteo histórico (reanálisis desde 1940) con coordenadas del circuito y hora de salida para 1950–2017 (la hora UTC solo está en 71 carreras); Wikipedia (condiciones de carrera) |
| M4 | **Mensajes de dirección de carrera, sanciones e investigaciones** | 0 | No hay línea de tiempo de incidentes ni tipificación fiable de drive-through o stop-and-go (141 `penalty_or_other` sin detalle) | FastF1 `messages=True` (2018+); documentos de decisión de la FIA (PDF, 2019+); Wikipedia (notas de las clasificaciones); `time_penalty_ms` de F1DB (solo el total: 12 casos en 2000–09, 103 en 2010–19 y 162 en 2020–26) |
| M5 | **Stints y neumáticos antes de 2011** | 0 % de compuesto entre 1950 y 2010; vida del neumático parcial en 2014–15 (1 038 y 2 864 vueltas sin dato) | La estrategia de neumáticos solo funciona desde 2011; antes solo se puede deducir de las paradas | Stints derivados de las paradas de F1DB (1994+) y de las entradas a boxes (1990+); Bridgestone/Michelin 2001–2010 (prime/option en notas de prensa de 2007–2010); Forix |
| M6 | **Telemetría 2018–2023 y de carrera** | 6 temporadas sin telemetría | La comparación de telemetría solo funciona desde 2024 | FastF1 (`--telemetry` para 2018–2023; la carga cuesta muchas peticiones, con un límite de 500/h) |
| M7 | **Validación de 1990–1995** | 106 287 tiempos `single_source` | El semáforo de calidad no cubre esas temporadas | No hay tiempos por vuelta en Ergast antes de 1996. Hipótesis: lap charts FIA/FOCA, Forix y la vuelta rápida de F1DB como control parcial (ya en `qa_fastest_laps`) |
| M8 | **FastF1 Italia 2018 ausente** | 925 vueltas sin stint, speed trap ni estado de pista; sin QA de clasificación | Estrategia sin tramos de FastF1 (las pausas se deducen de las entradas a boxes) | Volver a cargar con `f1-ingest fastf1 --season 2018` (quizás fue un fallo puntual de la API) |
| M9 | **Paradas de 1994 (Brasil, Mónaco) e Italia 1997** | 3 carreras | Página de paradas vacía | Documentos de la FIA (pit stop summary), formula1.com (archivo de resultados; hipótesis), las entradas a boxes de formula1db (ya en `fact_pit_lane_passes`) |
| M10 | **Tiempo parado** | 0 en todas las épocas | Solo existe el tiempo en el pit lane: no hay ranking de equipos por parada | DHL Fastest Pit Stop Award (tiempos parados de las paradas más rápidas, 2015+); derivar `PitInTime`/`PitOutTime` de FastF1 (tiempo en el pit lane, no parado) |
| M11 | **Speed traps intermedios y de meta** | `SpeedI1`, `SpeedI2` y `SpeedFL` en bronze, no expuestos | Menos variables para comparar velocidad punta | FastF1 (ya en bronze) |

### 4.3 Prioridad baja

| # | Hueco | Magnitud | Impacto | Fuentes posibles |
|---|---|---|---|---|
| B1 | **Tiempos por vuelta 1950–1989** | 524 867 vueltas (1950–1989) sin tiempo, solo con posición | No hay gráfico de ritmo antes de 1990 (solo lap chart) | Prácticamente inexistentes en abierto. Hipótesis: hojas de cronometraje de la época (Longines, Heuer, TAG), anuarios (*Autocourse*), Forix/Autosport, *Motor Sport* archive |
| B2 | **Posiciones desconocidas («?») en los años 50–60** | 43,6 % de las vueltas de los 50; 5,4 % de los 60 | Lap chart con huecos | Stats F1 (`tour-par-tour`), Forix, lap charts de revistas; muy costoso |
| B3 | **Vueltas que faltan en los años 50** | 3 097 vueltas en 95 pilotos (Indianápolis 1953–1955, relevos) | Lap chart incompleto en Indianápolis y en los relevos | Stats F1; resultados de la USAC para Indianápolis (hipótesis) |
| B4 | **Coches compartidos** | 117 pilotos, 531 vueltas sin separar | Vueltas de piloto aproximadas en los años 50 | Stats F1 reparte las vueltas por piloto (visto al revisar el V7) |
| B5 | **Vuelta rápida por piloto antes de 1980** | Solo la absoluta (94 + 104 + 147 filas en 1950–79); 74 % de los pilotos en los 80 | Rankings históricos de vuelta rápida incompletos | Stats F1 (`meilleur-tour`) |
| B6 | **Hora de salida histórica** | 71 de 1 172 carreras con hora UTC | Limita el cruce con la meteorología horaria | Wikipedia, formula1.com |
| B7 | **Piloto del día (porcentaje)** | 832 porcentajes sin exponer | Detalle menor | F1DB (ya en bronze) |
| B8 | **Dimensiones de F1DB sin modelo** (chasis, motor, inscritos, trazado, familias) | — | Fichas de coche y trazado, «coche de cada victoria» | F1DB (ya en bronze) |

---

## 5. Incoherencias abiertas conocidas

1. **Numeración de vueltas** (`int_lap_numbering`): 3 `inconsistent` (San Marino 1994, Japón 1994,
   Bélgica 2001) y 1 `pit_lap_convention` (España 1994). 487 carreras quedan con `no_evidence`; 486 son anteriores a 1994, porque sin paradas en
   F1DB (y casi sin vueltas rápidas por piloto) no hay con qué comprobar la numeración.
2. **Bandera roja en la vuelta equivocada** (§3.10): 24 vueltas en 22 carreras, entre ellas el caso de São Paulo 2024, v. 33.
3. **`dim_race.has_sprint`** falso en 12 sprints de 2021–2023.
4. **Paradas de F1DB sin entrada a boxes:** 41 de 21 297 (desfases de ±1 en 1994–95 y São Paulo 2023,
   donde el cambio de neumáticos con bandera roja cuenta como parada en la vuelta 1).
5. **Vida del neumático:** FastF1 y formula1db coinciden en el 95–98 % de las vueltas desde 2019 y
   solo en el 67 % en 2018. Se usa FastF1, pero en 2025–2026 no hay con qué contrastarla.
6. **`disputed`:** 305 vueltas (303 en 1996–2017 y 2 en 2023–24) conservan el valor de formula1db
   sin mayoría.
7. **Realineación de rondas de formula1db:** 17 carreras de 2023 venían etiquetadas con la ronda
   siguiente; se corrigen por contenido. En Mónaco 2023 hay un piloto sin emparejar (95 %).
8. **Vueltas sin resultado oficial:** Trintignant, Italia 1951 (29 vueltas; no figura en el resultado
   con vueltas) y Gasly, Gran Bretaña 2024 (1 vuelta; no tomó la salida).
9. **Francia 1981:** formula1db numera desde el relanzamiento: 10 pilotos con −1 y 4 con vueltas de
   más.
10. **Descalificados:** F1DB les pone 0 vueltas (Tyrrell 1984 y otros), así que la cobertura supera el
    100 % en los años 80.
11. **Tabla huérfana `silver.int_formula1db_laps_validated`** (1 226 299 filas) en `f1.duckdb`, sin
    modelo dbt: quedó de una versión anterior. Conviene borrarla o activar la limpieza de relaciones
    huérfanas.
12. **Compuestos `NAN`/`NONE`** guardados como texto en 2025–2026: deberían ser NULL (los cuenta el
    test de rellenado).
13. **QA de FastF1 frente a F1DB:** 30 parrillas (99,18 %), 8 tiempos de clasificación y 7 vueltas
    rápidas no coinciden. Dentro del umbral, pero sin revisar una por una.

---

## 6. Carreras concretas con huecos de vueltas (`missing_laps`, `no_laps`, `extra_laps`)

Formato `piloto(registradas/oficiales)`. Se omiten los coches compartidos y los descalificados.

| Carrera | Estado | Faltan | Detalle |
|---|---|---|---|
| Gran Bretaña 1950 | missing | 22 | joe-fry(45/64), peter-walker(2/5) |
| Indianápolis 1950 | missing | 98 | chitwood(82/136), banks(71/112), levrett(105/108) |
| Francia 1950 | missing | 84 | 11 pilotos: pozzi(14/56), etancelin(26/59)… |
| Italia 1950 | missing | 42 | serafini(47/80), taruffi(25/34) |
| Indianápolis 1951 | missing | 107 | mcgrath(100/200), scarborough(93/100) |
| Francia 1951 | missing | 42 | gonzález(35/77) |
| Italia 1951 | missing / no_laps / extra | 79 | bonetto(29/79), behra(0/29); trintignant con 29 vueltas y sin vueltas oficiales |
| Suiza 1952 | missing | 33 | andre-simon(18/51) |
| Francia 1952 | missing | 47 | fischer(33/66), de-graffenried(20/34) |
| Gran Bretaña 1952 | no_laps | 1 | cantoni(0/1) |
| Países Bajos 1952 | missing | 40 | landi(43/83) |
| Argentina 1953 | missing | 41 | trintignant(50/91) |
| Indianápolis 1953 | missing | 543 | 9 pilotos |
| Países Bajos 1953 | missing | 64 | bonetto(25/89) |
| Bélgica 1953 | missing | 22 | claes(13/35) |
| Italia 1953 | missing | 38 | mantovani(38/76) |
| Argentina 1954 | missing / extra | 1 | rosier(1/2); marimón con 48 vueltas registradas y 5 oficiales |
| Indianápolis 1954 | missing / extra | 620 | 11 pilotos; daywalt con 165 registradas y 111 oficiales |
| Bélgica 1954 | missing | 15 | hawthorn(20/35) |
| Gran Bretaña 1954 | missing | 12 | villoresi(30/40), bira(42/44) |
| Alemania 1954 | missing | 6 | gonzález(16/22) |
| Italia 1954 | missing | 48 | maglioli(30/78) |
| España 1954 | missing | 27 | de-graffenried(30/57) |
| Argentina 1955 | missing | 139 | herrmann, gonzález, bucci, castellotti |
| Mónaco 1955 | missing | 36 | taruffi(50/86) |
| Indianápolis 1955 | missing | 101 | bettenhausen(123/200), faulkner(176/200) |
| Bélgica 1955 | missing | 25 | mieres(10/35) |
| Gran Bretaña 1955 | missing | 58 | hawthorn, wharton, rolt |
| Argentina 1956 | missing | 158 | musso, landi, uria |
| Mónaco 1956 | missing | 90 | collins(54/100), bayol(44/88) |
| Indianápolis 1956 | missing | 37 | elisian(123/160) |
| Bélgica 1956 | missing | 23 | perdisa(13/36) |
| Francia 1956 | missing | 85 | hawthorn(10/56), perdisa(20/59) |
| Gran Bretaña 1956 | missing | 12 | castellotti(80/92) |
| Alemania 1956 | missing | 7 | de-portago, musso |
| Italia 1956 | missing | 29 | collins, maglioli, villoresi |
| Argentina 1957 | missing | 117 | perdisa(30/98), de-portago(49/98) |
| Mónaco 1957 | missing | 25 | scarlatti(42/64), von-trips(92/95) |
| Francia 1957 | missing | 38 | macdowel(30/68) |
| Gran Bretaña 1957 | missing | 3 | trintignant(85/88) |
| Pescara 1957 | no_laps | 2 | piotti(0/1), gould(0/1) |
| Italia 1957 | missing | 66 | scarlatti(50/84), simon(40/72) |
| Francia 1958 | missing | 15 | lewis-evans(20/35) |
| Italia 1958 | missing | 24 | gregory(45/69) |
| Marruecos 1958 | missing | 7 | bridger(26/30), picard(28/31) |
| Argentina 1960 | missing | 34 | trintignant(46/80) |
| Indianápolis 1960 | extra | 0 | russo (90 registradas / 84 oficiales) |
| Francia 1960 | missing | 1 | von-trips(30/31) |
| EE. UU. 1961 | missing | 62 | gendebien(30/92) |
| Mónaco 1965 | no_laps | 1 | ginther(0/1) |
| México 1966 | missing | 1 | solana(8/9) |
| Mónaco 1967 | missing | 3 | servoz-gavin(1/4) |
| México 1967 | no_laps | 1 | fisher(0/1) |
| Bélgica 1968 | no_laps | 1 | bonnier(0/1) |
| España 1969 | no_laps | 1 | oliver(0/1) |
| Brasil 1973 | missing | 1 | pace(8/9) |
| Suecia 1974 | missing | 2 | reutemann(29/30), regazzoni(23/24) |
| Francia 1981 | missing / extra | 17 | 10 pilotos con −1 y 4 con vueltas de más (numeración tras el relanzamiento) |
| Canadá 1983 | no_laps | 1 | surer(0/1) |
| Alemania 1986 | missing | 10 | brundle(24/34) |
| San Marino 1988 | no_laps | 1 | de-cesaris(0/1) |
| Mónaco 1988 | no_laps | 1 | piquet(0/1) |
| España 1997 | missing | 1 | hill(17/18) |
| Gran Bretaña 2024 | extra | 0 | gasly, 1 vuelta sin estar en el resultado |
| São Paulo 2024 | missing | 1 | colapinto(29/30) |

---

## 7. Resumen del impacto en la web (`web/src/app/[lang]/races/[id]/…`)

| Página | Depende de | Épocas en que sale vacía o incompleta |
|---|---|---|
| `lap-chart` | `position` | Huecos en 1950–1969 («?» y relevos) |
| `pace` | `lap_time_ms` | Vacía antes de 1990 (salvo 3 carreras), en 1990 (4 carreras) y en Hungría 1993; picos de suspensión sin marcar desde 2007 |
| `tyres` (API `/stints`) | `tyre_compound`, `is_pit_in_lap` | Vacía antes de 2011; Miami 2025 sin compuesto; sin Cx desde 2024 |
| `pitstops` | `fact_pit_stops`, `fact_pit_lane_passes` | Vacía antes de 1994 (entradas sin tipificar en 1990–93); faltan 3 carreras |
| `qualifying` | `fact_qualifying_result` | Antes de 2006 solo el mejor tiempo; faltan las sesiones de viernes y sábado de 1980–2005 |
| `telemetry` | `fact_quali_telemetry` | Solo 2024–2026 |
| Resultado del sprint | `fact_race_result` (SPRINT) | Hay resultado, pero no vueltas, paradas ni vuelta rápida |
| `quality` | `qa_summary` | No mide 2025–2026 ni 1950–1995 (todo `single_source`) |
