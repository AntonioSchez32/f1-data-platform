{#-
    race_data de F1DB con dos capas de corrección:
      1. race_data_corrections: correcciones heredadas de Script-2.sql (piloto o dorsal).
      2. race_data_overrides: valores corregidos con evidencia documentada (FIA, Stats F1).
         Solo se aplican si la fila sigue teniendo el piloto y el valor original revisados.
-#}
{%- set override_columns = {
    'position_display_order': 'integer',
    'position_number': 'integer',
    'position_text': 'varchar',
    'race_positions_gained': 'integer',
    'race_laps': 'integer',
    'race_grid_position_number': 'integer',
    'race_grid_position_text': 'varchar',
    'qualifying_q3_millis': 'integer',
    'qualifying_gap_millis': 'integer',
    'fastest_lap_lap': 'integer',
} -%}

with race_data as (
    select * from {{ ref('stg_f1db__race_data') }}
),

corrections as (
    select * from {{ ref('race_data_corrections') }}
),

legacy_corrected as (
    select
        race_data.* replace (
            coalesce(corrections.set_driver_id, race_data.driver_id) as driver_id,
            coalesce(corrections.set_driver_number, race_data.driver_number) as driver_number
        ),
        race_data.driver_id as original_driver_id,
        corrections.race_id is not null as is_corrected
    from race_data
    left join corrections
        on race_data.race_id = corrections.race_id
        and (corrections.session_type is null or corrections.session_type = race_data.session_type)
        and (corrections.match_driver_id is null or corrections.match_driver_id = race_data.driver_id)
        and (
            corrections.match_driver_number is null
            or corrections.match_driver_number = race_data.driver_number
        )
        and (
            corrections.match_position_display_order is null
            or corrections.match_position_display_order = race_data.position_display_order
        )
),

-- Una fila por celda corregida que sigue encajando con F1DB.
applicable_overrides as (
    select overrides.*
    from {{ ref('race_data_overrides') }} as overrides
    inner join legacy_corrected as rows
        on overrides.race_id = rows.race_id
        and overrides.session_type = rows.session_type
        and overrides.position_display_order = rows.position_display_order
        and overrides.driver_id = rows.driver_id
    where coalesce(overrides.f1db_value, '') = case overrides.column_name
        {%- for column in override_columns %}
        when '{{ column }}' then coalesce(rows.{{ column }}::varchar, '')
        {%- endfor %}
    end
),

pivoted as (
    select
        race_id,
        session_type,
        position_display_order,
        {%- for column in override_columns %}
        max(corrected_value) filter (
            where column_name = '{{ column }}' and action = 'set'
        ) as override_{{ column }},
        {%- endfor %}
        list(distinct column_name order by column_name) filter (where action = 'set')
            as overridden_columns,
        list(distinct column_name order by column_name) filter (where action = 'flag')
            as disputed_columns
    from applicable_overrides
    group by all
)

select
    legacy_corrected.* replace (
        {%- for column, type in override_columns.items() %}
        coalesce(
            pivoted.override_{{ column }}::{{ type }}, legacy_corrected.{{ column }}
        ) as {{ column }}{{ ',' if not loop.last }}
        {%- endfor %}
    ),
    coalesce(pivoted.overridden_columns, []) as overridden_columns,
    coalesce(pivoted.disputed_columns, []) as disputed_columns
from legacy_corrected
left join pivoted
    on legacy_corrected.race_id = pivoted.race_id
    and legacy_corrected.session_type = pivoted.session_type
    and legacy_corrected.position_display_order = pivoted.position_display_order
