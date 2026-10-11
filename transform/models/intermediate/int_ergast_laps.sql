{#- Vueltas de Ergast (1996-2022) con la carrera de F1DB. Desde D2 no entran en la fusión de
    vueltas (las sustituye Jolpica, decisión 49): solo alimentan el control informativo
    qa_jolpica_vs_ergast_laps (decisión 53). -#}
select races.race_id, laps.driver_number, laps.lap_number, laps.position, laps.lap_time_ms
from {{ ref('stg_ergast__lap_times') }} as laps
inner join {{ ref('stg_f1db__races') }} as races using (season, round)
