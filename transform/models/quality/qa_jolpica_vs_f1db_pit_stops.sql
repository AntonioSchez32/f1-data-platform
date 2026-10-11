{#- Control de las paradas de F1DB frente a Jolpica (decisión 52), desde 2011: cada parada de
    cualquiera de las dos, por carrera, piloto (int_jolpica_drivers) y número de parada, en las
    carreras que tienen paradas en las dos. Coincide si las dos la tienen, en la misma vuelta y
    con la misma duración (±1 ms; sin duración en Jolpica, solo la vuelta). Es el contraste que
    habría detectado el error de F1DB de Italia 2026; las correcciones siguen pasando por la
    seed de correcciones con evidencia. -#}
with jolpica as (
    select
        races.race_id,
        drivers.driver_id,
        stops.stop_number,
        stops.lap_number,
        stops.duration_ms
    from {{ ref('stg_jolpica__pit_stops') }} as stops
    inner join {{ ref('stg_f1db__races') }} as races using (season, round)
    inner join {{ ref('int_jolpica_drivers') }} as drivers using (driver_ref)
),

f1db as (
    select race_id, driver_id, stop_number, lap_number, time_ms as duration_ms
    from {{ ref('fact_pit_stops') }}
),

races as (
    select race_id from jolpica
    intersect
    select race_id from f1db
)

select
    race_id,
    driver_id,
    stop_number,
    f1db.lap_number as f1db_lap_number,
    jolpica.lap_number as jolpica_lap_number,
    f1db.duration_ms as f1db_duration_ms,
    jolpica.duration_ms as jolpica_duration_ms,
    coalesce(
        f1db.lap_number = jolpica.lap_number
        and coalesce(abs(f1db.duration_ms - jolpica.duration_ms) <= 1, jolpica.duration_ms is null),
        false
    ) as is_match
from f1db
full join jolpica using (race_id, driver_id, stop_number)
where race_id in (select race_id from races)
