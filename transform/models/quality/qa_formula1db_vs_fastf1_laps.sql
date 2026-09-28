{#- Contraste vuelta a vuelta entre formula1db.com (scraping del TFG) y FastF1 en las carreras que
    cubren ambas. Mide la fiabilidad del histórico, que es la única fuente antes de 2018.
    La vuelta 1 se excluye del tiempo: cada fuente la cronometra desde un punto distinto
    (salida frente a línea de meta), con diferencias sistemáticas de ~50-80 ms. -#}
with comparable_compounds as (
    select unnest(['SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET']) as compound
)

select
    legacy.race_id,
    legacy.driver_number,
    legacy.driver_id,
    legacy.lap_number,
    legacy.lap_time_ms as formula1db_lap_time_ms,
    fastf1.lap_time_ms as fastf1_lap_time_ms,
    legacy.position as formula1db_position,
    fastf1.position as fastf1_position,
    legacy.tyre_compound as formula1db_tyre,
    fastf1.tyre_compound as fastf1_tyre,
    fastf1.lap_number is not null as is_matched,
    case
        when legacy.lap_number = 1 or legacy.lap_time_ms is null or fastf1.lap_time_ms is null
            then null
        else abs(legacy.lap_time_ms - fastf1.lap_time_ms) <= 1
    end as is_time_match,
    case
        when legacy.position is null or fastf1.position is null then null
        else legacy.position = fastf1.position
    end as is_position_match,
    case
        when legacy.tyre_compound in (select compound from comparable_compounds)
            and fastf1.tyre_compound in (select compound from comparable_compounds)
            then legacy.tyre_compound = fastf1.tyre_compound
    end as is_tyre_match
from {{ ref('int_formula1db_laps') }} as legacy
left join {{ ref('int_fastf1_laps') }} as fastf1
    using (race_id, driver_number, lap_number)
where legacy.race_id in (select distinct race_id from {{ ref('int_fastf1_laps') }})
