{#- Telemetría (cada 10 m) de la vuelta más rápida de cada piloto en clasificación. -#}
with races as (
    select race_id, season, round from {{ ref('stg_f1db__races') }}
)

select
    races.race_id,
    numbers.driver_id,
    telemetry.* exclude (season, round)
from {{ ref('stg_fastf1__quali_telemetry') }} as telemetry
inner join races using (season, round)
left join {{ ref('int_driver_race_numbers') }} as numbers
    on races.race_id = numbers.race_id
    and telemetry.driver_number = numbers.driver_number
