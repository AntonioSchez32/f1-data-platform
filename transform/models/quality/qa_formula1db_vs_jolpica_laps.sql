{#- Contraste vuelta a vuelta entre formula1db.com (scraping del TFG) y Jolpica (sucesor de
    Ergast), tercera fuente que cubre desde 1996: valida el histórico en los años que FastF1 no
    cubre. Como en el contraste con FastF1, la vuelta 1 se excluye de la comparación de tiempos.
    Solo las carreras con vueltas de Jolpica (con sus tablas vacías de relleno, ninguna). -#}
with jolpica as (
    select * from {{ ref('int_jolpica_laps') }}
)

select
    legacy.race_id,
    legacy.driver_number,
    legacy.driver_id,
    legacy.lap_number,
    legacy.lap_time_ms as formula1db_lap_time_ms,
    jolpica.lap_time_ms as jolpica_lap_time_ms,
    legacy.position as formula1db_position,
    jolpica.position as jolpica_position,
    jolpica.lap_number is not null as is_matched,
    case
        when legacy.lap_number = 1 or legacy.lap_time_ms is null or jolpica.lap_time_ms is null
            then null
        else abs(legacy.lap_time_ms - jolpica.lap_time_ms) <= 1
    end as is_time_match,
    case
        when legacy.position is null or jolpica.position is null then null
        else legacy.position = jolpica.position
    end as is_position_match
from {{ ref('int_formula1db_laps') }} as legacy
left join jolpica using (race_id, driver_number, lap_number)
where legacy.race_id in (select distinct race_id from jolpica)
