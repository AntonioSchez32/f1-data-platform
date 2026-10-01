{#- Pasos por el pit lane: tiempo en el pit lane y, desde ~2024, tiempo parado. -#}
select
    session_key::bigint as session_key,
    driver_number::integer as driver_number,
    lap_number::integer as lap_number,
    {{ utc_timestamp('date') }} as date_utc,
    round(coalesce(lane_duration, pit_duration) * 1000)::bigint as lane_time_ms,
    round(stop_duration * 1000)::bigint as stop_time_ms
from {{ bronze_source('openf1', 'pit', 'openf1/pit/*/*.parquet', {
    'session_key': 'bigint', 'driver_number': 'bigint', 'lap_number': 'bigint', 'date': 'varchar',
    'lane_duration': 'double', 'pit_duration': 'double', 'stop_duration': 'double'
}) }}
