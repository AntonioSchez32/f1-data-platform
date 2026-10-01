{#- Mensajes de dirección de carrera de FastF1 (RaceControlMessages): hora UTC del mensaje y tiempo
    de sesión en que se publicó (comparable con los tiempos de las vueltas). -#}
select
    season::integer as season,
    round::integer as round,
    Time::timestamp as message_utc,
    SessionTime_ms::bigint as session_time_ms,
    Lap::integer as lap_number,
    Category as category,
    Flag as flag,
    Scope as scope,
    Sector::integer as sector,
    try_cast(RacingNumber as integer) as driver_number,
    Message as message,
    Status as status
from {{ bronze_source('fastf1', 'messages', 'fastf1/messages/*/*.parquet', {
    'season': 'bigint', 'round': 'bigint', 'Time': 'timestamp', 'SessionTime_ms': 'bigint',
    'Lap': 'bigint', 'Category': 'varchar', 'Flag': 'varchar', 'Scope': 'varchar',
    'Sector': 'bigint', 'RacingNumber': 'varchar', 'Message': 'varchar', 'Status': 'varchar'
}) }}
