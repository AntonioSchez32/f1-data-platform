{#- Falla si alguna comprobación de concordancia entre fuentes queda por debajo de su umbral. -#}
select check_id, description, compared, matched, match_pct, min_match_pct
from {{ ref('qa_summary') }}
where status = 'FAIL'
