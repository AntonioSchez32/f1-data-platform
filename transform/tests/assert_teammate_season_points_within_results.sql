{#- Los puntos del piloto en el resumen frente al compañero se cuentan una sola vez por
    carrera: nunca pueden superar la suma de sus puntos de carrera y sprint de la temporada
    (hasta C4a2 la web los sumaba una vez por compañero: Fangio 1955 con 106 en vez de 41). -#}
with season_points as (
    select races.season, results.driver_id, sum(results.points) as points
    from {{ ref('fact_race_result') }} as results
    inner join {{ ref('dim_race') }} as races using (race_id)
    group by all
)

select summary.season, summary.driver_id, summary.points, season_points.points as season_points
from {{ ref('agg_teammate_season') }} as summary
left join season_points using (season, driver_id)
where season_points.driver_id is null
    or summary.points > season_points.points + 0.005
