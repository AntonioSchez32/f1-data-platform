select
    id as tyre_manufacturer_id,
    name,
    country_id
from {{ source('f1db', 'tyre_manufacturer') }}
