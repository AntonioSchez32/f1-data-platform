{#- Si en la temporada el piloto tuvo un solo compañero y ninguno de los dos compartió coche,
    el resumen carrera a carrera (agg_teammate_season) coincide con el desglose por pareja
    (agg_teammate_h2h): mismas carreras y mismos puntos (Hamilton 2021 frente a Bottas). -#}
with single_pair as (
    select season, driver_id, any_value(teammate_id) as teammate_id,
        any_value(races_together) as races_together, any_value(points) as points,
        any_value(teammate_points) as teammate_points
    from {{ ref('agg_teammate_h2h') }}
    group by season, driver_id
    having count(*) = 1
),

shared_car_drivers as (
    select distinct races.season, results.driver_id
    from {{ ref('fact_race_result') }} as results
    inner join {{ ref('dim_race') }} as races using (race_id)
    where results.is_shared_car
)

select single_pair.*, summary.races_together as summary_races,
    summary.points as summary_points, summary.teammate_points as summary_teammate_points
from single_pair
left join {{ ref('agg_teammate_season') }} as summary using (season, driver_id)
where not exists (
        select 1 from shared_car_drivers
        where shared_car_drivers.season = single_pair.season
            and shared_car_drivers.driver_id in (single_pair.driver_id, single_pair.teammate_id)
    )
    and (
        summary.driver_id is null
        or summary.races_together <> single_pair.races_together
        or abs(summary.points - single_pair.points) > 0.005
        or abs(summary.teammate_points - single_pair.teammate_points) > 0.005
    )
