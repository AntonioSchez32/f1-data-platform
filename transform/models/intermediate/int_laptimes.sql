{#-
    Tiempos por vuelta fusionados (decisión A1 de la revisión de divergencias de 2026).

    - formula1db.com (scraping del TFG, 1950-2024) es la fuente principal: tiempo, posición,
      sectores, compuesto, entradas a boxes. Jolpica (1996+) y FastF1 (2018+) lo validan.
    - FastF1 completa cada vuelta con stint, vida del neumático, speed trap y estado de pista, y
      aporta las vueltas que formula1db no tiene (carreras posteriores y pilotos ausentes).
    - OpenF1 (2023+, decisión 20) es el respaldo de FastF1: aporta las carreras que no tienen ni
      formula1db ni FastF1, sin las vueltas que no se cruzan con un piloto de F1DB. En el resto
      contrasta el tiempo (confirmed_by 'openf1'); en las de formula1db no entra en la mayoría:
      lee el mismo feed que FastF1, así que su acuerdo con FastF1 no es una confirmación
      independiente. Solo contrasta en las carreras en que es fiable (int_openf1_race_reliability):
      en Australia 2026 sus vueltas van desplazadas una posición y marcarían como disputed
      vueltas correctas de FastF1.
    - Jolpica (1996+, sucesor de Ergast; decisiones 49-50) es la tercera fuente: vota en la
      mayoría, contrasta (confirmed_by 'jolpica') y rellena vueltas sueltas (N8). En las carreras
      sin formula1db ni FastF1 contrasta OpenF1 (DAT-06) y la sustituye como base si OpenF1 no es
      fiable o le faltan vueltas y Jolpica está completa (int_openf1_race_reliability; prioridad
      formula1db / FastF1 > OpenF1 fiable > Jolpica). Ergast ya no vota: nunca votan los dos.
    - Correcciones: seed lap_corrections (con evidencia; recalcula posiciones de la carrera) y
      mayoría (decisión A2): en las carreras de formula1db, FastF1 y Jolpica coinciden entre sí y
      contra formula1db; en las de FastF1 (2025+, decisión 27), OpenF1 fiable y Jolpica coinciden
      entre sí y contra FastF1 (Jolpica sale de los PDF de la FIA, independiente del directo). La
      mayoría de tiempo solo resuelve discrepancias de 1 s o más (las menores son de convención:
      dónde se corta la vuelta bajo SC, como en Estados Unidos 2024); la de posición compara con
      la posición ya recalculada por la seed (Qatar 2024 no se corrige dos veces).
    - Jolpica rellena vueltas sueltas ausentes en la base de la carrera (formula1db, FastF1 u
      OpenF1) dentro de las vueltas oficiales de los pilotos presentes, marcadas (N8).
    - Se eliminan las vueltas corridas después del final oficial en las carreras cuyo resultado
      se tomó antes de la bandera a cuadros real (A6).
    - Tiempos de FastF1 calculados como suma de los sectores cuando falta el de la vuelta
      (corrections: lap_time_ms:sectors; original_lap_time_ms queda nulo).
    - Bandera roja en la vuelta que contiene la suspensión (corrections: is_red_flag:suspension). Las
      fuentes marcan la vuelta en la que se muestra la bandera, pero el tiempo parado se suma a la
      siguiente, la del relanzamiento. Se marca la vuelta de un piloto si dura más de
      max(400 s, 3 veces la mediana de la carrera) y, además, hay una marca de roja en esa vuelta o
      en las tres anteriores, o al menos tres pilotos tienen una vuelta así en esa misma vuelta
      (umbrales en las vars red_flag_* de dbt_project.yml). Las marcas existentes no se tocan. Ver
      docs/revision_divergencias/INFORME.md (T3).

    validation_status (tiempo de vuelta):
      confirmed          otra fuente da el mismo tiempo (±1 ms); las vueltas de FastF1 solo
                         puede confirmarlas OpenF1 (mismo feed, distinto procesado)
      timing_convention  diferencia < 1 s, vuelta 1 o vuelta con bandera roja: cada fuente reparte
                         el tiempo de forma distinta
      disputed           otra fuente discrepa ≥ 1 s sin mayoría: se conserva formula1db
      corrected          valor corregido (seed con evidencia o mayoría de las otras dos fuentes)
      single_source      no hay otra fuente con la que contrastar
-#}
with openf1_laps as (
    -- OpenF1 de las carreras en que es fiable (las que solo tienen OpenF1 lo son por defecto).
    select *
    from {{ ref('int_openf1_laps') }}
    where race_id not in (
        select race_id from {{ ref('int_openf1_race_reliability') }} where not is_reliable
    )
),

-- Vueltas de Jolpica con piloto de F1DB (sin él no se publican; control
-- jolpica_lap_driver_attribution).
jolpica_laps as (
    select * from {{ ref('int_jolpica_laps') }} where driver_id is not null
),

reliability as (
    select * from {{ ref('int_openf1_race_reliability') }}
),

numbering as (
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
        select race_id, driver_id, lap_number
        from jolpica_laps
        union all
        select race_id, driver_id, lap_number
        from openf1_laps
        where driver_id is not null
    ) as laps
    inner join official using (race_id, driver_id)
    -- En coches compartidos (años 50) las vueltas oficiales son las del coche, no del piloto.
    where official.is_winner
        and not official.is_shared_car
        and laps.lap_number > official.official_laps
    -- China 2014 solo la delata Jolpica (antes Ergast): se fija aquí para que la regla no dependa
    -- de que Jolpica esté disponible (con sus tablas vacías de relleno, 13 vueltas de más).
    union
    select race_id from {{ ref('stg_f1db__races') }} where season = 2014 and round = 4
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
        (
            race_time_ms + sum(coalesce(corrected_lap_time_ms - lap_time_ms, 0)) over (
                partition by race_id, driver_number
                order by lap_number
                rows between unbounded preceding and current row
            )
        )::bigint as corrected_race_time_ms
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

-- 3. Contraste con FastF1, Jolpica y OpenF1.
compared as (
    select
        legacy.*,
        fastf1.lap_time_ms as fastf1_lap_time_ms,
        fastf1.position as fastf1_position,
        jolpica.lap_time_ms as jolpica_lap_time_ms,
        jolpica.position as jolpica_position,
        openf1.lap_time_ms as openf1_lap_time_ms,
        fastf1.stint as fastf1_stint,
        fastf1.tyre_age_laps as fastf1_tyre_age_laps,
        fastf1.speed_trap_kmh,
        fastf1.is_accurate,
        fastf1.lap_number is not null as has_fastf1,
        fastf1.is_yellow_flag as fastf1_is_yellow_flag,
        fastf1.is_safety_car as fastf1_is_safety_car,
        fastf1.is_virtual_safety_car as fastf1_is_virtual_safety_car,
        fastf1.is_red_flag as fastf1_is_red_flag,
        coalesce(fastf1.is_lap_time_from_sectors, false) as fastf1_from_sectors
    from formula1db_repositioned as legacy
    left join {{ ref('int_fastf1_laps') }} as fastf1
        using (race_id, driver_number, lap_number)
    left join jolpica_laps as jolpica
        using (race_id, driver_number, lap_number)
    left join openf1_laps as openf1
        using (race_id, driver_number, lap_number)
),

votes as (
    select
        *,
        coalesce(corrected_lap_time_ms, lap_time_ms) as checked_lap_time_ms,
        -- Mayoría: FastF1 y Jolpica coinciden entre sí y discrepan de formula1db en 1 s o más.
        lap_number > 1
            and abs(fastf1_lap_time_ms - jolpica_lap_time_ms) <= 1
            and abs(fastf1_lap_time_ms - lap_time_ms) >= 1000 as is_time_majority,
        -- Contra la posición ya recalculada por la seed, si la hay.
        fastf1_position = jolpica_position
            and fastf1_position <> coalesce(recalculated_position, position)
            as is_position_majority
    from compared
),

-- La mayoría de posición se aplica por vuelta: si deja dos pilotos con la misma posición (el que
-- recibe la mayoría ocupa la de otro que no la recibe, como Tsunoda y Verstappen en la vuelta 2 de
-- Japón 2024), no se aplica en esa vuelta y queda como disputa (qa_position_majority_withheld).
resolved as (
    select
        votes.* replace (
            votes.is_position_majority
            and not exists (
                select 1
                from {{ position_majority_conflicts('votes', 'fastf1_position',
                    'coalesce(recalculated_position, position)') }} as conflict
                where conflict.race_id = votes.race_id
                    and conflict.lap_number = votes.lap_number
            ) as is_position_majority
        )
    from votes
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
            else {{ lap_validation_status(
                'lap_time_ms',
                'lap_number',
                ['jolpica_lap_time_ms', 'fastf1_lap_time_ms', 'openf1_lap_time_ms']
            ) }}
        end as validation_status,
        list_filter(
            [
                case when abs(lap_time_ms - jolpica_lap_time_ms) <= 1 then 'jolpica' end,
                -- fastf1:sectors cuando el tiempo de FastF1 es la suma de los sectores.
                case
                    when abs(lap_time_ms - fastf1_lap_time_ms) <= 1
                        then case when fastf1_from_sectors then 'fastf1:sectors' else 'fastf1' end
                end,
                case when abs(lap_time_ms - openf1_lap_time_ms) <= 1 then 'openf1' end
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
--    En ellas OpenF1 fiable y Jolpica contrastan y, si coinciden entre sí y contra FastF1, corrigen
--    por mayoría (decisión 27): el tiempo, si la discrepancia es de 1 s o más; la posición, siempre.
fastf1_compared as (
    select
        fastf1.*,
        openf1.lap_time_ms as openf1_lap_time_ms,
        openf1.position as openf1_position,
        jolpica.lap_time_ms as jolpica_lap_time_ms,
        jolpica.position as jolpica_position,
        fastf1.lap_number > 1
            and abs(openf1.lap_time_ms - jolpica.lap_time_ms) <= 1
            and abs(fastf1.lap_time_ms - jolpica.lap_time_ms) >= 1000 as is_time_majority,
        openf1.position = jolpica.position and openf1.position <> fastf1.position
            as is_position_majority
    from {{ ref('int_fastf1_laps') }} as fastf1
    left join official using (race_id, driver_id)
    left join openf1_laps as openf1
        using (race_id, driver_number, lap_number)
    left join jolpica_laps as jolpica
        using (race_id, driver_number, lap_number)
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

fastf1_resolved as (
    select
        fastf1_compared.* replace (
            fastf1_compared.is_position_majority
            and not exists (
                select 1
                from {{ position_majority_conflicts('fastf1_compared', 'jolpica_position',
                    'position') }} as conflict
                where conflict.race_id = fastf1_compared.race_id
                    and conflict.lap_number = fastf1_compared.lap_number
            ) as is_position_majority
        )
    from fastf1_compared
),

fastf1_fill as (
    select
        race_id,
        driver_id,
        driver_number,
        lap_number,
        case when is_position_majority then jolpica_position else position end as position,
        case when is_time_majority then jolpica_lap_time_ms else lap_time_ms end as lap_time_ms,
        gap_to_leader_ms,
        sector_1_ms,
        sector_2_ms,
        sector_3_ms,
        stint,
        tyre_compound,
        tyre_age_laps,
        null::integer as formula1db_tyre_age_laps,
        is_pit_in_lap,
        is_pit_out_lap,
        is_yellow_flag,
        is_safety_car,
        is_virtual_safety_car,
        is_red_flag,
        is_deleted,
        is_accurate,
        speed_trap_kmh,
        'fastf1' as source,
        case
            when is_time_majority then 'corrected'
            else {{ lap_validation_status(
                'lap_time_ms', 'lap_number', ['openf1_lap_time_ms', 'jolpica_lap_time_ms']
            ) }}
        end as validation_status,
        -- fastf1:sectors no aplica: aquí FastF1 es la base, no una fuente que confirma.
        {{ lap_confirmed_by(
            'lap_time_ms', [['openf1', 'openf1_lap_time_ms'], ['jolpica', 'jolpica_lap_time_ms']]
        ) }} as confirmed_by,
        list_filter(
            [
                case when is_lap_time_from_sectors then 'lap_time_ms:sectors' end,
                case when is_time_majority then 'lap_time_ms:majority' end,
                case when is_position_majority then 'position:majority' end
            ],
            x -> x is not null
        ) as corrections,
        case when not is_lap_time_from_sectors then lap_time_ms end as original_lap_time_ms,
        position as original_position,
        lap_number as original_lap_number,
        'not_applicable' as lap_numbering_status
    from fastf1_resolved
),

-- 5. Carreras sin formula1db ni FastF1 (DAT-06): OpenF1 es la base salvo que Jolpica la sustituya
--    (int_openf1_race_reliability) o sea lo único que hay. Las vueltas de OpenF1 se contrastan con
--    Jolpica; las de una carrera con OpenF1 no fiable y Jolpica incompleta se publican igualmente,
--    con el aviso openf1_reliable_races.
openf1_attributed as (
    select * from {{ ref('int_openf1_laps') }} where driver_id is not null
),

backup_races as (
    select distinct race_id
    from (
        select race_id from openf1_attributed
        union all
        select race_id from jolpica_laps
    )
    where race_id not in (select race_id from formula1db_drivers)
        and race_id not in (select race_id from {{ ref('int_fastf1_laps') }})
),

jolpica_races as (
    select race_id
    from backup_races
    where race_id in (select race_id from reliability where is_replaced_by_jolpica)
        or race_id not in (select race_id from openf1_attributed)
),

openf1_fill as (
    select
        openf1.race_id,
        openf1.driver_id,
        openf1.driver_number,
        openf1.lap_number,
        openf1.position,
        openf1.lap_time_ms,
        openf1.gap_to_leader_ms,
        openf1.sector_1_ms,
        openf1.sector_2_ms,
        openf1.sector_3_ms,
        openf1.stint,
        openf1.tyre_compound,
        openf1.tyre_age_laps,
        null::integer as formula1db_tyre_age_laps,
        openf1.is_pit_in_lap,
        openf1.is_pit_out_lap,
        openf1.is_yellow_flag,
        openf1.is_safety_car,
        openf1.is_virtual_safety_car,
        openf1.is_red_flag,
        openf1.is_deleted,
        openf1.is_accurate,
        openf1.speed_trap_kmh,
        'openf1' as source,
        {{ lap_validation_status(
            'openf1.lap_time_ms', 'openf1.lap_number', ['jolpica.lap_time_ms']
        ) }} as validation_status,
        {{ lap_confirmed_by('openf1.lap_time_ms', [['jolpica', 'jolpica.lap_time_ms']]) }}
            as confirmed_by,
        list_filter(
            [
                case when openf1.is_lap_time_from_sectors then 'lap_time_ms:sectors' end,
                case when openf1.position_status = 'timing_only' then 'position:timing' end
            ],
            x -> x is not null
        ) as corrections,
        case when not openf1.is_lap_time_from_sectors then openf1.lap_time_ms end
            as original_lap_time_ms,
        openf1.position as original_position,
        openf1.lap_number as original_lap_number,
        'not_applicable' as lap_numbering_status
    from openf1_attributed as openf1
    left join jolpica_laps as jolpica
        using (race_id, driver_number, lap_number)
    where openf1.race_id in (select race_id from backup_races)
        and openf1.race_id not in (select race_id from jolpica_races)
),

-- 6. Jolpica como base de la carrera: sustituye a OpenF1 o es lo único que hay. Solo trae tiempo
--    y posición; OpenF1, si es fiable, la contrasta.
jolpica_race_fill as (
    select
        jolpica.race_id,
        jolpica.driver_id,
        jolpica.driver_number,
        jolpica.lap_number,
        jolpica.position,
        jolpica.lap_time_ms,
        {{ lap_validation_status(
            'jolpica.lap_time_ms', 'jolpica.lap_number', ['openf1.lap_time_ms']
        ) }} as validation_status,
        {{ lap_confirmed_by('jolpica.lap_time_ms', [['openf1', 'openf1.lap_time_ms']]) }}
            as confirmed_by
    from jolpica_laps as jolpica
    left join openf1_laps as openf1
        using (race_id, driver_number, lap_number)
    where jolpica.race_id in (select race_id from jolpica_races)
),

base_laps as (
    select race_id, driver_number, lap_number from formula1db_final
    union all
    select race_id, driver_number, lap_number from fastf1_fill
    union all
    select race_id, driver_number, lap_number from openf1_fill
),

base_drivers as (
    select distinct race_id, driver_number from base_laps
),

-- 7. Jolpica rellena vueltas sueltas que faltan en la base de la carrera (formula1db, FastF1 u
--    OpenF1), dentro de las vueltas oficiales de los pilotos presentes (N8). Nunca pisa una
--    vuelta existente.
jolpica_fill as (
    select
        jolpica.race_id,
        jolpica.driver_id,
        jolpica.driver_number,
        jolpica.lap_number,
        jolpica.position,
        jolpica.lap_time_ms,
        {{ lap_validation_status(
            'jolpica.lap_time_ms', 'jolpica.lap_number', ['openf1.lap_time_ms']
        ) }} as validation_status,
        {{ lap_confirmed_by('jolpica.lap_time_ms', [['openf1', 'openf1.lap_time_ms']]) }}
            as confirmed_by
    from jolpica_laps as jolpica
    inner join base_drivers using (race_id, driver_number)
    inner join official using (race_id, driver_id)
    left join openf1_laps as openf1
        using (race_id, driver_number, lap_number)
    where jolpica.lap_number <= official.official_laps
        and not exists (
            select 1
            from base_laps as present
            where present.race_id = jolpica.race_id
                and present.driver_number = jolpica.driver_number
                and present.lap_number = jolpica.lap_number
        )
),

-- Filas de Jolpica (base o relleno): solo tiempo y posición, el resto de columnas nulas.
jolpica_rows as (
    select
        race_id,
        driver_id,
        driver_number,
        lap_number,
        position,
        lap_time_ms,
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
        'jolpica' as source,
        validation_status,
        confirmed_by,
        []::varchar[] as corrections,
        lap_time_ms as original_lap_time_ms,
        position as original_position,
        lap_number as original_lap_number,
        'not_applicable' as lap_numbering_status
    from (
        select * from jolpica_race_fill
        union all
        select * from jolpica_fill
    )
),

unioned as (
    select * from formula1db_final
    union all by name
    select * from fastf1_fill
    union all by name
    select * from openf1_fill
    union all by name
    select * from jolpica_rows
),

tyres as (
    select race_id, pirelli_compound, relative_compound
    from {{ ref('int_tyre_compound_mapping') }}
    where is_consistent
),

races as (
    select race_id, season from {{ ref('stg_f1db__races') }}
),

-- 8. Bandera roja en la vuelta que contiene la suspensión (regla en la cabecera).
race_pace as (
    select race_id, median(lap_time_ms) as median_lap_time_ms
    from unioned
    group by race_id
),

long_laps as (
    select unioned.race_id, unioned.driver_id, unioned.driver_number, unioned.lap_number
    from unioned
    inner join race_pace using (race_id)
    where unioned.lap_time_ms > greatest(
        {{ var('red_flag_min_lap_ms') }},
        {{ var('red_flag_median_factor') }} * race_pace.median_lap_time_ms
    )
),

lap_summary as (
    select
        race_id,
        lap_number,
        bool_or(coalesce(is_red_flag, false)) as has_red_flag
    from unioned
    group by all
),

long_laps_per_lap as (
    select race_id, lap_number, count(*) as drivers
    from long_laps
    group by all
),

suspension_laps as (
    select long_laps.race_id, long_laps.driver_id, long_laps.driver_number, long_laps.lap_number
    from long_laps
    inner join long_laps_per_lap using (race_id, lap_number)
    where long_laps_per_lap.drivers >= {{ var('red_flag_min_drivers') }}
        or exists (
            select 1
            from lap_summary
            where lap_summary.race_id = long_laps.race_id
                and lap_summary.has_red_flag
                and lap_summary.lap_number
                between long_laps.lap_number - {{ var('red_flag_window_laps') }}
                and long_laps.lap_number
        )
),

flagged as (
    select
        unioned.* replace (
            case when suspension.race_id is not null then true else unioned.is_red_flag end
                as is_red_flag,
            case
                when suspension.race_id is not null and not coalesce(unioned.is_red_flag, false)
                    then list_append(unioned.corrections, 'is_red_flag:suspension')
                else unioned.corrections
            end as corrections,
            unioned.gap_to_leader_ms::bigint as gap_to_leader_ms
        )
    from unioned
    left join suspension_laps as suspension
        on unioned.race_id = suspension.race_id
        and unioned.driver_id is not distinct from suspension.driver_id
        and unioned.driver_number = suspension.driver_number
        and unioned.lap_number = suspension.lap_number
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
from flagged as unioned
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
