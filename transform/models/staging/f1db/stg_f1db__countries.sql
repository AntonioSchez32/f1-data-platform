select
    id as country_id,
    alpha2_code,
    alpha3_code,
    name as country_name,
    demonym,
    continent_id
from {{ source('f1db', 'country') }}
