{#- Control de los tiempos de clasificación de F1DB frente a Jolpica (decisión 52), desde 1994:
    Q1, Q2 y Q3 (±1 ms) de los pilotos con tiempo en las dos fuentes, cruzados por carrera, piloto
    (int_jolpica_drivers) y dorsal. En los formatos antiguos Jolpica pone sus una o dos sesiones
    en Q1 y Q2, como F1DB. -#}
with jolpica as (
    select races.race_id, drivers.driver_id, qualifying.*
    from {{ ref('stg_jolpica__qualifying') }} as qualifying
    inner join {{ ref('stg_f1db__races') }} as races using (season, round)
    left join {{ ref('int_jolpica_drivers') }} as drivers using (driver_ref)
    where races.race_id in (select race_id from {{ ref('fact_qualifying_result') }})
),

f1db as (
    select * from {{ ref('fact_qualifying_result') }} where session_type = 'QUALIFYING'
)

select
    jolpica.race_id,
    jolpica.driver_ref,
    jolpica.driver_id,
    jolpica.driver_number,
    session.name as session,
    session.jolpica_ms,
    session.f1db_ms,
    f1db.race_id is not null as is_matched,
    case
        when session.jolpica_ms is not null and session.f1db_ms is not null
            then abs(session.jolpica_ms - session.f1db_ms) <= 1
    end as is_time_match
from jolpica
left join f1db
    on jolpica.race_id = f1db.race_id
    and jolpica.driver_id = f1db.driver_id
    and jolpica.driver_number = f1db.driver_number
cross join lateral (
    values
        ('Q1', jolpica.q1_ms, f1db.q1_ms),
        ('Q2', jolpica.q2_ms, f1db.q2_ms),
        ('Q3', jolpica.q3_ms, f1db.q3_ms)
) as session(name, jolpica_ms, f1db_ms)
