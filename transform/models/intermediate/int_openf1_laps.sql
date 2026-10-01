{#-
    Vueltas de carrera de OpenF1 con las claves de F1DB (decisiones 20 y 25). Respaldan a FastF1
    en las carreras que aún no tiene y lo contrastan desde 2023 (int_laptimes y QA).

    - Carrera por la sesión (int_openf1_sessions) y piloto por dorsal (int_driver_race_numbers).
      Una vuelta sin piloto de F1DB se conserva aquí con `driver_id` nulo (test warn y control
      openf1_lap_driver_attribution) y no pasa a int_laptimes.
    - Fin de la vuelta: inicio de la siguiente o, en la última, inicio + duración. La vuelta 1
      suele venir sin inicio: se toma la salida (el inicio de la vuelta 1 de quien lo tiene). Su
      tiempo no se deduce de las marcas (difiere ~0,35 s del oficial, que se mide desde la
      parrilla); queda nulo si OpenF1 no lo da. Las vueltas sin fin (abandono a mitad de vuelta:
      sin vuelta siguiente ni duración) se descartan.
    - Tiempo: `lap_duration` o, si falta, la suma de los tres sectores (`is_lap_time_from_sectors`).
    - Posición al acabar la vuelta: la última del endpoint `position` hasta el fin de la vuelta más
      `openf1_position_tolerance_ms` (la posición se publica un instante después del paso por
      meta; calibrada con FastF1 2023-2024). Control: el orden de paso por meta en esa vuelta
      (`position_by_timing`). `position_status`:
        agreed         coinciden
        disputed       no coinciden: se publica la del endpoint position
        position_only  sin orden por tiempo (no debería ocurrir: toda vuelta tiene fin)
        timing_only    sin posición en el endpoint: se publica la del orden por tiempo
    - Neumático: tramo (`stints`) que contiene la vuelta; vida = vueltas al empezar el tramo + las
      del tramo (la primera vuelta con un juego nuevo es la 1, como en FastF1).
    - Boxes: entrada si `pit` registra la vuelta o la siguiente sale de boxes (en 2023 hay carreras
      sin endpoint `pit`); salida, `is_pit_out_lap`.
    - Estado de pista desde la dirección de carrera, por contención temporal en la vuelta de cada
      piloto: bandera roja (mensaje de roja dentro de la vuelta), Safety Car (de SAFETY CAR
      DEPLOYED al siguiente TRACK CLEAR / bandera verde) y VSC (del despliegue a VSC ENDING). Los
      textos se reconocen con la macro race_control_event.
      Las amarillas por sector no se derivan (`is_yellow_flag` nulo): marcarían de más frente al
      TrackStatus de FastF1.
-#}
with sessions as (
    select session_key, race_id
    from {{ ref('int_openf1_sessions') }}
    where is_race and race_id is not null
),

raw_laps as (
    select
        sessions.race_id,
        laps.*,
        lead(laps.date_start_utc) over (
            partition by laps.session_key, laps.driver_number order by laps.lap_number
        ) as next_lap_start_utc,
        lead(laps.is_pit_out_lap) over (
            partition by laps.session_key, laps.driver_number order by laps.lap_number
        ) as is_next_lap_pit_out,
        lead(laps.lap_number) over (
            partition by laps.session_key, laps.driver_number order by laps.lap_number
        ) as next_lap_number,
        min(laps.date_start_utc) filter (where laps.lap_number = 1)
            over (partition by laps.session_key) as race_start_utc
    from {{ ref('stg_openf1__laps') }} as laps
    inner join sessions using (session_key)
),

laps as (
    select
        *,
        coalesce(date_start_utc, case when lap_number = 1 then race_start_utc end)
            as lap_start_utc,
        -- La vuelta siguiente solo marca el final si es la inmediatamente posterior (sin huecos).
        coalesce(
            case when next_lap_number = lap_number + 1 then next_lap_start_utc end,
            date_start_utc + to_milliseconds(lap_time_ms)
        ) as lap_end_utc
    from raw_laps
),

finished_laps as (
    select * from laps where lap_end_utc is not null
),

positions as (
    select sessions.race_id, position.driver_number, position.date_utc, position.position
    from {{ ref('stg_openf1__position') }} as position
    inner join sessions using (session_key)
),

positioned as (
    select
        laps.race_id,
        laps.driver_number,
        laps.lap_number,
        positions.position
    from finished_laps as laps
    asof left join positions
        on laps.race_id = positions.race_id
        and laps.driver_number = positions.driver_number
        and laps.lap_end_utc + to_milliseconds({{ var('openf1_position_tolerance_ms') }})
        >= positions.date_utc
),

stints as (
    select sessions.race_id, stints.*
    from {{ ref('stg_openf1__stints') }} as stints
    inner join sessions using (session_key)
),

pit as (
    select distinct sessions.race_id, pit.driver_number, pit.lap_number
    from {{ ref('stg_openf1__pit') }} as pit
    inner join sessions using (session_key)
),

messages as (
    select
        sessions.race_id,
        rc.message_utc,
        {{ race_control_event('rc.message', 'rc.flag', 'rc.category', 'rc.scope') }} as event
    from {{ ref('stg_openf1__race_control') }} as rc
    inner join sessions using (session_key)
),

-- Periodos de Safety Car y VSC: del despliegue al primer final posterior (fin del VSC o pista
-- despejada).
period_starts as (
    select
        race_id,
        message_utc as start_utc,
        case event when 'vsc_deployed' then 'vsc' else 'sc' end as kind
    from messages
    where event in ('vsc_deployed', 'safety_car_deployed')
),

period_ends as (
    select
        race_id,
        message_utc as end_utc,
        case event when 'vsc_ending' then 'vsc' else 'any' end as kind
    from messages
    where event in ('vsc_ending', 'track_clear')
),

periods as (
    select
        period_starts.race_id,
        period_starts.kind,
        period_starts.start_utc,
        min(period_ends.end_utc) as end_utc
    from period_starts
    left join period_ends
        on period_starts.race_id = period_ends.race_id
        and period_ends.end_utc > period_starts.start_utc
        and (period_ends.kind = 'any' or period_ends.kind = period_starts.kind)
    group by all
),

red_flags as (
    select race_id, message_utc from messages where event = 'red_flag'
),

track_status as (
    select
        laps.race_id,
        laps.driver_number,
        laps.lap_number,
        bool_or(periods.kind = 'sc') as is_safety_car,
        bool_or(periods.kind = 'vsc') as is_virtual_safety_car
    from finished_laps as laps
    inner join periods
        on laps.race_id = periods.race_id
        and periods.start_utc < laps.lap_end_utc
        and coalesce(periods.end_utc, laps.lap_end_utc) > laps.lap_start_utc
    group by all
),

numbered as (
    select
        laps.*,
        positioned.position as position_from_feed,
        rank() over (partition by laps.race_id, laps.lap_number order by laps.lap_end_utc)
            as position_by_timing,
        (
            epoch_ms(laps.lap_end_utc)
            - min(epoch_ms(laps.lap_end_utc)) over (partition by laps.race_id, laps.lap_number)
        )::bigint as gap_to_leader_ms
    from finished_laps as laps
    left join positioned using (race_id, driver_number, lap_number)
)

select
    laps.race_id,
    numbers.driver_id,
    laps.driver_number::varchar as driver_number,
    laps.lap_number,
    coalesce(laps.position_from_feed, laps.position_by_timing) as position,
    laps.position_from_feed,
    laps.position_by_timing,
    case
        when laps.position_from_feed is null then 'timing_only'
        when laps.position_by_timing is null then 'position_only'
        when laps.position_from_feed = laps.position_by_timing then 'agreed'
        else 'disputed'
    end as position_status,
    coalesce(laps.lap_time_ms, laps.sector_1_ms + laps.sector_2_ms + laps.sector_3_ms)
        as lap_time_ms,
    laps.lap_time_ms is null
        and laps.sector_1_ms + laps.sector_2_ms + laps.sector_3_ms is not null
        as is_lap_time_from_sectors,
    laps.lap_start_utc,
    laps.lap_end_utc,
    laps.gap_to_leader_ms,
    laps.sector_1_ms,
    laps.sector_2_ms,
    laps.sector_3_ms,
    stint.stint,
    stint.tyre_compound,
    stint.tyre_age_at_start + laps.lap_number - stint.lap_start + 1 as tyre_age_laps,
    coalesce(laps.is_next_lap_pit_out and laps.next_lap_number = laps.lap_number + 1, false)
    or pit.lap_number is not null as is_pit_in_lap,
    laps.is_pit_out_lap,
    null::boolean as is_yellow_flag,
    coalesce(track_status.is_safety_car, false) as is_safety_car,
    coalesce(track_status.is_virtual_safety_car, false) as is_virtual_safety_car,
    exists (
        select 1
        from red_flags
        where red_flags.race_id = laps.race_id
            and red_flags.message_utc > laps.lap_start_utc
            and red_flags.message_utc <= laps.lap_end_utc
    ) as is_red_flag,
    null::boolean as is_deleted,
    null::boolean as is_accurate,
    laps.speed_trap_kmh,
    laps.session_key,
    'openf1' as source
from numbered as laps
left join {{ ref('int_driver_race_numbers') }} as numbers
    on laps.race_id = numbers.race_id
    and laps.driver_number::varchar = numbers.driver_number
left join stints as stint
    on laps.race_id = stint.race_id
    and laps.driver_number = stint.driver_number
    and laps.lap_number between stint.lap_start and coalesce(stint.lap_end, laps.lap_number)
left join pit
    on laps.race_id = pit.race_id
    and laps.driver_number = pit.driver_number
    and laps.lap_number = pit.lap_number
left join track_status
    on laps.race_id = track_status.race_id
    and laps.driver_number = track_status.driver_number
    and laps.lap_number = track_status.lap_number
-- Tramos solapados (OpenF1 a veces cierra uno después de abrir el siguiente): el más reciente.
qualify row_number() over (
    partition by laps.race_id, laps.driver_number, laps.lap_number order by stint.stint desc
) = 1
