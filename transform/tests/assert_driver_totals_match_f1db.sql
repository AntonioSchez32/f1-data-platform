{#- Paridad: las métricas calculadas desde los hechos deben coincidir con los totales oficiales
    de F1DB. Se excluyen los pilotos afectados por las correcciones del seed. Se parte de los
    totales oficiales (left join) para que también falle si un piloto desaparece del agregado,
    y se compara con «is distinct from» para no dejar pasar los nulos. -#}
with corrected_drivers as (
    select driver_id from {{ ref('int_race_data_corrected') }} where is_corrected
    union
    select original_driver_id from {{ ref('int_race_data_corrected') }} where is_corrected
),

official as (
    select * from {{ ref('stg_f1db__official_totals') }} where entity_type = 'driver'
)

select
    official.entity_id as driver_id,
    career.championships, official.championships as official_championships,
    career.race_entries, official.race_entries as official_race_entries,
    career.race_starts, official.race_starts as official_race_starts,
    career.wins, official.wins as official_wins,
    career.podiums, official.podiums as official_podiums,
    career.pole_positions, official.pole_positions as official_pole_positions,
    career.fastest_laps, official.fastest_laps as official_fastest_laps,
    career.grand_slams, official.grand_slams as official_grand_slams,
    career.points, official.points as official_points
from official
left join {{ ref('agg_driver_career') }} as career on career.driver_id = official.entity_id
where official.entity_id not in (select driver_id from corrected_drivers)
    and (
        career.driver_id is null
        or career.championships is distinct from official.championships
        or career.race_entries is distinct from official.race_entries
        or career.race_starts is distinct from official.race_starts
        or career.wins is distinct from official.wins
        or career.podiums is distinct from official.podiums
        or career.pole_positions is distinct from official.pole_positions
        or career.fastest_laps is distinct from official.fastest_laps
        or career.grand_slams is distinct from official.grand_slams
        or career.points is null
        or abs(career.points - official.points) > 0.005
    )
