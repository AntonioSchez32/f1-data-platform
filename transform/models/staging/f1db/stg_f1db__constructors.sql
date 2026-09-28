select
    id as constructor_id,
    name,
    full_name,
    country_id
from {{ source('f1db', 'constructor') }}
