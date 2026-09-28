{#- Usa el nombre de esquema tal cual (silver / gold) en lugar de prefijarlo con el del target. -#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name | trim if custom_schema_name else target.schema }}
{%- endmacro %}
