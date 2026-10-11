{#- Paradas de carrera de Jolpica (2011-hoy). La duración puede faltar en las carreras traídas
    por la API. -#}
select
    season::integer as season,
    round::integer as round,
    driver_ref,
    stop::integer as stop_number,
    lap::integer as lap_number,
    local_time,
    duration_ms::bigint as duration_ms,
    origin
from {{ source('jolpica', 'pit_stops') }}
