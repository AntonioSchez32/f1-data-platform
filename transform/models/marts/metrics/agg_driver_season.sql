{#- Resumen por piloto y temporada: posición final, puntos y resultados (página «Temporadas»).

    Una temporada existe si el piloto tiene cualquier inscripción en carrera, aunque no se
    clasificara o no tomara la salida (DNQ, DNPQ, DNP, EX: decisión 36). Se parte de los
    resultados y no de la clasificación final de F1DB, que hasta los años 2000 solo incluye a
    quien puntuó (DAT-01): Senna 1994 o los 16 pilotos de 1985 sin puntos se perdían. -#}
with results as (
    select results.*, races.season, races.round
    from {{ ref('fact_race_result') }} as results
    inner join {{ ref('dim_race') }} as races using (race_id)
    where results.session_type = 'RACE'
),

-- Equipo principal de la temporada: con el que más carreras disputó y, a igualdad, con el que
-- corrió más tarde (mode() no desempataba: Flockhart 1956 salía BRM o Connaught según la ejecución).
teams as (
    select
        season,
        driver_id,
        arg_max(constructor_id, (races, last_round, constructor_id)) as constructor_id
    from (
        select season, driver_id, constructor_id, count(distinct race_id) as races,
            max(round) as last_round
        from results
        group by all
    )
    group by all
),

season_results as (
    select
        season,
        driver_id,
        count(distinct race_id) as race_entries,
        -- Misma definición de salida que agg_driver_career (cuadra con F1DB).
        count(distinct race_id) filter (
            where position_text not in ('DNQ', 'DNPQ', 'DNP', 'EX', 'DNS')
        ) as race_starts,
        count(distinct race_id) filter (where is_win) as wins,
        count(distinct race_id) filter (where is_podium) as podiums,
        count(distinct race_id) filter (where is_pole_position) as pole_positions,
        count(distinct race_id) filter (where is_fastest_lap) as fastest_laps,
        min(position_number) as best_result
    from results
    group by season, driver_id
)

select
    season_results.season,
    season_results.driver_id,
    drivers.name as driver_name,
    teams.constructor_id,
    constructors.name as constructor_name,
    -- La clasificación se une con left join: sin fila, el piloto no puntuó (posición nula).
    standings.position_number as championship_position,
    standings.position_text as championship_position_text,
    coalesce(standings.points, 0) as points,
    coalesce(standings.championship_won, false) as championship_won,
    -- races se conserva por compatibilidad con la API: son las inscripciones (= race_entries).
    season_results.race_entries as races,
    season_results.race_entries,
    season_results.race_starts,
    season_results.wins,
    season_results.podiums,
    season_results.pole_positions,
    season_results.fastest_laps,
    season_results.best_result
from season_results
inner join {{ ref('dim_driver') }} as drivers using (driver_id)
left join {{ ref('stg_f1db__season_driver_standings') }} as standings using (season, driver_id)
left join teams using (season, driver_id)
left join {{ ref('dim_constructor') }} as constructors using (constructor_id)
