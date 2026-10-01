{#- Mensajes de dirección de carrera de OpenF1 (el mismo feed que los de FastF1). -#}
select
    session_key::bigint as session_key,
    {{ utc_timestamp('date') }} as message_utc,
    lap_number::integer as lap_number,
    category,
    flag,
    scope,
    sector::integer as sector,
    driver_number::integer as driver_number,
    message
from {{ bronze_source('openf1', 'race_control', 'openf1/race_control/*/*.parquet', {
    'session_key': 'bigint', 'date': 'varchar', 'lap_number': 'bigint', 'category': 'varchar',
    'flag': 'varchar', 'scope': 'varchar', 'sector': 'double', 'driver_number': 'double',
    'message': 'varchar'
}) }}
