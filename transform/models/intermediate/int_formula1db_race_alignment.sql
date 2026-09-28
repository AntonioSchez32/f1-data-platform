{#-
    Asigna cada carrera de formula1db.com a la carrera de F1DB por su CONTENIDO y no por la ronda
    con la que se etiquetó al hacer el scraping (el script de actualización fijaba `round_race` a
    mano; desde 2023-R7 los datos quedaron desplazados una ronda).

    Firma de una carrera: vueltas completadas por cada dorsal. Se compara con los resultados
    oficiales de todas las carreras de la misma temporada y se elige la de mayor coincidencia;
    en caso de empate se conserva la ronda etiquetada.
-#}
with legacy_driver_laps as (
    select season, round, driver_number, max(lap_number) as laps
    from {{ ref('stg_formula1db__lap_times') }}
    where driver_number <> ''
    group by all
),

legacy_races as (
    select
        season,
        round,
        count(distinct driver_number) filter (where driver_number <> '') as legacy_drivers
    from {{ ref('stg_formula1db__lap_times') }}
    group by all
),

official as (
    select races.season, races.round, races.race_id, results.driver_number, results.race_laps
    from {{ ref('int_race_data_corrected') }} as results
    inner join {{ ref('stg_f1db__races') }} as races using (race_id)
    where results.session_type = 'RACE_RESULT'
),

scores as (
    select
        legacy.season,
        legacy.round as labelled_round,
        official.round as candidate_round,
        official.race_id,
        count(*) filter (where legacy.laps = official.race_laps) as matching_drivers
    from legacy_driver_laps as legacy
    inner join official
        on legacy.season = official.season
        and legacy.driver_number = official.driver_number
    group by all
),

best as (
    select *
    from scores
    qualify row_number() over (
        partition by season, labelled_round
        order by matching_drivers desc, (candidate_round = labelled_round) desc
    ) = 1
),

labelled as (
    select season, round, race_id from {{ ref('stg_f1db__races') }}
)

select
    legacy_races.season,
    legacy_races.round as labelled_round,
    coalesce(best.race_id, labelled.race_id) as race_id,
    coalesce(best.candidate_round, legacy_races.round) as aligned_round,
    coalesce(best.candidate_round, legacy_races.round) <> legacy_races.round as is_realigned,
    legacy_races.legacy_drivers,
    coalesce(best.matching_drivers, 0) as matching_drivers,
    round(100.0 * coalesce(best.matching_drivers, 0) / nullif(legacy_races.legacy_drivers, 0), 1)
        as match_pct
from legacy_races
left join best
    on legacy_races.season = best.season
    and legacy_races.round = best.labelled_round
left join labelled
    on legacy_races.season = labelled.season
    and legacy_races.round = labelled.round
