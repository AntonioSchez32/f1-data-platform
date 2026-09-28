{#- Nombre de persona comparable entre fuentes: minúsculas, sin acentos ni guiones, sin «Jr.»
    y solo letras (p. ej. «José Froilán González» -> «jose froilan gonzalez»). -#}
{% macro normalize_name(column) -%}
    trim(regexp_replace(
        lower(strip_accents(replace(replace({{ column }}, ' Jr.', ''), '-', ' '))),
        '[^a-z ]', '', 'g'
    ))
{%- endmacro %}
