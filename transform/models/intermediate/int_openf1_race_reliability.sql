{#- Fiabilidad de las vueltas de OpenF1 por carrera: concordancia de sus tiempos (±1 ms, sin la
    vuelta 1) con los de la fuente publicada en las vueltas comunes (FastF1 o, si la carrera no lo
    tiene, formula1db.com).

    Una carrera con menos de `openf1_min_race_time_agreement_pct` de concordancia es
    `is_reliable = false`: OpenF1 tiene un defecto en ella (Australia 2026: las vueltas van
    desplazadas una posición respecto a FastF1) y no se usa para contrastar en int_laptimes ni
    entra en los controles con umbral; se cuenta en qa_summary (openf1_reliable_races) y se
    anuncia en las notas de la release. Se mide la concordancia, no la cobertura: una carrera a
    la que le faltan vueltas (Miami 2025, sin las 1-24) es fiable en las que tiene. Las carreras
    sin vueltas comunes con otra fuente (las que solo tienen OpenF1) no se pueden medir: cuentan
    como fiables. -#}
with openf1 as (
    select * from {{ ref('int_openf1_laps') }}
),

fastf1_races as (
    select distinct race_id from {{ ref('int_fastf1_laps') }}
),

reference as (
    select race_id, driver_number, lap_number, lap_time_ms
    from {{ ref('int_fastf1_laps') }}
    union all
    select race_id, driver_number, lap_number, lap_time_ms
    from {{ ref('int_formula1db_laps') }}
    where race_id not in (select race_id from fastf1_races)
),

compared as (
    select
        openf1.race_id,
        count(*) as compared_laps,
        count(*) filter (where abs(openf1.lap_time_ms - reference.lap_time_ms) <= 1)
            as matched_laps
    from openf1
    inner join reference using (race_id, driver_number, lap_number)
    where openf1.lap_number > 1
        and openf1.lap_time_ms is not null
        and reference.lap_time_ms is not null
    group by openf1.race_id
)

select
    races.race_id,
    coalesce(compared.compared_laps, 0) as compared_laps,
    coalesce(compared.matched_laps, 0) as matched_laps,
    round(100.0 * compared.matched_laps / nullif(compared.compared_laps, 0), 2) as match_pct,
    coalesce(
        100.0 * compared.matched_laps / nullif(compared.compared_laps, 0)
        >= {{ var('openf1_min_race_time_agreement_pct') }},
        true
    ) as is_reliable
from (select distinct race_id from openf1) as races
left join compared using (race_id)
