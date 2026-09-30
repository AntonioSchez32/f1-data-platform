{#- Paradas en boxes de F1DB. F1DB repite algunas filas idénticas salvo por el orden de la lista
    (Italia 2026: la segunda parada de 9 pilotos aparece dos veces, con la misma vuelta y el mismo
    tiempo); se deja una. Si dos filas de la misma parada no coinciden, el test de grano
    (race_id, driver_id, stop_number) falla en lugar de elegir una. -#}
select
    race_id,
    position_display_order,
    driver_number,
    driver_id,
    constructor_id,
    engine_manufacturer_id,
    tyre_manufacturer_id,
    pit_stop_stop as stop_number,
    pit_stop_lap as lap_number,
    pit_stop_time_millis as time_ms,
    pit_stop_time_millis / 1000.0 as time_seconds
from {{ ref('int_race_data_corrected') }}
where session_type = 'PIT_STOP'
qualify row_number() over (
    partition by
        race_id, driver_id, driver_number, constructor_id, pit_stop_stop, pit_stop_lap,
        pit_stop_time_millis
    order by position_display_order
) = 1
