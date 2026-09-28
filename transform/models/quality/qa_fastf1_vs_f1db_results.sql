{#- Contraste de resultados de carrera FastF1 frente a F1DB. Solo se comparan valores con la
    misma semántica: posición de los clasificados (FastF1 numera también a los retirados, F1DB
    usa DNF/DSQ...) y parrilla salvo salidas desde el pit lane (F1DB la deja vacía). -#}
with fastf1 as (
    select races.race_id, results.*
    from {{ ref('stg_fastf1__results') }} as results
    inner join {{ ref('stg_f1db__races') }} as races using (season, round)
),

f1db as (
    select * from {{ ref('fact_race_result') }} where session_type = 'RACE'
)

select
    fastf1.race_id,
    fastf1.driver_number,
    f1db.driver_id,
    fastf1.position as fastf1_position,
    f1db.position_text as f1db_position,
    fastf1.points as fastf1_points,
    f1db.points as f1db_points,
    fastf1.grid_position as fastf1_grid,
    f1db.grid_position as f1db_grid,
    f1db.driver_id is not null as is_matched,
    case when f1db.position_number is not null then fastf1.position = f1db.position_number end
        as is_position_match,
    fastf1.points = f1db.points as is_points_match,
    case
        when f1db.grid_position is not null and fastf1.grid_position > 0
            then fastf1.grid_position = f1db.grid_position
    end as is_grid_match
from fastf1
left join f1db
    on fastf1.race_id = f1db.race_id
    and fastf1.driver_number = f1db.driver_number
