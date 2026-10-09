{#- Paridad de las métricas de constructores con los totales oficiales de F1DB. Se parte de los
    totales oficiales (left join) para que también falle si un constructor desaparece del
    agregado, y se compara con «is distinct from» para no dejar pasar los nulos.
    `points` es nulo para quien solo corrió antes de 1958 (sin campeonato de constructores);
    F1DB da 0 en ese caso (decisión 37). -#}
with official as (
    select * from {{ ref('stg_f1db__official_totals') }} where entity_type = 'constructor'
)

select
    official.entity_id as constructor_id,
    career.championships, official.championships as official_championships,
    career.race_entries, official.race_entries as official_race_entries,
    career.wins, official.wins as official_wins,
    career.podiums, official.podiums as official_podiums,
    career.pole_positions, official.pole_positions as official_pole_positions,
    career.fastest_laps, official.fastest_laps as official_fastest_laps,
    career.points, official.points as official_points
from official
left join {{ ref('agg_constructor_career') }} as career
    on career.constructor_id = official.entity_id
where career.constructor_id is null
    or career.championships is distinct from official.championships
    or career.race_entries is distinct from official.race_entries
    or career.wins is distinct from official.wins
    or career.podiums is distinct from official.podiums
    or career.pole_positions is distinct from official.pole_positions
    or career.fastest_laps is distinct from official.fastest_laps
    or abs(coalesce(career.points, 0) - official.points) > 0.005
