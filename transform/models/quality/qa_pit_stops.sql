{#- Cada parada de F1DB debe tener su entrada a boxes en los datos de vueltas, en la misma vuelta
    (con el desfase de numeración de la carrera cuando es inconsistente). F1DB solo guarda las
    paradas reales: el resto de entradas al pit lane se tipifican en fact_pit_lane_passes. -#}
with stops as (
    select * from {{ ref('fact_pit_stops') }}
    where race_id in (select race_id from {{ ref('int_laptimes') }})
),

passes as (
    select * from {{ ref('fact_pit_lane_passes') }} where pass_type = 'pit_stop'
),

race_sources as (
    select race_id, mode(source) as source from {{ ref('int_laptimes') }} group by race_id
)

select
    stops.race_id,
    stops.driver_id,
    stops.stop_number,
    stops.lap_number,
    race_sources.source,
    passes.lap_number as pit_in_lap,
    passes.lap_number is not null as is_match
from stops
left join race_sources using (race_id)
left join passes
    on stops.race_id = passes.race_id
    and stops.driver_id = passes.driver_id
    and stops.stop_number = passes.stop_number
