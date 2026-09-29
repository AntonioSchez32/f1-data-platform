"""API de solo lectura sobre el modelo gold de F1 Data Platform.

Ejecución en desarrollo: `uv run uvicorn api.app.main:app --reload` (documentación en /docs).
"""

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from api.app.cache import DataCacheMiddleware
from api.app.config import Settings
from api.app.database import Database, resolve_database
from api.app.deps import DB
from api.app.release import database_sha, ensure_database, fetch_manifest, remove_old_versions
from api.app.routers import circuits, constructors, drivers, races, rankings, records, seasons
from api.app.schemas import Health, QualityCheck

log = logging.getLogger("api")


async def refresh_periodically(app: FastAPI, settings: Settings) -> None:
    """Comprueba cada cierto tiempo si el pipeline ha publicado datos nuevos y los carga."""
    database: Database = app.state.database
    while True:
        await asyncio.sleep(settings.refresh_hours * 3600)
        try:
            manifest = await asyncio.to_thread(
                fetch_manifest, settings.data_repo, settings.data_tag, settings.github_token
            )
            if database_sha(manifest)[:12] == database.version.id:
                continue
            path, manifest = await asyncio.to_thread(
                ensure_database,
                settings.data_repo,
                settings.data_tag,
                settings.github_token,
                settings.data_dir,
            )
            database.swap(path, manifest)
            # Margen para que terminen las consultas que usaban la versión anterior.
            await asyncio.sleep(120)
            database.close_retired()
            remove_old_versions(settings.data_dir, keep=path)
        except Exception:  # la versión actual sigue sirviéndose; se reintenta más tarde
            log.exception("No se pudieron actualizar los datos")


def create_app(settings: Settings | None = None, database: Database | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if database is not None:
            app.state.database = database
        else:
            path, manifest = await asyncio.to_thread(resolve_database, settings)
            app.state.database = Database(path, manifest)
        log.info(
            "Sirviendo %s (versión %s)", app.state.database.path, app.state.database.version.id
        )
        refresher = None
        if settings.data_repo and settings.refresh_hours > 0 and not settings.db_path:
            refresher = asyncio.create_task(refresh_periodically(app, settings))
        try:
            yield
        finally:
            if refresher:
                refresher.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await refresher
            app.state.database.close()

    app = FastAPI(
        title="F1 Data Platform API",
        version="1.0.0",
        summary="Resultados, vueltas, neumáticos, telemetría y estadísticas de la F1 (1950-hoy).",
        description=(
            "API de solo lectura sobre el modelo dimensional del proyecto. Fuentes: F1DB, FastF1, "
            "formula1db.com y Ergast (solo validación), conciliadas con documentos de la FIA. "
            "Los tiempos van en milisegundos y los identificadores son los de F1DB "
            "(p. ej. `lewis-hamilton`, `ferrari`).\n\n"
            "Código MIT. Los datos conservan la licencia de su fuente: F1DB (CC BY 4.0), Ergast "
            "(CC BY-NC-SA 3.0), el cronometraje de la F1 obtenido con FastF1 (© Formula One, uso "
            "académico no comercial) y formula1db.com (con permiso de su autor); ver "
            "[licencias de los datos](https://github.com/AntonioSchez32/f1-data-platform"
            "#licencia-y-atribuciones). Cita «F1 Data Platform» y la fuente original. Proyecto "
            "académico no oficial, sin relación con la Fórmula 1 ni con la FIA."
        ),
        license_info={"name": "MIT", "identifier": "MIT"},
        lifespan=lifespan,
    )
    app.add_middleware(DataCacheMiddleware, max_age=settings.cache_max_age)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["If-None-Match"],
        expose_headers=["ETag"],
    )
    for module in (seasons, races, drivers, constructors, records, rankings, circuits):
        app.include_router(module.router)

    @app.get(
        "/health", response_model=Health, tags=["Estado"], summary="Estado y versión de los datos"
    )
    def health(db: DB):
        version = db.version
        return {
            "status": "ok",
            "data": {
                "version": version.id,
                "generated_at": version.generated_at,
                "f1db_release": version.f1db_release,
                "last_completed_race": version.last_completed_race,
            },
        }

    @app.get(
        "/quality",
        response_model=list[QualityCheck],
        tags=["Estado"],
        summary="Controles de calidad de los datos (concordancia entre fuentes)",
    )
    def quality(db: DB):
        return db.query(
            """
            select check_id, description, compared, matched, match_pct,
                   min_match_pct::double as min_match_pct, status
            from quality.qa_summary
            order by case status when 'FAIL' then 0 when 'PASS' then 1 else 2 end, check_id
            """
        )

    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = create_app()
