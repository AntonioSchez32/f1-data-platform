{#- Duelo en carrera por pareja (decisión 46): las dos filas de una pareja comparan las mismas
    carreras (races_both_classified igual en los dos sentidos), en cada una gana uno de los
    dos (race_ahead de a y de b suman races_both_classified) y nunca se comparan más carreras
    de las compartidas. -#}
select a.season, a.constructor_id, a.driver_id, a.teammate_id, a.races_together,
    a.races_both_classified, a.race_ahead, b.races_both_classified as reverse_both_classified,
    b.race_ahead as reverse_race_ahead
from {{ ref('agg_teammate_h2h') }} as a
left join {{ ref('agg_teammate_h2h') }} as b
    on a.season = b.season
    and a.constructor_id = b.constructor_id
    and a.driver_id = b.teammate_id
    and a.teammate_id = b.driver_id
where b.driver_id is null
    or a.races_both_classified <> b.races_both_classified
    or a.race_ahead + b.race_ahead <> a.races_both_classified
    or a.races_both_classified > a.races_together
