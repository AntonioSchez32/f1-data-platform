{{ config(severity='warn') }}

{#- Avisa cuando una corrección de race_data_overrides ya no encaja con F1DB: el piloto o el valor
    original han cambiado (probablemente F1DB lo ha corregido en origen) y hay que revisarla. -#}
select overrides.*
from {{ ref('race_data_overrides') }} as overrides
where not exists (
    select 1
    from {{ ref('int_race_data_corrected') }} as rows
    where rows.race_id = overrides.race_id
        and rows.session_type = overrides.session_type
        and rows.driver_id = overrides.driver_id
        and list_contains(
            case overrides.action
                when 'set' then rows.overridden_columns
                else rows.disputed_columns
            end,
            overrides.column_name
        )
)
