{#- Vueltas de FastF1 con las claves de F1DB (carrera por temporada/ronda y piloto por dorsal).
    Si falta el tiempo de la vuelta pero están los tres sectores, se usa su suma: en las vueltas que
    tienen ambos coincide al milisegundo en más del 99,99 % (2018-2026). Se marca con
    `is_lap_time_from_sectors`. -#}
with races as (
    select race_id, season, round from {{ ref('stg_f1db__races') }}
)

select
    races.race_id,
    numbers.driver_id,
    laps.driver_number,
    laps.lap_number,
    laps.position,
    coalesce(laps.lap_time_ms, laps.sector_1_ms + laps.sector_2_ms + laps.sector_3_ms)
        as lap_time_ms,
    laps.lap_time_ms is null
        and laps.sector_1_ms + laps.sector_2_ms + laps.sector_3_ms is not null
        as is_lap_time_from_sectors,
    laps.session_time_ms,
    laps.lap_start_session_time_ms,
    (
        laps.session_time_ms
        - min(laps.session_time_ms) over (partition by races.race_id, laps.lap_number)
    )::bigint as gap_to_leader_ms,
    laps.sector_1_ms,
    laps.sector_2_ms,
    laps.sector_3_ms,
    laps.stint,
    laps.tyre_compound,
    laps.tyre_age_laps,
    laps.is_pit_in_lap,
    laps.is_pit_out_lap,
    laps.is_yellow_flag,
    laps.is_safety_car,
    laps.is_virtual_safety_car,
    laps.is_red_flag,
    laps.is_deleted,
    laps.is_accurate,
    laps.speed_trap_kmh,
    'fastf1' as source
from {{ ref('stg_fastf1__laps') }} as laps
inner join races using (season, round)
left join {{ ref('int_driver_race_numbers') }} as numbers
    on races.race_id = numbers.race_id
    and laps.driver_number = numbers.driver_number
