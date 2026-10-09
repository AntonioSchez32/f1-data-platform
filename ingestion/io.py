"""Utilidades de escritura: todos los ficheros se escriben de forma atómica e idempotente."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


class SourceNotFoundError(FileNotFoundError):
    """Falta la carpeta o el fichero de una fuente de carga única (formula1db.com, Ergast).

    Esas fuentes solo existen en el equipo del autor; en cualquier otro, el bronze se restaura
    desde la release publicada (README, «Reproducir desde cero»).
    """

    def __init__(self, source: str, missing: list[Path]):
        self.missing = missing
        paths = "\n".join(f"  - {path}" for path in missing)
        super().__init__(
            f"No se encuentra el origen de {source}:\n{paths}\n"
            "Estas fuentes no están en el repositorio. Para reproducir el proyecto, restaura el "
            "bronze publicado (README, sección «Reproducir desde cero»):\n"
            "  gh release download data-latest --pattern bronze.tar.gz --dir dist\n"
            "  uv run f1-ingest snapshot restore dist/bronze.tar.gz"
        )


def write_parquet(df: pd.DataFrame, path: Path) -> Path:
    """Escribe un DataFrame a Parquet reemplazando el fichero anterior de forma atómica.

    Volver a ejecutar la carga de la misma carrera sobrescribe su fichero, nunca añade filas.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)
    return path


def write_metadata(directory: Path, **fields) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "_metadata.json"
    payload = {"loaded_at": datetime.now(UTC).isoformat(timespec="seconds"), **fields}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_metadata(directory: Path) -> dict:
    path = directory / "_metadata.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
