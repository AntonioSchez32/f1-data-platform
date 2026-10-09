{#- Desde 2021 los puntos del duelo incluyen el sprint (DAT-04). Si el piloto tuvo un único
    compañero y compartió con él todas sus carreras de la temporada, sus puntos en el duelo son
    los de su temporada (desde 1991 no hay descartes). Vigila con datos reales lo que el unit
    test comprueba con datos inventados. -#}
with single_teammate as (
    select season, driver_id, any_value(races_together) as races_together,
        any_value(points) as points
    from {{ ref('agg_teammate_h2h') }}
    where season >= 2021
    group by season, driver_id
    having count(*) = 1
)

select single_teammate.*, seasons.race_entries, seasons.points as season_points
from single_teammate
inner join {{ ref('agg_driver_season') }} as seasons using (season, driver_id)
where single_teammate.races_together = seasons.race_entries
    and abs(single_teammate.points - seasons.points) > 0.005
