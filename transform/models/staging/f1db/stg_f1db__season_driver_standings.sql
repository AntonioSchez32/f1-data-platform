select
    year as season,
    position_display_order,
    position_number,
    position_text,
    driver_id,
    points,
    championship_won::boolean as championship_won
from {{ source('f1db', 'season_driver_standing') }}
