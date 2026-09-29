{#- Los compuestos sin dato (NaN, None, UNKNOWN de FastF1; vacíos de formula1db) son nulos. -#}
select race_id, tyre_compound, count(*) as laps
from {{ ref('fact_laptimes') }}
where upper(trim(tyre_compound)) in ('NAN', 'NONE', 'UNKNOWN', 'TEST_UNKNOWN', '')
group by all
