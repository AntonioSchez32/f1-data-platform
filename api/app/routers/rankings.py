"""Clasificaciones históricas filtrables por temporadas (páginas de récords del TFG).

Se calculan desde los resultados carrera a carrera con las mismas definiciones que
agg_driver_career y agg_constructor_career, así que con el rango completo coinciden con ellos y con
los totales de F1DB. Los puntos de constructor siguen la decisión 37: `points` es la cifra de F1DB
(carrera y sprint de las temporadas desde 1958, nula si el rango no incluye ninguna en que
corriera, porque antes no había campeonato de constructores) y `points_historical`, lo mismo desde
1950. Ninguna aplica los descartes de la época ni la regla de 1958-1978 del mejor coche.
"""

from typing import Literal

from fastapi import APIRouter, Query

from api.app.deps import DB
from api.app.schemas import ConstructorRanking, DriverRanking

router = APIRouter(prefix="/rankings", tags=["Récords"])

# Criterio de orden -> columna calculada (lista cerrada: nunca se interpola la entrada).
ORDER = Literal[
    "wins", "championships", "podiums", "pole_positions", "fastest_laps", "points", "entries"
]
CONSTRUCTOR_ORDER = Literal[
    "wins",
    "championships",
    "podiums",
    "pole_positions",
    "fastest_laps",
    "points",
    "points_historical",
    "entries",
]
NOT_STARTED = "('DNQ', 'DNPQ', 'DNP', 'EX', 'DNS')"


def _range(season_from: int | None, season_to: int | None) -> list:
    return [season_from, season_from, season_to, season_to]


RANGE_FILTER = "(? is null or d.season >= ?) and (? is null or d.season <= ?)"


@router.get("/drivers", response_model=list[DriverRanking], summary="Pilotos más laureados")
def driver_rankings(
    db: DB,
    season_from: int | None = Query(None, description="Desde esta temporada"),
    season_to: int | None = Query(None, description="Hasta esta temporada"),
    order_by: ORDER = "wins",
    limit: int = Query(50, ge=1, le=500),
):
    rows = db.query(
        f"""
        with results as (
            select r.* from gold.fact_race_result as r
            join gold.dim_race as d using (race_id)
            where {RANGE_FILTER}
        ),
        race as (
            select
                driver_id,
                count(distinct race_id) as entries,
                count(distinct race_id) filter (where position_text not in {NOT_STARTED}) as starts,
                count(distinct race_id) filter (where is_win) as wins,
                count(distinct race_id) filter (where is_podium) as podiums,
                count(distinct race_id) filter (where is_pole_position) as pole_positions,
                count(distinct race_id) filter (where is_fastest_lap) as fastest_laps
            from results where session_type = 'RACE'
            group by driver_id
        ),
        points as (
            select driver_id, round(sum(points), 2) as points from results group by driver_id
        ),
        titles as (
            select s.driver_id, count(*) as championships
            from gold.fact_driver_standing as s
            join gold.dim_race as d using (race_id)
            where d.is_season_final_race and s.championship_won and {RANGE_FILTER}
            group by s.driver_id
        )
        select
            race.driver_id as id, dr.name, dr.nationality_country as country,
            dr.nationality_alpha2 as country_alpha2, race.entries, race.starts, race.wins,
            race.podiums, race.pole_positions, race.fastest_laps,
            coalesce(points.points, 0) as points, coalesce(titles.championships, 0) as championships
        from race
        join gold.dim_driver as dr using (driver_id)
        left join points using (driver_id)
        left join titles using (driver_id)
        order by {order_by} desc, wins desc, podiums desc, name
        limit ?
        """,
        _range(season_from, season_to) + _range(season_from, season_to) + [limit],
    )
    return [{"rank": i + 1, **row} for i, row in enumerate(rows)]


@router.get(
    "/constructors", response_model=list[ConstructorRanking], summary="Constructores más laureados"
)
def constructor_rankings(
    db: DB,
    season_from: int | None = Query(None, description="Desde esta temporada"),
    season_to: int | None = Query(None, description="Hasta esta temporada"),
    order_by: CONSTRUCTOR_ORDER = "wins",
    limit: int = Query(50, ge=1, le=500),
):
    rows = db.query(
        f"""
        with results as (
            select r.*, d.season from gold.fact_race_result as r
            join gold.dim_race as d using (race_id)
            where {RANGE_FILTER}
        ),
        race as (
            select
                constructor_id,
                count(distinct race_id) as entries,
                count(distinct race_id) filter (where is_win) as wins,
                -- F1DB cuenta los podios por coche (los coches compartidos cuentan una vez).
                count(distinct race_id || '-' || driver_number) filter (where is_podium) as podiums,
                count(distinct race_id) filter (where is_pole_position) as pole_positions,
                count(*) filter (where is_fastest_lap) as fastest_laps
            from results where session_type = 'RACE'
            group by constructor_id
        ),
        -- Carrera y sprint (decisión 37). El filtro sin filas da nulo: sin temporadas desde 1958
        -- no hay `points`.
        points as (
            select
                constructor_id,
                round(sum(points) filter (where season >= 1958), 2) as points,
                round(sum(points), 2) as points_historical
            from results
            group by constructor_id
        ),
        titles as (
            select s.constructor_id, count(*) as championships
            from gold.fact_constructor_standing as s
            join gold.dim_race as d using (race_id)
            where d.is_season_final_race and s.championship_won and {RANGE_FILTER}
            group by s.constructor_id
        )
        select
            race.constructor_id as id, c.name, c.country_constructor as country,
            c.alpha2_constructor as country_alpha2, race.entries, race.wins, race.podiums,
            race.pole_positions, race.fastest_laps, points.points,
            coalesce(points.points_historical, 0) as points_historical,
            coalesce(titles.championships, 0) as championships
        from race
        join gold.dim_constructor as c using (constructor_id)
        left join points using (constructor_id)
        left join titles using (constructor_id)
        order by {order_by} desc nulls last, wins desc, podiums desc, name
        limit ?
        """,
        _range(season_from, season_to) + _range(season_from, season_to) + [limit],
    )
    return [{"rank": i + 1, **row} for i, row in enumerate(rows)]
