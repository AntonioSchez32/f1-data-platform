select
    year as season,
    position_display_order,
    position_number,
    position_text,
    constructor_id,
    engine_manufacturer_id,
    points,
    championship_won::boolean as championship_won
from {{ source('f1db', 'season_constructor_standing') }}
