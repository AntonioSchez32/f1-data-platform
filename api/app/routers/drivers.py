"""Pilotos: listado, ficha, temporadas, resultados y comparativa con el compañero."""

from fastapi import APIRouter, Query

from api.app.deps import DB, not_found
from api.app.schemas import (
    DriverDetail,
    DriverRaceResult,
    DriverSeason,
    DriverSummary,
    TeammateComparison,
)

router = APIRouter(prefix="/drivers", tags=["Pilotos"])

SUMMARY_COLUMNS = """
    c.driver_id, c.name, c.nationality_alpha2, c.first_season, c.last_season,
    coalesce(c.race_starts, 0) as race_starts, coalesce(c.wins, 0) as wins,
    coalesce(c.podiums, 0) as podiums, coalesce(c.championships, 0) as championships
"""


def _require_driver(db: DB, driver_id: str) -> None:
    if not db.query_one("select 1 from gold.dim_driver where driver_id = ?", [driver_id]):
        raise not_found(f"el piloto {driver_id}")


@router.get("", response_model=list[DriverSummary], summary="Buscar pilotos")
def list_drivers(
    db: DB,
    search: str | None = Query(None, min_length=2, description="Parte del nombre"),
    season: int | None = Query(None, description="Solo pilotos de esta temporada"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    return db.query(
        f"""
        select {SUMMARY_COLUMNS}
        from gold.agg_driver_career as c
        where (? is null or strip_accents(lower(c.name)) like '%' || strip_accents(lower(?)) || '%')
            and (? is null or c.driver_id in (
                select driver_id from gold.agg_driver_season where season = ?))
        order by c.wins desc, c.podiums desc, c.race_starts desc, c.name
        limit ? offset ?
        """,
        [search, search, season, season, limit, offset],
    )


@router.get("/{driver_id}", response_model=DriverDetail, summary="Ficha y estadísticas de carrera")
def get_driver(driver_id: str, db: DB):
    driver = db.query_one(
        f"""
        select {SUMMARY_COLUMNS},
            d.full_name, d.abbreviation, d.permanent_number, d.date_of_birth, d.date_of_death,
            d.place_of_birth, d.nationality_country as nationality,
            coalesce(c.race_entries, 0) as race_entries,
            coalesce(c.pole_positions, 0) as pole_positions,
            coalesce(c.fastest_laps, 0) as fastest_laps,
            coalesce(c.grand_slams, 0) as grand_slams, coalesce(c.points, 0) as points,
            c.best_race_result, c.best_championship_position,
            c.laps_completed::bigint as laps_completed, c.win_rate_pct, c.podium_rate_pct
        from gold.agg_driver_career as c
        join gold.dim_driver as d using (driver_id)
        where c.driver_id = ?
        """,
        [driver_id],
    )
    if not driver:
        raise not_found(f"el piloto {driver_id}")
    return driver


@router.get(
    "/{driver_id}/seasons", response_model=list[DriverSeason], summary="Temporada a temporada"
)
def driver_seasons(driver_id: str, db: DB):
    _require_driver(db, driver_id)
    return db.query(
        """
        select season, constructor_id, constructor_name, championship_position,
               championship_position_text, points, coalesce(championship_won, false) as is_champion,
               races, wins, podiums, pole_positions, fastest_laps, best_result
        from gold.agg_driver_season
        where driver_id = ?
        order by season
        """,
        [driver_id],
    )


@router.get(
    "/{driver_id}/results",
    response_model=list[DriverRaceResult],
    summary="Resultados carrera a carrera",
)
def driver_results(driver_id: str, db: DB, season: int | None = None):
    _require_driver(db, driver_id)
    return db.query(
        """
        select r.race_id, d.season, d.round, d.grand_prix_name, lower(r.session_type) as session,
               r.constructor_id, r.position_number as position, r.position_text,
               r.grid_position, r.points
        from gold.fact_race_result as r
        join gold.dim_race as d using (race_id)
        where r.driver_id = ? and (? is null or d.season = ?)
        order by d.season, d.round, r.session_type desc
        """,
        [driver_id, season, season],
    )


@router.get(
    "/{driver_id}/teammates",
    response_model=list[TeammateComparison],
    summary="Comparativa con cada compañero de equipo (carrera, clasificación y puntos)",
)
def teammates(driver_id: str, db: DB):
    _require_driver(db, driver_id)
    return db.query(
        """
        select h.season, h.constructor_id, c.name as constructor_name, h.teammate_id,
               t.name as teammate_name, h.races_together, h.race_ahead, h.race_ahead_pct,
               h.qualifyings_together, h.quali_ahead, h.quali_ahead_pct, h.points,
               h.teammate_points
        from gold.agg_teammate_h2h as h
        join gold.dim_constructor as c using (constructor_id)
        join gold.dim_driver as t on t.driver_id = h.teammate_id
        where h.driver_id = ?
        order by h.season, c.name, t.name
        """,
        [driver_id],
    )
