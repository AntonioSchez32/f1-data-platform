{#- Vueltas publicadas cuya posición contradicen los dos votantes de la mayoría (FastF1 y Jolpica
    en las carreras de formula1db; OpenF1 fiable y Jolpica en las de FastF1) sin que se haya
    corregido: la mayoría de posición no se aplica en una vuelta si dejaría dos pilotos con la
    misma posición (int_laptimes). Son disputas para revisar con la hoja de vueltas de la FIA. -#}
with laps as (
    select * from {{ ref('int_laptimes') }} where source in ('formula1db', 'fastf1')
),

openf1 as (
    select *
    from {{ ref('int_openf1_laps') }}
    where race_id not in (
        select race_id from {{ ref('int_openf1_race_reliability') }} where not is_reliable
    )
)

select
    laps.race_id,
    laps.driver_id,
    laps.driver_number,
    laps.lap_number,
    laps.source,
    laps.position,
    case laps.source when 'formula1db' then fastf1.position else openf1.position end
        as other_voter_position,
    jolpica.position as jolpica_position
from laps
inner join {{ ref('int_jolpica_laps') }} as jolpica
    using (race_id, driver_number, lap_number)
left join {{ ref('int_fastf1_laps') }} as fastf1
    using (race_id, driver_number, lap_number)
left join openf1
    using (race_id, driver_number, lap_number)
where jolpica.position = case laps.source when 'formula1db' then fastf1.position else openf1.position end
    and jolpica.position <> laps.position
