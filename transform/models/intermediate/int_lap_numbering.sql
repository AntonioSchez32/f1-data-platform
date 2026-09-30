{#-
    Numeración de vueltas de formula1db.com frente a F1DB, por carrera (decisión N5).

    En carreras relanzadas o disputadas en dos partes, las fuentes pueden contar las vueltas desde
    salidas distintas. El desfase (vuelta de formula1db - vuelta de F1DB) se estima con dos
    evidencias independientes: la vuelta rápida de cada piloto (mismo tiempo, ±1 ms) y cada parada
    en boxes (vuelta de entrada en formula1db más cercana). Cada evidencia necesita 3 casos.

    numbering_status:
      consistent     todas las evidencias dan desfase 0 (≥ 80 % de los casos)
      renumbered     todas dan el mismo desfase distinto de 0 (≥ 80 % de los casos): se aplica
      pit_lap_convention  vueltas rápidas con desfase 0 y paradas de F1DB una vuelta después que
                     la entrada a boxes de formula1db: F1DB apunta la vuelta en la que se pierde
                     el tiempo parado. Es una convención, no un error (España 1994)
      inconsistent   las evidencias no cuadran entre sí o ninguna llega al 80 %: se conserva la
                     numeración y se marca

    Empates: en cada caso se elige el desfase más cercano a 0 y, a igualdad, el menor; en cada
    evidencia, el desfase con más casos, luego el más cercano a 0 y luego el menor. Así la salida
    no depende del orden de lectura (antes, arg_min/arg_max sin desempate).

    Revisión de C1 (2026): Pacífico 1994 y São Paulo 2023 tenían desfase 0 en las dos evidencias,
    pero solo el 76 % y el 78 % de las paradas cuadraban, así que pasan de consistent a
    inconsistent. No es un problema de numeración (las vueltas rápidas cuadran al 100 %): en
    Pacífico 1994, 10 de las 41 paradas de F1DB siguen la convención de España 1994 (una vuelta
    después de la entrada a boxes); en São Paulo 2023, la bandera roja de la vuelta 1 hizo que
    F1DB apuntara 15 paradas en la vuelta 1 y formula1db la entrada en la 2. Solo cambia la
    etiqueta: applied_lap_shift sigue en 0 y fact_pit_lane_passes aplica un desfase de paradas 0.

    Pendiente para otra iteración (revisión de 2026): en San Marino y Japón 1994 las paradas de
    F1DB y en Bélgica 2001 sus vueltas rápidas están desfasadas; se propuso corregir esos datos de
    F1DB en lugar de renumerar (ver docs/revision_divergencias/INFORME.md).
-#}
with laps as (
    select * from {{ ref('int_formula1db_laps') }} where driver_id is not null
),

f1db as (
    select * from {{ ref('int_race_data_corrected') }}
),

fastest_lap_offsets as (
    select
        fastest.race_id,
        'fastest_lap' as evidence,
        arg_min(
            laps.lap_number - fastest.fastest_lap_lap,
            (
                abs(laps.lap_number - fastest.fastest_lap_lap),
                laps.lap_number - fastest.fastest_lap_lap
            )
        ) as lap_offset
    from f1db as fastest
    inner join laps
        on fastest.race_id = laps.race_id
        and fastest.driver_id = laps.driver_id
        and abs(laps.lap_time_ms - fastest.fastest_lap_time_millis) <= 1
    where fastest.session_type = 'FASTEST_LAP' and fastest.fastest_lap_lap is not null
    group by fastest.race_id, fastest.driver_id, fastest.position_display_order
),

pit_stop_offsets as (
    select
        stops.race_id,
        'pit_stop' as evidence,
        arg_min(
            laps.lap_number - stops.pit_stop_lap,
            (abs(laps.lap_number - stops.pit_stop_lap), laps.lap_number - stops.pit_stop_lap)
        ) as lap_offset
    from f1db as stops
    inner join laps
        on stops.race_id = laps.race_id
        and stops.driver_id = laps.driver_id
        and laps.is_pit_in_lap
    where stops.session_type = 'PIT_STOP'
    group by stops.race_id, stops.driver_id, stops.pit_stop_stop
),

offset_counts as (
    select race_id, evidence, lap_offset, count(*) as cases
    from (select * from fastest_lap_offsets union all select * from pit_stop_offsets)
    group by all
),

per_evidence as (
    select
        race_id,
        evidence,
        sum(cases) as cases,
        arg_max(lap_offset, (cases, -abs(lap_offset), -lap_offset)) as dominant_offset,
        max(cases) / sum(cases) as dominant_share
    from offset_counts
    group by all
    having sum(cases) >= 3
),

per_race as (
    select
        race_id,
        max(dominant_offset) filter (where evidence = 'fastest_lap') as fastest_lap_offset,
        max(dominant_share) filter (where evidence = 'fastest_lap') as fastest_lap_share,
        max(dominant_offset) filter (where evidence = 'pit_stop') as pit_stop_offset,
        max(dominant_share) filter (where evidence = 'pit_stop') as pit_stop_share,
        count(distinct dominant_offset) as distinct_offsets,
        min(dominant_offset) as common_offset,
        min(dominant_share) as min_share
    from per_evidence
    group by race_id
),

official_laps as (
    select race_id, max(race_laps) as race_laps
    from f1db
    where session_type = 'RACE_RESULT'
    group by race_id
),

max_laps as (
    select race_id, max(lap_number) as max_lap from laps group by race_id
)

select
    per_race.race_id,
    per_race.fastest_lap_offset,
    per_race.fastest_lap_share,
    per_race.pit_stop_offset,
    per_race.pit_stop_share,
    case
        when per_race.distinct_offsets = 1
            and per_race.common_offset = 0
            and per_race.min_share >= 0.8
            then 'consistent'
        when coalesce(per_race.fastest_lap_offset, 0) = 0 and per_race.pit_stop_offset = -1
            and per_race.pit_stop_share >= 0.8
            then 'pit_lap_convention'
        when per_race.distinct_offsets = 1
            and per_race.min_share >= 0.8
            and max_laps.max_lap - per_race.common_offset <= official_laps.race_laps
            then 'renumbered'
        else 'inconsistent'
    end as numbering_status,
    case
        when per_race.distinct_offsets = 1
            and per_race.common_offset <> 0
            and per_race.min_share >= 0.8
            and max_laps.max_lap - per_race.common_offset <= official_laps.race_laps
            then -per_race.common_offset
        else 0
    end as applied_lap_shift
from per_race
left join official_laps using (race_id)
left join max_laps using (race_id)
