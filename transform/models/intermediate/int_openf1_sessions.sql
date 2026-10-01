{#- Sesiones de OpenF1 con la carrera de F1DB de su Gran Premio.

    La sesión de carrera (`Race`) se casa con F1DB por temporada y fecha local (la de
    `race.date`); el resto de sesiones del mismo meeting (sprint y clasificaciones) heredan esa
    carrera. Las sesiones canceladas no cuentan. Una carrera que OpenF1 ya tiene y F1DB aún no ha
    publicado queda con `race_id` nulo: no se modela y se cuenta en qa_summary
    (openf1_race_session_matching), sin detener el pipeline (decisión 26).

    `is_name_consistent` es un control del casamiento: el nombre del Gran Premio en OpenF1
    coincide con el de F1DB o, si no (OpenF1 dice «Mexico City Grand Prix» y F1DB «Mexican Grand
    Prix»), el país (test de severidad warn). -#}
with sessions as (
    select * from {{ ref('stg_openf1__sessions') }} where not is_cancelled
),

races as (
    select
        races.race_id,
        races.season,
        races.race_date,
        grands_prix.full_name,
        grands_prix.name,
        countries.country_name
    from {{ ref('stg_f1db__races') }} as races
    left join {{ ref('stg_f1db__grands_prix') }} as grands_prix using (grand_prix_id)
    left join {{ ref('stg_f1db__countries') }} as countries using (country_id)
),

-- F1DB fecha casi todas las carreras con la fecha local, pero Las Vegas 2023 (sábado por la noche
-- en Las Vegas) con la del domingo en UTC: se admite un día de diferencia y se toma la más
-- cercana. Dos carreras nunca están a menos de 6 días, así que no hay ambigüedad.
race_sessions as (
    select
        sessions.meeting_key,
        races.race_id,
        races.full_name,
        races.name,
        races.country_name
    from sessions
    inner join races
        on sessions.season = races.season
        and abs(races.race_date - sessions.local_date) <= 1
    where sessions.session_name = 'Race'
    qualify row_number() over (
        partition by sessions.session_key
        order by abs(races.race_date - sessions.local_date), races.race_id
    ) = 1
)

select
    sessions.session_key,
    sessions.meeting_key,
    sessions.season,
    sessions.session_name,
    sessions.session_type,
    sessions.session_name = 'Race' as is_race,
    sessions.session_name = 'Sprint' as is_sprint,
    race_sessions.race_id,
    sessions.date_start_utc,
    sessions.date_end_utc,
    sessions.local_date,
    sessions.location,
    meetings.meeting_name,
    {{ normalize_name('meetings.meeting_name') }} in (
        {{ normalize_name('race_sessions.full_name') }}, {{ normalize_name('race_sessions.name') }}
    )
    or {{ normalize_name('sessions.country_name') }}
    = {{ normalize_name('race_sessions.country_name') }} as is_name_consistent
from sessions
left join race_sessions using (meeting_key)
left join {{ ref('stg_openf1__meetings') }} as meetings using (meeting_key)
