{#- Calendario de sesiones de OpenF1 (todas: libres, clasificación, sprint y carrera). La fecha
    local de la sesión (UTC + gmt_offset del circuito) es la que usa F1DB en `race.date`. -#}
select
    session_key::bigint as session_key,
    meeting_key::bigint as meeting_key,
    year::integer as season,
    session_name,
    session_type,
    {{ utc_timestamp('date_start') }} as date_start_utc,
    {{ utc_timestamp('date_end') }} as date_end_utc,
    try_cast(gmt_offset as interval) as gmt_offset,
    ({{ utc_timestamp('date_start') }} + try_cast(gmt_offset as interval))::date as local_date,
    circuit_key::bigint as circuit_key,
    circuit_short_name,
    country_code,
    country_name,
    location,
    coalesce(is_cancelled::boolean, false) as is_cancelled
from {{ bronze_source('openf1', 'sessions', 'openf1/sessions/*.parquet', {
    'session_key': 'bigint', 'meeting_key': 'bigint', 'year': 'bigint', 'session_name': 'varchar',
    'session_type': 'varchar', 'date_start': 'varchar', 'date_end': 'varchar',
    'gmt_offset': 'varchar', 'circuit_key': 'bigint', 'circuit_short_name': 'varchar',
    'country_code': 'varchar', 'country_name': 'varchar', 'location': 'varchar',
    'is_cancelled': 'boolean'
}) }}
