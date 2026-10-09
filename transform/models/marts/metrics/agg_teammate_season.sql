{#- Resumen de la temporada frente al compañero (decisiones 45 y 46): una fila por piloto y
    temporada.

    Los puntos salen de agg_teammate_race: los del piloto, una sola vez por carrera (una fila
    por carrera y equipo, así que no se duplican aunque tuviera varios compañeros), frente a
    los del mejor compañero de cada carrera, sumados carrera a carrera. Solo entran las
    carreras en que tuvo algún compañero.

    El duelo de posiciones es la suma de los duelos por pareja de agg_teammate_h2h: con dos
    compañeros, una carrera cuenta una vez por cada uno. En carrera solo se comparan las
    carreras en que los dos terminan clasificados (decisión 46). -#}
with points as (
    select
        season,
        driver_id,
        count(distinct race_id) as races_together,
        round(sum(points), 2) as points,
        round(sum(teammate_points), 2) as teammate_points
    from {{ ref('agg_teammate_race') }}
    group by all
),

duels as (
    -- Las sumas de enteros de DuckDB son HUGEINT, que gold no admite (assert_gold_without_hugeint).
    select
        season,
        driver_id,
        sum(races_both_classified)::bigint as races_both_classified,
        sum(race_ahead)::bigint as race_ahead,
        sum(qualifyings_together)::bigint as qualifyings_together,
        sum(quali_ahead)::bigint as quali_ahead
    from {{ ref('agg_teammate_h2h') }}
    group by all
)

select
    points.season,
    points.driver_id,
    points.races_together,
    points.points,
    points.teammate_points,
    round(points.points - points.teammate_points, 2) as points_difference,
    coalesce(duels.races_both_classified, 0) as races_both_classified,
    coalesce(duels.race_ahead, 0) as race_ahead,
    round(100.0 * duels.race_ahead / nullif(duels.races_both_classified, 0), 1)
        as race_ahead_pct,
    coalesce(duels.qualifyings_together, 0) as qualifyings_together,
    coalesce(duels.quali_ahead, 0) as quali_ahead,
    round(100.0 * duels.quali_ahead / nullif(duels.qualifyings_together, 0), 1)
        as quali_ahead_pct
from points
left join duels using (season, driver_id)
