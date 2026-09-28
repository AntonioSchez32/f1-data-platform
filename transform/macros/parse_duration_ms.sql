{#-
    Convierte tiempos en texto ('1:39.019', '42.414', '1:02:03.5') a milisegundos.
    Devuelve NULL para valores no numéricos como '-' o ''.
-#}
{% macro parse_duration_ms(column) -%}
    case
        when regexp_full_match(trim({{ column }}), '\d+(:\d{1,2})*(\.\d+)?')
            then round(
                list_reduce(
                    list_transform(string_split(trim({{ column }}), ':'), lambda s: try_cast(s as double)),
                    lambda acc, x: acc * 60 + x
                ) * 1000
            )::bigint
    end
{%- endmacro %}
