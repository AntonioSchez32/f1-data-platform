{#- Duelo entre compañeros de equipo por temporada: % de veces por delante en carrera y en
    clasificación, y puntos frente al compañero (medidas del TFG, Listado 5.9). -#}
with race_results as (
    select results.race_id, races.season, results.constructor_id, results.driver_id,
        results.position_display_order, results.points
    from {{ ref('fact_race_result') }} as results
    inner join {{ ref('dim_race') }} as races using (race_id)
    where results.session_type = 'RACE' and not results.is_shared_car
),

quali_results as (
    select race_id, constructor_id, driver_id, position_display_order
    from {{ ref('fact_qualifying_result') }}
    where session_type = 'QUALIFYING'
),

race_pairs as (
    select
        a.season,
        a.constructor_id,
        a.driver_id,
        b.driver_id as teammate_id,
        count(*) as races_together,
        count(*) filter (where a.position_display_order < b.position_display_order) as race_ahead,
        sum(a.points) as points,
        sum(b.points) as teammate_points
    from race_results as a
    inner join race_results as b
        on a.race_id = b.race_id
        and a.constructor_id = b.constructor_id
        and a.driver_id <> b.driver_id
    group by all
),

quali_pairs as (
    select
        races.season,
        a.constructor_id,
        a.driver_id,
        b.driver_id as teammate_id,
        count(*) as qualifyings_together,
        count(*) filter (where a.position_display_order < b.position_display_order) as quali_ahead
    from quali_results as a
    inner join quali_results as b
        on a.race_id = b.race_id
        and a.constructor_id = b.constructor_id
        and a.driver_id <> b.driver_id
    inner join {{ ref('dim_race') }} as races on a.race_id = races.race_id
    group by all
)

select
    race_pairs.season,
    race_pairs.constructor_id,
    race_pairs.driver_id,
    race_pairs.teammate_id,
    race_pairs.races_together,
    race_pairs.race_ahead,
    round(100.0 * race_pairs.race_ahead / race_pairs.races_together, 1) as race_ahead_pct,
    coalesce(quali_pairs.qualifyings_together, 0) as qualifyings_together,
    coalesce(quali_pairs.quali_ahead, 0) as quali_ahead,
    round(100.0 * quali_pairs.quali_ahead / nullif(quali_pairs.qualifyings_together, 0), 1)
        as quali_ahead_pct,
    race_pairs.points,
    race_pairs.teammate_points,
    race_pairs.points - race_pairs.teammate_points as points_difference
from race_pairs
left join quali_pairs using (season, constructor_id, driver_id, teammate_id)
