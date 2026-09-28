{#- Resumen por piloto y temporada: posición final, puntos y resultados (página «Temporadas»). -#}
with results as (
    select results.*, races.season
    from {{ ref('fact_race_result') }} as results
    inner join {{ ref('dim_race') }} as races using (race_id)
    where results.session_type = 'RACE'
),

season_results as (
    select
        season,
        driver_id,
        count(distinct race_id) as races,
        count(distinct race_id) filter (where is_win) as wins,
        count(distinct race_id) filter (where is_podium) as podiums,
        count(distinct race_id) filter (where is_pole_position) as pole_positions,
        count(distinct race_id) filter (where is_fastest_lap) as fastest_laps,
        min(position_number) as best_result,
        -- Equipo principal de la temporada (con el que más carreras disputó).
        mode(constructor_id) as constructor_id
    from results
    group by season, driver_id
)

select
    standings.season,
    standings.driver_id,
    drivers.name as driver_name,
    season_results.constructor_id,
    constructors.name as constructor_name,
    standings.position_number as championship_position,
    standings.position_text as championship_position_text,
    standings.points,
    standings.championship_won,
    coalesce(season_results.races, 0) as races,
    coalesce(season_results.wins, 0) as wins,
    coalesce(season_results.podiums, 0) as podiums,
    coalesce(season_results.pole_positions, 0) as pole_positions,
    coalesce(season_results.fastest_laps, 0) as fastest_laps,
    season_results.best_result
from {{ ref('stg_f1db__season_driver_standings') }} as standings
inner join {{ ref('dim_driver') }} as drivers using (driver_id)
left join season_results using (season, driver_id)
left join {{ ref('dim_constructor') }} as constructors using (constructor_id)
