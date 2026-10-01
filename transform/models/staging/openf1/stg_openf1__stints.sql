{#- Tramos de neumático. `tyre_age_at_start` son las vueltas que ya tenía el juego (0 si es
    nuevo). Los compuestos sin dato (UNKNOWN, TEST_UNKNOWN) quedan nulos, como en FastF1. -#}
select
    session_key::bigint as session_key,
    driver_number::integer as driver_number,
    stint_number::integer as stint,
    lap_start::integer as lap_start,
    lap_end::integer as lap_end,
    case
        when upper(compound) not in ('NAN', 'NONE', 'UNKNOWN', 'TEST_UNKNOWN', '')
            then upper(compound)
    end as tyre_compound,
    tyre_age_at_start::integer as tyre_age_at_start
from {{ bronze_source('openf1', 'stints', 'openf1/stints/*/*.parquet', {
    'session_key': 'bigint', 'driver_number': 'bigint', 'stint_number': 'bigint',
    'lap_start': 'double', 'lap_end': 'double', 'compound': 'varchar',
    'tyre_age_at_start': 'bigint'
}) }}
