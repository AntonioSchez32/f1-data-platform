{#- Cuadro de mando de calidad: una fila por comprobación con el porcentaje de concordancia y el
    umbral mínimo aceptado. El test assert_quality_thresholds falla si alguna queda por debajo. -#}
with checks as (
    select
        'formula1db_vs_fastf1_lap_time' as check_id,
        'Tiempo por vuelta idéntico (±1 ms) entre formula1db.com y FastF1' as description,
        count(is_time_match) as compared,
        count(*) filter (where is_time_match) as matched,
        98.0 as min_match_pct
    from {{ ref('qa_formula1db_vs_fastf1_laps') }}

    union all
    select
        'formula1db_vs_fastf1_position',
        'Posición en pista por vuelta entre formula1db.com y FastF1',
        count(is_position_match),
        count(*) filter (where is_position_match),
        98.0
    from {{ ref('qa_formula1db_vs_fastf1_laps') }}

    union all
    select
        'formula1db_vs_fastf1_tyre',
        'Compuesto de neumático por vuelta entre formula1db.com y FastF1',
        count(is_tyre_match),
        count(*) filter (where is_tyre_match),
        98.0
    from {{ ref('qa_formula1db_vs_fastf1_laps') }}

    union all
    select
        'formula1db_vs_jolpica_coverage',
        'Vueltas de formula1db.com que también existen en Jolpica (1996-2024)',
        count(*),
        count(*) filter (where is_matched),
        98.0
    from {{ ref('qa_formula1db_vs_jolpica_laps') }}

    union all
    select
        'formula1db_vs_jolpica_lap_time',
        'Tiempo por vuelta idéntico (±1 ms) entre formula1db.com y Jolpica',
        count(is_time_match),
        count(*) filter (where is_time_match),
        98.0
    from {{ ref('qa_formula1db_vs_jolpica_laps') }}

    union all
    select
        'formula1db_vs_jolpica_position',
        'Posición en pista por vuelta entre formula1db.com y Jolpica',
        count(is_position_match),
        count(*) filter (where is_position_match),
        98.0
    from {{ ref('qa_formula1db_vs_jolpica_laps') }}

    union all
    select
        'fastf1_vs_f1db_race_position',
        'Posición final de los clasificados entre FastF1 y F1DB',
        count(is_position_match),
        count(*) filter (where is_position_match),
        100.0
    from {{ ref('qa_fastf1_vs_f1db_results') }}

    union all
    select
        'fastf1_vs_f1db_points',
        'Puntos por carrera entre FastF1 y F1DB',
        count(is_points_match),
        count(*) filter (where is_points_match),
        100.0
    from {{ ref('qa_fastf1_vs_f1db_results') }}

    union all
    select
        'fastf1_vs_f1db_grid',
        'Posición de parrilla entre FastF1 y F1DB',
        count(is_grid_match),
        count(*) filter (where is_grid_match),
        99.0
    from {{ ref('qa_fastf1_vs_f1db_results') }}

    union all
    select
        'fastf1_vs_f1db_qualifying',
        'Tiempos de Q1/Q2/Q3 entre FastF1 y F1DB',
        count(is_time_match),
        count(*) filter (where is_time_match),
        99.0
    from {{ ref('qa_fastf1_vs_f1db_qualifying') }}

    union all
    select
        'f1db_pit_stops_in_laps_' || source,
        'Paradas de F1DB con su entrada a boxes en las vueltas (' || source || ')',
        count(*),
        count(*) filter (where is_match),
        -- Las carreras sin formula1db ni FastF1 (base OpenF1 o Jolpica) no bloquean la
        -- publicación (decisión 26): su control es informativo y las notas de la release lo
        -- anuncian (NOTICE_CHECKS).
        case when source in ('openf1', 'jolpica') then null else 99.0 end
    from {{ ref('qa_pit_stops') }}
    group by source

    union all
    select
        'fastest_lap_' || source,
        'Vuelta más rápida de cada piloto (' || source || ') frente a la oficial de F1DB',
        count(*),
        count(*) filter (where is_match),
        case source when 'fastf1' then 99.0 when 'openf1' then null when 'jolpica' then null
            else 95.0 end
    from {{ ref('qa_fastest_laps') }}
    group by source

    union all
    select
        'lap_completeness_' || source,
        'Pilotos con todas sus vueltas oficiales registradas ('
            || source || ', sin coches compartidos ni descalificados)',
        count(*),
        count(*) filter (where status = 'ok'),
        case source when 'fastf1' then 99.0 when 'openf1' then null when 'jolpica' then null
            else 97.0 end
    from {{ ref('int_lap_completeness') }}
    where status not in ('shared_car', 'disqualified')
    group by source

    union all
    select
        'lap_driver_attribution',
        'Vueltas asignadas a un piloto de F1DB',
        count(*),
        count(driver_id),
        99.9
    from {{ ref('int_laptimes') }}

    union all
    select
        'lap_time_' || validation_status,
        'Vueltas con estado de validación ' || validation_status || ' (int_laptimes)',
        (select count(*) from {{ ref('int_laptimes') }}),
        count(*),
        null
    from {{ ref('int_laptimes') }}
    group by validation_status

    union all
    select
        'lap_source_' || source,
        'Vueltas cuya fuente es ' || source,
        (select count(*) from {{ ref('int_laptimes') }}),
        count(*),
        null
    from {{ ref('int_laptimes') }}
    group by source

    union all
    select
        'lap_numbering_' || numbering_status,
        'Carreras con numeración de vueltas ' || numbering_status || ' frente a F1DB',
        (select count(*) from {{ ref('int_lap_numbering') }}),
        count(*),
        null
    from {{ ref('int_lap_numbering') }}
    group by numbering_status

    union all
    select
        'pit_lane_pass_' || pass_type,
        'Entradas al pit lane de tipo ' || pass_type,
        (select count(*) from {{ ref('fact_pit_lane_passes') }}),
        count(*),
        null
    from {{ ref('fact_pit_lane_passes') }}
    group by pass_type

    union all
    select
        'tyre_mapping_consistent',
        'Carreras 2019-2023 con equivalencia coherente entre compuesto real y relativo',
        count(distinct race_id),
        count(distinct race_id) filter (where is_consistent),
        100.0
    from {{ ref('int_tyre_compound_mapping') }}

    union all
    select
        'f1db_overrides_' || decision,
        'Celdas de F1DB corregidas con evidencia (decisión ' || decision || ')',
        count(*),
        count(*) filter (where applied),
        100.0
    from (
        select
            overrides.decision,
            exists (
                select 1
                from {{ ref('int_race_data_corrected') }} as rows
                where rows.race_id = overrides.race_id
                    and rows.session_type = overrides.session_type
                    and list_contains(
                        case overrides.action
                            when 'set' then rows.overridden_columns
                            else rows.disputed_columns
                        end,
                        overrides.column_name
                    )
                    and rows.driver_id = overrides.driver_id
            ) as applied
        from {{ ref('race_data_overrides') }} as overrides
    )
    group by decision

    -- OpenF1 (2023+): respaldo y contraste de FastF1 (decisiones 20-26). Un defecto de OpenF1 no
    -- debe impedir publicar: las carreras en que sus tiempos no concuerdan con la fuente publicada
    -- (int_openf1_race_reliability; Australia 2026, con las vueltas desplazadas) quedan fuera de
    -- los controles con umbral y se cuentan en openf1_reliable_races, y la cobertura (huecos como
    -- las vueltas 1-24 de Miami 2025) es informativa. Los controles con umbral miden la calidad de
    -- OpenF1 donde se usa.
    union all
    select
        'openf1_reliable_races',
        'Carreras cuyas vueltas de OpenF1 concuerdan con la fuente publicada (al menos el '
            || {{ var('openf1_min_race_time_agreement_pct') }} || ' % de los tiempos)',
        count(*) filter (where compared_laps > 0),
        count(*) filter (where compared_laps > 0 and is_reliable),
        null
    from {{ ref('int_openf1_race_reliability') }}

    union all
    select
        'openf1_vs_fastf1_coverage',
        'Vueltas de FastF1 que también están en OpenF1 (carreras con las dos)',
        count(*) filter (where is_in_fastf1),
        count(*) filter (where is_in_fastf1 and is_in_openf1),
        null
    from {{ ref('qa_openf1_vs_fastf1_laps') }}

    union all
    select
        'openf1_vs_fastf1_lap_time',
        'Tiempo por vuelta idéntico (±1 ms) entre OpenF1 y FastF1 (carreras fiables)',
        count(is_time_match),
        count(*) filter (where is_time_match),
        99.0
    from {{ ref('qa_openf1_vs_fastf1_laps') }}
    where is_reliable_race

    union all
    select
        'openf1_vs_fastf1_position',
        'Posición al acabar la vuelta (OpenF1, endpoint position) frente a FastF1 (carreras '
            || 'fiables)',
        count(is_position_match),
        count(*) filter (where is_position_match),
        99.0
    from {{ ref('qa_openf1_vs_fastf1_laps') }}
    where is_reliable_race

    union all
    select
        'openf1_vs_fastf1_tyre',
        'Compuesto de neumático por vuelta entre OpenF1 y FastF1 (carreras fiables)',
        count(is_compound_match),
        count(*) filter (where is_compound_match),
        98.0
    from {{ ref('qa_openf1_vs_fastf1_laps') }}
    where is_reliable_race

    union all
    select
        'openf1_vs_fastf1_' || item,
        'Concordancia de ' || label || ' por vuelta entre OpenF1 y FastF1 (carreras fiables)',
        count(is_match),
        count(*) filter (where is_match),
        null
    from (
        select
            unnest([
                'stint', 'tyre_age', 'pit_in', 'safety_car', 'virtual_safety_car', 'red_flag'
            ]) as item,
            unnest([
                'tramo de neumático', 'vida del neumático', 'entrada a boxes',
                'Safety Car (dirección de carrera)', 'VSC (dirección de carrera)',
                'bandera roja (dirección de carrera)'
            ]) as label,
            unnest([
                is_stint_match, is_tyre_age_match, is_pit_in_match, is_safety_car_match,
                is_virtual_safety_car_match, is_red_flag_match
            ]) as is_match
        from {{ ref('qa_openf1_vs_fastf1_laps') }}
        where is_reliable_race
    )
    group by all

    union all
    select
        'openf1_position_vs_timing',
        'Vueltas de OpenF1 cuya posición (endpoint position) coincide con el orden de paso por meta',
        count(*) filter (where position_status in ('agreed', 'disputed')),
        count(*) filter (where position_status = 'agreed'),
        99.0
    from {{ ref('int_openf1_laps') }}

    union all
    select
        'openf1_lap_completeness',
        'Pilotos con todas sus vueltas oficiales en OpenF1 (sin descalificados)',
        count(*),
        count(*) filter (where is_laps_complete),
        null
    from {{ ref('qa_openf1_vs_f1db') }}

    union all
    select
        'openf1_vs_f1db_race_position',
        'Posición final de los clasificados entre OpenF1 (session_result) y F1DB',
        count(is_position_match),
        count(*) filter (where is_position_match),
        98.0
    from {{ ref('qa_openf1_vs_f1db') }}
    where is_reliable_race

    union all
    select
        'openf1_vs_f1db_pit_stops',
        'Paradas de F1DB con su entrada a boxes en las vueltas de OpenF1 (carreras fiables)',
        coalesce(sum(f1db_stops), 0)::bigint,
        coalesce(sum(matched_stops), 0)::bigint,
        98.0
    from {{ ref('qa_openf1_vs_f1db') }}
    where is_reliable_race

    -- Avisos: filas de OpenF1 que no se cruzan con F1DB y no se publican. No bloquean (decisión
    -- 26); el manifiesto y las notas de la release los anuncian (NOTICE_CHECKS en snapshot.py).
    union all
    select
        'openf1_lap_driver_attribution',
        'Vueltas de OpenF1 con piloto de F1DB (las que no, no se publican)',
        count(*),
        count(driver_id),
        null
    from {{ ref('int_openf1_laps') }}

    union all
    select
        'openf1_race_session_matching',
        'Sesiones de carrera de OpenF1 ya disputadas casadas con una carrera de F1DB',
        count(*),
        count(race_id),
        null
    from {{ ref('int_openf1_sessions') }}
    where is_race and date_end_utc < now()::timestamp

    -- Jolpica (decisiones 49-53). Avisos (NOTICE_CHECKS): vueltas sin piloto de F1DB (F1DB aún no
    -- tiene la carrera), carreras publicadas sin vueltas de Jolpica (Jolpica vacía o con retraso;
    -- normal el lunes después de un GP) y carreras solo con OpenF1 que no se han podido contrastar.
    union all
    select
        'jolpica_lap_driver_attribution',
        'Vueltas de Jolpica con piloto de F1DB (las que no, no se publican)',
        (select count(*) from {{ ref('stg_jolpica__lap_times') }}),
        count(driver_id),
        null
    from {{ ref('int_jolpica_laps') }}

    union all
    select
        'jolpica_lap_coverage',
        'Carreras con vueltas publicadas desde 1996 que tienen vueltas de Jolpica',
        count(*),
        count(*) filter (
            where race_id in (
                select race_id from {{ ref('int_jolpica_laps') }} where driver_id is not null
            )
        ),
        null
    from (
        select distinct race_id
        from {{ ref('int_laptimes') }}
        where race_id in (select race_id from {{ ref('stg_f1db__races') }} where season >= 1996)
    )

    union all
    select
        'openf1_unverified_races',
        'Carreras solo con OpenF1 contrastadas con Jolpica (DAT-06)',
        count(*) filter (where coalesce(reference_source, 'jolpica') = 'jolpica'),
        count(*) filter (where reference_source = 'jolpica' and compared_laps > 0),
        null
    from {{ ref('int_openf1_race_reliability') }}

    -- Controles informativos frente a F1DB (decisión 52) y de los cambios de Jolpica frente a
    -- Ergast (decisión 53). No bloquean ni salen en las notas de la release: las diferencias
    -- históricas darían el mismo aviso en todas.
    union all
    select
        'jolpica_vs_f1db_' || case session_type when 'R' then 'race' else 'sprint' end
            || '_results',
        'Resultados de ' || case session_type when 'R' then 'carrera' else 'sprint' end
            || ' de Jolpica iguales a los de F1DB (clasificación, puntos y vueltas)',
        count(is_match),
        count(*) filter (where is_match),
        null
    from {{ ref('qa_jolpica_vs_f1db_results') }}
    group by session_type

    union all
    select
        'jolpica_vs_f1db_grid',
        'Posición de parrilla entre Jolpica y F1DB (carrera y sprint, sin salidas del pit lane)',
        count(is_grid_match),
        count(*) filter (where is_grid_match),
        null
    from {{ ref('qa_jolpica_vs_f1db_results') }}

    union all
    select
        'jolpica_vs_f1db_results_coverage',
        'Resultados de Jolpica con su fila en F1DB (piloto y dorsal)',
        count(*),
        count(*) filter (where is_matched),
        null
    from {{ ref('qa_jolpica_vs_f1db_results') }}

    union all
    select
        'jolpica_vs_f1db_qualifying',
        'Tiempos de Q1/Q2/Q3 (±1 ms) entre Jolpica y F1DB',
        count(is_time_match),
        count(*) filter (where is_time_match),
        null
    from {{ ref('qa_jolpica_vs_f1db_qualifying') }}

    union all
    select
        'jolpica_vs_f1db_pit_stops',
        'Paradas de F1DB y Jolpica con la misma vuelta y duración (±1 ms) desde 2011',
        count(*),
        count(*) filter (where is_match),
        null
    from {{ ref('qa_jolpica_vs_f1db_pit_stops') }}

    union all
    select
        'position_majority_withheld',
        'Vueltas sin disputas de posición (los dos votantes de la mayoría coinciden contra la '
            || 'posición publicada y no se corrige porque repetiría posiciones en la vuelta)',
        (select count(*) from {{ ref('int_laptimes') }} where position is not null),
        (select count(*) from {{ ref('int_laptimes') }} where position is not null) - count(*),
        null
    from {{ ref('qa_position_majority_withheld') }}

    union all
    select
        'jolpica_vs_ergast_laps',
        'Vueltas de 1996-2022 iguales en Jolpica y en el volcado de Ergast de 2022',
        count(*),
        count(*) filter (where change_type = 'same'),
        null
    from {{ ref('qa_jolpica_vs_ergast_laps') }}

    union all
    select
        'red_flag_messages_on_laps',
        'Banderas rojas de la dirección de carrera con alguna vuelta marcada (sin las mostradas '
            || 'antes de la vuelta 1)',
        count(*),
        count(*) filter (where is_lap_flagged),
        100.0
    from {{ ref('qa_red_flags') }}
    where phase = 'race'

    union all
    select
        'formula1db_race_alignment',
        'Carreras de formula1db.com cuya ronda etiquetada coincide con su contenido',
        count(*),
        count(*) filter (where not is_realigned),
        null
    from {{ ref('int_formula1db_race_alignment') }}
)

select
    *,
    round(100.0 * matched / nullif(compared, 0), 2) as match_pct,
    case
        when min_match_pct is null then 'INFO'
        when compared = 0 then 'NO_DATA'
        when 100.0 * matched / compared >= min_match_pct then 'PASS'
        else 'FAIL'
    end as status
from checks
