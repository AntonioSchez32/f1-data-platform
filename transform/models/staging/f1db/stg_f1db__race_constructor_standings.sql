select
    race_id,
    position_display_order,
    position_number,
    position_text,
    constructor_id,
    engine_manufacturer_id,
    points,
    positions_gained,
    championship_won::boolean as championship_won
from {{ source('f1db', 'race_constructor_standing') }}
