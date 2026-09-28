{#-
    Tiempos por vuelta fusionados (decisión A1 de la revisión de divergencias de 2026).

    - formula1db.com (scraping del TFG, 1950-2024) es la fuente principal: tiempo, posición,
      sectores, compuesto, entradas a boxes. Ergast (1996-2022) y FastF1 (2018+) lo validan.
    - FastF1 completa cada vuelta con stint, vida del neumático, speed trap y estado de pista, y
      aporta las vueltas que formula1db no tiene (carreras posteriores y pilotos ausentes).
    - Correcciones: seed lap_corrections (con evidencia; recalcula posiciones de la carrera) y
      mayoría (FastF1 y Ergast coinciden entre sí y contra formula1db; decisión A2).
    - Ergast solo rellena vueltas sueltas ausentes en formula1db, marcadas (N8).
    - Se eliminan las vueltas corridas después del final oficial en las carreras cuyo resultado
      se tomó antes de la bandera a cuadros real (A6).

    validation_status (tiempo de vuelta):
      confirmed          otra fuente da el mismo tiempo (±1 ms)
      timing_convention  diferencia < 1 s, vuelta 1 o vuelta con bandera roja: cada fuente reparte
                         el tiempo de forma distinta
      disputed           otra fuente discrepa ≥ 1 s sin mayoría: se conserva formula1db
      corrected          valor corregido (seed con evidencia o mayoría de las otras dos fuentes)
      single_source      no hay otra fuente con la que contrastar
-#}
with numbering as (
    select race_id, numbering_status, applied_lap_shift from {{ ref('int_lap_numbering') }}
),

lap_corrections as (
    select * from {{ ref('lap_corrections') }}
),

official as (
    select
        race_id,
        driver_id,
        sum(race_laps) as official_laps,
        bool_or(position_number is not null) as is_classified,
        bool_or(position_number = 1) as is_winner,
        bool_or(race_shared_car) as is_shared_car
    from {{ ref('int_race_data_corrected') }}
    where session_type = 'RACE_RESULT'
    group by all
),

-- Carreras cuyo resultado oficial se tomó antes de que el líder dejara de rodar (bandera a cuadros
-- anticipada o resultado a una vuelta anterior): alguna fuente registra al ganador más allá de
-- las vueltas oficiales (China 2014, Canadá 2018, Japón 2019, Bélgica 2021, Japón 2022).
count_back_races as (
    select distinct laps.race_id
    from (
        select race_id, driver_id, lap_number from {{ ref('int_formula1db_laps') }}
        union all
        select race_id, driver_id, lap_number from {{ ref('int_fastf1_laps') }}
        union all
        select ergast.race_id, numbers.driver_id, ergast.lap_number
        from {{ ref('int_ergast_laps') }} as ergast
        inner join {{ ref('int_driver_race_numbers') }} as numbers using (race_id, driver_number)
    ) as laps
    inner join official using (race_id, driver_id)
    -- En coches compartidos (años 50) las vueltas oficiales son las del coche, no del piloto.
    where official.is_winner
        and not official.is_shared_car
        and laps.lap_number > official.official_laps
),

-- 1. formula1db con la numeración conciliada y las correcciones con evidencia.
formula1db as (
    select
        laps.* replace (laps.lap_number + coalesce(numbering.applied_lap_shift, 0) as lap_number),
        laps.lap_number as original_lap_number,
        coalesce(numbering.numbering_status, 'no_evidence') as lap_numbering_status,
        corrections.corrected_value as corrected_lap_time_ms
    from {{ ref('int_formula1db_laps') }} as laps
    left join numbering using (race_id)
    left join lap_corrections as corrections
        on laps.race_id = corrections.race_id
        and laps.driver_id = corrections.driver_id
        and laps.lap_number = corrections.lap_number
        and corrections.column_name = 'lap_time_ms'
        and laps.lap_time_ms = corrections.original_value
),

-- 2. En las carreras con correcciones, posición y diferencia con el líder se recalculan con el
--    tiempo acumulado corregido (formula1db.com calcula ambas así).
formula1db_corrected_time as (
    select
        *,
        race_id in (select race_id from lap_corrections) as is_race_corrected,
        race_time_ms + sum(coalesce(corrected_lap_time_ms - lap_time_ms, 0)) over (
            partition by race_id, driver_number
            order by lap_number
            rows between unbounded preceding and current row
        ) as corrected_race_time_ms
    from formula1db
),

formula1db_repositioned as (
    select
        * replace (
            case
                when is_race_corrected and gap_to_leader_ms is not null
                    then corrected_race_time_ms
                        - min(corrected_race_time_ms) over (partition by race_id, lap_number)
                else gap_to_leader_ms
            end as gap_to_leader_ms
        ),
        case
            when is_race_corrected
                then rank() over (partition by race_id, lap_number order by corrected_race_time_ms)
        end as recalculated_position
    from formula1db_corrected_time
),

-- 3. Contraste con FastF1 y Ergast.
compared as (
    select
        legacy.*,
        fastf1.lap_time_ms as fastf1_lap_time_ms,
        fastf1.position as fastf1_position,
        ergast.lap_time_ms as ergast_lap_time_ms,
        ergast.position as ergast_position,
        fastf1.stint as fastf1_stint,
        fastf1.tyre_age_laps as fastf1_tyre_age_laps,
        fastf1.speed_trap_kmh,
        fastf1.is_accurate,
        fastf1.lap_number is not null as has_fastf1,
        fastf1.is_yellow_flag as fastf1_is_yellow_flag,
        fastf1.is_safety_car as fastf1_is_safety_car,
        fastf1.is_virtual_safety_car as fastf1_is_virtual_safety_car,
        fastf1.is_red_flag as fastf1_is_red_flag
    from formula1db_repositioned as legacy
    left join {{ ref('int_fastf1_laps') }} as fastf1
        using (race_id, driver_number, lap_number)
    left join {{ ref('int_ergast_laps') }} as ergast
        using (race_id, driver_number, lap_number)
),

resolved as (
    select
        *,
        coalesce(corrected_lap_time_ms, lap_time_ms) as checked_lap_time_ms,
        -- Mayoría: FastF1 y Ergast coinciden entre sí y contra formula1db.
        lap_number > 1
            and abs(fastf1_lap_time_ms - ergast_lap_time_ms) <= 1
            and abs(fastf1_lap_time_ms - lap_time_ms) > 1 as is_time_majority,
        fastf1_position = ergast_position and fastf1_position <> position as is_position_majority
    from compared
),

formula1db_final as (
    select
        race_id,
        driver_id,
        driver_number,
        lap_number,
        case
            when is_position_majority then fastf1_position
            else coalesce(recalculated_position, position)
        end as position,
        case
            when corrected_lap_time_ms is not null then corrected_lap_time_ms
            when is_time_majority then fastf1_lap_time_ms
            else lap_time_ms
        end as lap_time_ms,
        gap_to_leader_ms,
        sector_1_ms,
        sector_2_ms,
        sector_3_ms,
        fastf1_stint as stint,
        tyre_compound,
        coalesce(fastf1_tyre_age_laps, tyre_age_laps) as tyre_age_laps,
        tyre_age_laps as formula1db_tyre_age_laps,
        is_pit_in_lap,
        is_pit_out_lap,
        coalesce(fastf1_is_yellow_flag, is_yellow_flag) as is_yellow_flag,
        coalesce(fastf1_is_safety_car, is_safety_car) as is_safety_car,
        coalesce(fastf1_is_virtual_safety_car, is_virtual_safety_car) as is_virtual_safety_car,
        coalesce(fastf1_is_red_flag, is_red_flag) as is_red_flag,
        is_deleted,
        is_accurate,
        speed_trap_kmh,
        'formula1db' as source,
        case
            when corrected_lap_time_ms is not null or is_time_majority then 'corrected'
            when abs(lap_time_ms - ergast_lap_time_ms) <= 1
                or abs(lap_time_ms - fastf1_lap_time_ms) <= 1 then 'confirmed'
            when coalesce(ergast_lap_time_ms, fastf1_lap_time_ms) is null or lap_time_ms is null
                then 'single_source'
            when lap_number = 1
                or least(
                    abs(lap_time_ms - ergast_lap_time_ms), abs(lap_time_ms - fastf1_lap_time_ms)
                ) < 1000
                or greatest(lap_time_ms, ergast_lap_time_ms, fastf1_lap_time_ms) > 300000
                then 'timing_convention'
            else 'disputed'
        end as validation_status,
        list_filter(
            [
                case when abs(lap_time_ms - ergast_lap_time_ms) <= 1 then 'ergast' end,
                case when abs(lap_time_ms - fastf1_lap_time_ms) <= 1 then 'fastf1' end
            ],
            x -> x is not null
        ) as confirmed_by,
        list_filter(
            [
                case when corrected_lap_time_ms is not null then 'lap_time_ms:seed' end,
                case when is_time_majority then 'lap_time_ms:majority' end,
                case when recalculated_position <> position then 'position:recalculated' end,
                case when is_position_majority then 'position:majority' end
            ],
            x -> x is not null
        ) as corrections,
        lap_time_ms as original_lap_time_ms,
        position as original_position,
        original_lap_number,
        lap_numbering_status
    from resolved
),

formula1db_drivers as (
    select distinct race_id, driver_number from formula1db_final
),

-- 4. FastF1 aporta las carreras sin formula1db y los pilotos ausentes en ella (con vueltas oficiales).
fastf1_fill as (
    select
        fastf1.race_id,
        fastf1.driver_id,
        fastf1.driver_number,
        fastf1.lap_number,
        fastf1.position,
        fastf1.lap_time_ms,
        fastf1.gap_to_leader_ms,
        fastf1.sector_1_ms,
        fastf1.sector_2_ms,
        fastf1.sector_3_ms,
        fastf1.stint,
        fastf1.tyre_compound,
        fastf1.tyre_age_laps,
        null::integer as formula1db_tyre_age_laps,
        fastf1.is_pit_in_lap,
        fastf1.is_pit_out_lap,
        fastf1.is_yellow_flag,
        fastf1.is_safety_car,
        fastf1.is_virtual_safety_car,
        fastf1.is_red_flag,
        fastf1.is_deleted,
        fastf1.is_accurate,
        fastf1.speed_trap_kmh,
        'fastf1' as source,
        'single_source' as validation_status,
        []::varchar[] as confirmed_by,
        []::varchar[] as corrections,
        fastf1.lap_time_ms as original_lap_time_ms,
        fastf1.position as original_position,
        fastf1.lap_number as original_lap_number,
        'not_applicable' as lap_numbering_status
    from {{ ref('int_fastf1_laps') }} as fastf1
    left join official using (race_id, driver_id)
    where not exists (
        select 1 from formula1db_drivers as present where present.race_id = fastf1.race_id
    )
        or (
            not exists (
                select 1
                from formula1db_drivers as present
                where present.race_id = fastf1.race_id
                    and present.driver_number = fastf1.driver_number
            )
            and official.official_laps > 0
        )
),

-- 5. Ergast rellena vueltas sueltas que faltan en formula1db dentro de las vueltas oficiales.
ergast_fill as (
    select
        ergast.race_id,
        numbers.driver_id,
        ergast.driver_number,
        ergast.lap_number,
        ergast.position,
        ergast.lap_time_ms,
        null::bigint as gap_to_leader_ms,
        null::bigint as sector_1_ms,
        null::bigint as sector_2_ms,
        null::bigint as sector_3_ms,
        null::integer as stint,
        null::varchar as tyre_compound,
        null::integer as tyre_age_laps,
        null::integer as formula1db_tyre_age_laps,
        null::boolean as is_pit_in_lap,
        null::boolean as is_pit_out_lap,
        null::boolean as is_yellow_flag,
        null::boolean as is_safety_car,
        null::boolean as is_virtual_safety_car,
        null::boolean as is_red_flag,
        null::boolean as is_deleted,
        null::boolean as is_accurate,
        null::double as speed_trap_kmh,
        'ergast' as source,
        'single_source' as validation_status,
        []::varchar[] as confirmed_by,
        []::varchar[] as corrections,
        ergast.lap_time_ms as original_lap_time_ms,
        ergast.position as original_position,
        ergast.lap_number as original_lap_number,
        'not_applicable' as lap_numbering_status
    from {{ ref('int_ergast_laps') }} as ergast
    inner join formula1db_drivers using (race_id, driver_number)
    inner join {{ ref('int_driver_race_numbers') }} as numbers using (race_id, driver_number)
    inner join official
        on ergast.race_id = official.race_id
        and numbers.driver_id = official.driver_id
    where ergast.lap_number <= official.official_laps
        and not exists (
            select 1
            from formula1db_final as present
            where present.race_id = ergast.race_id
                and present.driver_number = ergast.driver_number
                and present.lap_number = ergast.lap_number
        )
),

unioned as (
    select * from formula1db_final
    union all by name
    select * from fastf1_fill
    union all by name
    select * from ergast_fill
),

tyres as (
    select race_id, pirelli_compound, relative_compound
    from {{ ref('int_tyre_compound_mapping') }}
    where is_consistent
),

races as (
    select race_id, season from {{ ref('stg_f1db__races') }}
)

select
    unioned.*,
    -- Compuesto real de Pirelli: C0-C6 (2019-2023) o nombre comercial (hasta 2018).
    case
        when regexp_matches(unioned.tyre_compound, '^C[0-6]$') then unioned.tyre_compound
        when races.season <= 2018 then nullif(unioned.tyre_compound, '')
        when unioned.tyre_compound in ('INTERMEDIATE', 'WET') then unioned.tyre_compound
    end as tyre_compound_pirelli,
    -- Compuesto relativo de la carrera (HARD/MEDIUM/SOFT desde 2019).
    case
        when regexp_matches(unioned.tyre_compound, '^C[0-6]$') then tyres.relative_compound
        when unioned.tyre_compound in ('INTERMEDIATE', 'WET') then unioned.tyre_compound
        when races.season >= 2019 and unioned.tyre_compound in ('HARD', 'MEDIUM', 'SOFT')
            then unioned.tyre_compound
    end as tyre_compound_relative
from unioned
inner join races using (race_id)
left join tyres
    on unioned.race_id = tyres.race_id
    and unioned.tyre_compound = tyres.pirelli_compound
left join official
    on unioned.race_id = official.race_id
    and unioned.driver_id = official.driver_id
-- A6: en esas carreras se eliminan las vueltas de los clasificados posteriores al final oficial.
where not coalesce(
    unioned.race_id in (select race_id from count_back_races)
    and official.is_classified
    and unioned.lap_number > official.official_laps,
    false
)
