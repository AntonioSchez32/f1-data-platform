{#- Totales que F1DB publica precalculados. Solo se usan como referencia en los tests de
    paridad: las métricas del modelo se calculan desde los hechos, no desde aquí. -#}
select
    'driver' as entity_type,
    id as entity_id,
    total_championship_wins as championships,
    total_race_entries as race_entries,
    total_race_starts as race_starts,
    total_race_wins as wins,
    total_podiums as podiums,
    total_pole_positions as pole_positions,
    total_fastest_laps as fastest_laps,
    total_grand_slams as grand_slams
from {{ source('f1db', 'driver') }}

union all

select
    'constructor',
    id,
    total_championship_wins,
    total_race_entries,
    total_race_starts,
    total_race_wins,
    total_podiums,
    total_pole_positions,
    total_fastest_laps,
    null
from {{ source('f1db', 'constructor') }}
