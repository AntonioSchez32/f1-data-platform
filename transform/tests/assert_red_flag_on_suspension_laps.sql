{#- La vuelta que contiene una suspensión con bandera roja lleva la marca (regla de int_laptimes):
    ninguna vuelta en la que al menos tres pilotos tardan más de max(400 s, 3 veces la mediana de
    la carrera) queda sin marcar (umbrales en las vars red_flag_* de dbt_project.yml). Caso de referencia: São Paulo 2024, vuelta 33. -#}
with pace as (
    select race_id, median(lap_time_ms) as median_lap_time_ms
    from {{ ref('fact_laptimes') }}
    group by race_id
)

select laps.race_id, laps.lap_number, count(*) as unflagged_long_laps
from {{ ref('fact_laptimes') }} as laps
inner join pace using (race_id)
where laps.lap_time_ms > greatest(
    {{ var('red_flag_min_lap_ms') }}, {{ var('red_flag_median_factor') }} * pace.median_lap_time_ms
)
    and not coalesce(laps.is_red_flag, false)
group by laps.race_id, laps.lap_number
having count(*) >= {{ var('red_flag_min_drivers') }}
