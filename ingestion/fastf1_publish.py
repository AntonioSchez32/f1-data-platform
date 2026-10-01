"""Carga FastF1 en el equipo del autor y la publica para el pipeline (`f1-ingest fastf1-publish`).

El servidor de cronometraje de la F1 (livetiming.formula1.com, detrás de CloudFront) responde 403
a los runners de GitHub Actions con cualquier User-Agent y 200 desde una conexión doméstica, así
que el pipeline no puede descargar FastF1. Tras cada GP, esta orden:

1. carga las temporadas indicadas (por defecto, la en curso) con la ingesta de siempre;
2. empaqueta todo `data/bronze/fastf1` en `dist/bronze-fastf1.tar.gz` con su manifiesto
   (`bronze-fastf1.json`: fecha, carreras por temporada y SHA-256);
3. los sube con la CLI `gh` a la release `bronze-fastf1` (el manifiesto el último) y, si se pide,
   lanza el pipeline, que superpone la copia al último snapshot.

Sin `gh` (o sin sesión) deja los ficheros en `dist/` y explica cómo subirlos a mano.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from datetime import date
from pathlib import Path

from ingestion import snapshot
from ingestion.config import BRONZE_DIR, PROJECT_ROOT

RELEASE_TAG = "bronze-fastf1"
WORKFLOW = "pipeline.yml"
RELEASE_TITLE = "FastF1 (copia cargada en el equipo del autor)"
INSTALL_HELP = (
    "Instala la CLI de GitHub e inicia sesión:\n"
    "    winget install GitHub.cli\n"
    "    gh auth login\n"
    "(abre una terminal nueva tras instalarla) y vuelve a ejecutar la orden."
)

Runner = Callable[..., subprocess.CompletedProcess]


def default_seasons(today: date | None = None) -> list[int]:
    """La temporada en curso; en enero, también la anterior (carreras de final de año)."""
    today = today or date.today()
    return [today.year - 1, today.year] if today.month == 1 else [today.year]


def ingest(
    seasons: list[int],
    rounds: list[int] | None = None,
    telemetry: bool = True,
    force: bool = False,
) -> list[str]:
    """Carga las temporadas (la telemetría, solo desde 2024: el cargador la omite antes) y
    devuelve las carreras con error. Si se alcanza el límite de peticiones, lo indica y deja el
    resto para otra ejecución (la carga es incremental)."""
    from ingestion import fastf1_loader

    failed = []
    for season in seasons:
        summary = fastf1_loader.load_season(season, rounds=rounds, telemetry=telemetry, force=force)
        print(
            f"{season}: {len(summary.loaded)} cargadas, "
            f"{len(summary.skipped)} ya existentes, {len(summary.failed)} con error"
        )
        failed += summary.failed
        for label in summary.tyre_fix_skipped:
            print(f"  Aviso: {label} cargada con los neumáticos sin corregir (rodeo de FastF1)")
        for label in summary.extras_failed:
            print(f"  Aviso: {label} sin dirección de carrera o meteo; se reintentará")
        if summary.rate_limited:
            print(
                "Límite de 500 peticiones/hora de la API alcanzado; "
                "vuelve a ejecutar la orden más tarde para continuar."
            )
            break
    return failed


class GhError(Exception):
    """Una orden de `gh` falló por algo distinto de «la release no existe»."""


def _capture(run: Runner, args: list[str]) -> subprocess.CompletedProcess:
    # UTF-8 explícito: con text=True, Windows decodificaría la salida de gh con cp1252.
    return run(
        args,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        cwd=PROJECT_ROOT,
    )


def _not_found(result: subprocess.CompletedProcess) -> bool:
    """`gh` indica que la release o el fichero no existen (no es un error de red o permisos)."""
    stderr = (result.stderr or "").lower()
    return any(
        text in stderr for text in ("release not found", "no assets match", "no assets to download")
    )


def gh_problem(run: Runner = subprocess.run) -> str | None:
    """Por qué no se puede usar `gh` (no instalado o sin sesión), o None si está lista."""
    if shutil.which("gh") is None:
        return "La CLI de GitHub (gh) no está instalada o no está en el PATH."
    if _capture(run, ["gh", "auth", "status"]).returncode != 0:
        return "La CLI de GitHub (gh) no tiene una sesión iniciada."
    return None


def release_notes(manifest: dict) -> str:
    seasons = manifest.get("races_per_season", {})
    return (
        f"Copia de `bronze/fastf1` cargada con FastF1 {manifest.get('fastf1_version')} en el "
        f"equipo del autor el {manifest['generated_at']}: el servidor de cronometraje de la F1 "
        "rechaza las conexiones desde GitHub Actions. El pipeline la superpone al último "
        "snapshot en cada ejecución. Se actualiza con `f1-ingest fastf1-publish`.\n\n"
        "Carreras por temporada: " + ", ".join(f"{s}: {n}" for s, n in seasons.items()) + "\n\n"
        "Licencia: cronometraje © Formula One World Championship Limited (F1 Live Timing), sin "
        "licencia abierta; se redistribuye solo con fines académicos y no comerciales.\n"
    )


def published_manifest(repo: str | None = None, run: Runner = subprocess.run) -> dict | None:
    """El `bronze-fastf1.json` publicado, o None si aún no hay release o no tiene manifiesto.

    Cualquier otro fallo (red, permisos, repositorio sin determinar, JSON dañado) lanza
    `GhError`: sin el manifiesto no se puede comprobar que la copia local esté completa.
    """
    target = ["--repo", repo] if repo else []
    with tempfile.TemporaryDirectory() as tmp:
        result = _capture(
            run,
            [
                "gh",
                "release",
                "download",
                RELEASE_TAG,
                "--pattern",
                snapshot.FASTF1_MANIFEST,
                "--dir",
                tmp,
                *target,
            ],
        )
        path = Path(tmp) / snapshot.FASTF1_MANIFEST
        if result.returncode != 0:
            if _not_found(result):
                return None
            raise GhError(f"gh release download: {(result.stderr or '').strip()}")
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise GhError(
                f"el {snapshot.FASTF1_MANIFEST} publicado no es un JSON válido ({exc}); "
                f"bórralo de la release {RELEASE_TAG} y vuelve a ejecutar la orden"
            ) from exc


def upload(
    out_dir: Path, manifest: dict, repo: str | None = None, run: Runner = subprocess.run
) -> None:
    """Sube la copia a la release `bronze-fastf1`, creándola si no existe.

    Lanza `GhError` o `subprocess.CalledProcessError` si algo falla.
    """
    target = ["--repo", repo] if repo else []

    def gh(*args: str) -> subprocess.CompletedProcess:
        # Sin capturar la salida: el progreso y los errores de gh se ven en la consola.
        return run(["gh", *args, *target], check=True, cwd=PROJECT_ROOT)

    notes = release_notes(manifest)
    exists = _capture(run, ["gh", "release", "view", RELEASE_TAG, *target])
    if exists.returncode != 0:
        if not _not_found(exists):
            raise GhError(f"gh release view: {(exists.stderr or '').strip()}")
        gh(
            "release",
            "create",
            RELEASE_TAG,
            "--latest=false",
            "--title",
            RELEASE_TITLE,
            "--notes",
            notes,
        )
    # El manifiesto va el último: el pipeline comprueba con él el SHA-256 del tarball, así que
    # si lo descarga a mitad de la subida lo detecta y sigue con el FastF1 del snapshot.
    gh("release", "upload", RELEASE_TAG, str(out_dir / snapshot.FASTF1_ARCHIVE), "--clobber")
    gh("release", "upload", RELEASE_TAG, str(out_dir / snapshot.FASTF1_MANIFEST), "--clobber")
    gh("release", "edit", RELEASE_TAG, "--notes", notes)


def _error(message: str) -> None:
    sys.stdout.flush()  # los mensajes de stderr, después de lo ya escrito en stdout
    print(message, file=sys.stderr)


def publish(
    seasons: list[int] | None = None,
    out_dir: Path = Path("dist"),
    bronze_dir: Path | None = None,
    do_ingest: bool = True,
    do_upload: bool = True,
    run_pipeline: bool = False,
    repo: str | None = None,
    run: Runner = subprocess.run,
) -> int:
    """Carga, empaqueta y publica. Devuelve el código de salida de la orden:

    - 0: publicada (o empaquetada, con `do_upload=False`).
    - 1: publicada, pero alguna carrera no se pudo cargar (se reintenta la próxima vez).
    - 3: sin `gh` utilizable (no instalada o sin sesión): la copia queda en `out_dir`.
    - 4: la copia local tiene menos carreras que la publicada: no se sube nada.
    - 5: no se pudo consultar la release publicada (red, permisos, manifiesto dañado).
    - 6: falló la subida: hay que repetirla (el pipeline usa entretanto el FastF1 del snapshot).
    - 7: la copia se publicó, pero no se pudo lanzar el pipeline.
    """
    # Absoluta: gh se ejecuta desde la raíz del repositorio, no desde el directorio actual.
    out_dir = out_dir.resolve()
    seasons = seasons or default_seasons()
    bronze_dir = bronze_dir or BRONZE_DIR

    # Antes de cargar nada (la carga puede tardar): se avisa ya, pero se carga y empaqueta igual
    # para poder subir la copia a mano.
    problem = gh_problem(run) if do_upload else None
    if problem:
        _error(f"{problem}\n{INSTALL_HELP}\nSe carga y empaqueta igualmente para subirla a mano.")

    failed = ingest(seasons) if do_ingest else []
    manifest = snapshot.pack_fastf1(bronze_dir, out_dir, seasons if do_ingest else None)
    info = manifest["files"][snapshot.FASTF1_ARCHIVE]
    print(f"{out_dir / snapshot.FASTF1_ARCHIVE}: {info['bytes']} bytes, sha256 {info['sha256']}")
    print(
        "Carreras por temporada: "
        + ", ".join(f"{s}: {n}" for s, n in manifest["races_per_season"].items())
    )
    for label in failed:
        _error(f"  ERROR: {label} (se publica el resto; vuelve a intentarlo más tarde)")

    if not do_upload:
        print("--dry-run: no se sube nada ni se consulta GitHub.")
        return 1 if failed else 0

    if problem:
        _error(
            f"{problem}\n{INSTALL_HELP}\n"
            f"También puedes subir a mano {snapshot.FASTF1_ARCHIVE} y, después, "
            f"{snapshot.FASTF1_MANIFEST} (están en {out_dir}) desde la página Releases del "
            f"repositorio en GitHub, a la release {RELEASE_TAG} (si no existe, créala con la "
            "etiqueta bronze-fastf1 y sin marcar «Set as the latest release»)."
        )
        return 3

    try:
        published = published_manifest(repo, run)
    except GhError as exc:
        _error(f"No se pudo consultar la copia publicada: {exc}\nNo se sube nada.")
        return 5
    if published:
        fewer = snapshot.fewer_races(
            published.get("races_per_season", {}), manifest["races_per_season"]
        )
        if fewer:
            _error(
                "La copia local tiene menos carreras que la publicada el "
                f"{published.get('generated_at')} ({'; '.join(fewer)}). ¿Falta algo en "
                f"{bronze_dir / 'fastf1'}? No se sube nada: publicar desde aquí no borraría esas "
                "carreras (el pipeline superpone la copia), pero indica un equipo incompleto."
            )
            return 4

    try:
        upload(out_dir, manifest, repo, run)
    except (GhError, subprocess.CalledProcessError) as exc:
        _error(
            f"La subida a la release {RELEASE_TAG} falló ({exc}). Vuelve a ejecutar la orden con "
            "--skip-ingest; mientras tanto, el pipeline sigue con el FastF1 del último snapshot "
            "(detecta una copia a medio subir por su SHA-256)."
        )
        return 6
    print(f"Publicada la release {RELEASE_TAG}.")

    if run_pipeline:
        try:
            run(
                ["gh", "workflow", "run", WORKFLOW, *(["--repo", repo] if repo else [])],
                check=True,
                cwd=PROJECT_ROOT,
            )
        except subprocess.CalledProcessError as exc:
            _error(
                f"La copia SÍ está publicada, pero no se pudo lanzar el pipeline ({exc}). "
                f"Lánzalo con `gh workflow run {WORKFLOW}` o desde la pestaña Actions "
                "(«Pipeline de datos» → Run workflow); si no, se ejecutará el lunes a las "
                "06:00 UTC."
            )
            return 7
        print("Pipeline lanzado: sigue su progreso con `gh run watch` o en la pestaña Actions.")
    else:
        print(
            "El pipeline la usará en su próxima ejecución (lunes, 06:00 UTC); para no esperar, "
            "vuelve a ejecutar la orden con --skip-ingest --run-pipeline."
        )
    return 1 if failed else 0
