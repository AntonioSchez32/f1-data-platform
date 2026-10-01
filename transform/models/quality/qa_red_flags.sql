{#- Cada bandera roja de la dirección de carrera (fact_race_control_message, 2018+) debe tener
    alguna vuelta marcada con bandera roja en fact_laptimes, en la vuelta del líder en que se
    mostró, la anterior o la siguiente (cada piloto la ve en su propia vuelta).

    Se excluyen de forma explícita (`phase`):
      pre_start  la roja se mostró antes del inicio de la vuelta 1 según el cronometraje: en las
                 vueltas de formación (Bélgica 2021 y 2025, Mónaco 2022), donde ninguna vuelta la
                 contiene. FastF1 cuenta la vuelta 1 desde el relanzamiento, así que las rojas de
                 la vuelta 1 con nueva salida desde parrilla (Japón y Mónaco 2024) también caen
                 aquí; esas sí están marcadas por formula1db.com.
      after_end  la roja se mostró después de la última vuelta publicada de la carrera: terminó
                 la carrera y el resultado se tomó antes (Bélgica 2021: las vueltas posteriores al
                 final oficial se eliminan, regla A6 de int_laptimes).
      no_laps    la carrera no tiene vueltas.
    Inicio de la vuelta 1: en FastF1, su tiempo de sesión (LapStartTime); en OpenF1, la salida.

    Las marcas de las carreras con FastF1 salen solo de su TrackStatus (los mensajes no las
    cambian, para no alterar el histórico). Si una carrera nueva de FastF1 trajera una roja en
    carrera sin el código '5', este control (umbral del 100 %) fallaría y detendría la
    publicación: habría que revisar esa carrera y, si procede, marcar la vuelta con los mensajes
    también en FastF1 (como ya se hace en int_openf1_laps). -#}
with messages as (
    select * from {{ ref('fact_race_control_message') }} where event = 'red_flag'
),

fastf1_start as (
    select race_id, min(lap_start_session_time_ms) as start_session_time_ms
    from {{ ref('int_fastf1_laps') }}
    where lap_number = 1
    group by race_id
),

openf1_start as (
    select race_id, min(lap_start_utc) as start_utc
    from {{ ref('int_openf1_laps') }}
    where lap_number = 1
    group by race_id
),

race_laps as (
    select race_id, max(lap_number) as last_lap
    from {{ ref('fact_laptimes') }}
    group by race_id
),

flagged as (
    select distinct race_id, lap_number
    from {{ ref('fact_laptimes') }}
    where is_red_flag
)

select
    messages.race_id,
    messages.message_seq,
    messages.source,
    messages.lap_number,
    messages.message_utc,
    messages.message,
    case
        when race_laps.race_id is null then 'no_laps'
        when messages.session_time_ms < fastf1_start.start_session_time_ms
            or messages.message_utc < openf1_start.start_utc
            then 'pre_start'
        when messages.lap_number - 1 > race_laps.last_lap then 'after_end'
        else 'race'
    end as phase,
    exists (
        select 1
        from flagged
        where flagged.race_id = messages.race_id
            and flagged.lap_number between messages.lap_number - 1 and messages.lap_number + 1
    ) as is_lap_flagged
from messages
left join race_laps using (race_id)
left join fastf1_start using (race_id)
left join openf1_start using (race_id)
