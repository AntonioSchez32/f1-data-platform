{#- Vueltas de carrera de Jolpica (1996-hoy), identificadas por temporada, ronda y driverRef. El
    dorsal y el piloto de F1DB se añaden en int_jolpica_laps. Desde 2025 salen de los PDF de la
    FIA y pueden llegar días después de la carrera. -#}
select
    season::integer as season,
    round::integer as round,
    driver_ref,
    lap::integer as lap_number,
    position::integer as position,
    time_ms::bigint as lap_time_ms,
    origin
from {{ source('jolpica', 'lap_times') }}
