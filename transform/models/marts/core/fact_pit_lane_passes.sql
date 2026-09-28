{#-
    Todas las entradas al pit lane registradas en las vueltas (decisión N4). La FIA y las fuentes
    de vueltas cuentan cualquier entrada; F1DB (fact_pit_stops) solo las paradas reales. Cada paso
    se tipifica:
      pit_stop          coincide con una parada de F1DB
      red_flag          entrada con bandera roja
      retirement        el piloto no terminó y entra en su última vuelta
      safety_car        paso bajo Safety Car o VSC sin parada registrada en F1DB
      penalty_or_other  resto (drive-through, stop-and-go, entradas sin parar...)
      unclassified      carrera sin paradas en F1DB (antes de 1994): no se puede tipificar
-#}
with laps as (
    select * from {{ ref('int_laptimes') }} where is_pit_in_lap and driver_id is not null
),

-- En carreras con numeración inconsistente o con otra convención de vuelta de parada, las
-- paradas de F1DB van desfasadas respecto a las vueltas (int_lap_numbering).
pit_offsets as (
    select
        race_id,
        case
            when numbering_status in ('inconsistent', 'pit_lap_convention')
                then coalesce(pit_stop_offset, 0)
            else 0
        end as pit_stop_offset
    from {{ ref('int_lap_numbering') }}
),

stops as (
    select race_id, driver_id, pit_stop_stop as stop_number, pit_stop_lap as lap_number
    from {{ ref('int_race_data_corrected') }}
    where session_type = 'PIT_STOP'
),

official as (
    select
        race_id,
        driver_id,
        sum(race_laps) as official_laps,
        bool_or(position_number is not null) as is_classified
    from {{ ref('int_race_data_corrected') }}
    where session_type = 'RACE_RESULT'
    group by all
),

matched as (
    select
        laps.race_id,
        laps.driver_id,
        laps.driver_number,
        laps.lap_number,
        laps.source,
        laps.is_safety_car,
        laps.is_virtual_safety_car,
        laps.is_red_flag,
        stops.stop_number,
        stops.lap_number as f1db_stop_lap
    from laps
    left join pit_offsets using (race_id)
    left join stops
        on laps.race_id = stops.race_id
        and laps.driver_id = stops.driver_id
        and laps.lap_number - coalesce(pit_offsets.pit_stop_offset, 0) = stops.lap_number
    qualify row_number() over (
        partition by laps.race_id, laps.driver_id, laps.driver_number, laps.lap_number
        order by stops.stop_number
    ) = 1
)

select
    matched.race_id,
    matched.driver_id,
    matched.driver_number,
    matched.lap_number,
    matched.stop_number,
    case
        when matched.stop_number is not null then 'pit_stop'
        when matched.race_id not in (select race_id from stops) then 'unclassified'
        when matched.is_red_flag then 'red_flag'
        when not official.is_classified and matched.lap_number >= official.official_laps
            then 'retirement'
        when matched.is_safety_car or matched.is_virtual_safety_car then 'safety_car'
        else 'penalty_or_other'
    end as pass_type,
    matched.source
from matched
left join official using (race_id, driver_id)
