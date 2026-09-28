{#- Clasificación del campeonato de pilotos tras cada carrera. -#}
select * from {{ ref('stg_f1db__race_driver_standings') }}
