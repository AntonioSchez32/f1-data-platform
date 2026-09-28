{#- Clasificación del campeonato de constructores tras cada carrera. -#}
select * from {{ ref('stg_f1db__race_constructor_standings') }}
