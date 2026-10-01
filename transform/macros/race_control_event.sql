{#- Tipo de evento de un mensaje de dirección de carrera, o nulo. El texto cambia con los años
    (en 2026: «VSC DEPLOYED» en vez de «VIRTUAL SAFETY CAR DEPLOYED» y la roja como
    «RED FLAG - RACE SUSPENDED» sin bandera): todas las reglas que lo usan pasan por aquí. -#}
{% macro race_control_event(message, flag, category, scope) -%}
    case
        when {{ flag }} = 'RED' or {{ message }} like 'RED FLAG%' then 'red_flag'
        when {{ message }} like 'VIRTUAL SAFETY CAR DEPLOYED%' or {{ message }} like 'VSC DEPLOYED%'
            then 'vsc_deployed'
        when {{ message }} like 'VIRTUAL SAFETY CAR ENDING%' or {{ message }} like 'VSC ENDING%'
            then 'vsc_ending'
        when {{ message }} like 'SAFETY CAR DEPLOYED%' then 'safety_car_deployed'
        when {{ message }} like 'SAFETY CAR IN THIS LAP%' then 'safety_car_in'
        when {{ category }} = 'Flag' and {{ scope }} = 'Track' and {{ flag }} in ('CLEAR', 'GREEN')
            then 'track_clear'
        when {{ flag }} = 'CHEQUERED' then 'chequered_flag'
    end
{%- endmacro %}
