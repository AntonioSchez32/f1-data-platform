{#- Vueltas de Jolpica (1996-hoy) con la carrera de F1DB (por temporada y ronda) y el dorsal de
    sus resultados de carrera, como hacía int_ergast_laps. El piloto de F1DB sale del dorsal
    (int_driver_race_numbers): es nulo si F1DB aún no tiene los resultados de la carrera, y esas
    vueltas no se publican (control jolpica_lap_driver_attribution). Desde 1996 ningún piloto
    lleva dos dorsales en una carrera, así que el dorsal no duplica vueltas (test de grano). -#}
with numbers as (
    select season, round, driver_ref, any_value(driver_number) as driver_number
    from {{ ref('stg_jolpica__results') }}
    where session_type = 'R'
    group by all
    having count(distinct driver_number) = 1
)

select
    races.race_id,
    driver_numbers.driver_id,
    numbers.driver_number,
    laps.lap_number,
    laps.position,
    laps.lap_time_ms
from {{ ref('stg_jolpica__lap_times') }} as laps
inner join {{ ref('stg_f1db__races') }} as races using (season, round)
inner join numbers using (season, round, driver_ref)
left join {{ ref('int_driver_race_numbers') }} as driver_numbers
    on races.race_id = driver_numbers.race_id
    and numbers.driver_number = driver_numbers.driver_number
