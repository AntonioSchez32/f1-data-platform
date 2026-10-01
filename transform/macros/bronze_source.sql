{#-
    Fuente de bronze que puede no tener ficheros todavía: devuelve `source(source_name,
    table_name)` o, si el patrón `glob` (relativo a la carpeta bronze) no encuentra ninguno, una
    relación vacía con las columnas `columns` ({nombre: tipo}, los del Parquet de bronze), así que
    los modelos que dependen de ella compilan y sus unit tests tienen los mismos tipos con o sin
    datos.

    Hace falta para las tablas nuevas de D1: la CI ejecuta dbt contra el último snapshot
    publicado, que no tiene OpenF1 hasta que el pipeline lo carga por primera vez, ni los mensajes
    y la meteo de FastF1 hasta que el autor publica la recarga. `read_parquet` falla con un patrón
    sin ficheros.
-#}
{% macro bronze_source(source_name, table_name, glob, columns) -%}
    {%- set relation = source(source_name, table_name) -%}
    {%- set found = 1 -%}
    {%- if execute -%}
        {%- set bronze_dir = env_var('F1_BRONZE_DIR', '../data/bronze') -%}
        {%- set result = run_query(
            "select count(*) from glob('" ~ bronze_dir ~ "/" ~ glob ~ "')"
        ) -%}
        {%- set found = result.columns[0].values()[0] -%}
    {%- endif -%}
    {%- if found > 0 -%}
        {{ relation }}
    {%- else -%}
        (select {% for column, type in columns.items() -%}
            null::{{ type }} as {{ column }}{% if not loop.last %}, {% endif %}
        {%- endfor %} where false)
    {%- endif -%}
{%- endmacro %}

{#- Instante ISO 8601 con zona (OpenF1: '2024-05-19T13:03:16.593+00:00') como TIMESTAMP en UTC. -#}
{% macro utc_timestamp(column) -%}
    timezone('UTC', try_cast({{ column }} as timestamptz))
{%- endmacro %}
