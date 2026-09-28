select
    race_id,
    position_display_order,
    driver_number,
    driver_id,
    constructor_id,
    engine_manufacturer_id,
    tyre_manufacturer_id,
    pit_stop_stop as stop_number,
    pit_stop_lap as lap_number,
    pit_stop_time_millis as time_ms,
    pit_stop_time_millis / 1000.0 as time_seconds
from {{ ref('int_race_data_corrected') }}
where session_type = 'PIT_STOP'
