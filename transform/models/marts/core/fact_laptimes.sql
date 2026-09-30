{#- Tiempos por vuelta (fact_gp_laptimes del TFG) fusionados de formula1db.com, FastF1 y, en
    vueltas sueltas, Ergast (columna `source`), con marcas de calidad procedentes de la
    conciliación con los resultados oficiales. -#}
with completeness as (
    select race_id, driver_id, official_laps, status
    from {{ ref('int_lap_completeness') }}
)

select
    laps.*,
    -- Vuelta de abandono: FastF1 la registra aunque el piloto no llegue a completarla. No se
    -- evalúa si las vueltas oficiales del piloto no son comparables: en los coches compartidos
    -- F1DB no reparte las vueltas del coche entre sus pilotos (se ocultaban 3 578 vueltas, como
    -- las de Behra en el #24 en Bélgica 1955) y a los descalificados les pone 0 (Norris y Piastri
    -- en Las Vegas 2025).
    coalesce(
        laps.lap_number > completeness.official_laps
        and completeness.status not in ('shared_car', 'disqualified'),
        false
    ) as is_incomplete_lap,
    coalesce(completeness.status, 'unmatched_driver') as quality_status
from {{ ref('int_laptimes') }} as laps
left join completeness using (race_id, driver_id)
