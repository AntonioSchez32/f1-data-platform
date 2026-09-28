"""Carga única del volcado CSV de Ergast (octubre 2022) guardado durante el TFG.

Ergast ya no se actualiza, así que no alimenta el modelo: se usa como tercera fuente
independiente para validar los tiempos por vuelta de formula1db.com entre 1996 y 2017, periodo
que FastF1 no cubre.
"""

import logging
import zipfile
from pathlib import Path

import pandas as pd

from ingestion.config import BRONZE_DIR, PROJECT_ROOT
from ingestion.io import write_metadata, write_parquet

log = logging.getLogger(__name__)

OUT_DIR = BRONZE_DIR / "ergast"
DEFAULT_ZIP = PROJECT_ROOT.parent / "ERGAST API" / "f1db_csv.zip"
TABLES = ["races", "results", "drivers", "lap_times", "pit_stops", "qualifying"]


def load(zip_path: Path = DEFAULT_ZIP) -> dict:
    stats = {}
    with zipfile.ZipFile(zip_path) as zf:
        for table in TABLES:
            with zf.open(f"{table}.csv") as fh:
                df = pd.read_csv(fh, na_values=["\\N"], keep_default_na=False)
            write_parquet(df, OUT_DIR / f"{table}.parquet")
            stats[table] = len(df)
            log.info("ergast.%s: %d filas", table, len(df))
    write_metadata(OUT_DIR, source=str(zip_path), tables=stats)
    return stats
