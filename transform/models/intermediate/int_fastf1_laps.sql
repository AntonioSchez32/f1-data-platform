{#- Vueltas de FastF1 con las claves de F1DB (carrera por temporada/ronda y piloto por dorsal). -#}
with races as (
    select race_id, season, round from {{ ref('stg_f1db__races') }}
)

select
    races.race_id,
    numbers.driver_id,
    laps.driver_number,
    laps.lap_number,
    laps.position,
    laps.lap_time_ms,
    laps.session_time_ms,
    laps.session_time_ms
        - min(laps.session_time_ms) over (partition by races.race_id, laps.lap_number)
        as gap_to_leader_ms,
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
