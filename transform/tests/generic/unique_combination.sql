{#- La combinación de columnas identifica unívocamente cada fila (clave compuesta del hecho). -#}
{% test unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as occurrences
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
