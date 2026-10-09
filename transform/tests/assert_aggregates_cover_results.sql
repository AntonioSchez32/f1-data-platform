{#- Cobertura de los agregados (DAT-05): todo par (temporada, piloto) con alguna inscripción en
    carrera tiene fila en agg_driver_season, y los años primero y último de pilotos y
    constructores coinciden con los de sus resultados (decisión 36). Con este test, la pérdida
    de las temporadas sin puntos (DAT-01 a DAT-03) habría fallado. -#}
with results as (
    select races.season, results.driver_id, results.constructor_id
    from {{ ref('fact_race_result') }} as results
    inner join {{ ref('dim_race') }} as races using (race_id)
    where results.session_type = 'RACE'
),

missing_seasons as (
    select distinct 'agg_driver_season' as model, driver_id as entity_id, season
    from results
    where not exists (
        select 1 from {{ ref('agg_driver_season') }} as agg
        where agg.season = results.season and agg.driver_id = results.driver_id
    )
),

driver_years as (
    select driver_id, min(season) as first_season, max(season) as last_season
    from results
    group by driver_id
),

constructor_years as (
    select constructor_id, min(season) as first_season, max(season) as last_season
    from results
    group by constructor_id
),

wrong_driver_years as (
    select 'agg_driver_career', career.driver_id, career.first_season
    from {{ ref('agg_driver_career') }} as career
    left join driver_years using (driver_id)
    where career.first_season is distinct from driver_years.first_season
        or career.last_season is distinct from driver_years.last_season
),

wrong_constructor_years as (
    select 'agg_constructor_career', career.constructor_id, career.first_season
    from {{ ref('agg_constructor_career') }} as career
    left join constructor_years using (constructor_id)
    where career.first_season is distinct from constructor_years.first_season
        or career.last_season is distinct from constructor_years.last_season
)

select * from missing_seasons
union all
select * from wrong_driver_years
union all
select * from wrong_constructor_years
