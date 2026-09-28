select
    id as driver_id,
    name,
    first_name,
    last_name,
    full_name,
    abbreviation,
    permanent_number,
    gender,
    date_of_birth,
    date_of_death,
    place_of_birth,
    country_of_birth_country_id,
    nationality_country_id
from {{ source('f1db', 'driver') }}
