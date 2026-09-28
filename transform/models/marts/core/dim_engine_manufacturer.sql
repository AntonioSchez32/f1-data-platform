select
    engines.engine_manufacturer_id,
    engines.name,
    countries.country_name as country_engine_manufacturer,
    countries.demonym as demonym_engine_manufacturer,
    countries.alpha2_code as alpha2_engine_manufacturer
from {{ ref('stg_f1db__engine_manufacturers') }} as engines
left join {{ ref('stg_f1db__countries') }} as countries using (country_id)
