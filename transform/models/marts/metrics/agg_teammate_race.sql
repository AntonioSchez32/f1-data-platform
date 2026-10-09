{#- Puntos frente al compañero carrera a carrera (decisión 45): una fila por carrera, equipo y
    piloto, con sus puntos y los del mejor compañero de esa carrera (el que más puntos sumó).

    Los puntos son los reales del fin de semana: todas sus filas de carrera, también las de
    coche compartido, más el sprint (DAT-04). Son compañeros los demás pilotos inscritos con el
    mismo equipo en esa carrera (también los DNQ o DNS, como en agg_teammate_h2h), salvo aquel
    con el que compartió coche: los dos tienen una fila con el mismo número y al menos una está
    marcada como coche compartido. F1DB solo marca la del piloto que entra (Argentina 1956:
    Fangio en el n.º 34 de Musso); un mismo número sin marca es una sustitución, no un coche
    compartido (Mónaco 1955: Herrmann no toma la salida y Simon corre su n.º 4). Si no queda
    ningún compañero, la carrera no tiene fila. -#}
with sprint_points as (
    select race_id, constructor_id, driver_id, sum(points) as points
    from {{ ref('fact_race_result') }}
    where session_type = 'SPRINT'
    group by all
),

-- Una fila por carrera, equipo y piloto: en los años 50 un piloto podía conducir dos coches.
entries as (
    select
        results.race_id,
        results.constructor_id,
        results.driver_id,
        sum(results.points) as race_points,
        min(results.position_display_order) as position_display_order,
        bool_or(results.position_number is not null) as is_classified
    from {{ ref('fact_race_result') }} as results
    where results.session_type = 'RACE'
    group by all
),

shared_cars as (
    -- Parejas que compartieron coche (en los dos sentidos).
    select distinct a.race_id, a.constructor_id, a.driver_id, b.driver_id as teammate_id
    from {{ ref('fact_race_result') }} as a
    inner join {{ ref('fact_race_result') }} as b
        on a.race_id = b.race_id
        and a.constructor_id = b.constructor_id
        and a.driver_number = b.driver_number
        and a.driver_id <> b.driver_id
    where a.session_type = 'RACE' and b.session_type = 'RACE'
        and (a.is_shared_car or b.is_shared_car)
),

race_entries as (
    select
        entries.race_id,
        entries.constructor_id,
        entries.driver_id,
        round(entries.race_points + coalesce(sprint_points.points, 0), 2) as points,
        entries.position_display_order,
        entries.is_classified
    from entries
    left join sprint_points using (race_id, constructor_id, driver_id)
),

teammates as (
    select
        a.race_id,
        a.constructor_id,
        a.driver_id,
        a.points,
        a.is_classified,
        b.driver_id as teammate_id,
        b.points as teammate_points,
        b.is_classified as teammate_is_classified,
        count(*) over (partition by a.race_id, a.constructor_id, a.driver_id) as teammates
    from race_entries as a
    inner join race_entries as b
        on a.race_id = b.race_id
        and a.constructor_id = b.constructor_id
        and a.driver_id <> b.driver_id
    left join shared_cars
        on a.race_id = shared_cars.race_id
        and a.constructor_id = shared_cars.constructor_id
        and a.driver_id = shared_cars.driver_id
        and b.driver_id = shared_cars.teammate_id
    where shared_cars.race_id is null
    -- Mejor compañero: el de más puntos; a igualdad, el mejor clasificado y luego el id.
    qualify row_number() over (
        partition by a.race_id, a.constructor_id, a.driver_id
        order by b.points desc, b.position_display_order, b.driver_id
    ) = 1
)

select
    teammates.race_id,
    races.season,
    races.round,
    teammates.constructor_id,
    teammates.driver_id,
    teammates.points,
    teammates.teammate_id,
    teammates.teammate_points,
    round(teammates.points - teammates.teammate_points, 2) as points_difference,
    teammates.teammates,
    teammates.is_classified,
    teammates.teammate_is_classified,
    teammates.is_classified and teammates.teammate_is_classified as both_classified
from teammates
inner join {{ ref('dim_race') }} as races using (race_id)
