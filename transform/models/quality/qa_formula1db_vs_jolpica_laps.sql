{#- Contraste vuelta a vuelta entre formula1db.com (scraping del TFG) y Ergast, tercera fuente
    independiente que cubre 1996-2022: valida el histórico en los años que FastF1 no cubre.
    Como en el contraste con FastF1, la vuelta 1 se excluye de la comparación de tiempos. -#}
with ergast as (
    select * from {{ ref('int_ergast_laps') }}
)

select
    legacy.race_id,
    legacy.driver_number,
    legacy.driver_id,
    legacy.lap_number,
    legacy.lap_time_ms as formula1db_lap_time_ms,
    ergast.lap_time_ms as ergast_lap_time_ms,
    legacy.position as formula1db_position,
    ergast.position as ergast_position,
    ergast.lap_number is not null as is_matched,
    case
        when legacy.lap_number = 1 or legacy.lap_time_ms is null or ergast.lap_time_ms is null
            then null
        else abs(legacy.lap_time_ms - ergast.lap_time_ms) <= 1
    end as is_time_match,
    case
        when legacy.position is null or ergast.position is null then null
        else legacy.position = ergast.position
    end as is_position_match
from {{ ref('int_formula1db_laps') }} as legacy
left join ergast using (race_id, driver_number, lap_number)
where legacy.race_id in (select distinct race_id from ergast)
