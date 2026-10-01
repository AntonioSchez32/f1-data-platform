{#- Vueltas de OpenF1 (todas las sesiones cargadas), con los tiempos en milisegundos. La vuelta 1
    suele venir sin `date_start` ni `lap_duration`. -#}
select
    session_key::bigint as session_key,
    driver_number::integer as driver_number,
    lap_number::integer as lap_number,
    {{ utc_timestamp('date_start') }} as date_start_utc,
    round(lap_duration * 1000)::bigint as lap_time_ms,
    round(duration_sector_1 * 1000)::bigint as sector_1_ms,
    round(duration_sector_2 * 1000)::bigint as sector_2_ms,
    round(duration_sector_3 * 1000)::bigint as sector_3_ms,
    coalesce(is_pit_out_lap::boolean, false) as is_pit_out_lap,
    i1_speed::double as speed_i1_kmh,
    i2_speed::double as speed_i2_kmh,
    st_speed::double as speed_trap_kmh
from {{ bronze_source('openf1', 'laps', 'openf1/laps/*/*.parquet', {
    'session_key': 'bigint', 'driver_number': 'bigint', 'lap_number': 'bigint',
    'date_start': 'varchar', 'lap_duration': 'double', 'duration_sector_1': 'double',
    'duration_sector_2': 'double', 'duration_sector_3': 'double', 'is_pit_out_lap': 'boolean',
    'i1_speed': 'double', 'i2_speed': 'double', 'st_speed': 'double'
}) }}
