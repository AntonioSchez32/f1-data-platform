{#- Vueltas de Ergast (1996-2022) con la carrera de F1DB. Solo se usan para validar y, marcadas,
    para rellenar huecos puntuales de formula1db.com (decisión N8). -#}
select races.race_id, laps.driver_number, laps.lap_number, laps.position, laps.lap_time_ms
from {{ ref('stg_ergast__lap_times') }} as laps
inner join {{ ref('stg_f1db__races') }} as races using (season, round)
