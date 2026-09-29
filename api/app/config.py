"""Configuración de la API a partir de variables de entorno.

Origen de los datos, por orden de preferencia:
1. `F1_API_DB_PATH`: un fichero DuckDB concreto (sin actualizaciones automáticas).
2. `F1_DATA_REPO`: la GitHub Release del pipeline; se descarga y se comprueba periódicamente. Si
   GitHub no responde al arrancar, se sirve la última copia verificada (descargada antes o la de
   respaldo de la imagen, `F1_API_SEED_DIR`) y se reintenta más tarde.
3. En desarrollo, `dist/f1.duckdb` (snapshot local) o `data/gold/f1.duckdb` (salida de dbt).
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name) or default


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    db_path: Path | None = field(
        default_factory=lambda: Path(p) if (p := _env("F1_API_DB_PATH")) else None
    )
    data_repo: str | None = field(default_factory=lambda: _env("F1_DATA_REPO"))
    data_tag: str = field(default_factory=lambda: _env("F1_DATA_TAG", "data-latest"))
    # Token de solo lectura (Contents: read), necesario si el repositorio es privado.
    github_token: str | None = field(default_factory=lambda: _env("F1_GITHUB_TOKEN"))
    # Carpeta donde se guardan las bases de datos descargadas.
    data_dir: Path = field(
        default_factory=lambda: Path(_env("F1_API_DATA_DIR", str(PROJECT_ROOT / "data" / "api")))
    )
    # Copia de respaldo de solo lectura (la imagen Docker la trae de la release al construirse):
    # evita la descarga si sigue vigente y permite arrancar si GitHub no responde.
    seed_dir: Path | None = field(
        default_factory=lambda: Path(p) if (p := _env("F1_API_SEED_DIR")) else None
    )
    # Cada cuántas horas se comprueba si hay datos nuevos (0 = nunca).
    refresh_hours: float = field(default_factory=lambda: float(_env("F1_API_REFRESH_HOURS", "6")))
    cors_origins: list[str] = field(
        default_factory=lambda: _split(_env("F1_API_CORS_ORIGINS", "http://localhost:3000"))
    )
    cache_max_age: int = field(default_factory=lambda: int(_env("F1_API_CACHE_MAX_AGE", "600")))


def local_candidates() -> list[Path]:
    """Bases de datos locales de desarrollo, por orden de preferencia."""
    return [PROJECT_ROOT / "dist" / "f1.duckdb", PROJECT_ROOT / "data" / "gold" / "f1.duckdb"]
