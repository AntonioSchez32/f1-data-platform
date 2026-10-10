# Traspaso de D2a a D2b (10/10/2026)

D2a está en `265bf95`, aprobado con una condición: comparar con datos reales de Jolpica antes de dar por buena la fusión de D2b. El 10/10 api.jolpi.ca no respondía desde el equipo del autor.

## Bronze de Jolpica

- **Rutas:** `data/bronze/jolpica/{races,drivers,constructors,results,qualifying,lap_times,pit_stops}.parquet` y `_metadata.json`. Las tablas existen siempre, también con `--empty-if-missing`.
- **Metadatos:** `schema_version` (1), `dump_hash`, `dump_uploaded_at`, `last_dump_race`, `api_races` (temporada, ronda y filas por tabla), `api_failed`, `warnings`, `tables` y `empty_placeholder` cuando son tablas vacías de relleno.
- **Esquema común** para el volcado y la API (es el de la API de Ergast). Todas las tablas llevan `origin` (`dump` o `api`) y no tienen claves duplicadas:
  - `races(season, round, race_name, race_date, race_time, circuit_ref, circuit_name, locality, country)`.
  - `drivers(driver_ref, forename, surname, code, permanent_number, date_of_birth, nationality)`.
  - `constructors(constructor_ref, name, nationality)`.
  - `results(season, round, session_type 'R'|'SR', driver_ref, constructor_ref, car_number, position, position_text, points, grid, laps, status, time_ms, fastest_lap_rank, fastest_lap_number, fastest_lap_ms)`:
    - `position_text` vale R, D, W o F si el piloto no se clasificó;
    - `time_ms` solo existe para los clasificados.
  - `qualifying(season, round, driver_ref, constructor_ref, car_number, position, q1_ms, q2_ms, q3_ms)`. Los formatos antiguos QA/QO/QB van en q1 y q2.
  - `lap_times(season, round, driver_ref, lap, position, time_ms)`. Solo carrera.
  - `pit_stops(season, round, driver_ref, stop, lap, local_time, duration_ms)`. Solo carrera; `duration_ms` puede ser nulo cuando viene de la API.

## Cruce con F1DB

- El volcado es la base de datos interna de Jolpica (`formula_one_*.csv`), no el formato Ergast. **No hay `raceId` ni `driverId` enteros.**
- **Carreras:** por (season, round), como hoy `int_ergast_laps` con `stg_f1db__races`.
- **Pilotos:** `driver_ref` es el `driverRef` de Ergast (`max_verstappen`), no el id de F1DB. Para pasarlo a F1DB, usa el dorsal de `results.car_number` en cada carrera (como `stg_ergast__lap_times`) o la fecha de nacimiento + apellido de `drivers`.

## Peculiaridades

- Todos los tiempos van en milisegundos enteros, truncados como hace la API.
  - El `time_ms` de los resultados de la API sale de `millis`, calculado con coma flotante, así que puede diferir en 1 ms del volcado.
- Los sprints solo están en `results`.
- Desde 2025 las vueltas llegan de los PDF de la FIA y pueden llegar tarde.
- Puede haber tablas vacías de relleno (`empty_placeholder`): no añadas pruebas de «no vacío» que rompan la primera ejecución.

## Qué tiene que hacer D2b (decisiones 49–54)

1. **Staging de Jolpica en lugar de Ergast.** Jolpica ocupa el papel de Ergast en `int_laptimes`:
   - vota en la mayoría (decisión A2);
   - rellena vueltas sueltas (N8).

   Ergast deja de votar: nunca votan los dos a la vez. Su volcado se queda en `bronze-static-v1` solo como referencia.
2. **Contraste de las carreras que solo tienen OpenF1 (DAT-06).** En una carrera sin FastF1 se usan las vueltas de Jolpica en lugar de las de OpenF1 si se cumple alguna de estas condiciones:
   - OpenF1 concuerda menos del 90 % con Jolpica;
   - a OpenF1 le faltan vueltas.

   Prioridad: formula1db / FastF1 > OpenF1 fiable > Jolpica. Lleva unit tests propios.
3. **Controles de calidad frente a F1DB:** paradas (duración desde 2011), resultados (carrera y sprint) y clasificación (Q1–Q3), como avisos en `qa_summary`.
4. **Control informativo de los cambios de Jolpica frente a Ergast en 1996–2022.** Revisa y documenta el primer cambio.
5. **README:** actualizar las secciones sobre la fusión de vueltas, que aún describen a Ergast como fuente activa.
6. **Recuentos:** si cambian los de `fact_laptimes` en más de 5 filas, declararlo en `api/tests/smoke/cambios_esperados.json` (umbral de ING-02).
7. **No dar por buena la fusión** sin `uv run f1-ingest jolpica --compare 2026 14 --compare 2005 1 --compare 2024 6` con datos reales.
