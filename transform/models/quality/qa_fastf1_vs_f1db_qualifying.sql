{#- Contraste de tiempos de clasificación (Q1, Q2, Q3) FastF1 frente a F1DB. -#}
with fastf1 as (
    select races.race_id, results.*
    from {{ ref('stg_fastf1__quali_results') }} as results
    inner join {{ ref('stg_f1db__races') }} as races using (season, round)
),

f1db as (
    select * from {{ ref('fact_qualifying_result') }} where session_type = 'QUALIFYING'
),

compared as (
    select
        fastf1.race_id,
        fastf1.driver_number,
        f1db.driver_id,
        session.name as session,
        session.fastf1_ms,
        session.f1db_ms
    from fastf1
    left join f1db
        on fastf1.race_id = f1db.race_id
        and fastf1.driver_number = f1db.driver_number
    cross join lateral (
        values
            ('Q1', fastf1.q1_ms, f1db.q1_ms),
            ('Q2', fastf1.q2_ms, f1db.q2_ms),
            ('Q3', fastf1.q3_ms, f1db.q3_ms)
    ) as session(name, fastf1_ms, f1db_ms)
)

select
    *,
    driver_id is not null as is_matched,
    case when fastf1_ms is not null and f1db_ms is not null then fastf1_ms = f1db_ms end
        as is_time_match
from compared
where fastf1_ms is not null or f1db_ms is not null
