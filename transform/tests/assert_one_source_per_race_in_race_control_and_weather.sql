{#- La dirección de carrera y la meteo toman una sola fuente por carrera (FastF1 preferente, OpenF1
    si FastF1 no la tiene): mezclar las dos duplicaría los mensajes y las muestras. -#}
select 'fact_race_control_message' as model, race_id, count(distinct source) as sources
from {{ ref('fact_race_control_message') }}
group by race_id
having count(distinct source) > 1

union all
select 'fact_weather_sample', race_id, count(distinct source)
from {{ ref('fact_weather_sample') }}
group by race_id
having count(distinct source) > 1
