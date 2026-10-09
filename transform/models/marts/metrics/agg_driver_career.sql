{#- Récords de carrera deportiva por piloto (medidas DAX del TFG, sección 5.3.3).

    Los años de la carrera deportiva salen de los resultados (cualquier inscripción en carrera,
    decisión 36) y no de la clasificación final de F1DB, que omite a quien no puntuó (DAT-02:
    Senna acababa en 1993 y Lauda empezaba en 1973). -#}
with races as (
    select results.*, calendar.season
    from {{ ref('fact_race_result') }} as results
    inner join {{ ref('dim_race') }} as calendar using (race_id)
    where results.session_type = 'RACE'
),

sprints as (
    select * from {{ ref('fact_race_result') }} where session_type = 'SPRINT'
),

race_stats as (
    select
        driver_id,
        min(season) as first_season,
        max(season) as last_season,
        min(season) filter (where position_text not in ('DNQ', 'DNPQ', 'DNP', 'EX', 'DNS'))
            as first_start_season,
        max(season) filter (where position_text not in ('DNQ', 'DNPQ', 'DNP', 'EX', 'DNS'))
            as last_start_season,
        count(distinct race_id) as race_entries,
        count(distinct race_id) filter (
            where position_text not in ('DNQ', 'DNPQ', 'DNP', 'EX', 'DNS')
        ) as race_starts,
        count(distinct race_id) filter (where is_win) as wins,
        count(distinct race_id) filter (where is_podium) as podiums,
        count(distinct race_id) filter (where is_pole_position) as pole_positions,
        count(distinct race_id) filter (where is_fastest_lap) as fastest_laps,
        count(distinct race_id) filter (where is_grand_slam) as grand_slams,
        count(distinct race_id) filter (where is_driver_of_the_day) as driver_of_the_day,
        round(sum(points), 2) as race_points,
        min(position_number) as best_race_result,
        sum(laps)::bigint as laps_completed
    from races
    group by driver_id
),

sprint_stats as (
    select
        driver_id,
        count(distinct race_id) filter (where is_win) as sprint_wins,
        round(sum(points), 2) as sprint_points
    from sprints
    group by driver_id
),

championships as (
    select
        driver_id,
        count(*) filter (where championship_won) as championships,
        min(position_number) as best_championship_position,
        round(sum(points), 2) as championship_points
    from {{ ref('stg_f1db__season_driver_standings') }}
    group by driver_id
)

select
    drivers.driver_id,
    drivers.name,
    drivers.nationality_country,
    drivers.nationality_alpha2,
    coalesce(championships.championships, 0) as championships,
    championships.best_championship_position,
    race_stats.first_season,
    race_stats.last_season,
    race_stats.first_start_season,
    race_stats.last_start_season,
    coalesce(race_stats.race_entries, 0) as race_entries,
    coalesce(race_stats.race_starts, 0) as race_starts,
    coalesce(race_stats.wins, 0) as wins,
    coalesce(race_stats.podiums, 0) as podiums,
    coalesce(race_stats.pole_positions, 0) as pole_positions,
    coalesce(race_stats.fastest_laps, 0) as fastest_laps,
    coalesce(race_stats.grand_slams, 0) as grand_slams,
    coalesce(race_stats.driver_of_the_day, 0) as driver_of_the_day,
    coalesce(sprint_stats.sprint_wins, 0) as sprint_wins,
    round(coalesce(race_stats.race_points, 0) + coalesce(sprint_stats.sprint_points, 0), 2) as points,
    coalesce(championships.championship_points, 0) as championship_points,
    race_stats.best_race_result,
    coalesce(race_stats.laps_completed, 0) as laps_completed,
    round(100.0 * race_stats.wins / nullif(race_stats.race_starts, 0), 2) as win_rate_pct,
    round(100.0 * race_stats.podiums / nullif(race_stats.race_starts, 0), 2) as podium_rate_pct
from {{ ref('dim_driver') }} as drivers
left join race_stats using (driver_id)
left join sprint_stats using (driver_id)
left join championships using (driver_id)
