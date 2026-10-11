{#-
    Estado de validación del tiempo de una vuelta frente a las otras fuentes (int_laptimes):
    confirmed (alguna da el mismo tiempo, ±1 ms), single_source (ninguna lo tiene),
    timing_convention (vuelta 1, diferencia < 1 s o vuelta de más de 5 min, típica de la bandera
    roja) o disputed. El estado corrected lo decide el modelo antes de llamar a la macro.
    `others` es la lista de columnas con el tiempo de cada otra fuente (least, greatest y
    coalesce de DuckDB ignoran los nulos).
-#}
{% macro lap_validation_status(time, lap_number, others) -%}
    case
        when {% for other in others %}abs({{ time }} - {{ other }}) <= 1{{ ' or ' if not loop.last }}{% endfor %}
            then 'confirmed'
        when coalesce({{ others | join(', ') }}) is null or {{ time }} is null then 'single_source'
        when {{ lap_number }} = 1
            or least({% for other in others %}abs({{ time }} - {{ other }}){{ ', ' if not loop.last }}{% endfor %}) < 1000
            or greatest({{ time }}, {{ others | join(', ') }}) > 300000
            then 'timing_convention'
        else 'disputed'
    end
{%- endmacro %}

{#- Fuentes que dan el mismo tiempo (±1 ms): `sources` es una lista de pares [nombre, columna]. -#}
{% macro lap_confirmed_by(time, sources) -%}
    list_filter(
        [
            {%- for name, column in sources %}
            case when abs({{ time }} - {{ column }}) <= 1 then '{{ name }}' end{{ ',' if not loop.last }}
            {%- endfor %}
        ],
        x -> x is not null
    )
{%- endmacro %}

{#- Vueltas (race_id, lap_number) de `relation` en las que aplicar la mayoría de posición
    (`is_position_majority`, con `voted` como posición votada y `current` como la que hay) dejaría
    dos pilotos con la misma posición. -#}
{% macro position_majority_conflicts(relation, voted, current) -%}
    (
        select race_id, lap_number
        from (
            select
                race_id,
                lap_number,
                case when is_position_majority then {{ voted }} else {{ current }} end
                    as resulting_position,
                is_position_majority
            from {{ relation }}
        )
        where resulting_position is not null
        group by race_id, lap_number, resulting_position
        having count(*) > 1 and bool_or(is_position_majority)
    )
{%- endmacro %}
