{#- Tiempos por vuelta (fact_gp_laptimes del TFG) fusionados de formula1db.com, FastF1 y, en
    vueltas sueltas, Ergast (columna `source`), con marcas de calidad procedentes de la
    conciliación con los resultados oficiales. -#}
with completeness as (
    select race_id, driver_id, official_laps, status
    from {{ ref('int_lap_completeness') }}
)

select
    laps.*,
    -- Vuelta de abandono: FastF1 la registra aunque el piloto no llegue a completarla.
    coalesce(laps.lap_number > completeness.official_laps, false) as is_incomplete_lap,
    coalesce(completeness.status, 'unmatched_driver') as quality_status
from {{ ref('int_laptimes') }} as laps
left join completeness using (race_id, driver_id)
