{#- Récords por constructor (medidas de constructores del TFG, Fig. 5.17), con los mismos
    criterios que F1DB: victorias por carrera, podios por coche (un coche compartido por
    varios pilotos cuenta una vez) y vueltas rápidas por piloto acreditado (en los años 50
    varios pilotos podían compartir la vuelta rápida). -#}
with races as (
    select * from {{ ref('fact_race_result') }} where session_type = 'RACE'
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
        count(distinct (race_id, position_number)) filter (where is_podium) as podiums,
        count(*) filter (where is_fastest_lap) as fastest_laps
    from races
    group by constructor_id
),

championships as (
    select
        constructor_id,
        count(distinct season) filter (where championship_won) as championships,
        min(position_number) as best_championship_position,
        min(season) as first_season,
        max(season) as last_season
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
    coalesce(championships.first_season, race_first.first_season) as first_season,
    coalesce(championships.last_season, race_first.last_season) as last_season,
    coalesce(race_stats.race_entries, 0) as race_entries,
    coalesce(race_stats.wins, 0) as wins,
    coalesce(car_stats.podiums, 0) as podiums,
    coalesce(race_stats.podium_races, 0) as podium_races,
    coalesce(race_stats.one_two_finishes, 0) as one_two_finishes,
    coalesce(race_stats.pole_positions, 0) as pole_positions,
    coalesce(car_stats.fastest_laps, 0) as fastest_laps,
    coalesce(race_stats.race_points, 0) as race_points
from {{ ref('dim_constructor') }} as constructors
left join race_stats using (constructor_id)
left join car_stats using (constructor_id)
left join championships using (constructor_id)
left join (
    select constructor_id, min(season) as first_season, max(season) as last_season
    from races
    inner join {{ ref('dim_race') }} using (race_id)
    group by constructor_id
) as race_first using (constructor_id)
