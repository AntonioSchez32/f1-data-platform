{#- Contraste vuelta a vuelta entre OpenF1 y FastF1 en las carreras que tienen las dos (2023+).
    Mide la fiabilidad de OpenF1 como respaldo: cobertura, tiempo, posición al acabar la vuelta
    (as-of del endpoint position), neumático, entradas a boxes y estado de pista derivado de la
    dirección de carrera. Las dos leen el mismo feed: discrepar indica un error de procesado de
    una de ellas, no una medida independiente.

    Una fila por vuelta de cualquiera de las dos fuentes (`is_in_openf1`, `is_in_fastf1`). La
    vuelta 1 se excluye del tiempo, como en qa_formula1db_vs_fastf1_laps. `is_reliable_race`
    (int_openf1_race_reliability) separa las carreras con un defecto de OpenF1: los controles con
    umbral solo miden las fiables. -#}
with openf1 as (
    select * from {{ ref('int_openf1_laps') }}
    where race_id in (select race_id from {{ ref('int_fastf1_laps') }})
),

fastf1 as (
    select * from {{ ref('int_fastf1_laps') }}
    where race_id in (select race_id from {{ ref('int_openf1_laps') }})
),

comparable_compounds as (
    select unnest(['SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET']) as compound
)

select
    coalesce(openf1.race_id, fastf1.race_id) as race_id,
    coalesce(openf1.driver_number, fastf1.driver_number) as driver_number,
    coalesce(openf1.lap_number, fastf1.lap_number) as lap_number,
    coalesce(reliability.is_reliable, true) as is_reliable_race,
    openf1.lap_number is not null as is_in_openf1,
    fastf1.lap_number is not null as is_in_fastf1,
    openf1.lap_time_ms as openf1_lap_time_ms,
    fastf1.lap_time_ms as fastf1_lap_time_ms,
    openf1.position as openf1_position,
    fastf1.position as fastf1_position,
    openf1.position_status,
    case
        when coalesce(openf1.lap_number, fastf1.lap_number) = 1
            or openf1.lap_time_ms is null
            or fastf1.lap_time_ms is null
            then null
        else abs(openf1.lap_time_ms - fastf1.lap_time_ms) <= 1
    end as is_time_match,
    case
        when openf1.position is not null and fastf1.position is not null
            then openf1.position = fastf1.position
    end as is_position_match,
    case
        when openf1.tyre_compound in (select compound from comparable_compounds)
            and fastf1.tyre_compound in (select compound from comparable_compounds)
            then openf1.tyre_compound = fastf1.tyre_compound
    end as is_compound_match,
    case
        when openf1.stint is not null and fastf1.stint is not null
            then openf1.stint = fastf1.stint
    end as is_stint_match,
    case
        when openf1.tyre_age_laps is not null and fastf1.tyre_age_laps is not null
            then openf1.tyre_age_laps = fastf1.tyre_age_laps
    end as is_tyre_age_match,
    case
        when openf1.lap_number is not null and fastf1.lap_number is not null
            then openf1.is_pit_in_lap = fastf1.is_pit_in_lap
    end as is_pit_in_match,
    case
        when openf1.lap_number is not null and fastf1.lap_number is not null
            then openf1.is_safety_car = fastf1.is_safety_car
    end as is_safety_car_match,
    case
        when openf1.lap_number is not null and fastf1.lap_number is not null
            then openf1.is_virtual_safety_car = fastf1.is_virtual_safety_car
    end as is_virtual_safety_car_match,
    case
        when openf1.lap_number is not null and fastf1.lap_number is not null
            then openf1.is_red_flag = fastf1.is_red_flag
    end as is_red_flag_match
from openf1
full outer join fastf1 using (race_id, driver_number, lap_number)
left join {{ ref('int_openf1_race_reliability') }} as reliability
    on reliability.race_id = coalesce(openf1.race_id, fastf1.race_id)
