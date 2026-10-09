{#- Desde 1991 todos los puntos de carrera (y sprint) cuentan para el campeonato: la suma de
    puntos de los resultados debe coincidir con la clasificación final de la temporada. Es un
    error, no un aviso, desde C4 (DAT-05): hoy da 0 filas. -#}
with results as (
    select races.season, results.driver_id, sum(results.points) as points
    from {{ ref('fact_race_result') }} as results
    inner join {{ ref('dim_race') }} as races using (race_id)
    where races.season >= 1991
    group by all
)

select results.season, results.driver_id, results.points, standings.points as standings_points
from results
inner join {{ ref('stg_f1db__season_driver_standings') }} as standings using (season, driver_id)
where abs(results.points - standings.points) > 0.01
