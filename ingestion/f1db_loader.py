"""Carga de F1DB (https://github.com/f1db/f1db) en la capa bronze.

Sustituye la descarga manual del TFG: localiza la última release publicada en GitHub,
descarga la base de datos SQLite y vuelca cada tabla a Parquet con DuckDB, respetando
los tipos declarados en SQLite.
"""

import logging
import os
import shutil
import zipfile
from pathlib import Path

import duckdb
import requests

from ingestion.config import BRONZE_DIR, F1DB_ASSET, F1DB_REPO, RAW_DIR
from ingestion.io import read_metadata, write_metadata

log = logging.getLogger(__name__)

OUT_DIR = BRONZE_DIR / "f1db"


def latest_release() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.get(
        f"https://api.github.com/repos/{F1DB_REPO}/releases/latest", headers=headers, timeout=30
    )
    resp.raise_for_status()
    release = resp.json()
    asset = next(a for a in release["assets"] if a["name"] == F1DB_ASSET)
    return {
        "tag": release["tag_name"],
        "published_at": release["published_at"],
        "url": asset["browser_download_url"],
    }


def download_sqlite(release: dict) -> Path:
    target_dir = RAW_DIR / "f1db" / release["tag"]
    db_path = target_dir / "f1db.db"
    if db_path.exists():
        return db_path

    target_dir.mkdir(parents=True, exist_ok=True)
    zip_path = target_dir / F1DB_ASSET
    log.info("Descargando %s", release["url"])
    with requests.get(release["url"], stream=True, timeout=120) as resp:
        resp.raise_for_status()
        with open(zip_path, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extract("f1db.db", target_dir)
    zip_path.unlink()
    return db_path


def export_tables(db_path: Path, out_dir: Path) -> dict[str, int]:
    """Exporta todas las tablas (no las vistas, que se derivan de race_data) a Parquet."""
    tmp_dir = out_dir.with_name(out_dir.name + ".tmp")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    tmp_dir.mkdir(parents=True)

    con = duckdb.connect()
    con.execute("INSTALL sqlite; LOAD sqlite;")
    con.execute(f"ATTACH '{db_path.as_posix()}' AS src (TYPE sqlite, READ_ONLY)")
    tables = [
        row[0]
        for row in con.execute(
            "SELECT table_name FROM duckdb_tables() WHERE database_name = 'src' ORDER BY 1"
        ).fetchall()
    ]
    counts = {}
    for table in tables:
        target = (tmp_dir / f"{table}.parquet").as_posix()
        con.execute(f"COPY (SELECT * FROM src.{table}) TO '{target}' (FORMAT parquet)")
        counts[table] = con.execute(f"SELECT count(*) FROM src.{table}").fetchone()[0]
    con.close()

    # Sustitución atómica del directorio: bronze nunca queda a medio escribir.
    shutil.rmtree(out_dir, ignore_errors=True)
    tmp_dir.rename(out_dir)
    return counts


def load(force: bool = False) -> dict:
    release = latest_release()
    current = read_metadata(OUT_DIR)
    if not force and current.get("release") == release["tag"]:
        log.info("F1DB %s ya cargada; nada que hacer", release["tag"])
        return current

    db_path = download_sqlite(release)
    counts = export_tables(db_path, OUT_DIR)
    write_metadata(
        OUT_DIR, release=release["tag"], published_at=release["published_at"], tables=counts
    )
    log.info("F1DB %s cargada: %d tablas", release["tag"], len(counts))
    return read_metadata(OUT_DIR)
