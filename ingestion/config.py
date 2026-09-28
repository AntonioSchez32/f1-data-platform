"""Rutas y constantes compartidas por los cargadores."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("F1_DATA_DIR", PROJECT_ROOT / "data")).resolve()

RAW_DIR = DATA_DIR / "raw"
BRONZE_DIR = DATA_DIR / "bronze"
CACHE_DIR = DATA_DIR / "cache"

F1DB_REPO = "f1db/f1db"
F1DB_ASSET = "f1db-sqlite.zip"

# Primera temporada con datos de cronometraje completos en FastF1.
FASTF1_FIRST_SEASON = 2018

# Directorio con los CSV obtenidos por web scraping durante el TFG.
LEGACY_CSV_DIR = PROJECT_ROOT.parent / "FORMULA 1 DB"
