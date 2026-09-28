"""Dependencias compartidas por los routers."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from api.app.database import Database


def get_database(request: Request) -> Database:
    return request.app.state.database


DB = Annotated[Database, Depends(get_database)]


def not_found(what: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"No existe {what}")


def split_ids(value: str | None, limit: int | None = None) -> list[str] | None:
    """Convierte «a,b,c» en una lista; valida el número máximo de elementos."""
    if not value:
        return None
    ids = [item.strip() for item in value.split(",") if item.strip()]
    if limit and len(ids) > limit:
        raise HTTPException(status_code=422, detail=f"Como máximo {limit} identificadores")
    return ids
