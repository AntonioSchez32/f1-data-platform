{#- Dimensión de pilotos con países desnormalizados (decisión de diseño del TFG, sección 5.2). -#}
with countries as (
    select * from {{ ref('stg_f1db__countries') }}
)

select
    drivers.driver_id,
    drivers.name,
    drivers.first_name,
    drivers.last_name,
    drivers.full_name,
    drivers.abbreviation,
    drivers.permanent_number,
    drivers.gender,
    drivers.date_of_birth,
    drivers.date_of_death,
    drivers.place_of_birth,
    birth.country_name as country_of_birth_name,
    nationality.country_name as nationality_country,
    nationality.demonym as nationality_demonym,
    nationality.alpha2_code as nationality_alpha2
from {{ ref('stg_f1db__drivers') }} as drivers
left join countries as birth on drivers.country_of_birth_country_id = birth.country_id
left join countries as nationality on drivers.nationality_country_id = nationality.country_id
