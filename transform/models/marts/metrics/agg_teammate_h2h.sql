{#- Duelo entre compañeros de equipo por temporada: % de veces por delante en carrera y en
    clasificación, y puntos frente al compañero (medidas del TFG, Listado 5.9).

    Solo cuentan las carreras compartidas: las que los dos disputaron con el mismo equipo y
    sin coche compartido. Los puntos son los de la carrera más los del sprint de ese mismo fin
    de semana (puntúa para el campeonato desde 2021: DAT-04); el sprint de un fin de semana sin
    carrera compartida no cuenta. Por eso no cuadran con el campeonato si el compañero cambió
    durante la temporada.

    El duelo en carrera sigue la definición del TFG (decisión 46): solo compara las carreras en
    que los dos terminan clasificados (position_number no nulo), para quitar las averías y los
    accidentes ajenos al piloto. races_together son todas las compartidas (las de los puntos) y
    races_both_classified, las comparadas en el duelo. Los puntos de la temporada frente al
    mejor compañero de cada carrera están en agg_teammate_race y agg_teammate_season. -#}
with sprint_points as (
    -- Una fila por piloto, equipo y carrera, para no duplicar las filas de carrera al unirla.
    select race_id, constructor_id, driver_id, sum(points) as points
    from {{ ref('fact_race_result') }}
    where session_type = 'SPRINT'
    group by all
),

race_results as (
    select results.race_id, races.season, results.constructor_id, results.driver_id,
        results.position_display_order, results.position_number,
        coalesce(results.points, 0) + coalesce(sprint_points.points, 0) as points
    from {{ ref('fact_race_result') }} as results
    inner join {{ ref('dim_race') }} as races using (race_id)
    left join sprint_points using (race_id, constructor_id, driver_id)
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
        count(*) filter (where a.position_number is not null and b.position_number is not null)
            as races_both_classified,
        -- Entre clasificados el orden de position_display_order es el de position_number.
        count(*) filter (
            where a.position_number is not null and b.position_number is not null
                and a.position_display_order < b.position_display_order
        ) as race_ahead,
        round(sum(a.points), 2) as points,
        round(sum(b.points), 2) as teammate_points
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
    race_pairs.races_both_classified,
    race_pairs.race_ahead,
    round(100.0 * race_pairs.race_ahead / nullif(race_pairs.races_both_classified, 0), 1)
        as race_ahead_pct,
    coalesce(quali_pairs.qualifyings_together, 0) as qualifyings_together,
    coalesce(quali_pairs.quali_ahead, 0) as quali_ahead,
    round(100.0 * quali_pairs.quali_ahead / nullif(quali_pairs.qualifyings_together, 0), 1)
        as quali_ahead_pct,
    race_pairs.points,
    race_pairs.teammate_points,
    round(race_pairs.points - race_pairs.teammate_points, 2) as points_difference
from race_pairs
left join quali_pairs using (season, constructor_id, driver_id, teammate_id)
