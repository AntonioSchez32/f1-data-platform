{#- Meteo de FastF1 (WeatherData). `sample_utc` es una estimación: tiempo de sesión más la hora
    UTC del tiempo cero, calculada con los mensajes de dirección de carrera (precisión de ~1 s;
    nula si la carrera no tiene mensajes). -#}
select
    season::integer as season,
    round::integer as round,
    Date::timestamp as sample_utc,
    Time_ms::bigint as session_time_ms,
    AirTemp::double as air_temperature_c,
    TrackTemp::double as track_temperature_c,
    Humidity::double as humidity_pct,
    Pressure::double as pressure_mbar,
    Rainfall::boolean as is_raining,
    WindDirection::integer as wind_direction_deg,
    WindSpeed::double as wind_speed_ms
from {{ bronze_source('fastf1', 'weather', 'fastf1/weather/*/*.parquet', {
    'season': 'bigint', 'round': 'bigint', 'Date': 'timestamp', 'Time_ms': 'bigint',
    'AirTemp': 'double', 'TrackTemp': 'double', 'Humidity': 'double', 'Pressure': 'double',
    'Rainfall': 'boolean', 'WindDirection': 'bigint', 'WindSpeed': 'double'
}) }}
