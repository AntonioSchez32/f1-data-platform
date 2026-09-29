"""Snapshots de datos para el pipeline: empaqueta y restaura lo que no está en Git.

El pipeline de GitHub Actions no tiene los CSV del TFG (formula1db.com, Ergast) ni el histórico de
FastF1, así que cada ejecución parte del último snapshot publicado en la GitHub Release
`data-latest`, añade lo nuevo y publica el siguiente. Ficheros del snapshot:

- `bronze.tar.gz`     capa bronze completa (entrada de la siguiente ejecución)
- `f1.duckdb`         base de datos para la API: esquemas `gold` y `quality.qa_summary`
- `gold-parquet.zip`  tablas gold en Parquet (Power BI u otras herramientas)
- `manifest.json`     versión de las fuentes, cobertura, estado de calidad y sumas SHA-256
"""

import hashlib
import json
import tarfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from ingestion.config import DATA_DIR
from ingestion.io import read_metadata

BRONZE_ARCHIVE = "bronze.tar.gz"
API_DATABASE = "f1.duckdb"
GOLD_PARQUET_ARCHIVE = "gold-parquet.zip"
MANIFEST = "manifest.json"
# Fuentes que solo existen en el equipo del autor: sin ellas `dbt build` no puede ejecutarse.
STATIC_SOURCES = ("formula1db", "ergast")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pack_bronze(bronze_dir: Path, out: Path) -> Path:
    """Empaqueta la capa bronze con rutas relativas a `data/` (`bronze/...`)."""
    missing = [s for s in STATIC_SOURCES if not (bronze_dir / s).is_dir()]
    if missing:
        raise FileNotFoundError(f"Faltan fuentes estáticas en {bronze_dir}: {', '.join(missing)}")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    with tarfile.open(tmp, "w:gz") as tar:
        for path in sorted(bronze_dir.rglob("*")):
            if path.is_file() and not path.name.endswith(".tmp"):
                tar.add(path, arcname=Path("bronze") / path.relative_to(bronze_dir))
    tmp.replace(out)
    return out


def restore_bronze(archive: Path, data_dir: Path = DATA_DIR) -> list[str]:
    """Extrae un snapshot de bronze en `data_dir`. Devuelve las fuentes restauradas."""
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        if any(not m.name.startswith("bronze/") for m in members):
            raise ValueError(f"{archive} no es un snapshot de bronze")
        # El filtro 'data' rechaza rutas absolutas, enlaces y escapes del directorio de destino.
        tar.extractall(data_dir, filter="data")
    # dbt crea la base de datos pero no su directorio.
    (data_dir / "gold").mkdir(parents=True, exist_ok=True)
    return sorted({Path(m.name).parts[1] for m in members if len(Path(m.name).parts) > 2})


def build_api_database(warehouse: Path, out: Path) -> dict[str, int]:
    """Copia el esquema gold y el resumen de calidad a una base de datos compacta."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    con = duckdb.connect(str(out))
    try:
        con.execute(f"attach '{warehouse.as_posix()}' as warehouse (read_only)")
        tables = [
            row[0]
            for row in con.execute(
                "select table_name from duckdb_tables() "
                "where database_name = 'warehouse' and schema_name = 'gold' order by 1"
            ).fetchall()
        ]
        if not tables:
            raise ValueError(f"{warehouse} no tiene tablas en el esquema gold")
        counts = {}
        for schema, table in [("gold", t) for t in tables] + [("quality", "qa_summary")]:
            con.execute(f"create schema if not exists {schema}")
            source = f"warehouse.{schema}.{table}"
            con.execute(f"create table {schema}.{table} as select * from {source}")
            counts[f"{schema}.{table}"] = con.execute(
                f"select count(*) from {schema}.{table}"
            ).fetchone()[0]
        con.execute("detach warehouse")
        con.execute("checkpoint")
    finally:
        con.close()
    return counts


def export_gold_parquet(database: Path, out: Path) -> Path:
    """Exporta cada tabla gold a Parquet dentro de un zip."""
    staging = out.with_suffix(".d")
    staging.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(database), read_only=True)
    try:
        tables = [
            r[0]
            for r in con.execute(
                "select table_name from duckdb_tables() where schema_name = 'gold' order by 1"
            ).fetchall()
        ]
        for table in tables:
            target = (staging / f"{table}.parquet").as_posix()
            con.execute(f"copy gold.{table} to '{target}' (format parquet, compression zstd)")
    finally:
        con.close()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zf:  # Parquet ya va comprimido
        for path in sorted(staging.glob("*.parquet")):
            zf.write(path, arcname=path.name)
            path.unlink()
    staging.rmdir()
    return out


def summarize(database: Path, bronze_dir: Path) -> dict:
    """Datos del manifiesto: versión de F1DB, cobertura de FastF1, última carrera y calidad."""
    con = duckdb.connect(str(database), read_only=True)
    try:
        last_race = con.execute(
            "select season, round, official_name from gold.dim_race "
            "where is_completed order by race_date desc limit 1"
        ).fetchone()
        quality = dict(
            con.execute(
                "select status, count(*) from quality.qa_summary group by status"
            ).fetchall()
        )
    finally:
        con.close()
    fastf1_laps = bronze_dir / "fastf1" / "laps"
    seasons = {}
    if fastf1_laps.is_dir():
        for season_dir in sorted(fastf1_laps.glob("season=*")):
            seasons[season_dir.name.split("=")[1]] = len(list(season_dir.glob("*.parquet")))
    return {
        "f1db_release": read_metadata(bronze_dir / "f1db").get("release"),
        "fastf1_races_per_season": seasons,
        "last_completed_race": (
            {"season": last_race[0], "round": last_race[1], "name": last_race[2]}
            if last_race
            else None
        ),
        "quality_checks": quality,
    }


def pack(out_dir: Path, data_dir: Path = DATA_DIR, warehouse: Path | None = None) -> dict:
    """Genera el snapshot completo en `out_dir` y devuelve su manifiesto."""
    warehouse = warehouse or data_dir / "gold" / "f1.duckdb"
    if not warehouse.exists():
        raise FileNotFoundError(f"No existe {warehouse}: ejecuta antes `dbt build`")
    bronze_dir = data_dir / "bronze"
    out_dir.mkdir(parents=True, exist_ok=True)

    files = [
        pack_bronze(bronze_dir, out_dir / BRONZE_ARCHIVE),
        out_dir / API_DATABASE,
        out_dir / GOLD_PARQUET_ARCHIVE,
    ]
    tables = build_api_database(warehouse, files[1])
    export_gold_parquet(files[1], files[2])

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        **summarize(files[1], bronze_dir),
        "tables": tables,
        "files": {f.name: {"bytes": f.stat().st_size, "sha256": sha256(f)} for f in files},
    }
    (out_dir / MANIFEST).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest


def release_notes(manifest: dict) -> str:
    """Texto de la GitHub Release a partir del manifiesto."""
    race = manifest.get("last_completed_race") or {}
    quality = manifest.get("quality_checks", {})
    seasons = manifest.get("fastf1_races_per_season", {})
    lines = [
        f"Datos generados el {manifest['generated_at']} por el pipeline.",
        "",
        f"- Última carrera con resultados: {race.get('season')} R{race.get('round')} "
        f"({race.get('name')})",
        f"- F1DB: {manifest.get('f1db_release')}",
        "- FastF1 (carreras por temporada): "
        + ", ".join(f"{season}: {n}" for season, n in seasons.items()),
        "- Controles de calidad: "
        + ", ".join(f"{status} {n}" for status, n in sorted(quality.items())),
        "",
        "Fuentes: F1DB (CC BY 4.0), FastF1, formula1db.com (datos del TFG, con permiso para "
        "divulgación) y Ergast (solo validación).",
        "",
        "Licencia: no hay una única. F1DB y lo derivado de él, CC BY 4.0; la parte de Ergast, "
        "CC BY-NC-SA 3.0; el cronometraje de la F1 (FastF1), © Formula One, solo para uso "
        "académico no comercial; formula1db.com, con permiso de su autor. Detalle en "
        "https://github.com/AntonioSchez32/f1-data-platform#licencia-y-atribuciones",
    ]
    return "\n".join(lines) + "\n"
