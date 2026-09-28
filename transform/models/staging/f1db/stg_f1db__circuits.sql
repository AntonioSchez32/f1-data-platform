select
    id as circuit_id,
    name,
    full_name,
    type as circuit_type,
    place_name,
    country_id,
    latitude,
    longitude,
    length as circuit_length_km,
    turns
from {{ source('f1db', 'circuit') }}
