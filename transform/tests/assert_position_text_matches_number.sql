{#- position_text es una posición si y solo si position_number tiene valor, y entonces son la
    misma (DAT-05). Los códigos sin posición (DNF, DNQ, NC...) los fija accepted_values. -#}
select 'fact_race_result' as model, race_id, session_type, position_display_order,
    position_text, position_number
from {{ ref('fact_race_result') }}
where (position_number is not null or regexp_full_match(position_text, '[1-9][0-9]*'))
    and position_text is distinct from position_number::varchar

union all

select 'fact_qualifying_result', race_id, session_type, position_display_order,
    position_text, position_number
from {{ ref('fact_qualifying_result') }}
where (position_number is not null or regexp_full_match(position_text, '[1-9][0-9]*'))
    and position_text is distinct from position_number::varchar
