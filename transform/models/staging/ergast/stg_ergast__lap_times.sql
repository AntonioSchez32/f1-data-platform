{#- Vueltas de Ergast con temporada, ronda y dorsal (Ergast identifica al piloto por su propio id;
    el dorsal de cada carrera sale de sus resultados). -#}
with numbers as (
    select raceId, driverId, any_value(number::integer::varchar) as driver_number
    from {{ source('ergast', 'results') }}
    group by all
)

select
    races.year::integer as season,
    races.round::integer as round,
    numbers.driver_number,
    laps.lap::integer as lap_number,
    laps.position::integer as position,
    laps.milliseconds::bigint as lap_time_ms
from {{ source('ergast', 'lap_times') }} as laps
inner join {{ source('ergast', 'races') }} as races using (raceId)
left join numbers using (raceId, driverId)
