"""Acceso de solo lectura a la base de datos gold.

Una conexión DuckDB compartida y un cursor por consulta (DuckDB permite usar cursores de la misma
conexión desde varios hilos). Cuando llega una versión nueva de los datos se abre otra conexión y
se sustituye; la anterior se cierra un rato después, cuando ya no quedan consultas en curso.
"""

import hashlib
import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from api.app.config import Settings, local_candidates
from api.app.release import MANIFEST_ASSET, ensure_database

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DataVersion:
    """Identifica los datos servidos: se usa en las ETag y en /health."""

    id: str
    generated_at: str | None
    f1db_release: str | None
    last_completed_race: dict | None


def version_from_manifest(manifest: dict | None, path: Path) -> DataVersion:
    if manifest:
        digest = manifest["files"]["f1.duckdb"]["sha256"]
    else:
        stat = path.stat()
        digest = hashlib.sha256(f"{path}:{stat.st_size}:{stat.st_mtime_ns}".encode()).hexdigest()
    manifest = manifest or {}
    return DataVersion(
        id=digest[:12],
        generated_at=manifest.get("generated_at"),
        f1db_release=manifest.get("f1db_release"),
        last_completed_race=manifest.get("last_completed_race"),
    )


class Database:
    def __init__(self, path: Path, manifest: dict | None = None):
        self._lock = threading.Lock()
        self._retired: list[duckdb.DuckDBPyConnection] = []
        self._open(path, manifest)

    def _open(self, path: Path, manifest: dict | None) -> None:
        connection = duckdb.connect(str(path), read_only=True)
        tables = connection.execute(
            "select count(*) from duckdb_tables() where schema_name = 'gold'"
        ).fetchone()[0]
        if not tables:
            connection.close()
            raise ValueError(f"{path} no tiene tablas en el esquema gold")
        with self._lock:
            old = getattr(self, "_connection", None)
            self._connection = connection
            self.path = path
            self.version = version_from_manifest(manifest, path)
            if old is not None:
                self._retired.append(old)

    def swap(self, path: Path, manifest: dict | None) -> None:
        """Pasa a servir otra versión de los datos sin cortar las consultas en curso."""
        self._open(path, manifest)
        log.info("Datos actualizados a la versión %s", self.version.id)

    def close_retired(self) -> None:
        with self._lock:
            retired, self._retired = self._retired, []
        for connection in retired:
            connection.close()

    def close(self) -> None:
        self.close_retired()
        self._connection.close()

    def query(self, sql: str, params: list | tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            cursor = self._connection.cursor()
        try:
            result = cursor.execute(sql, list(params))
            columns = [c[0] for c in result.description]
            return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]
        finally:
            cursor.close()

    def query_one(self, sql: str, params: list | tuple = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None


def resolve_database(settings: Settings) -> tuple[Path, dict | None]:
    """Decide qué base de datos servir (ver api.app.config)."""
    if settings.db_path:
        if not settings.db_path.exists():
            raise FileNotFoundError(f"F1_API_DB_PATH apunta a {settings.db_path}, que no existe")
        return settings.db_path, _local_manifest(settings.db_path)
    if settings.data_repo:
        return ensure_database(
            settings.data_repo, settings.data_tag, settings.github_token, settings.data_dir
        )
    for candidate in local_candidates():
        if candidate.exists():
            return candidate, _local_manifest(candidate)
    raise FileNotFoundError(
        "No hay datos que servir: define F1_DATA_REPO (release del pipeline), F1_API_DB_PATH "
        "o ejecuta `dbt build` en local."
    )


def _local_manifest(path: Path) -> dict | None:
    manifest = path.with_name(MANIFEST_ASSET)
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data.get("files", {}).get("f1.duckdb"):
            return data
    return None
