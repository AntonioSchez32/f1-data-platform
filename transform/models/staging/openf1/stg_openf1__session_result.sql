{#- Resultado de la sesión. `duration` y `gap_to_leader` se guardan como texto JSON (un número,
    un texto como «+1 LAP» o, en clasificación, la lista Q1/Q2/Q3); aquí solo se extrae el tiempo
    total numérico de la carrera. `position` llega como número o, en algunas sesiones, como texto
    con valores no numéricos (`"RT"`, retirado): esos quedan nulos. -#}
select
    session_key::bigint as session_key,
    driver_number::integer as driver_number,
    try_cast(trim(position::varchar, '"') as double)::integer as position,
    number_of_laps::integer as laps,
    coalesce(dnf::boolean, false) as is_dnf,
    coalesce(dns::boolean, false) as is_dns,
    coalesce(dsq::boolean, false) as is_dsq,
    round(try_cast(try_cast(duration as json) as double) * 1000)::bigint as time_ms,
    gap_to_leader as gap_to_leader_json,
    points::double as points
from {{ bronze_source('openf1', 'session_result', 'openf1/session_result/*/*.parquet', {
    'session_key': 'bigint', 'driver_number': 'bigint', 'position': 'double',
    'number_of_laps': 'bigint', 'dnf': 'boolean', 'dns': 'boolean', 'dsq': 'boolean',
    'duration': 'varchar', 'gap_to_leader': 'varchar', 'points': 'double'
}) }}
