{#- Dorsal de cada piloto en cada carrera: clave para cruzar las vueltas de FastF1, Ergast y
    formula1db.com (identificadas por dorsal y nombre) y la telemetría de clasificación con los
    pilotos de F1DB.

    Solo cuentan las sesiones con resultado de carrera, parrilla o clasificación (y las del sprint):
    en los libres de 2010-2013 los pilotos de pruebas del viernes llevaban el dorsal del titular y
    daban 294 parejas (carrera, dorsal) con dos pilotos. Con este filtro solo quedan los coches
    compartidos o relevados anteriores a 1982, donde el dorsal era del coche (ver
    _intermediate__models.yml). -#}
select distinct
    race_data.race_id,
    races.season,
    race_data.driver_number,
    race_data.driver_id,
    drivers.name as driver_name,
    {{ normalize_name('drivers.name') }} as normalized_name,
    {{ normalize_name('drivers.last_name') }} as normalized_last_name
from {{ ref('int_race_data_corrected') }} as race_data
inner join {{ ref('stg_f1db__races') }} as races using (race_id)
inner join {{ ref('stg_f1db__drivers') }} as drivers using (driver_id)
where race_data.driver_number is not null
    and race_data.session_type in (
        'RACE_RESULT',
        'STARTING_GRID_POSITION',
        'QUALIFYING_RESULT',
        'SPRINT_RACE_RESULT',
        'SPRINT_STARTING_GRID_POSITION',
        'SPRINT_QUALIFYING_RESULT'
    )
