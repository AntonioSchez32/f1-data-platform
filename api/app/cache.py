"""Caché HTTP: las respuestas solo dependen de la URL y de la versión de los datos.

Cada GET correcto lleva `Cache-Control` y una ETag derivada de ambas. Si el cliente (o una CDN)
envía `If-None-Match` con la ETag vigente, se responde 304 sin ejecutar la consulta. Al publicarse
datos nuevos cambia la versión y, con ella, todas las ETag.
"""

import hashlib

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

UNCACHED_PATHS = {"/health"}


def etag_for(version_id: str, request: Request) -> str:
    url = f"{request.url.path}?{request.url.query}"
    return f'W/"{version_id}-{hashlib.sha1(url.encode()).hexdigest()[:16]}"'


class DataCacheMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_age: int):
        super().__init__(app)
        self.max_age = max_age

    async def dispatch(self, request: Request, call_next) -> Response:
        database = getattr(request.app.state, "database", None)
        if request.method != "GET" or database is None or request.url.path in UNCACHED_PATHS:
            return await call_next(request)

        etag = etag_for(database.version.id, request)
        cache_control = f"public, max-age={self.max_age}, stale-while-revalidate=86400"
        if etag in {tag.strip() for tag in request.headers.get("if-none-match", "").split(",")}:
            return Response(status_code=304, headers={"ETag": etag, "Cache-Control": cache_control})

        response = await call_next(request)
        if response.status_code == 200:
            response.headers["ETag"] = etag
            response.headers["Cache-Control"] = cache_control
        return response
