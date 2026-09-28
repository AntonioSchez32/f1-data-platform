{#- La vuelta más rápida de cada piloto calculada desde las vueltas registradas debe coincidir con
    la vuelta rápida oficial de F1DB (sesión FASTEST_LAP), para ambas fuentes de vueltas. -#}
with recorded as (
    select race_id, driver_id, source, min(lap_time_ms) as best_lap_ms
    from {{ ref('int_laptimes') }}
    where not coalesce(is_deleted, false) and lap_time_ms is not null and driver_id is not null
    group by all
),

official as (
    select race_id, driver_id, min(fastest_lap_time_millis) as fastest_lap_ms
    from {{ ref('int_race_data_corrected') }}
    where session_type = 'FASTEST_LAP' and fastest_lap_time_millis is not null
    group by all
)

select
    recorded.race_id,
    recorded.driver_id,
    recorded.source,
    recorded.best_lap_ms,
    official.fastest_lap_ms,
    recorded.best_lap_ms - official.fastest_lap_ms as difference_ms,
    abs(recorded.best_lap_ms - official.fastest_lap_ms) <= 1 as is_match
from recorded
inner join official using (race_id, driver_id)
