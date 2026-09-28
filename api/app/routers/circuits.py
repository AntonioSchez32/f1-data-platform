"""Circuitos con su ubicación (mapa mundial de Grandes Premios)."""

from fastapi import APIRouter, Query

from api.app.deps import DB
from api.app.schemas import Circuit

router = APIRouter(prefix="/circuits", tags=["Circuitos"])


@router.get("", response_model=list[Circuit], summary="Circuitos y carreras disputadas en cada uno")
def list_circuits(
    db: DB,
    season_from: int | None = Query(None, description="Desde esta temporada"),
    season_to: int | None = Query(None, description="Hasta esta temporada"),
):
    return db.query(
        """
        select
            circuit_id, any_value(circuit_name) as name, any_value(circuit_place_name) as place,
            any_value(circuit_country) as country, any_value(circuit_alpha2) as country_alpha2,
            any_value(circuit_latitude) as latitude, any_value(circuit_longitude) as longitude,
            count(*) as races, min(season) as first_season, max(season) as last_season,
            list(distinct grand_prix_name order by grand_prix_name) as grands_prix
        from gold.dim_race
        where is_completed
            and (? is null or season >= ?)
            and (? is null or season <= ?)
        group by circuit_id
        order by races desc, name
        """,
        [season_from, season_from, season_to, season_to],
    )
