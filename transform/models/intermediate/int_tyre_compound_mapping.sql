{#-
    Equivalencia, por carrera, entre el compuesto real de Pirelli (C0-C6, el que guarda
    formula1db.com en 2019-2023) y el relativo (HARD, MEDIUM, SOFT, el que da FastF1). Decisión N6.

    Para cada compuesto real se toma el relativo más frecuente en las vueltas que tienen ambas
    fuentes. La equivalencia solo se acepta si es coherente: cada compuesto real de la carrera
    tiene un relativo distinto y un compuesto más duro (número menor) nunca es más blando.
-#}
with pairs as (
    select
        legacy.race_id,
        legacy.tyre_compound as pirelli_compound,
        fastf1.tyre_compound as relative_compound,
        count(*) as laps
    from {{ ref('int_formula1db_laps') }} as legacy
    inner join {{ ref('int_fastf1_laps') }} as fastf1
        using (race_id, driver_number, lap_number)
    where regexp_matches(legacy.tyre_compound, '^C[0-6]$')
        and fastf1.tyre_compound in ('HARD', 'MEDIUM', 'SOFT')
    group by all
),

dominant as (
    select
        race_id,
        pirelli_compound,
        arg_max(relative_compound, laps) as relative_compound,
        sum(laps) as laps,
        max(laps) / sum(laps) as share
    from pairs
    group by all
),

checked as (
    select
        *,
        count(*) over (partition by race_id, relative_compound) as compounds_with_same_relative,
        -- Rango de dureza: al ordenar por compuesto real, el relativo no puede ablandarse y volver.
        case relative_compound when 'HARD' then 1 when 'MEDIUM' then 2 else 3 end as softness,
        lag(case relative_compound when 'HARD' then 1 when 'MEDIUM' then 2 else 3 end)
            over (partition by race_id order by pirelli_compound) as previous_softness
    from dominant
)

select
    race_id,
    pirelli_compound,
    relative_compound,
    laps,
    round(share, 3) as share,
    bool_and(compounds_with_same_relative = 1 and coalesce(softness > previous_softness, true))
        over (partition by race_id) as is_consistent
from checked
