{#- Récords por constructor (medidas de constructores del TFG, Fig. 5.17), con los mismos
    criterios que F1DB: victorias por carrera, podios por coche (un coche compartido por
    varios pilotos cuenta una vez) y vueltas rápidas por piloto acreditado (en los años 50
    varios pilotos podían compartir la vuelta rápida).

    Los años primero y último salen solo de los resultados (cualquier inscripción en carrera,
    decisión 36): el campeonato de constructores empieza en 1958 y la clasificación daba a
    Ferrari desde 1958 y a Tyrrell hasta 1997 (DAT-03).

    Puntos (decisión 37), definición única que usa también la API:
    - points: la de F1DB (constructor.total_points), carrera más sprint de las temporadas desde
      1958; nulo si el constructor no corrió desde 1958, porque antes no había campeonato de
      constructores (Ferrari 11 409).
    - points_historical: lo mismo desde 1950 (Ferrari 12 001,77). Atribuye al chasis los puntos
      de los coches privados de los años 50.
    Ninguna aplica los descartes de la época ni la regla de 1958-1978 de que solo puntuaba el
    mejor coche de cada equipo. race_points (solo carrera, desde 1950) queda por compatibilidad. -#}
with results as (
    select results.*, races.season
    from {{ ref('fact_race_result') }} as results
    inner join {{ ref('dim_race') }} as races using (race_id)
),

races as (
    select * from results where session_type = 'RACE'
),

per_race as (
    select
        constructor_id,
        race_id,
        bool_or(is_win) as won,
        bool_or(is_podium) as podium,
        count(*) filter (where position_number in (1, 2)) = 2 as one_two,
        bool_or(is_pole_position) as pole,
        bool_or(is_fastest_lap) as fastest_lap,
        round(sum(points), 2) as points
    from races
    group by constructor_id, race_id
),

race_stats as (
    select
        constructor_id,
        count(*) as race_entries,
        count(*) filter (where won) as wins,
        count(*) filter (where podium) as podium_races,
        count(*) filter (where one_two) as one_two_finishes,
        count(*) filter (where pole) as pole_positions,
        round(sum(points), 2) as race_points
    from per_race
    group by constructor_id
),

car_stats as (
    select
        constructor_id,
        min(season) as first_season,
        max(season) as last_season,
        count(distinct (race_id, position_number)) filter (where is_podium) as podiums,
        count(*) filter (where is_fastest_lap) as fastest_laps
    from races
    group by constructor_id
),

-- Carrera y sprint. sum() de un filtro sin filas es nulo: el constructor que solo corrió
-- antes de 1958 se queda sin `points`.
points as (
    select
        constructor_id,
        round(sum(points) filter (where season >= 1958), 2) as points,
        round(sum(points), 2) as points_historical
    from results
    group by constructor_id
),

championships as (
    select
        constructor_id,
        count(distinct season) filter (where championship_won) as championships,
        min(position_number) as best_championship_position
    from {{ ref('stg_f1db__season_constructor_standings') }}
    group by constructor_id
)

select
    constructors.constructor_id,
    constructors.name,
    constructors.country_constructor,
    constructors.alpha2_constructor,
    coalesce(championships.championships, 0) as championships,
    championships.best_championship_position,
    car_stats.first_season,
    car_stats.last_season,
    coalesce(race_stats.race_entries, 0) as race_entries,
    coalesce(race_stats.wins, 0) as wins,
    coalesce(car_stats.podiums, 0) as podiums,
    coalesce(race_stats.podium_races, 0) as podium_races,
    coalesce(race_stats.one_two_finishes, 0) as one_two_finishes,
    coalesce(race_stats.pole_positions, 0) as pole_positions,
    coalesce(car_stats.fastest_laps, 0) as fastest_laps,
    coalesce(race_stats.race_points, 0) as race_points,
    points.points,
    points.points_historical
from {{ ref('dim_constructor') }} as constructors
left join race_stats using (constructor_id)
left join car_stats using (constructor_id)
left join points using (constructor_id)
left join championships using (constructor_id)
