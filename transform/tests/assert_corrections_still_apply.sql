{{ config(severity='warn') }}

{#- Avisa cuando una corrección del seed ya no encaja con ninguna fila de F1DB: probablemente
    F1DB la ha corregido en origen y puede eliminarse del seed. -#}
select corrections.*
from {{ ref('race_data_corrections') }} as corrections
where not exists (
    select 1
    from {{ ref('stg_f1db__race_data') }} as race_data
    where race_data.race_id = corrections.race_id
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
)
