"""Una carrera: resultados, clasificación, vuelta a vuelta, neumáticos, paradas, dirección de
carrera, meteo y telemetría."""

from typing import Literal

from fastapi import APIRouter, Query

from api.app.codes import race_driver_codes
from api.app.deps import DB, not_found, split_ids
from api.app.routers.seasons import RACE_SUMMARY_SQL
from api.app.schemas import (
    Lap,
    PitLanePass,
    PitStop,
    QualifyingResult,
    RaceControlMessage,
    RaceDetail,
    RaceResult,
    Stint,
    TelemetryLap,
    WeatherSample,
)

router = APIRouter(prefix="/races", tags=["Carreras"])

DRIVERS_PARAM = Query(None, description="Identificadores de piloto separados por comas")


def _require_race(db: DB, race_id: int) -> None:
    if not db.query_one("select 1 from gold.dim_race where race_id = ?", [race_id]):
        raise not_found(f"la carrera {race_id}")


@router.get("/{race_id}", response_model=RaceDetail, summary="Datos de la carrera y el circuito")
def get_race(race_id: int, db: DB):
    race = db.query_one(
        f"""
        select base.*, r.race_time_utc, r.laps, r.distance as distance_km, r.circuit_type,
               r.direction, r.course_length as course_length_km, r.turns,
               r.circuit_latitude as latitude, r.circuit_longitude as longitude,
               r.is_season_final_race,
               r.sprint_qualifying_format is not null as has_sprint_qualifying
        from ({RACE_SUMMARY_SQL}) as base
        join gold.dim_race as r using (race_id)
        where base.race_id = ?
        """,
        [race_id],
    )
    if not race:
        raise not_found(f"la carrera {race_id}")
    return race


@router.get("/{race_id}/results", response_model=list[RaceResult], summary="Resultado")
def race_results(race_id: int, db: DB, session: Literal["race", "sprint"] = "race"):
    _require_race(db, race_id)
    # Los códigos se calculan con todos los pilotos de la carrera (carrera y sprint), así que un
    # piloto lleva el mismo en todas las pestañas.
    codes = race_driver_codes(
        [
            (row["driver_id"], row["abbreviation"], row["first_name"], row["started"])
            for row in db.query(
                """
                select
                    r.driver_id, any_value(d.abbreviation) as abbreviation,
                    any_value(d.first_name) as first_name,
                    coalesce(bool_or(r.laps > 0 or r.grid_position is not null), false)
                        as started
                from gold.fact_race_result as r
                join gold.dim_driver as d using (driver_id)
                where r.race_id = ?
                group by r.driver_id
                """,
                [race_id],
            )
        ]
    )
    rows = db.query(
        """
        select
            r.position_number as position, r.position_text, r.driver_number, r.driver_id,
            d.name as driver_name, r.constructor_id, c.name as constructor_name,
            r.grid_position, r.grid_position_text, r.laps, r.time_ms, r.gap_ms, r.gap_laps,
            r.points, r.positions_gained, r.pit_stops, r.reason_retired, r.is_fastest_lap,
            coalesce(r.overridden_columns, []) as corrected_fields
        from gold.fact_race_result as r
        join gold.dim_driver as d using (driver_id)
        join gold.dim_constructor as c using (constructor_id)
        where r.race_id = ? and r.session_type = ?
        order by r.position_display_order
        """,
        [race_id, session.upper()],
    )
    return [row | {"driver_code": codes.get(row["driver_id"])} for row in rows]


@router.get("/{race_id}/qualifying", response_model=list[QualifyingResult], summary="Clasificación")
def qualifying(
    race_id: int, db: DB, session: Literal["qualifying", "sprint_qualifying"] = "qualifying"
):
    _require_race(db, race_id)
    return db.query(
        """
        select
            q.position_number as position, q.position_text, q.driver_number, q.driver_id,
            d.name as driver_name, q.constructor_id, c.name as constructor_name,
            q.q1_ms, q.q2_ms, q.q3_ms, q.best_time_ms, q.gap_to_pole_pct
        from gold.fact_qualifying_result as q
        join gold.dim_driver as d using (driver_id)
        join gold.dim_constructor as c using (constructor_id)
        where q.race_id = ? and q.session_type = ?
        order by q.position_display_order
        """,
        [race_id, session.upper()],
    )


@router.get(
    "/{race_id}/laps",
    response_model=list[Lap],
    summary="Vuelta a vuelta: posición, tiempos, neumático y estado de pista",
)
def laps(race_id: int, db: DB, drivers: str | None = DRIVERS_PARAM):
    _require_race(db, race_id)
    ids = split_ids(drivers, limit=30)
    return db.query(
        """
        select
            driver_id, driver_number, lap_number as lap, position, lap_time_ms, gap_to_leader_ms,
            sector_1_ms, sector_2_ms, sector_3_ms,
            coalesce(tyre_compound_relative, nullif(tyre_compound, '')) as compound,
            tyre_compound_pirelli as compound_pirelli, tyre_age_laps,
            is_pit_in_lap, is_pit_out_lap, is_yellow_flag, is_safety_car, is_virtual_safety_car,
            is_red_flag, source, validation_status
        from gold.fact_laptimes
        where race_id = ? and (? is null or list_contains(?, driver_id))
            and not is_incomplete_lap
        order by lap_number, position nulls last, driver_id, driver_number
        """,
        [race_id, ids, ids],
    )


@router.get(
    "/{race_id}/stints",
    response_model=list[Stint],
    summary="Estrategia de neumáticos: tramos entre paradas con su compuesto",
)
def stints(race_id: int, db: DB):
    # Un piloto que condujo dos coches en la misma carrera (años 50) tiene un tramo por coche: la
    # ventana va por piloto y dorsal para no mezclar las vueltas de los dos.
    _require_race(db, race_id)
    return db.query(
        """
        with laps as (
            select
                driver_id, driver_number, lap_number,
                coalesce(tyre_compound_relative, nullif(tyre_compound, '')) as compound,
                tyre_age_laps,
                -- Empieza un tramo nuevo tras entrar en boxes o si cambia el compuesto.
                case when lag(lap_number) over w is null
                          or coalesce(lag(is_pit_in_lap) over w, false)
                          or lag(coalesce(tyre_compound_relative, tyre_compound)) over w
                             is distinct from coalesce(tyre_compound_relative, tyre_compound)
                     then 1 else 0 end as is_new_stint
            from gold.fact_laptimes
            where race_id = ? and not is_incomplete_lap
            window w as (partition by driver_id, driver_number order by lap_number)
        ),
        numbered as (
            select *, sum(is_new_stint) over (
                partition by driver_id, driver_number order by lap_number rows unbounded preceding
            ) as stint
            from laps
        )
        select
            driver_id, driver_number, stint::integer as stint, any_value(compound) as compound,
            min(lap_number) as start_lap, max(lap_number) as end_lap, count(*) as laps,
            arg_min(tyre_age_laps, lap_number) as tyre_age_at_start
        from numbered
        group by driver_id, driver_number, stint
        order by driver_id, min(lap_number), stint
        """,
        [race_id],
    )


@router.get("/{race_id}/pitstops", response_model=list[PitStop], summary="Paradas en boxes")
def pit_stops(race_id: int, db: DB):
    _require_race(db, race_id)
    return db.query(
        """
        select p.driver_id, d.name as driver_name, p.constructor_id, p.stop_number as stop,
               p.lap_number as lap, p.time_ms as duration_ms
        from gold.fact_pit_stops as p
        join gold.dim_driver as d using (driver_id)
        where p.race_id = ?
        order by p.lap_number, p.stop_number, p.driver_id
        """,
        [race_id],
    )


@router.get(
    "/{race_id}/pit-lane-passes",
    response_model=list[PitLanePass],
    summary="Todas las entradas al pit lane, tipificadas (paradas, Safety Car, sanciones...)",
)
def pit_lane_passes(race_id: int, db: DB):
    _require_race(db, race_id)
    return db.query(
        """
        select driver_id, driver_number, lap_number as lap, pass_type, stop_number as stop
        from gold.fact_pit_lane_passes
        where race_id = ?
        order by lap_number, driver_id, driver_number
        """,
        [race_id],
    )


@router.get(
    "/{race_id}/race-control",
    response_model=list[RaceControlMessage],
    summary="Mensajes de dirección de carrera: banderas, Safety Car, VSC, sanciones (2018+)",
)
def race_control(
    race_id: int,
    db: DB,
    category: str | None = Query(
        None, description="Solo esta categoría (Flag, SafetyCar, Drs, CarEvent, Other...)"
    ),
    flag: str | None = Query(None, description="Solo esta bandera (RED, YELLOW, BLUE...)"),
):
    _require_race(db, race_id)
    return db.query(
        """
        select
            message_seq as seq, source, message_utc as utc, session_time_ms,
            lap_number as lap, category, flag, scope, sector, driver_number, driver_id,
            message, event
        from gold.fact_race_control_message
        where race_id = ?
            and (?::varchar is null or category = ?)
            and (?::varchar is null or flag = ?)
        order by message_seq
        """,
        [race_id, category, category, flag, flag],
    )


@router.get(
    "/{race_id}/weather",
    response_model=list[WeatherSample],
    summary="Meteo de la carrera, una muestra por minuto (2018+)",
)
def weather(race_id: int, db: DB):
    _require_race(db, race_id)
    return db.query(
        """
        select
            sample_seq as seq, source, sample_utc as utc, session_time_ms, air_temperature_c,
            track_temperature_c, humidity_pct, pressure_mbar, is_raining, wind_direction_deg,
            wind_speed_ms
        from gold.fact_weather_sample
        where race_id = ?
        order by sample_seq
        """,
        [race_id],
    )


@router.get(
    "/{race_id}/telemetry",
    response_model=list[TelemetryLap],
    summary="Telemetría de la vuelta más rápida de clasificación (2024+)",
)
def telemetry(
    race_id: int,
    db: DB,
    drivers: str = Query(..., description="De 1 a 4 identificadores de piloto, por comas"),
):
    _require_race(db, race_id)
    ids = split_ids(drivers, limit=4)
    rows = db.query(
        """
        select
            driver_id, any_value(driver_code) as driver_code,
            any_value(lap_time_ms) as lap_time_ms, any_value(tyre_compound) as tyre_compound,
            list(distance_m order by distance_m) as distance_m,
            list(speed_kmh order by distance_m) as speed_kmh,
            list(throttle_pct order by distance_m) as throttle_pct,
            list(is_braking order by distance_m) as is_braking,
            list(gear order by distance_m) as gear,
            list(x order by distance_m) as x,
            list(y order by distance_m) as y
        from gold.fact_quali_telemetry
        where race_id = ? and list_contains(?, driver_id)
        group by driver_id
        """,
        [race_id, ids],
    )
    if not rows:
        raise not_found(f"telemetría de esos pilotos en la carrera {race_id}")
    order = {driver: i for i, driver in enumerate(ids)}
    return sorted(rows, key=lambda row: order.get(row["driver_id"], len(order)))
