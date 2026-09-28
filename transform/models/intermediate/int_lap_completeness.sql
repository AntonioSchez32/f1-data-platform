{#-
    Conciliación, por carrera y piloto, de las vueltas registradas (FastF1 / formula1db.com)
    con las vueltas completadas según el resultado oficial de F1DB.

    Estados:
      ok                  todas las vueltas oficiales están, sin huecos
      shared_car          coche compartido (años 50): la fuente no separa las vueltas por piloto
      disqualified        descalificado: F1DB no computa sus vueltas, no es comparable
      missing_laps        faltan vueltas o hay huecos en la secuencia
      extra_laps          hay más de una vuelta por encima de las oficiales
      no_laps             la carrera tiene vueltas pero este piloto no
    Una única vuelta por encima de las oficiales es la vuelta de abandono (FastF1 la registra
    aunque no se complete) y no se considera error.
-#}
with official as (
    select
        race_id,
        driver_id,
        coalesce(sum(race_laps), 0) as official_laps,
        bool_or(race_shared_car) as is_shared_car,
        bool_or(position_text = 'DSQ') as is_disqualified
    from {{ ref('int_race_data_corrected') }}
    where session_type = 'RACE_RESULT'
        -- Se excluyen los inscritos que no tomaron la salida (no pueden tener vueltas).
        and (race_laps > 0 or position_text not in ('DNQ', 'DNPQ', 'DNP', 'EX', 'DNS'))
    group by all
),

recorded as (
    select
        laps.race_id,
        laps.driver_id,
        mode(laps.source) as source,
        count(distinct laps.lap_number) as recorded_laps,
        count(distinct laps.lap_number) filter (where laps.lap_number <= official.official_laps)
            as recorded_in_range,
        max(laps.lap_number) as last_lap
    from {{ ref('int_laptimes') }} as laps
    left join official using (race_id, driver_id)
    where laps.driver_id is not null
    group by all
),

-- Fuente principal de la carrera (la de la mayoría de sus vueltas).
races_with_laps as (
    select race_id, mode(source) as source from {{ ref('int_laptimes') }} group by race_id
),

joined as (
    select
        coalesce(official.race_id, recorded.race_id) as race_id,
        coalesce(official.driver_id, recorded.driver_id) as driver_id,
        coalesce(recorded.source, races_with_laps.source) as source,
        official.official_laps,
        recorded.recorded_laps,
        recorded.recorded_in_range,
        recorded.last_lap,
        coalesce(official.is_shared_car, false) as is_shared_car,
        coalesce(official.is_disqualified, false) as is_disqualified
    from official
    full outer join recorded using (race_id, driver_id)
    left join races_with_laps on official.race_id = races_with_laps.race_id
    where coalesce(official.race_id, recorded.race_id) in (select race_id from races_with_laps)
)

select
    *,
    -- Vueltas dentro del rango oficial que no están registradas (huecos o final ausente).
    coalesce(official_laps, 0) - coalesce(recorded_in_range, 0) as missing_laps,
    greatest(coalesce(last_lap, 0) - coalesce(official_laps, 0), 0) as laps_beyond_official,
    case
        when is_shared_car then 'shared_car'
        when is_disqualified then 'disqualified'
        -- Abandono en la vuelta 1: ninguna vuelta completada ni registrada.
        when recorded_laps is null and official_laps = 0 then 'ok'
        when recorded_laps is null then 'no_laps'
        when official_laps is null then 'extra_laps'
        when last_lap - official_laps > 1 then 'extra_laps'
        when recorded_in_range < official_laps then 'missing_laps'
        else 'ok'
    end as status
from joined
