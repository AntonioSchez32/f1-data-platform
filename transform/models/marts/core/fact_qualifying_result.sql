{#- Resultados de clasificación con mejor tiempo y diferencia porcentual con la pole
    (qualifying_best_* y qualifying_gap_percentage del TFG). -#}
with qualifying as (
    select
        *,
        coalesce(
            least(qualifying_q1_millis, qualifying_q2_millis, qualifying_q3_millis),
            qualifying_time_millis
        ) as best_time_ms
    from {{ ref('int_race_data_corrected') }}
    where session_type in ('QUALIFYING_RESULT', 'SPRINT_QUALIFYING_RESULT')
)

select
    race_id,
    case session_type when 'QUALIFYING_RESULT' then 'QUALIFYING' else 'SPRINT_QUALIFYING' end
        as session_type,
    position_display_order,
    position_number,
    position_text,
    driver_number,
    driver_id,
    constructor_id,
    engine_manufacturer_id,
    tyre_manufacturer_id,
    qualifying_time_millis as time_ms,
    qualifying_q1_millis as q1_ms,
    qualifying_q2_millis as q2_ms,
    qualifying_q3_millis as q3_ms,
    qualifying_laps as laps,
    best_time_ms,
    round(
        100.0 * (best_time_ms / min(best_time_ms) over (partition by race_id, session_type) - 1),
        3
    ) as gap_to_pole_pct,
    coalesce(position_number = 1, false) as is_pole,
    overridden_columns
from qualifying
