select
    season::integer as season,
    round::integer as round,
    Driver as driver_code,
    DriverNumber as driver_number,
    Compound as tyre_compound,
    LapTime_ms as lap_time_ms,
    Distance as distance_m,
    Speed as speed_kmh,
    RPM as rpm,
    nGear as gear,
    Throttle as throttle_pct,
    Brake::boolean as is_braking,
    DRS as drs,
    X as x,
    Y as y
from {{ source('fastf1', 'quali_telemetry') }}
