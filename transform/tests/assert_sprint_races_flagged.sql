{#- Toda carrera con resultado de sprint tiene has_sprint (F1DB solo da la fecha desde 2024). -#}
select distinct results.race_id
from {{ ref('fact_race_result') }} as results
inner join {{ ref('dim_race') }} as races using (race_id)
where results.session_type = 'SPRINT'
    and not races.has_sprint
