select
    season::integer as season,
    round::integer as round,
    DriverNumber as driver_number,
    Abbreviation as driver_code,
    Position::integer as position,
    Q1_ms as q1_ms,
    Q2_ms as q2_ms,
    Q3_ms as q3_ms
from {{ source('fastf1', 'quali_results') }}
