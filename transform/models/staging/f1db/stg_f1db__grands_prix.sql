select
    id as grand_prix_id,
    name,
    full_name,
    short_name,
    abbreviation,
    country_id
from {{ source('f1db', 'grand_prix') }}
