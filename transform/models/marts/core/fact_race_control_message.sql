{#- Mensajes de dirección de carrera de la carrera (banderas, Safety Car y VSC, bandera roja,
    investigaciones y sanciones, DRS...), 2018+ (decisiones 29 y 30).

    Una sola fuente por carrera: FastF1 si tiene mensajes de esa carrera (2018+, preferente) y, si
    no, OpenF1 (2023+). Las dos leen el mismo feed (RaceControlMessages), así que los campos
    coinciden; solo FastF1 da el tiempo de sesión (`session_time_ms`, comparable con los tiempos
    de las vueltas) y el estado del DRS (`status`). `message_seq` numera los mensajes de la carrera
    por orden de publicación. `event` clasifica los mensajes de estado de pista (red_flag,
    safety_car_deployed, safety_car_in, vsc_deployed, vsc_ending, track_clear, chequered_flag;
    macro race_control_event). -#}
with races as (
    select race_id, season, round from {{ ref('stg_f1db__races') }}
),

fastf1 as (
    select
        races.race_id,
        'fastf1' as source,
        messages.message_utc,
        messages.session_time_ms,
        messages.lap_number,
        messages.category,
        messages.flag,
        messages.scope,
        messages.sector,
        messages.driver_number,
        messages.message,
        messages.status
    from {{ ref('stg_fastf1__race_control_messages') }} as messages
    inner join races using (season, round)
),

openf1 as (
    select
        sessions.race_id,
        'openf1' as source,
        messages.message_utc,
        null::bigint as session_time_ms,
        messages.lap_number,
        messages.category,
        messages.flag,
        messages.scope,
        messages.sector,
        messages.driver_number,
        messages.message,
        null::varchar as status
    from {{ ref('stg_openf1__race_control') }} as messages
    inner join {{ ref('int_openf1_sessions') }} as sessions using (session_key)
    where sessions.is_race
        and sessions.race_id is not null
        and sessions.race_id not in (select race_id from fastf1)
),

unioned as (
    select * from fastf1
    union all by name
    select * from openf1
)

select
    unioned.race_id,
    row_number() over (
        partition by unioned.race_id
        order by
            unioned.session_time_ms, unioned.message_utc, unioned.category, unioned.message,
            unioned.driver_number
    )::integer as message_seq,
    unioned.source,
    unioned.message_utc,
    unioned.session_time_ms,
    unioned.lap_number,
    unioned.category,
    unioned.flag,
    unioned.scope,
    unioned.sector,
    unioned.driver_number,
    numbers.driver_id,
    unioned.message,
    unioned.status,
    {{ race_control_event('unioned.message', 'unioned.flag', 'unioned.category', 'unioned.scope') }}
        as event
from unioned
left join {{ ref('int_driver_race_numbers') }} as numbers
    on unioned.race_id = numbers.race_id
    and unioned.driver_number::varchar = numbers.driver_number
