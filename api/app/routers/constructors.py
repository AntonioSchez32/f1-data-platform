"""Constructores: listado, ficha y temporadas."""

from fastapi import APIRouter, Query

from api.app.deps import DB, not_found
from api.app.schemas import ConstructorDetail, ConstructorSeason, ConstructorSummary

router = APIRouter(prefix="/constructors", tags=["Constructores"])

SUMMARY_COLUMNS = """
    c.constructor_id, c.name, c.alpha2_constructor as country_alpha2, c.first_season,
    c.last_season, coalesce(c.race_entries, 0) as race_entries, coalesce(c.wins, 0) as wins,
    coalesce(c.championships, 0) as championships
"""


@router.get("", response_model=list[ConstructorSummary], summary="Buscar constructores")
def list_constructors(
    db: DB,
    search: str | None = Query(None, min_length=2, description="Parte del nombre"),
    season: int | None = Query(None, description="Solo constructores de esta temporada"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return db.query(
        f"""
        select {SUMMARY_COLUMNS}
        from gold.agg_constructor_career as c
        where (? is null or strip_accents(lower(c.name)) like '%' || strip_accents(lower(?)) || '%')
            and (? is null or c.constructor_id in (
                select r.constructor_id from gold.fact_race_result as r
                join gold.dim_race as d using (race_id) where d.season = ?))
        order by c.wins desc, c.race_entries desc, c.name
        limit ? offset ?
        """,
        [search, search, season, season, limit, offset],
    )


@router.get("/{constructor_id}", response_model=ConstructorDetail, summary="Ficha del constructor")
def get_constructor(constructor_id: str, db: DB):
    row = db.query_one(
        f"""
        select {SUMMARY_COLUMNS}, d.full_name, c.country_constructor as country,
               coalesce(c.podiums, 0) as podiums,
               coalesce(c.one_two_finishes, 0) as one_two_finishes,
               coalesce(c.pole_positions, 0) as pole_positions,
               coalesce(c.fastest_laps, 0) as fastest_laps,
               c.points, coalesce(c.points_historical, 0) as points_historical,
               c.best_championship_position
        from gold.agg_constructor_career as c
        join gold.dim_constructor as d using (constructor_id)
        where c.constructor_id = ?
        """,
        [constructor_id],
    )
    if not row:
        raise not_found(f"el constructor {constructor_id}")
    return row


@router.get(
    "/{constructor_id}/seasons",
    response_model=list[ConstructorSeason],
    summary="Temporada a temporada: posición en el campeonato, victorias y pilotos",
)
def constructor_seasons(constructor_id: str, db: DB):
    if not db.query_one(
        "select 1 from gold.dim_constructor where constructor_id = ?", [constructor_id]
    ):
        raise not_found(f"el constructor {constructor_id}")
    return db.query(
        """
        with results as (
            select d.season, r.*
            from gold.fact_race_result as r
            join gold.dim_race as d using (race_id)
            where r.constructor_id = ?
        ),
        seasons as (
            select season, count(distinct race_id) filter (
                       where is_win and session_type = 'RACE') as wins,
                   list(distinct {'id': driver_id, 'name': dr.name}) as drivers
            from results join gold.dim_driver as dr using (driver_id)
            group by season
        ),
        final_standing as (
            select d.season, s.position_number, s.position_text, s.points, s.championship_won
            from gold.fact_constructor_standing as s
            join gold.dim_race as d using (race_id)
            where s.constructor_id = ?
            qualify row_number() over (partition by d.season order by d.round desc) = 1
        )
        select seasons.season, f.position_number as championship_position,
               f.position_text as championship_position_text, f.points,
               coalesce(f.championship_won, false) as is_champion, seasons.wins,
               seasons.drivers
        from seasons left join final_standing as f using (season)
        order by seasons.season
        """,
        [constructor_id, constructor_id],
    )
