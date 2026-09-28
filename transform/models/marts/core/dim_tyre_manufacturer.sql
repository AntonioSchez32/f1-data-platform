select
    tyres.tyre_manufacturer_id,
    tyres.name,
    countries.country_name as country_tyre_manufacturer,
    countries.demonym as demonym_tyre_manufacturer,
    countries.alpha2_code as alpha2_tyre_manufacturer
from {{ ref('stg_f1db__tyre_manufacturers') }} as tyres
left join {{ ref('stg_f1db__countries') }} as countries using (country_id)
