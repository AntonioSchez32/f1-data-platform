{#- Meteo de la carrera (una muestra por minuto durante toda la sesión), 2018+ (decisiones 29 y
    30): temperatura del aire y de la pista, humedad, presión, lluvia y viento.

    Una sola fuente por carrera: FastF1 si tiene la meteo de esa carrera (2018+, preferente) y, si
    no, OpenF1 (2023+). En FastF1, `sample_utc` es una estimación (tiempo de sesión más la hora
    del tiempo cero calculada con los mensajes de dirección de carrera, ~1 s) y `session_time_ms`
    el dato original; en OpenF1, `sample_utc` es el dato original y no hay tiempo de sesión.
    `sample_seq` numera las muestras de la carrera por orden. -#}
with races as (
    select race_id, season, round from {{ ref('stg_f1db__races') }}
),

fastf1 as (
    select
        races.race_id,
        'fastf1' as source,
        weather.sample_utc,
        weather.session_time_ms,
        weather.air_temperature_c,
        weather.track_temperature_c,
        weather.humidity_pct,
        weather.pressure_mbar,
        weather.is_raining,
        weather.wind_direction_deg,
        weather.wind_speed_ms
    from {{ ref('stg_fastf1__weather') }} as weather
    inner join races using (season, round)
),

openf1 as (
    select
        sessions.race_id,
        'openf1' as source,
        weather.sample_utc,
        null::bigint as session_time_ms,
        weather.air_temperature_c,
        weather.track_temperature_c,
        weather.humidity_pct,
        weather.pressure_mbar,
        weather.is_raining,
        weather.wind_direction_deg,
        weather.wind_speed_ms
    from {{ ref('stg_openf1__weather') }} as weather
    inner join {{ ref('int_openf1_sessions') }} as sessions using (session_key)
    where sessions.is_race
        and sessions.race_id is not null
        and sessions.race_id not in (select race_id from fastf1)
),

unioned as (
    select * from fastf1
    union all by name
    select * from openf1
)

select
    race_id,
    row_number() over (
        partition by race_id order by session_time_ms, sample_utc
    )::integer as sample_seq,
    source,
    sample_utc,
    session_time_ms,
    air_temperature_c,
    track_temperature_c,
    humidity_pct,
    pressure_mbar,
    is_raining,
    wind_direction_deg,
    wind_speed_ms
from unioned
