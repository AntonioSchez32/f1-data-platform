{#- Vueltas de formula1db.com (scraping del TFG) con las claves de F1DB. La carrera se toma de la
    realineación por contenido (int_formula1db_race_alignment), no de la ronda etiquetada. -#}
with legacy_laps as (
    select alignment.race_id, laps.*
    from {{ ref('stg_formula1db__lap_times') }} as laps
    inner join {{ ref('int_formula1db_race_alignment') }} as alignment
        on laps.season = alignment.season
        and laps.round = alignment.labelled_round
),

numbers as (
    select
        *,
        count(distinct driver_id) over (partition by race_id, normalized_last_name)
            as drivers_with_last_name
    from {{ ref('int_driver_race_numbers') }}
),

-- El piloto se resuelve una vez por (carrera, dorsal, nombre) y no vuelta a vuelta, con nombres
-- normalizados (formula1db escribe «Giuseppe Farina» donde F1DB dice «Nino Farina»). En los coches
-- compartidos de los años 50 el dorsal es del coche, así que el nombre pesa más que el dorsal.
-- Preferencia: 1 dorsal y nombre, 2 dorsal y apellido, 3 nombre, 4 apellido único en la carrera,
-- 5 solo dorsal.
legacy_drivers as (
    select distinct
        race_id,
        driver_number,
        driver_name,
        {{ normalize_name('driver_name') }} as normalized_name
    from legacy_laps
),

candidates as (
    select
        legacy_drivers.race_id,
        legacy_drivers.driver_number,
        legacy_drivers.driver_name,
        numbers.driver_id,
        legacy_drivers.normalized_name = numbers.normalized_name as is_name_match,
        ends_with(' ' || legacy_drivers.normalized_name, ' ' || numbers.normalized_last_name)
            as is_last_name_match,
        legacy_drivers.driver_number = numbers.driver_number as is_number_match,
        numbers.drivers_with_last_name
    from legacy_drivers
    inner join numbers
        on legacy_drivers.race_id = numbers.race_id
        and (
            legacy_drivers.driver_number = numbers.driver_number
            or legacy_drivers.normalized_name = numbers.normalized_name
            or ends_with(' ' || legacy_drivers.normalized_name, ' ' || numbers.normalized_last_name)
        )
),

ranked as (
    select
        *,
        case
            when is_number_match and is_name_match then 1
            when is_number_match and is_last_name_match then 2
            when is_name_match then 3
            when is_last_name_match and drivers_with_last_name = 1 then 4
            when is_number_match then 5
        end as match_level
    from candidates
),

legacy_driver_match as (
    select race_id, driver_number, driver_name, driver_id, match_level
    from ranked
    where match_level is not null
    qualify row_number() over (
        partition by race_id, driver_number, driver_name
        order by match_level, driver_id
    ) = 1
)

select
    race_id,
    driver_id,
    driver_number,
    driver_name as source_driver_name,
    match_level as driver_match_level,
    lap_number,
    position,
    lap_time_ms,
    race_time_ms,
    gap_to_leader_ms,
    sector_1_ms,
    sector_2_ms,
    sector_3_ms,
    null::integer as stint,
    tyre_compound,
    tyre_age_laps,
    is_pit_in_lap,
    is_pit_out_lap,
    is_yellow_flag,
    is_safety_car,
    is_virtual_safety_car,
    is_red_flag,
    is_deleted,
    'formula1db' as source
from legacy_laps
left join legacy_driver_match using (race_id, driver_number, driver_name)
