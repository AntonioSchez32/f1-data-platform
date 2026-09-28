{#- Cada carrera completada tiene exactamente un coche ganador (los coches compartidos de los
    años 50 pueden repartir la victoria entre varios pilotos del mismo coche). -#}
select race_id, session_type, count(distinct driver_number) as winning_cars
from {{ ref('fact_race_result') }}
where is_win
group by race_id, session_type
having count(distinct driver_number) <> 1
