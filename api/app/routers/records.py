"""Récords históricos de pilotos y constructores."""

from typing import Literal

from fastapi import APIRouter, Query

from api.app.deps import DB
from api.app.schemas import RecordEntry

router = APIRouter(prefix="/records", tags=["Récords"])

# Métrica pública -> columna de la tabla agregada (lista cerrada: nunca se interpola la entrada).
DRIVER_METRICS = {
    "championships": "championships",
    "wins": "wins",
    "podiums": "podiums",
    "pole_positions": "pole_positions",
    "fastest_laps": "fastest_laps",
    "race_starts": "race_starts",
    "points": "points",
    "grand_slams": "grand_slams",
}
CONSTRUCTOR_METRICS = {
    "championships": "championships",
    "wins": "wins",
    "podiums": "podiums",
    "pole_positions": "pole_positions",
    "fastest_laps": "fastest_laps",
    "race_entries": "race_entries",
    "one_two_finishes": "one_two_finishes",
    # Decisión 37: la cifra de F1DB (desde 1958, nula antes) y la histórica (desde 1950).
    "points": "points",
    "points_historical": "points_historical",
}


def _ranking(db: DB, table: str, key: str, alpha2: str, column: str, limit: int) -> list[dict]:
    return db.query(
        f"""
        select rank() over (order by {column} desc) as rank, {key} as id, name,
               {alpha2} as country_alpha2, {column}::double as value
        from gold.{table}
        where {column} > 0
        order by {column} desc, name
        limit ?
        """,
        [limit],
    )


@router.get("/drivers", response_model=list[RecordEntry], summary="Ranking histórico de pilotos")
def driver_records(
    db: DB,
    metric: Literal[tuple(DRIVER_METRICS)] = "wins",  # type: ignore[valid-type]
    limit: int = Query(20, ge=1, le=100),
):
    return _ranking(
        db, "agg_driver_career", "driver_id", "nationality_alpha2", DRIVER_METRICS[metric], limit
    )


@router.get(
    "/constructors", response_model=list[RecordEntry], summary="Ranking histórico de constructores"
)
def constructor_records(
    db: DB,
    metric: Literal[tuple(CONSTRUCTOR_METRICS)] = "wins",  # type: ignore[valid-type]
    limit: int = Query(20, ge=1, le=100),
):
    return _ranking(
        db,
        "agg_constructor_career",
        "constructor_id",
        "alpha2_constructor",
        CONSTRUCTOR_METRICS[metric],
        limit,
    )
