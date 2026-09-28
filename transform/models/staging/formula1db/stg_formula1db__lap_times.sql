{#- Tiempos por vuelta obtenidos por web scraping de formula1db.com (TFG).
    Los valores ausentes venían como '-' y los tiempos como texto 'm:ss.sss'. -#}
with source as (
    select * from {{ source('formula1db', 'lap_times') }}
    -- Descarta filas que no son vueltas ('Grid', 'Start', 'A').
    where try_cast(lap as integer) is not null
)

select
    season::integer as season,
    round::integer as round,
    car_number as driver_number,
    driver_name,
    lap::integer as lap_number,
    try_cast(rank as integer) as position,
    {{ parse_duration_ms('lap_time') }} as lap_time_ms,
    {{ parse_duration_ms('time') }} as race_time_ms,
    {{ parse_duration_ms("ltrim(gap, '+')") }} as gap_to_leader_ms,
    try_cast(regexp_extract(gap, '\+(\d+) Lap', 1) as integer) as gap_to_leader_laps,
    {{ parse_duration_ms("ltrim(interval, '+')") }} as interval_ms,
    {{ parse_duration_ms('sector_1') }} as sector_1_ms,
    {{ parse_duration_ms('sector_2') }} as sector_2_ms,
    {{ parse_duration_ms('sector_3') }} as sector_3_ms,
    case upper(nullif(tyre, '-'))
        when 'H' then 'HARD'
        when 'M' then 'MEDIUM'
        when 'S' then 'SOFT'
        when 'SS' then 'SUPERSOFT'
        when 'US' then 'ULTRASOFT'
        when 'HS' then 'HYPERSOFT'
        when 'I' then 'INTERMEDIATE'
        when 'W' then 'WET'
        else upper(nullif(tyre, '-'))
    end as tyre_compound,
    try_cast(tyre_age as integer) as tyre_age_laps,
    contains(status, 'Pit') as is_pit_in_lap,
    contains(status, 'Out Lap') as is_pit_out_lap,
    contains(status, 'Yellow Flag') as is_yellow_flag,
    regexp_matches(status, '(^|, )Safety Car') as is_safety_car,
    contains(status, 'Virtual Safety Car') as is_virtual_safety_car,
    contains(status, 'Red Flag') as is_red_flag,
    contains(status, 'Lap Time Deleted') as is_deleted
from source
