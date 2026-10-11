{#- Resultados de carrera ('R') y sprint ('SR') de Jolpica. En los años 50 un piloto puede tener
    dos filas en la misma carrera (dos coches): la clave lleva el dorsal. -#}
select
    season::integer as season,
    round::integer as round,
    session_type,
    driver_ref,
    constructor_ref,
    car_number::varchar as driver_number,
    position::integer as position,
    -- Posición o, sin clasificar: R (retirado), D (descalificado), W (no tomó la salida),
    -- F (no se clasificó para la carrera).
    position_text,
    points::double as points,
    grid::integer as grid,
    laps::integer as laps,
    status,
    time_ms::bigint as time_ms,
    fastest_lap_rank::integer as fastest_lap_rank,
    fastest_lap_number::integer as fastest_lap_number,
    fastest_lap_ms::bigint as fastest_lap_ms,
    origin
from {{ source('jolpica', 'results') }}
