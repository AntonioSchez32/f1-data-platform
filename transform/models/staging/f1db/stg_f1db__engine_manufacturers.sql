select
    id as engine_manufacturer_id,
    name,
    country_id
from {{ source('f1db', 'engine_manufacturer') }}
