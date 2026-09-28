select
    constructors.constructor_id,
    constructors.name,
    constructors.full_name,
    countries.country_name as country_constructor,
    countries.demonym as demonym_constructor,
    countries.alpha2_code as alpha2_constructor
from {{ ref('stg_f1db__constructors') }} as constructors
left join {{ ref('stg_f1db__countries') }} as countries using (country_id)
