"""Carga única de los CSV obtenidos por web scraping de formula1db.com durante el TFG.

Los scripts de Selenium dejan de usarse, pero sus datos (tiempos por vuelta anteriores a
2018, que FastF1 no cubre) se conservan en bronze. Como los CSV se generaron con
`mode="a"`, se eliminan las filas duplicadas exactas.
"""

import logging
import re
from pathlib import Path

import pandas as pd

from ingestion.config import BRONZE_DIR, LEGACY_CSV_DIR
from ingestion.io import write_metadata, write_parquet

log = logging.getLogger(__name__)

OUT_DIR = BRONZE_DIR / "formula1db"

FILES = {
    "lap_times": "f1_lap_times.csv",
    "race_entries": "f1_race_entries.csv",
    "drivers": "f1_drivers.csv",
}

RENAMES = {"+-": "positions_change", "No.": "car_number"}


def snake_case(name: str) -> str:
    name = RENAMES.get(name, name)
    return re.sub(r"[^0-9a-z]+", "_", name.strip().lower()).strip("_")


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    df = df.rename(columns=snake_case)
    before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    return df, before - len(df)


def load(source_dir: Path = LEGACY_CSV_DIR) -> dict:
    stats = {}
    for name, filename in FILES.items():
        path = source_dir / filename
        if not path.exists():
            log.warning("No se encuentra %s; se omite", path)
            continue
        df, dropped = clean(pd.read_csv(path, dtype=str, keep_default_na=False))
        write_parquet(df, OUT_DIR / f"{name}.parquet")
        stats[name] = {"rows": len(df), "duplicates_dropped": dropped}
        log.info("%s: %d filas (%d duplicadas eliminadas)", name, len(df), dropped)
    write_metadata(OUT_DIR, source=str(source_dir), tables=stats)
    return stats
