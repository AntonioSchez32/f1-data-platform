{#- Contraste de OpenF1 con F1DB por carrera y piloto (2023+): vueltas completadas (las de
    int_openf1_laps frente a las oficiales), posición final (session_result) y paradas (endpoint
    pit frente a fact_pit_stops, por vuelta de entrada).

    Solo pilotos con resultado de carrera en F1DB, sin descalificados (F1DB no computa sus
    vueltas) y en carreras con vueltas de OpenF1. `is_reliable_race`: ver
    int_openf1_race_reliability. -#}
with sessions as (
    select session_key, race_id
    from {{ ref('int_openf1_sessions') }}
    where is_race and race_id is not null
),

official as (
    select
        race_id,
        driver_id,
        any_value(driver_number) as driver_number,
        coalesce(sum(race_laps), 0)::bigint as official_laps,
        min(position_number) as position,
        bool_or(position_text = 'DSQ') as is_disqualified
    from {{ ref('int_race_data_corrected') }}
    where session_type = 'RACE_RESULT'
        and race_id in (select race_id from {{ ref('int_openf1_laps') }})
        and (race_laps > 0 or position_text not in ('DNQ', 'DNPQ', 'DNP', 'EX', 'DNS'))
    group by all
),

recorded as (
    select
        race_id,
        driver_id,
        count(*) filter (where lap_number <= official.official_laps) as recorded_in_range
    from {{ ref('int_openf1_laps') }}
    inner join official using (race_id, driver_id)
    group by all
),

results as (
    select sessions.race_id, numbers.driver_id, result.position
    from {{ ref('stg_openf1__session_result') }} as result
    inner join sessions using (session_key)
    inner join {{ ref('int_driver_race_numbers') }} as numbers
        on sessions.race_id = numbers.race_id
        and result.driver_number::varchar = numbers.driver_number
),

-- Carreras en las que OpenF1 tiene el endpoint pit (en varias de 2023 da 404).
pit_races as (
    select distinct sessions.race_id
    from {{ ref('stg_openf1__pit') }} as pit
    inner join sessions using (session_key)
),

stops as (
    select race_id, driver_id, count(*) as f1db_stops
    from {{ ref('fact_pit_stops') }}
    where race_id in (select race_id from pit_races)
    group by all
),

stops_matched as (
    select stops.race_id, stops.driver_id, count(*) as matched_stops
    from {{ ref('fact_pit_stops') }} as stops
    inner join {{ ref('int_openf1_laps') }} as laps
        on stops.race_id = laps.race_id
        and stops.driver_id = laps.driver_id
        and stops.lap_number = laps.lap_number
        and laps.is_pit_in_lap
    where stops.race_id in (select race_id from pit_races)
    group by all
)

select
    official.race_id,
    official.driver_id,
    coalesce(reliability.is_reliable, true) as is_reliable_race,
    official.official_laps,
    coalesce(recorded.recorded_in_range, 0) as recorded_in_range,
    coalesce(recorded.recorded_in_range, 0) = official.official_laps as is_laps_complete,
    official.position as f1db_position,
    results.position as openf1_position,
    case
        when official.position is not null and results.position is not null
            then official.position = results.position
    end as is_position_match,
    stops.f1db_stops,
    coalesce(stops_matched.matched_stops, 0) as matched_stops
from official
left join recorded using (race_id, driver_id)
left join results using (race_id, driver_id)
left join stops using (race_id, driver_id)
left join stops_matched using (race_id, driver_id)
left join {{ ref('int_openf1_race_reliability') }} as reliability using (race_id)
where not official.is_disqualified
