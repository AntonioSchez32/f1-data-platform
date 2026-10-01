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

FastF1 se carga en el equipo del autor, porque el servidor de cronometraje de la F1 rechaza las
IP de GitHub Actions, y se publica aparte (`bronze-fastf1.tar.gz` y `bronze-fastf1.json`, release
`bronze-fastf1`; ver `ingestion/fastf1_publish.py`). El pipeline la superpone al snapshot.

OpenF1 (2023+) sí se descarga en el pipeline, de forma incremental, y tiene su propia copia
(`bronze-openf1.tar.gz` y `bronze-openf1.json`, release `bronze-openf1`): el pipeline la descarga,
comprueba su SHA-256, la superpone, pide solo las sesiones nuevas y la vuelve a subir si cambió
(ver `openf1_upload_decision`).
"""

import hashlib
import json
import re
import shutil
import tarfile
import zipfile
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

import duckdb

from ingestion.config import DATA_DIR
from ingestion.io import read_metadata

BRONZE_ARCHIVE = "bronze.tar.gz"
STATIC_ARCHIVE = "bronze-static.tar.gz"
API_DATABASE = "f1.duckdb"
GOLD_PARQUET_ARCHIVE = "gold-parquet.zip"
MANIFEST = "manifest.json"
FASTF1_ARCHIVE = "bronze-fastf1.tar.gz"
FASTF1_MANIFEST = "bronze-fastf1.json"
# Fuentes que solo existen en el equipo del autor: sin ellas `dbt build` no puede ejecutarse.
STATIC_SOURCES = ("formula1db", "ergast")
# Único tipo de fichero que puede traer la copia de FastF1: un Parquet por carrera y tabla.
FASTF1_MEMBER = re.compile(r"bronze/fastf1/[a-z_]+/season=\d{4}/round=\d{2}\.parquet")
OPENF1_ARCHIVE = "bronze-openf1.tar.gz"
OPENF1_MANIFEST = "bronze-openf1.json"
# Ficheros que puede traer la copia de OpenF1: un Parquet por endpoint y sesión, el calendario
# (sessions y meetings) por temporada y los huecos conocidos.
OPENF1_SESSION_FILE = re.compile(r"bronze/openf1/[a-z_]+/season=(\d{4})/session=(\d+)\.parquet")
OPENF1_MEMBER = re.compile(
    r"bronze/openf1/(?:[a-z_]+/season=\d{4}/session=\d+\.parquet"
    r"|(?:sessions|meetings)/season=\d{4}\.parquet|_gaps\.json)"
)
# Controles informativos de qa_summary cuyo hueco se anota en el manifiesto y en las notas: filas
# que no se pudieron cruzar con F1DB y no se publican, pero no detienen la publicación (dec. 26).
NOTICE_CHECKS = {
    "openf1_lap_driver_attribution": "vueltas de OpenF1 sin piloto de F1DB (no se publican)",
    "openf1_race_session_matching": "sesiones de carrera de OpenF1 sin carrera de F1DB",
    "openf1_reliable_races": (
        "carrera(s) en que OpenF1 no concuerda con la fuente publicada (no se usa para contrastar)"
    ),
    "lap_completeness_openf1": (
        "pilotos sin todas sus vueltas oficiales en las carreras que solo tienen OpenF1"
    ),
    "fastest_lap_openf1": (
        "vueltas rápidas de OpenF1 que no coinciden con la oficial (carreras solo con OpenF1)"
    ),
    "f1db_pit_stops_in_laps_openf1": (
        "paradas de F1DB sin su entrada a boxes en las vueltas de OpenF1 (carreras solo con OpenF1)"
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


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


def fastf1_races_per_season(bronze_dir: Path) -> dict[str, int]:
    """Carreras de FastF1 por temporada (una por Parquet de vueltas)."""
    laps = bronze_dir / "fastf1" / "laps"
    if not laps.is_dir():
        return {}
    return {
        season_dir.name.split("=")[1]: len(list(season_dir.glob("*.parquet")))
        for season_dir in sorted(laps.glob("season=*"))
    }


def fewer_races(previous: dict[str, int], current: dict[str, int]) -> list[str]:
    """Temporadas con menos carreras de FastF1 que antes (p. ej. `2026: 14 de 15`)."""
    return [
        f"{season}: {current.get(season, 0)} de {n}"
        for season, n in sorted(previous.items())
        if current.get(season, 0) < n
    ]


def fastf1_copy_warnings(previous: dict, races: dict[str, int], copy: dict) -> list[str]:
    """Avisos al superponer una copia de FastF1 sobre el snapshot (`previous`, su manifest.json).

    - La copia trae menos carreras que el snapshot (se conservan las del snapshot).
    - La copia es más antigua que la usada en el snapshot: sus carreras sustituirían a versiones
      más recientes. Los manifiestos anteriores a `fastf1_copy` no tienen fecha y no avisan.
    """
    warnings = []
    fewer = fewer_races(previous.get("fastf1_races_per_season", {}), races)
    if fewer:
        warnings.append(
            f"La copia de FastF1 trae menos carreras que el snapshot ({'; '.join(fewer)}); "
            "se conservan las del snapshot."
        )
    used = (previous.get("fastf1_copy") or {}).get("generated_at")
    current = copy.get("generated_at")
    if used and current:
        try:
            older = datetime.fromisoformat(current) < datetime.fromisoformat(used)
        except (TypeError, ValueError):  # fecha ilegible, o una con zona y otra sin
            older = False
        if older:
            warnings.append(
                f"La copia de FastF1 ({current}) es más antigua que la usada en el snapshot "
                f"({used}): sus carreras sustituyen a versiones más recientes. Vuelve a publicarla "
                "con `f1-ingest fastf1-publish`."
            )
    return warnings


def pack_fastf1(bronze_dir: Path, out_dir: Path, seasons: list[int] | None = None) -> dict:
    """Empaqueta `bronze/fastf1` (y nada más) y escribe su manifiesto. Devuelve el manifiesto.

    Falla si la carpeta está vacía o tiene ficheros que la restauración rechazaría: mejor
    enterarse aquí que en el pipeline.
    """
    root = bronze_dir / "fastf1"
    files = [p for p in root.rglob("*") if p.is_file() and not p.name.endswith(".tmp")]
    if not files:
        raise FileNotFoundError(f"No hay datos de FastF1 en {root}")
    unexpected = [
        p
        for p in files
        if not FASTF1_MEMBER.fullmatch(f"bronze/{p.relative_to(bronze_dir).as_posix()}")
    ]
    if unexpected:
        raise ValueError(
            "Ficheros inesperados en bronze/fastf1 (solo se publican "
            "<tabla>/season=AAAA/round=RR.parquet): " + ", ".join(str(p) for p in unexpected[:5])
        )
    archive = _pack(bronze_dir, out_dir / FASTF1_ARCHIVE, ("fastf1",))
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "seasons_ingested": seasons or [],
        "fastf1_version": _package_version("fastf1"),
        "races_per_season": fastf1_races_per_season(bronze_dir),
        "files": {archive.name: {"bytes": archive.stat().st_size, "sha256": sha256(archive)}},
    }
    (out_dir / FASTF1_MANIFEST).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest


def restore_fastf1(archive: Path, data_dir: Path = DATA_DIR) -> dict[str, int]:
    """Superpone la copia de FastF1 publicada desde el equipo del autor.

    Solo admite ficheros normales `bronze/fastf1/<tabla>/season=AAAA/round=RR.parquet`. Se
    superpone (sin `replace`): cada carrera que trae sustituye a la del snapshot y las que no trae
    se conservan, así que publicar desde un equipo con menos temporadas no borra ninguna.
    Devuelve las carreras que trae la copia por temporada (sus Parquet de vueltas).
    """
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
    # Miembro a miembro (no por nombre): un enlace con el nombre de un Parquet válido no pasa.
    bad = [m.name for m in members if not (m.isfile() and FASTF1_MEMBER.fullmatch(m.name))]
    names = [m.name for m in members]
    if bad or not names:
        raise ValueError(f"{archive} no es una copia de FastF1: {', '.join(bad[:5])}")
    restore_bronze(archive, data_dir)
    races: dict[str, int] = {}
    for name in sorted(set(names)):
        parts = name.split("/")
        if parts[2] == "laps":
            season = parts[3].split("=")[1]
            races[season] = races.get(season, 0) + 1
    return races


def _openf1_files(bronze_dir: Path) -> dict[str, str]:
    """Ficheros de `bronze/openf1` (como `bronze/openf1/...`) con su SHA-256."""
    root = bronze_dir / "openf1"
    if not root.is_dir():
        return {}
    return {
        f"bronze/{path.relative_to(bronze_dir).as_posix()}": sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.name.endswith(".tmp")
    }


def openf1_sessions_per_season(files) -> dict[str, int]:
    """Sesiones de OpenF1 con algún endpoint cargado, por temporada."""
    sessions: dict[str, set[str]] = {}
    for name in files:
        match = OPENF1_SESSION_FILE.fullmatch(name)
        if match:
            sessions.setdefault(match[1], set()).add(match[2])
    return {season: len(keys) for season, keys in sorted(sessions.items())}


def pack_openf1(bronze_dir: Path, out_dir: Path) -> dict:
    """Empaqueta `bronze/openf1` y escribe su manifiesto. Devuelve el manifiesto.

    `content` (ruta → SHA-256 de cada fichero) y `content_sha256` describen el contenido con
    independencia del tar.gz, que cambia de bytes en cada empaquetado: con ellos se decide si hay
    que subir la copia y se comprueba que la nueva no pierde nada de la publicada.
    """
    from ingestion.openf1_loader import known_gaps

    files = _openf1_files(bronze_dir)
    if not files:
        raise FileNotFoundError(f"No hay datos de OpenF1 en {bronze_dir / 'openf1'}")
    unexpected = [name for name in files if not OPENF1_MEMBER.fullmatch(name)]
    if unexpected:
        raise ValueError(
            "Ficheros inesperados en bronze/openf1 (solo se publican "
            "<endpoint>/season=AAAA/session=N.parquet, el calendario y _gaps.json): "
            + ", ".join(unexpected[:5])
        )
    archive = _pack(bronze_dir, out_dir / OPENF1_ARCHIVE, ("openf1",))
    listing = "".join(f"{name}\t{digest}\n" for name, digest in sorted(files.items()))
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "sessions_per_season": openf1_sessions_per_season(files),
        "known_gaps": known_gaps(bronze_dir / "openf1"),
        "content_sha256": hashlib.sha256(listing.encode()).hexdigest(),
        "content": files,
        "files": {archive.name: {"bytes": archive.stat().st_size, "sha256": sha256(archive)}},
    }
    (out_dir / OPENF1_MANIFEST).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest


def restore_openf1(archive: Path, data_dir: Path = DATA_DIR) -> dict[str, int]:
    """Superpone la copia de OpenF1 (como la de FastF1: sin vaciar lo que ya hay).

    Solo admite ficheros normales que encajen en `OPENF1_MEMBER`; con cualquier otro miembro no
    se extrae nada. Devuelve las sesiones por temporada que trae la copia.
    """
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
    bad = [m.name for m in members if not (m.isfile() and OPENF1_MEMBER.fullmatch(m.name))]
    if bad or not members:
        raise ValueError(f"{archive} no es una copia de OpenF1: {', '.join(bad[:5])}")
    restore_bronze(archive, data_dir)
    return openf1_sessions_per_season(m.name for m in members)


def openf1_upload_decision(
    release_state: str, previous: dict | None, current: dict
) -> tuple[bool, str]:
    """Si hay que subir la copia nueva de OpenF1 y por qué.

    `release_state`: `missing` (no existe la release), `verified` (se descargó y su SHA-256
    cuadra; `previous` es su manifiesto) o `unverified` (existe, pero no se pudo descargar o el
    tarball no cuadra con su manifiesto, p. ej. una subida anterior que falló a medias).

    Nunca se sube si la copia nueva no contiene todos los ficheros que lista el manifiesto
    publicado o cambia alguno de sesión (no se reescriben nunca; el calendario y los huecos sí
    pueden cambiar). Sin verificar, solo se sube si se pudo leer ese manifiesto y la copia nueva
    lo contiene: así una subida a medias no deja la release sin actualizar para siempre (las
    sesiones que hubiera en un tarball más nuevo que su manifiesto y no estén en el snapshot ya
    se han vuelto a pedir en esta ejecución, porque faltaban). Si no se puede leer, no se
    sobrescribe; para recuperarla, se borra la release `bronze-openf1` y la siguiente ejecución
    la crea de nuevo a partir del snapshot más lo que falte.
    """
    if release_state == "missing":
        return True, "primera copia: no existe la release"
    old = (previous or {}).get("content") or {}
    if release_state != "verified" and not old:
        return False, (
            "la release existe pero no se pudo verificar ni leer su manifiesto: no se "
            "sobrescribe (para recuperarla, borra la release bronze-openf1)"
        )
    if release_state == "verified" and previous.get("content_sha256") == current.get(
        "content_sha256"
    ):
        return False, "sin cambios"
    new = current.get("content") or {}
    if not old:
        return False, "el manifiesto publicado no lista su contenido: no se sobrescribe"
    lost = sorted(name for name in old if name not in new)
    changed = sorted(
        name
        for name in old
        if name in new and new[name] != old[name] and OPENF1_SESSION_FILE.fullmatch(name)
    )
    if lost or changed:
        detail = "; ".join(
            ([f"faltan {len(lost)} ficheros, p. ej. {lost[0]}"] if lost else [])
            + ([f"cambian {len(changed)}, p. ej. {changed[0]}"] if changed else [])
        )
        return False, f"la copia nueva no contiene a la publicada ({detail}): no se sube"
    added = sum(name not in old for name in new)
    if release_state != "verified":
        return True, (
            f"la release no cuadraba con su manifiesto, pero la copia nueva lo contiene "
            f"({added} ficheros nuevos)"
        )
    return True, f"{added} ficheros nuevos"


def lap_data_races(warehouse: Path, bronze_dir: Path) -> dict:
    """Carreras con vueltas en bronze (FastF1 u OpenF1).

    - `latest`: la última carrera de F1DB con vueltas de alguna de las dos fuentes en bronze; la
      prueba de humo exige que la API devuelva sus vueltas.
    - `openf1_only`: las que tienen vueltas de OpenF1 y no de FastF1 (recordatorio de la rutina de
      FastF1 en el equipo del autor).

    Las sesiones de OpenF1 se casan con las carreras con `silver.int_openf1_sessions`.
    """
    fastf1 = {
        (int(path.parent.name.split("=")[1]), int(path.stem.split("=")[1]))
        for path in (bronze_dir / "fastf1" / "laps").glob("season=*/round=*.parquet")
    }
    import pyarrow.parquet as pq

    # Solo ficheros con filas: uno vacío no son vueltas (la ingesta ya no los escribe).
    openf1 = sorted(
        int(path.stem.split("=")[1])
        for path in (bronze_dir / "openf1" / "laps").glob("season=*/session=*.parquet")
        if pq.read_metadata(path).num_rows > 0
    )
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        races = con.execute(
            "select race_id, season, round, official_name, race_date from gold.dim_race"
        ).fetchall()
        has_sessions = con.execute(
            "select count(*) from duckdb_tables() "
            "where schema_name = 'silver' and table_name = 'int_openf1_sessions'"
        ).fetchone()[0]
        openf1_races = set()
        if has_sessions and openf1:
            openf1_races = {
                row[0]
                for row in con.execute(
                    "select race_id from silver.int_openf1_sessions "
                    "where is_race and race_id is not null and list_contains(?, session_key)",
                    [openf1],
                ).fetchall()
            }
    finally:
        con.close()
    with_laps = []
    for race_id, season, round_number, name, race_date in races:
        sources = [
            source
            for source, present in (
                ("fastf1", (season, round_number) in fastf1),
                ("openf1", race_id in openf1_races),
            )
            if present
        ]
        if sources:
            with_laps.append(
                (
                    race_date,
                    {
                        "race_id": race_id,
                        "season": season,
                        "round": round_number,
                        "name": name,
                        "sources": sources,
                    },
                )
            )
    with_laps.sort(key=lambda row: row[0])
    return {
        "latest": with_laps[-1][1] if with_laps else None,
        "openf1_only": [race for _, race in with_laps if race["sources"] == ["openf1"]],
    }


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
        columns = {
            row[0]
            for row in con.execute(
                "select column_name from duckdb_columns() "
                "where schema_name = 'quality' and table_name = 'qa_summary'"
            ).fetchall()
        }
        notices = {}
        if {"compared", "matched"} <= columns:
            notices = {
                check_id: compared - matched
                for check_id, compared, matched in con.execute(
                    "select check_id, compared, matched from quality.qa_summary "
                    "where list_contains(?, check_id)",
                    [list(NOTICE_CHECKS)],
                ).fetchall()
                if compared - matched > 0
            }
    finally:
        con.close()
    return {
        "f1db_release": read_metadata(bronze_dir / "f1db").get("release"),
        "fastf1_races_per_season": fastf1_races_per_season(bronze_dir),
        "last_completed_race": (
            {"season": last_race[0], "round": last_race[1], "name": last_race[2]}
            if last_race
            else None
        ),
        "quality_checks": quality,
        # Filas sin cruzar con F1DB que no se publican (avisos, no errores; ver NOTICE_CHECKS).
        "quality_notices": notices,
        "openf1_sessions_per_season": openf1_sessions_per_season(
            f"bronze/{path.relative_to(bronze_dir).as_posix()}"
            for path in (bronze_dir / "openf1").glob("*/season=*/session=*.parquet")
        ),
    }


def _copy_reference(copy: dict | None, archive: str) -> dict | None:
    """Fecha y SHA-256 de una copia superpuesta (FastF1 u OpenF1), o None si no se usó."""
    if not copy:
        return None
    return {
        "generated_at": copy.get("generated_at"),
        "sha256": copy.get("files", {}).get(archive, {}).get("sha256"),
    }


def pack(
    out_dir: Path,
    data_dir: Path = DATA_DIR,
    warehouse: Path | None = None,
    release_tag: str | None = None,
    fastf1_copy: dict | None = None,
    openf1_copy: dict | None = None,
) -> dict:
    """Genera el snapshot completo en `out_dir` y devuelve su manifiesto.

    `release_tag` es la release fechada donde se publicará: la API descarga la base de datos de
    ella, así que el `manifest.json` de `data-latest` funciona como puntero. `fastf1_copy` es el
    manifiesto de la copia de FastF1 superpuesta en esta ejecución (None si no se usó ninguna);
    `openf1_copy`, el de la copia de OpenF1 que corresponde al bronze de esta ejecución (la
    recién subida o la superpuesta), o None si no hay ninguna publicada que lo recoja.
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

    laps = lap_data_races(warehouse, bronze_dir)
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "release_tag": release_tag,
        "fastf1_copy": _copy_reference(fastf1_copy, FASTF1_ARCHIVE),
        "openf1_copy": _copy_reference(openf1_copy, OPENF1_ARCHIVE),
        **summarize(files[1], bronze_dir),
        "latest_race_with_lap_data": laps["latest"],
        "openf1_only_races": laps["openf1_only"],
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
    copy = manifest.get("fastf1_copy")
    openf1_copy = manifest.get("openf1_copy")
    openf1_seasons = manifest.get("openf1_sessions_per_season") or {}
    openf1_only = manifest.get("openf1_only_races") or []
    latest = manifest.get("latest_race_with_lap_data")
    notices = manifest.get("quality_notices") or {}
    lines = [
        f"Datos generados el {manifest['generated_at']} por el pipeline"
        + (f" (release {manifest['release_tag']})." if manifest.get("release_tag") else "."),
        "",
        f"- Última carrera con resultados: {race.get('season')} R{race.get('round')} "
        f"({race.get('name')})",
        f"- F1DB: {manifest.get('f1db_release')}",
        "- FastF1 (carreras por temporada): "
        + ", ".join(f"{season}: {n}" for season, n in seasons.items()),
        "- Copia de FastF1 (release bronze-fastf1): "
        + (
            f"la del {copy['generated_at']} (sha256 {(copy.get('sha256') or '')[:12]})"
            if copy
            else "no usada; FastF1 queda como en el snapshot anterior"
        ),
        "- OpenF1 (sesiones por temporada): "
        + (", ".join(f"{season}: {n}" for season, n in openf1_seasons.items()) or "ninguna"),
        "- Copia de OpenF1 (release bronze-openf1): "
        + (
            f"la del {openf1_copy['generated_at']} "
            f"(sha256 {(openf1_copy.get('sha256') or '')[:12]})"
            if openf1_copy
            else "ninguna publicada todavía"
        ),
        "- Última carrera con vueltas: "
        + (
            f"{latest['season']} R{latest['round']} ({latest['name']}; "
            f"{', '.join(latest['sources'])})"
            if latest
            else "ninguna"
        ),
        "- Carreras con vueltas solo de OpenF1 (falta cargar FastF1 con "
        "`uv run f1-ingest fastf1-publish --run-pipeline`): "
        + (
            ", ".join(f"{r['season']} R{r['round']} ({r['name']})" for r in openf1_only)
            if openf1_only
            else "ninguna"
        ),
        "- Controles de calidad: "
        + ", ".join(f"{status} {n}" for status, n in sorted(quality.items())),
        *[
            f"- **Aviso:** {n} {NOTICE_CHECKS.get(check_id, check_id)} (control {check_id})"
            for check_id, n in sorted(notices.items())
        ],
        "",
        "Fuentes: F1DB (CC BY 4.0), FastF1, OpenF1, formula1db.com (datos del TFG, con permiso "
        "para divulgación) y Ergast (solo validación).",
        "",
        "Licencia: no hay una única. F1DB y lo derivado de él, CC BY 4.0; la parte de Ergast, "
        "CC BY-NC-SA 3.0; lo derivado de OpenF1 (filas con source = 'openf1' y bronze/openf1), "
        "CC BY-NC-SA 4.0; el cronometraje de la F1 (FastF1), © Formula One, solo para uso "
        "académico no comercial; formula1db.com, con permiso de su autor. Detalle en "
        "https://github.com/AntonioSchez32/f1-data-platform#licencia-y-atribuciones",
    ]
    return "\n".join(lines) + "\n"
