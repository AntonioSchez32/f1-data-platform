{#- Casos de referencia del resumen frente al compañero (decisión 45), comprobados a mano.
    Fangio 1955: 41 puntos en sus 6 carreras con compañero (9+1+9+8+6+8; el campeonato da 40
    por los descartes) frente a 28 del mejor compañero de cada carrera (1+0+6+6+9+6). En
    Argentina, Herrmann, Kling y Moss compartieron el n.º 8 y cada uno suma 1 punto. Fangio
    1956 vigila la exclusión del compañero de coche compartido: 33 frente a 21; si Musso o
    Collins contaran como compañeros en las carreras en que le cedieron el coche, serían 29. -#}
with expected as (
    select * from (values
        (1955, 'juan-manuel-fangio', 6, 41.0, 28.0),
        (1956, 'juan-manuel-fangio', 7, 33.0, 21.0),
        (2021, 'lewis-hamilton', 22, 387.5, 226.0)
    ) as t (season, driver_id, races_together, points, teammate_points)
)

select expected.*, summary.races_together as actual_races, summary.points as actual_points,
    summary.teammate_points as actual_teammate_points
from expected
left join {{ ref('agg_teammate_season') }} as summary using (season, driver_id)
where summary.driver_id is null
    or summary.races_together <> expected.races_together
    or abs(summary.points - expected.points) > 0.005
    or abs(summary.teammate_points - expected.teammate_points) > 0.005
