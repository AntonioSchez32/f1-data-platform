"""API de solo lectura sobre el modelo gold de F1 Data Platform.

Ejecución en desarrollo: `uv run uvicorn api.app.main:app --reload` (documentación en /docs).
"""

import asyncio
import contextlib
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from api.app.cache import DataCacheMiddleware
from api.app.config import Settings
from api.app.database import Database, Resolved, resolve_database
from api.app.deps import DB
from api.app.release import (
    database_sha,
    describe_error,
    ensure_database,
    fetch_manifest,
    remove_old_versions,
)
from api.app.routers import circuits, constructors, drivers, races, rankings, records, seasons
from api.app.schemas import Health, QualityCheck

log = logging.getLogger("api")

# Tras un fallo (p. ej. GitHub no respondía al arrancar) se reintenta pronto, no a las 6 h.
RETRY_AFTER_ERROR_SECONDS = 600
# Margen para que terminen las consultas que usaban la versión anterior antes de cerrarla.
RETIRE_AFTER_SECONDS = 120


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class RefreshState:
    """De dónde salen los datos servidos y cómo fue la última comprobación de versión nueva."""

    source: str
    started_at: str
    last_check_at: str | None = None
    last_success_at: str | None = None
    last_error: str | None = None

    @classmethod
    def from_resolved(cls, resolved: Resolved) -> "RefreshState":
        now = _now()
        return cls(
            source=resolved.source,
            started_at=now,
            last_check_at=now if resolved.source != "file" else None,
            last_success_at=now if resolved.source == "release" else None,
            last_error=resolved.error,
        )

    def failed(self, error: Exception) -> None:
        self.last_error = describe_error(error)


async def refresh_periodically(app: FastAPI, settings: Settings) -> None:
    """Comprueba cada cierto tiempo si el pipeline ha publicado datos nuevos y los carga."""
    database: Database = app.state.database
    state: RefreshState = app.state.refresh
    seed_dirs = [settings.seed_dir] if settings.seed_dir else []
    while True:
        delay = settings.refresh_hours * 3600
        if state.last_error:
            delay = min(delay, RETRY_AFTER_ERROR_SECONDS)
        await asyncio.sleep(delay)
        state.last_check_at = _now()
        try:
            manifest = await asyncio.to_thread(
                fetch_manifest, settings.data_repo, settings.data_tag, settings.github_token
            )
            swapped = False
            if database_sha(manifest)[:12] != database.version.id:
                path, manifest = await asyncio.to_thread(
                    ensure_database,
                    settings.data_repo,
                    settings.data_tag,
                    settings.github_token,
                    settings.data_dir,
                    seed_dirs,
                )
                database.swap(path, manifest)
                swapped = True
            state.source = "release"
            state.last_success_at = _now()
            state.last_error = None
            if swapped:
                await asyncio.sleep(RETIRE_AFTER_SECONDS)
                database.close_retired()
                remove_old_versions(settings.data_dir, keep=database.path)
        except Exception as error:  # la versión actual sigue sirviéndose; se reintenta más tarde
            state.failed(error)
            log.exception("No se pudieron actualizar los datos")


def create_app(settings: Settings | None = None, database: Database | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        started = time.perf_counter()
        if database is not None:
            app.state.database = database
            app.state.refresh = RefreshState.from_resolved(Resolved(database.path, None, "file"))
        else:
            resolved = await asyncio.to_thread(resolve_database, settings)
            app.state.database = Database(resolved.path, resolved.manifest)
            app.state.refresh = RefreshState.from_resolved(resolved)
        log.info(
            "Sirviendo %s (versión %s, origen %s); arranque en %.1f s",
            app.state.database.path,
            app.state.database.version.id,
            app.state.refresh.source,
            time.perf_counter() - started,
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
        "/health",
        response_model=Health,
        tags=["Estado"],
        summary="Estado, versión de los datos y último refresco",
        responses={503: {"description": "La base de datos no responde"}},
    )
    def health(db: DB, request: Request):
        # Una consulta real: si la base no responde, el servicio no está sano.
        try:
            last_race = db.query_one(
                """
                select season, round, official_name as name
                from gold.dim_race
                where is_completed
                order by race_date desc
                limit 1
                """
            )
        except Exception as error:
            log.exception("La base de datos no responde")
            raise HTTPException(status_code=503, detail="La base de datos no responde") from error
        version = db.version
        refresh: RefreshState = request.app.state.refresh
        degraded = refresh.source == "copy" or refresh.last_error is not None
        return {
            "status": "degraded" if degraded else "ok",
            "data": {
                "version": version.id,
                "generated_at": version.generated_at,
                "f1db_release": version.f1db_release,
                "release_tag": version.release_tag,
                "last_completed_race": last_race,
            },
            "refresh": {
                "source": refresh.source,
                "started_at": refresh.started_at,
                "last_check_at": refresh.last_check_at,
                "last_success_at": refresh.last_success_at,
                "last_error": refresh.last_error,
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
