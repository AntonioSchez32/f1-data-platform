{#- Dorsal de cada piloto en cada carrera: clave para cruzar las vueltas de FastF1 y de
    formula1db.com (identificadas por dorsal y nombre) con los pilotos de F1DB. -#}
select distinct
    race_data.race_id,
    race_data.driver_number,
    race_data.driver_id,
    drivers.name as driver_name,
    {{ normalize_name('drivers.name') }} as normalized_name,
    {{ normalize_name('drivers.last_name') }} as normalized_last_name
from {{ ref('int_race_data_corrected') }} as race_data
inner join {{ ref('stg_f1db__drivers') }} as drivers using (driver_id)
where race_data.driver_number is not null
