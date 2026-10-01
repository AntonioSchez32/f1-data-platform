{#- Meteo de OpenF1: una muestra por minuto. -#}
select
    session_key::bigint as session_key,
    {{ utc_timestamp('date') }} as sample_utc,
    air_temperature::double as air_temperature_c,
    track_temperature::double as track_temperature_c,
    humidity::double as humidity_pct,
    pressure::double as pressure_mbar,
    rainfall::integer > 0 as is_raining,
    wind_direction::integer as wind_direction_deg,
    wind_speed::double as wind_speed_ms
from {{ bronze_source('openf1', 'weather', 'openf1/weather/*/*.parquet', {
    'session_key': 'bigint', 'date': 'varchar', 'air_temperature': 'double',
    'track_temperature': 'double', 'humidity': 'double', 'pressure': 'double',
    'rainfall': 'bigint', 'wind_direction': 'bigint', 'wind_speed': 'double'
}) }}
