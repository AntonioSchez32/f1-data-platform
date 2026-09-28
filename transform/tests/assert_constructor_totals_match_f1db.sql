{#- Paridad de las métricas de constructores con los totales oficiales de F1DB. -#}
with official as (
    select * from {{ ref('stg_f1db__official_totals') }} where entity_type = 'constructor'
)

select
    career.constructor_id,
    career.championships, official.championships as official_championships,
    career.race_entries, official.race_entries as official_race_entries,
    career.wins, official.wins as official_wins,
    career.podiums, official.podiums as official_podiums,
    career.pole_positions, official.pole_positions as official_pole_positions,
    career.fastest_laps, official.fastest_laps as official_fastest_laps
from {{ ref('agg_constructor_career') }} as career
inner join official on career.constructor_id = official.entity_id
where career.championships <> official.championships
    or career.race_entries <> official.race_entries
    or career.wins <> official.wins
    or career.podiums <> official.podiums
    or career.pole_positions <> official.pole_positions
    or career.fastest_laps <> official.fastest_laps
