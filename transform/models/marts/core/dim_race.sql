{#- Dimensión de carreras con temporada, circuito y Gran Premio desnormalizados (TFG, Fig. 5.6). -#}
with races as (
    select * from {{ ref('stg_f1db__races') }}
),

countries as (
    select * from {{ ref('stg_f1db__countries') }}
),

completed as (
    select distinct race_id
    from {{ ref('stg_f1db__race_data') }}
    where session_type = 'RACE_RESULT'
)

select
    races.race_id,
    races.season,
    races.round,
    races.race_date,
    races.race_time_utc,
    races.official_name,
    races.qualifying_format,
    races.sprint_qualifying_format,
    races.has_sprint,
    races.circuit_type,
    races.direction,
    races.course_length,
    races.turns,
    races.laps,
    races.distance,
    races.scheduled_laps,
    races.scheduled_distance,
    races.drivers_championship_decider,
    races.constructors_championship_decider,
    completed.race_id is not null as is_completed,
    races.round = max(races.round) over (partition by races.season) as is_season_final_race,
    circuits.circuit_id,
    circuits.name as circuit_name,
    circuits.full_name as circuit_full_name,
    circuits.place_name as circuit_place_name,
    circuits.latitude as circuit_latitude,
    circuits.longitude as circuit_longitude,
    circuit_country.country_name as circuit_country,
    circuit_country.demonym as circuit_demonym,
    circuit_country.alpha2_code as circuit_alpha2,
    circuit_country.alpha3_code as circuit_alpha3,
    grands_prix.grand_prix_id,
    grands_prix.name as grand_prix_name,
    grands_prix.full_name as grand_prix_full_name,
    grands_prix.short_name as grand_prix_short_name,
    grands_prix.abbreviation as grand_prix_abbreviation,
    gp_country.country_name as grand_prix_country,
    gp_country.demonym as grand_prix_demonym
from races
left join completed using (race_id)
left join {{ ref('stg_f1db__circuits') }} as circuits using (circuit_id)
left join countries as circuit_country on circuits.country_id = circuit_country.country_id
left join {{ ref('stg_f1db__grands_prix') }} as grands_prix using (grand_prix_id)
left join countries as gp_country on grands_prix.country_id = gp_country.country_id
