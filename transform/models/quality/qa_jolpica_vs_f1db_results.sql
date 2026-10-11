{#- Control de los resultados de carrera y sprint de F1DB frente a Jolpica (decisión 52): uno por
    fila de Jolpica, cruzada por carrera, sesión, piloto (int_jolpica_drivers) y dorsal, en las
    carreras que F1DB ya tiene. Solo se comparan valores con la misma semántica:
      - clasificación: si F1DB lo clasifica, la misma posición (`position` de Jolpica, que
        numera a todos; su `position_text` marca 'R' también a los retirados clasificados, como
        Verstappen en Bakú 2021); si no, que Jolpica tampoco le dé una posición en texto;
      - puntos y vueltas (is_match);
      - parrilla aparte (is_grid_match), salvo las salidas desde el pit lane (Jolpica da el hueco
        o 0; F1DB, 'PL'): en los años 60-80 difieren a menudo en un puesto por cómo se cuenta la
        parrilla tras las sanciones o los que no salen.
    Las correcciones de F1DB con evidencia (race_data_overrides) prevalecen: una diferencia con
    Jolpica es un aviso para revisar, no un error. -#}
with jolpica as (
    select races.race_id, drivers.driver_id, results.*
    from {{ ref('stg_jolpica__results') }} as results
    inner join {{ ref('stg_f1db__races') }} as races using (season, round)
    left join {{ ref('int_jolpica_drivers') }} as drivers using (driver_ref)
    where races.race_id in (select race_id from {{ ref('fact_race_result') }})
),

f1db as (
    select * from {{ ref('fact_race_result') }}
),

compared as (
    select
        jolpica.race_id,
        jolpica.session_type,
        jolpica.driver_ref,
        jolpica.driver_id,
        jolpica.driver_number,
        jolpica.position_text as jolpica_position_text,
        f1db.position_text as f1db_position_text,
        jolpica.points as jolpica_points,
        f1db.points as f1db_points,
        jolpica.laps as jolpica_laps,
        f1db.laps as f1db_laps,
        jolpica.grid as jolpica_grid,
        f1db.grid_position as f1db_grid,
        f1db.race_id is not null as is_matched,
        case
            when f1db.race_id is not null
                then case
                    when f1db.position_number is not null
                        then coalesce(jolpica.position = f1db.position_number, false)
                    else try_cast(jolpica.position_text as integer) is null
                end
        end as is_position_match,
        case when f1db.race_id is not null then jolpica.points = f1db.points end
            as is_points_match,
        case when f1db.race_id is not null then jolpica.laps = f1db.laps end as is_laps_match,
        case
            when f1db.grid_position is not null and jolpica.grid > 0
                then jolpica.grid = f1db.grid_position
        end as is_grid_match
    from jolpica
    left join f1db
        on jolpica.race_id = f1db.race_id
        and jolpica.driver_id = f1db.driver_id
        and jolpica.driver_number = f1db.driver_number
        and f1db.session_type = case jolpica.session_type when 'R' then 'RACE' else 'SPRINT' end
)

select
    *,
    case
        when is_matched
            then is_position_match and coalesce(is_points_match, true)
            and coalesce(is_laps_match, true)
    end as is_match
from compared
