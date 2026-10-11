{#- Clasificación de Jolpica (1994-hoy). Los formatos antiguos de una o dos sesiones van en Q1 y
    Q2, como en la API. -#}
select
    season::integer as season,
    round::integer as round,
    driver_ref,
    constructor_ref,
    car_number::varchar as driver_number,
    position::integer as position,
    q1_ms::bigint as q1_ms,
    q2_ms::bigint as q2_ms,
    q3_ms::bigint as q3_ms,
    origin
from {{ source('jolpica', 'qualifying') }}
