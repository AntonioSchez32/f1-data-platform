"""Snapshots de datos para el pipeline: empaqueta y restaura lo que no está en Git.

El pipeline de GitHub Actions no tiene los CSV del TFG (formula1db.com, Ergast) ni el histórico de
FastF1, así que cada ejecución parte del último snapshot publicado, añade lo nuevo y publica el
siguiente en una release fechada e inmutable (`data-AAAA-MM-DD`) y en `data-latest`. Ficheros del
snapshot:

- `bronze.tar.gz`     capa bronze completa (entrada de la siguiente ejecución)
- `f1.duckdb`         base de datos para la API: esquemas `gold` y `quality.qa_summary`
- `gold-parquet.zip`  tablas gold en Parquet (Power BI u otras herramientas)
- `manifest.json`     versión de las fuentes, cobertura, estado de calidad, sumas SHA-256 y la
                      release fechada de la que forman parte (`release_tag`)

Las fuentes estáticas (formula1db.com y Ergast), que ya no se pueden volver a obtener, tienen
además su propia copia inmutable, `bronze-static.tar.gz` (release `bronze-static-v1`).
"""

import hashlib
import json
import re
import shutil
import tarfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from ingestion.config import DATA_DIR
from ingestion.io import read_metadata

BRONZE_ARCHIVE = "bronze.tar.gz"
STATIC_ARCHIVE = "bronze-static.tar.gz"
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


def _check_static_sources(bronze_dir: Path) -> None:
    missing = [
        s
        for s in STATIC_SOURCES
        if not (bronze_dir / s).is_dir() or not any((bronze_dir / s).iterdir())
    ]
    if missing:
        raise FileNotFoundError(f"Faltan fuentes estáticas en {bronze_dir}: {', '.join(missing)}")


def _pack(bronze_dir: Path, out: Path, sources: tuple[str, ...] | None = None) -> Path:
    """Empaqueta bronze (o solo `sources`) con rutas relativas a `data/` (`bronze/...`)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    roots = [bronze_dir / s for s in sources] if sources else [bronze_dir]
    with tarfile.open(tmp, "w:gz") as tar:
        for root in roots:
            for path in sorted(root.rglob("*")):
                if path.is_file() and not path.name.endswith(".tmp"):
                    tar.add(path, arcname=Path("bronze") / path.relative_to(bronze_dir))
    tmp.replace(out)
    return out


def pack_bronze(bronze_dir: Path, out: Path) -> Path:
    """Empaqueta la capa bronze completa."""
    _check_static_sources(bronze_dir)
    return _pack(bronze_dir, out)


def pack_static(bronze_dir: Path, out: Path) -> Path:
    """Empaqueta solo las fuentes estáticas: la copia inmutable que nunca se sobrescribe."""
    _check_static_sources(bronze_dir)
    return _pack(bronze_dir, out, STATIC_SOURCES)


def restore_bronze(archive: Path, data_dir: Path = DATA_DIR, replace: bool = False) -> list[str]:
    """Extrae un snapshot de bronze en `data_dir`. Devuelve las fuentes restauradas.

    Con `replace`, las carpetas de las fuentes que trae el archivo se vacían antes: quedan
    exactamente como en él (se usa con la copia inmutable de las fuentes estáticas).
    """
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        if any(not m.name.startswith("bronze/") for m in members):
            raise ValueError(f"{archive} no es un snapshot de bronze")
        sources = sorted({Path(m.name).parts[1] for m in members if len(Path(m.name).parts) > 2})
        # Antes del filtro de tarfile: un nombre como `bronze/../x` no puede llegar al rmtree.
        if any(not re.fullmatch(r"[A-Za-z0-9_-]+", source) for source in sources):
            raise ValueError(f"{archive} no es un snapshot de bronze")
        if replace:
            for source in sources:
                shutil.rmtree(data_dir / "bronze" / source, ignore_errors=True)
        # El filtro 'data' rechaza rutas absolutas, enlaces y escapes del directorio de destino.
        tar.extractall(data_dir, filter="data")
    # dbt crea la base de datos pero no su directorio.
    (data_dir / "gold").mkdir(parents=True, exist_ok=True)
    return sources


def table_count_regressions(
    previous: dict[str, int],
    current: dict[str, int],
    expected: dict | None = None,
    max_shrink: float = 0.02,
) -> list[str]:
    """Tablas que desaparecen o pierden filas respecto al snapshot anterior.

    `expected` declara los cambios intencionados (`api/tests/smoke/cambios_esperados.json`):
    `{"removed": [tabla, ...], "shrink": {tabla: fracción}}`. Cuando el snapshot anterior ya
    recoge el cambio, la entrada deja de tener efecto y puede borrarse.
    """
    expected = expected or {}
    removed = set(expected.get("removed", []))
    shrink = expected.get("shrink", {})
    problems = []
    for table, rows in sorted(previous.items()):
        if table not in current:
            if table not in removed:
                problems.append(f"{table} desaparece")
            continue
        limit = shrink.get(table, max_shrink)
        if current[table] < rows * (1 - limit):
            problems.append(f"{table} pasa de {rows} a {current[table]} filas (límite {limit:.0%})")
    return problems


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


def pack(
    out_dir: Path,
    data_dir: Path = DATA_DIR,
    warehouse: Path | None = None,
    release_tag: str | None = None,
) -> dict:
    """Genera el snapshot completo en `out_dir` y devuelve su manifiesto.

    `release_tag` es la release fechada donde se publicará: la API descarga la base de datos de
    ella, así que el `manifest.json` de `data-latest` funciona como puntero.
    """
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
        "release_tag": release_tag,
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
        f"Datos generados el {manifest['generated_at']} por el pipeline"
        + (f" (release {manifest['release_tag']})." if manifest.get("release_tag") else "."),
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
