{#- Cambios de posición en pista: una fila cada vez que cambia la de un piloto. -#}
select
    session_key::bigint as session_key,
    driver_number::integer as driver_number,
    {{ utc_timestamp('date') }} as date_utc,
    position::integer as position
from {{ bronze_source('openf1', 'position', 'openf1/position/*/*.parquet', {
    'session_key': 'bigint', 'driver_number': 'bigint', 'date': 'varchar', 'position': 'bigint'
}) }}
