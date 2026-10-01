{#- TrackStatus de FastF1 concatena códigos: 2 = bandera amarilla, 4 = Safety Car,
    5 = bandera roja, 6/7 = Virtual Safety Car. Los compuestos sin dato (NaN o None de pandas
    convertidos a texto, UNKNOWN y TEST_UNKNOWN de FastF1) quedan como nulos. -#}
select
    season::integer as season,
    round::integer as round,
    Driver as driver_code,
    DriverNumber as driver_number,
    LapNumber::integer as lap_number,
    Position::integer as position,
    LapTime_ms as lap_time_ms,
    Time_ms as session_time_ms,
    LapStartTime_ms as lap_start_session_time_ms,
    Sector1Time_ms as sector_1_ms,
    Sector2Time_ms as sector_2_ms,
    Sector3Time_ms as sector_3_ms,
    Stint::integer as stint,
    case
        when upper(Compound) not in ('NAN', 'NONE', 'UNKNOWN', 'TEST_UNKNOWN', '')
            then upper(Compound)
    end as tyre_compound,
    TyreLife::integer as tyre_age_laps,
    FreshTyre as is_fresh_tyre,
    PitInTime_ms is not null as is_pit_in_lap,
    PitOutTime_ms is not null as is_pit_out_lap,
    contains(coalesce(TrackStatus, ''), '2') as is_yellow_flag,
    contains(coalesce(TrackStatus, ''), '4') as is_safety_car,
    regexp_matches(coalesce(TrackStatus, ''), '[67]') as is_virtual_safety_car,
    contains(coalesce(TrackStatus, ''), '5') as is_red_flag,
    coalesce(Deleted, false) as is_deleted,
    IsAccurate as is_accurate,
    SpeedST as speed_trap_kmh
from {{ source('fastf1', 'laps') }}
