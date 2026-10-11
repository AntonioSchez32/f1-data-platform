{#- Piloto de F1DB de cada driverRef de Jolpica, para los controles frente a F1DB (resultados,
    clasificación y paradas).

    Candidatos: los pilotos de F1DB que comparten carrera, sesión (carrera o sprint) y dorsal con
    el driverRef en los resultados. Solo valen los que confirma la fecha de nacimiento o el
    apellido de Jolpica dentro del nombre de F1DB, y de ellos el más frecuente. Ninguno de los dos
    criterios basta solo: con el dorsal, los coches compartidos de los años 50 dan parejas falsas
    (chitwood con Bettenhausen, pozzi con Rosier); con la fecha y el nombre, homónimos y fechas
    repetidas (clapham con Bruce Halford). Con el volcado del 25/09/2026: 801 de 818 pilotos con
    resultados, uno a uno; slotemaker (coche compartido con Seidel en 1962) queda sin piloto. -#}
with candidates as (
    select results.driver_ref, race_data.driver_id, count(*) as shared_entries
    from {{ ref('stg_jolpica__results') }} as results
    inner join {{ ref('stg_f1db__races') }} as races using (season, round)
    inner join {{ ref('int_race_data_corrected') }} as race_data
        on race_data.race_id = races.race_id
        and race_data.driver_number = results.driver_number
        and race_data.session_type = case results.session_type
            when 'R' then 'RACE_RESULT' else 'SPRINT_RACE_RESULT'
        end
    group by all
),

confirmed as (
    select candidates.*
    from candidates
    inner join {{ ref('stg_jolpica__drivers') }} as jolpica using (driver_ref)
    inner join {{ ref('stg_f1db__drivers') }} as f1db using (driver_id)
    where f1db.date_of_birth = jolpica.date_of_birth
        or contains({{ normalize_name('f1db.name') }}, {{ normalize_name('jolpica.surname') }})
)

select driver_ref, arg_max(driver_id, shared_entries) as driver_id
from confirmed
group by driver_ref
