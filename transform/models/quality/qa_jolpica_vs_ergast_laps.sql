{#- Control informativo de los cambios de Jolpica frente al volcado de Ergast de 2022 (decisión
    53): vuelta a vuelta, en las carreras que tienen los dos (Ergast llega hasta 2022 R20).
    Jolpica es un proyecto vivo que corrige errores: una diferencia no bloquea nada, pero el
    recuento dice cuánto se ha movido la fuente. Las del primer cambio están revisadas en el
    README (fusión de vueltas). -#}
with ergast as (
    select * from {{ ref('int_ergast_laps') }}
),

jolpica as (
    select * from {{ ref('int_jolpica_laps') }}
    where race_id in (select race_id from ergast)
)

select
    race_id,
    driver_number,
    lap_number,
    ergast.lap_time_ms as ergast_lap_time_ms,
    jolpica.lap_time_ms as jolpica_lap_time_ms,
    ergast.position as ergast_position,
    jolpica.position as jolpica_position,
    case
        when ergast.lap_number is null then 'only_jolpica'
        when jolpica.lap_number is null then 'only_ergast'
        when coalesce(
            abs(ergast.lap_time_ms - jolpica.lap_time_ms) > 1,
            ergast.lap_time_ms is distinct from jolpica.lap_time_ms
        ) then 'lap_time'
        when ergast.position is distinct from jolpica.position then 'position'
        else 'same'
    end as change_type
from ergast
full join jolpica using (race_id, driver_number, lap_number)
-- Sin Jolpica (tablas vacías de relleno) no hay nada que comparar.
where race_id in (select race_id from jolpica)
