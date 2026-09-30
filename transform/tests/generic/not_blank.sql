{#- La columna no está vacía ni tiene solo espacios (los nulos los comprueba not_null). -#}
{% test not_blank(model, column_name) %}
select {{ column_name }}
from {{ model }}
where trim({{ column_name }}) = ''
{% endtest %}
