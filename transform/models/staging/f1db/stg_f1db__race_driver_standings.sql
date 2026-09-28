select
    race_id,
    position_display_order,
    position_number,
    position_text,
    driver_id,
    points,
    positions_gained,
    championship_won::boolean as championship_won
from {{ source('f1db', 'race_driver_standing') }}
