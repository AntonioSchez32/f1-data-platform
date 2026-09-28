"""Temporadas, calendario y clasificaciones del campeonato."""

from typing import Literal

from fastapi import APIRouter, Query

from api.app.deps import DB, not_found
from api.app.schemas import (
    ConstructorStanding,
    DriverStanding,
    SeasonDetail,
    SeasonSummary,
    StandingsProgression,
)

router = APIRouter(prefix="/seasons", tags=["Temporadas"])

RACE_SUMMARY_SQL = """
    select
        r.race_id, r.season, r.round, r.race_date as date, r.grand_prix_id, r.grand_prix_name,
        r.official_name, r.circuit_id, r.circuit_name, r.circuit_country as country,
        r.circuit_alpha2 as country_alpha2, r.has_sprint, r.is_completed,
        case when w.driver_id is not null then {'id': w.driver_id, 'name': d.name} end as winner
    from gold.dim_race as r
    left join gold.fact_race_result as w
        on w.race_id = r.race_id and w.session_type = 'RACE' and w.position_number = 1
        -- Coches compartidos en los años 50: un único ganador por carrera (el primero listado).
        and w.position_display_order = (
            select min(x.position_display_order) from gold.fact_race_result as x
            where x.race_id = r.race_id and x.session_type = 'RACE' and x.position_number = 1
        )
    left join gold.dim_driver as d on d.driver_id = w.driver_id
"""


@router.get("", response_model=list[SeasonSummary], summary="Temporadas con sus campeones")
def list_seasons(db: DB):
    return db.query("""
        with races as (
            select season, count(*) as races, count(*) filter (where is_completed) as completed
            from gold.dim_race group by season
        ),
        drivers as (
            select s.season, {'id': s.driver_id, 'name': s.driver_name} as champion
            from gold.agg_driver_season as s where s.championship_won
        ),
        constructors as (
            select r.season, {'id': c.constructor_id, 'name': d.name} as champion
            from gold.fact_constructor_standing as c
            join gold.dim_race as r using (race_id)
            join gold.dim_constructor as d using (constructor_id)
            where r.is_season_final_race and c.championship_won
        )
        select
            races.season, races.races, races.completed as completed_races,
            drivers.champion as drivers_champion, constructors.champion as constructors_champion
        from races
        left join drivers using (season)
        left join constructors using (season)
        order by races.season desc
    """)


@router.get("/{season}", response_model=SeasonDetail, summary="Calendario de una temporada")
def get_season(season: int, db: DB):
    races = db.query(RACE_SUMMARY_SQL + " where r.season = ? order by r.round", [season])
    if not races:
        raise not_found(f"la temporada {season}")
    return {"season": season, "races": races}


def _standings_race(db: DB, season: int, round_: int | None) -> int:
    """Carrera cuya clasificación se muestra: la ronda pedida o la última disputada."""
    row = db.query_one(
        """
        select race_id from gold.dim_race
        where season = ? and is_completed and (? is null or round <= ?)
        order by round desc limit 1
        """,
        [season, round_, round_],
    )
    if not row:
        raise not_found(f"ninguna carrera disputada en {season}")
    return row["race_id"]


@router.get(
    "/{season}/standings/drivers",
    response_model=list[DriverStanding],
    summary="Clasificación de pilotos (tras la última carrera o la ronda indicada)",
)
def driver_standings(
    season: int, db: DB, round: int | None = Query(None, ge=1, description="Tras esta ronda")
):
    race_id = _standings_race(db, season, round)
    return db.query(
        """
        with rounds as (
            select race_id from gold.dim_race
            where season = ? and round <= (select round from gold.dim_race where race_id = ?)
        ),
        wins as (
            select driver_id, count(*) as wins from gold.fact_race_result
            where session_type = 'RACE' and is_win and race_id in (select race_id from rounds)
            group by driver_id
        ),
        teams as (
            select res.driver_id, list(distinct c.name order by c.name) as constructors
            from gold.fact_race_result as res
            join gold.dim_constructor as c using (constructor_id)
            where res.race_id in (select race_id from rounds)
            group by res.driver_id
        )
        select
            s.position_number as position, s.position_text, s.driver_id, d.name,
            d.nationality_alpha2, coalesce(teams.constructors, []) as constructors,
            s.points, coalesce(wins.wins, 0) as wins,
            coalesce(s.championship_won, false) as is_champion
        from gold.fact_driver_standing as s
        join gold.dim_driver as d using (driver_id)
        left join wins using (driver_id)
        left join teams using (driver_id)
        where s.race_id = ?
        order by s.position_display_order
        """,
        [season, race_id, race_id],
    )


@router.get(
    "/{season}/standings/constructors",
    response_model=list[ConstructorStanding],
    summary="Clasificación de constructores (desde 1958)",
)
def constructor_standings(
    season: int, db: DB, round: int | None = Query(None, ge=1, description="Tras esta ronda")
):
    race_id = _standings_race(db, season, round)
    return db.query(
        """
        with rounds as (
            select race_id from gold.dim_race
            where season = ? and round <= (select round from gold.dim_race where race_id = ?)
        ),
        wins as (
            select constructor_id, count(distinct race_id) as wins from gold.fact_race_result
            where session_type = 'RACE' and is_win and race_id in (select race_id from rounds)
            group by constructor_id
        )
        select
            s.position_number as position, s.position_text, s.constructor_id, c.name,
            c.alpha2_constructor as country_alpha2, e.name as engine, s.points,
            coalesce(wins.wins, 0) as wins, coalesce(s.championship_won, false) as is_champion
        from gold.fact_constructor_standing as s
        join gold.dim_constructor as c using (constructor_id)
        left join gold.dim_engine_manufacturer as e using (engine_manufacturer_id)
        left join wins using (constructor_id)
        where s.race_id = ?
        order by s.position_display_order
        """,
        [season, race_id, race_id],
    )


@router.get(
    "/{season}/standings/progression",
    response_model=list[StandingsProgression],
    summary="Puntos acumulados ronda a ronda (gráfico de evolución del campeonato)",
)
def standings_progression(
    season: int,
    db: DB,
    type: Literal["drivers", "constructors"] = "drivers",
    top: int = Query(10, ge=1, le=50, description="Solo los N primeros de la clasificación final"),
):
    if type == "drivers":
        fact, key, dim, name = "fact_driver_standing", "driver_id", "dim_driver", "name"
    else:
        fact, key, dim, name = (
            "fact_constructor_standing",
            "constructor_id",
            "dim_constructor",
            "name",
        )
    rows = db.query(
        f"""
        with season_races as (
            select race_id, round, grand_prix_name from gold.dim_race
            where season = ? and is_completed
        ),
        last_race as (select race_id from season_races order by round desc limit 1),
        leaders as (
            select {key} from gold.{fact}
            where race_id = (select race_id from last_race)
            order by position_display_order limit ?
        )
        select r.round, r.race_id, r.grand_prix_name, s.{key} as id, d.{name} as name,
               s.points, s.position_number as position
        from gold.{fact} as s
        join season_races as r using (race_id)
        join gold.{dim} as d using ({key})
        where s.{key} in (select {key} from leaders)
        order by r.round, s.position_display_order
        """,
        [season, top],
    )
    if not rows:
        raise not_found(f"clasificación de {type} en {season}")
    return rows
