{#- Pilotos de Jolpica (driverRef de Ergast) con los datos que confirman el cruce con F1DB. -#}
select
    driver_ref,
    forename,
    surname,
    date_of_birth::date as date_of_birth,
    origin
from {{ source('jolpica', 'drivers') }}
