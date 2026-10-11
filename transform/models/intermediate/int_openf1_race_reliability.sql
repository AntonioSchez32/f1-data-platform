{#- Fiabilidad de las vueltas de OpenF1 por carrera: concordancia de sus tiempos (±1 ms, sin la
    vuelta 1) con los de la fuente de referencia en las vueltas comunes: FastF1, si la carrera no
    lo tiene formula1db.com y, si tampoco, Jolpica (DAT-06, decisión 50).

    Una carrera con menos de `openf1_min_race_time_agreement_pct` de concordancia es
    `is_reliable = false`: OpenF1 tiene un defecto en ella (Australia 2026: las vueltas van
    desplazadas una posición respecto a FastF1) y no se usa para contrastar en int_laptimes ni
    entra en los controles con umbral; se cuenta en qa_summary (openf1_reliable_races) y se
    anuncia en las notas de la release. Se mide la concordancia, no la cobertura: una carrera a
    la que le faltan vueltas (Miami 2025, sin las 1-24) es fiable en las que tiene. Las carreras
    sin vueltas comunes con ninguna fuente (solo OpenF1, sin Jolpica todavía) no se pueden medir:
    cuentan como fiables y el control openf1_unverified_races lo avisa.

    En las carreras sin formula1db ni FastF1 (las que medimos contra Jolpica), Jolpica sustituye
    a OpenF1 como base de la carrera (`is_replaced_by_jolpica`) si está completa (al menos
    `jolpica_min_lap_coverage_pct` de las vueltas oficiales de F1DB) y además OpenF1 no es fiable
    o le faltan vueltas (cubre menos de `openf1_min_lap_coverage_pct` de las de Jolpica) y Jolpica
    tiene más. Si Jolpica está incompleta, se queda OpenF1 aunque no sea fiable: es lo único que
    hay, y el aviso openf1_reliable_races lo anuncia. Prioridad en una carrera: formula1db /
    FastF1 > OpenF1 fiable > Jolpica. -#}
with openf1 as (
    select * from {{ ref('int_openf1_laps') }}
),

fastf1_races as (
    select distinct race_id from {{ ref('int_fastf1_laps') }}
),

formula1db_races as (
    select distinct race_id from {{ ref('int_formula1db_laps') }}
),

jolpica as (
    select * from {{ ref('int_jolpica_laps') }} where driver_id is not null
),

reference as (
    select race_id, driver_number, lap_number, lap_time_ms, 'fastf1' as reference_source
    from {{ ref('int_fastf1_laps') }}
    union all
    select race_id, driver_number, lap_number, lap_time_ms, 'formula1db'
    from {{ ref('int_formula1db_laps') }}
    where race_id not in (select race_id from fastf1_races)
    union all
    select race_id, driver_number, lap_number, lap_time_ms, 'jolpica'
    from jolpica
    where race_id not in (select race_id from fastf1_races)
        and race_id not in (select race_id from formula1db_races)
),

reference_races as (
    select distinct race_id, reference_source from reference
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
),

-- Cobertura frente a Jolpica (solo donde Jolpica es la referencia) y de Jolpica frente a las
-- vueltas oficiales de F1DB.
openf1_counts as (
    select race_id, count(*) as openf1_laps
    from openf1
    where driver_id is not null
    group by race_id
),

jolpica_counts as (
    select
        jolpica.race_id,
        count(*) as jolpica_laps,
        count(openf1.lap_number) as jolpica_laps_in_openf1
    from jolpica
    left join openf1
        on jolpica.race_id = openf1.race_id
        and jolpica.driver_number = openf1.driver_number
        and jolpica.lap_number = openf1.lap_number
        and openf1.driver_id is not null
    group by jolpica.race_id
),

official as (
    select race_id, coalesce(sum(race_laps), 0)::bigint as official_laps
    from {{ ref('int_race_data_corrected') }}
    where session_type = 'RACE_RESULT'
    group by race_id
),

measured as (
    select
        races.race_id,
        reference_races.reference_source,
        coalesce(compared.compared_laps, 0) as compared_laps,
        coalesce(compared.matched_laps, 0) as matched_laps,
        round(100.0 * compared.matched_laps / nullif(compared.compared_laps, 0), 2) as match_pct,
        coalesce(
            100.0 * compared.matched_laps / nullif(compared.compared_laps, 0)
            >= {{ var('openf1_min_race_time_agreement_pct') }},
            true
        ) as is_reliable,
        coalesce(openf1_counts.openf1_laps, 0) as openf1_laps,
        coalesce(jolpica_counts.jolpica_laps, 0) as jolpica_laps,
        coalesce(jolpica_counts.jolpica_laps_in_openf1, 0) as jolpica_laps_in_openf1,
        official.official_laps
    from (select distinct race_id from openf1) as races
    left join reference_races using (race_id)
    left join compared using (race_id)
    left join openf1_counts using (race_id)
    left join jolpica_counts using (race_id)
    left join official using (race_id)
),

flagged as (
    select
        *,
        reference_source = 'jolpica'
            and 100.0 * jolpica_laps_in_openf1 / nullif(jolpica_laps, 0)
            < {{ var('openf1_min_lap_coverage_pct') }} as is_missing_laps,
        reference_source = 'jolpica'
            and jolpica_laps >= {{ var('jolpica_min_lap_coverage_pct') }} / 100.0 * official_laps
            and official_laps > 0 as is_jolpica_complete
    from measured
)

select
    * replace (
        coalesce(is_missing_laps, false) as is_missing_laps,
        coalesce(is_jolpica_complete, false) as is_jolpica_complete
    ),
    coalesce(
        is_jolpica_complete
        and (not is_reliable or (is_missing_laps and jolpica_laps > openf1_laps)),
        false
    ) as is_replaced_by_jolpica
from flagged
