{#- Las sumas de DuckDB devuelven HUGEINT (128 bits), que Parquet, Power BI y la API no esperan:
    en gold todas las columnas enteras deben ser como mucho BIGINT. Se ejecuta tras los modelos
    que las producían. -#}
-- depends_on: {{ ref('fact_laptimes') }}
-- depends_on: {{ ref('agg_driver_career') }}
select table_name, column_name, data_type
from duckdb_columns()
where database_name = current_database()
    and schema_name = 'gold'
    and data_type in ('HUGEINT', 'UHUGEINT')
