"""Utilidades de escritura: todos los ficheros se escriben de forma atómica e idempotente."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


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
