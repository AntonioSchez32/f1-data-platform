"""Descarga de la base de datos desde las GitHub Releases que publica el pipeline.

Solo usa la biblioteca estándar.
- Repositorio público (sin token): enlaces directos de descarga de la release, que no consumen
  el límite de 60 peticiones/hora de la API de GitHub (compartido por IP en los servicios cloud).
- Repositorio privado: API de GitHub con un token de lectura de contenidos. La descarga redirige
  a un almacén externo que rechaza la cabecera Authorization, así que la redirección se sigue a
  mano sin ella.

El `manifest.json` de `data-latest` hace de puntero: indica la release fechada e inmutable
(`release_tag`, p. ej. `data-2026-10-05`) de la que se descarga `f1.duckdb`. Así, mientras el
pipeline sobrescribe los ficheros de `data-latest`, la API nunca descarga una base a medio subir.
Los manifiestos antiguos, sin `release_tag`, siguen funcionando: la base se pide a la misma release.

Cada versión se guarda como `f1-<sha256[:12]>.duckdb` con su manifiesto al lado
(`f1-<sha256[:12]>.json`): así la versión nueva puede abrirse mientras la anterior sigue en uso (en
Windows un fichero abierto no puede reemplazarse) y, si GitHub falla, la API puede arrancar con la
última copia verificada (ver `latest_copy`).

Uso como programa (la imagen Docker lo usa para llevar una copia de respaldo):
    python -m api.app.release --repo usuario/f1-data-platform --out /opt/f1-seed
"""

import argparse
import contextlib
import hashlib
import http.client
import json
import logging
import os
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger(__name__)

API = "https://api.github.com"
DATABASE_ASSET = "f1.duckdb"
MANIFEST_ASSET = "manifest.json"
USER_AGENT = "f1-data-platform-api"

# Reintentos ante fallos transitorios de GitHub: 3 intentos, con esperas de 2 y 4 s.
ATTEMPTS = 3
# El manifiesto es pequeño: si GitHub no contesta pronto, mejor pasar a la copia local (uvicorn no
# abre el puerto hasta terminar el arranque). La base (unos 55 MB) tiene más margen.
MANIFEST_TIMEOUT_SECONDS = 15
DATABASE_TIMEOUT_SECONDS = 600
BACKOFF_SECONDS = 2.0
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def _open(url: str, token: str | None, accept: str, timeout: int = 60):
    headers = {"Accept": accept, "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        return _opener.open(urllib.request.Request(url, headers=headers), timeout=timeout)
    except urllib.error.HTTPError as err:
        if err.code in (301, 302, 303, 307, 308):
            location = urllib.request.Request(
                err.headers["Location"], headers={"User-Agent": USER_AGENT}
            )
            return urllib.request.urlopen(location, timeout=timeout)
        raise


def _is_transient(error: Exception) -> bool:
    if isinstance(error, urllib.error.HTTPError):
        return error.code in RETRYABLE_STATUS
    # Errores de red: DNS, conexión rechazada o cortada, tiempo de espera agotado, respuesta
    # cortada a mitad (IncompleteRead) o TLS. OSError no: FileNotFoundError es un error definitivo.
    return isinstance(
        error,
        urllib.error.URLError
        | TimeoutError
        | ConnectionError
        | http.client.HTTPException
        | ssl.SSLError,
    )


def describe_error(error: BaseException) -> str:
    """Texto breve del error para los logs y /health (que es público)."""
    return f"{type(error).__name__}: {error}"[:300]


def _retry[T](action: Callable[[], T], what: str) -> T:
    """Ejecuta `action` y la repite con espera exponencial si el fallo es transitorio."""
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return action()
        except Exception as error:
            if attempt == ATTEMPTS or not _is_transient(error):
                raise
            delay = BACKOFF_SECONDS * 2 ** (attempt - 1)
            log.warning("%s falló (%s); reintento %d en %.0f s", what, error, attempt, delay)
            time.sleep(delay)
    raise AssertionError("inalcanzable")


def _assets(repo: str, tag: str, token: str | None) -> dict[str, dict]:
    url = f"{API}/repos/{repo}/releases/tags/{tag}"
    with _open(url, token, "application/vnd.github+json") as response:
        release = json.load(response)
    return {asset["name"]: asset for asset in release.get("assets", [])}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def database_sha(manifest: dict) -> str:
    return manifest["files"][DATABASE_ASSET]["sha256"]


def _is_verified(path: Path, expected_sha: str) -> bool:
    """Si la copia se puede leer y su SHA-256 es el esperado. Una copia ilegible (p. ej. sin
    permiso de lectura para el usuario de la API) se descarta: no debe impedir el arranque."""
    try:
        return sha256(path) == expected_sha
    except OSError as error:
        log.warning("Se descarta %s: no se puede leer (%s)", path, error)
        return False


def versioned_path(data_dir: Path, manifest: dict) -> Path:
    return data_dir / f"f1-{database_sha(manifest)[:12]}.duckdb"


def _asset_url(repo: str, tag: str, name: str, token: str | None) -> str:
    """URL de descarga de un fichero de la release (directa si no hay token)."""
    if not token:
        return f"https://github.com/{repo}/releases/download/{tag}/{name}"
    assets = _assets(repo, tag, token)
    if name not in assets:
        raise FileNotFoundError(f"La release {tag} de {repo} no tiene {name}")
    return assets[name]["url"]


def fetch_manifest(repo: str, tag: str, token: str | None) -> dict:
    """Manifiesto de la release: fecha, versión de las fuentes y SHA-256 de cada fichero."""

    def fetch() -> dict:
        url = _asset_url(repo, tag, MANIFEST_ASSET, token)
        with _open(url, token, "application/octet-stream", MANIFEST_TIMEOUT_SECONDS) as response:
            return json.load(response)

    return _retry(fetch, f"Descarga del manifiesto de {repo}@{tag}")


def _download(url: str, token: str | None, target_dir: Path) -> Path:
    """Descarga a un temporal con nombre único (varios procesos pueden descargar a la vez)."""
    with (
        _open(url, token, "application/octet-stream", DATABASE_TIMEOUT_SECONDS) as response,
        tempfile.NamedTemporaryFile(dir=target_dir, suffix=".download", delete=False) as f,
    ):
        tmp = Path(f.name)
        try:
            while chunk := response.read(1 << 20):
                f.write(chunk)
        except BaseException:
            f.close()
            tmp.unlink(missing_ok=True)
            raise
    # NamedTemporaryFile crea el fichero con permisos 0600: la copia de respaldo de la imagen se
    # descarga como root y la API la lee con otro usuario.
    with contextlib.suppress(OSError):
        tmp.chmod(0o644)
    return tmp


def _find_copy(manifest: dict, dirs: list[Path]) -> Path | None:
    """Una copia ya descargada (o incluida en la imagen) cuyo SHA-256 es el del manifiesto."""
    expected = database_sha(manifest)
    for directory in dirs:
        candidate = versioned_path(directory, manifest)
        if candidate.exists() and _is_verified(candidate, expected):
            return candidate
    return None


def ensure_database(
    repo: str,
    tag: str,
    token: str | None,
    data_dir: Path,
    seed_dirs: list[Path] | None = None,
) -> tuple[Path, dict]:
    """Devuelve la base de datos de la versión publicada, descargándola si hace falta.

    Solo se da por buena si su SHA-256 coincide con el del manifiesto. Antes de descargar se busca
    en `data_dir` y en `seed_dirs` (la copia de respaldo de la imagen Docker).
    """
    manifest = fetch_manifest(repo, tag, token)
    if found := _find_copy(manifest, [data_dir, *(seed_dirs or [])]):
        return found, manifest

    data_dir.mkdir(parents=True, exist_ok=True)
    source_tag = manifest.get("release_tag") or tag
    expected = database_sha(manifest)

    def download() -> Path:
        url = _asset_url(repo, source_tag, DATABASE_ASSET, token)
        return _download(url, token, data_dir)

    tmp = _retry(download, f"Descarga de {DATABASE_ASSET} de {repo}@{source_tag}")
    if sha256(tmp) != expected:
        tmp.unlink(missing_ok=True)
        raise ValueError(f"El SHA-256 de {DATABASE_ASSET} no coincide con el manifiesto")
    target = versioned_path(data_dir, manifest)
    tmp.replace(target)
    # El manifiesto se guarda al lado: permite arrancar con esta copia si GitHub falla.
    target.with_suffix(".json").write_text(json.dumps(manifest, ensure_ascii=False), "utf-8")
    log.info("Datos descargados de %s@%s (%s)", repo, source_tag, manifest.get("generated_at"))
    return target, manifest


def latest_copy(dirs: list[Path]) -> tuple[Path, dict] | None:
    """La copia verificada más reciente (por fecha de generación) entre las ya descargadas."""
    copies = []
    for directory in dirs:
        for sidecar in directory.glob("f1-*.json"):
            with contextlib.suppress(OSError, ValueError, KeyError, TypeError):
                manifest = json.loads(sidecar.read_text("utf-8"))
                path = versioned_path(directory, manifest)
                if path.exists():
                    copies.append((manifest.get("generated_at") or "", path, manifest))
    for _, path, manifest in sorted(copies, key=lambda c: c[0], reverse=True):
        if _is_verified(path, database_sha(manifest)):
            return path, manifest
        log.warning("Se descarta %s: no coincide con su manifiesto", path)
    return None


def remove_old_versions(data_dir: Path, keep: Path) -> None:
    """Borra las versiones descargadas que ya no se usan (si otro proceso las tiene, las deja)."""
    for path in data_dir.glob("f1-*.duckdb"):
        if path != keep:
            with contextlib.suppress(OSError):
                path.unlink()
                path.with_suffix(".json").unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    """Descarga la versión publicada en `--out` (copia de respaldo de la imagen Docker)."""
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument(
        "--repo", required=True, help="Repositorio, p. ej. usuario/f1-data-platform"
    )
    parser.add_argument("--tag", default="data-latest")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    path, manifest = ensure_database(
        args.repo, args.tag, os.environ.get("F1_GITHUB_TOKEN"), args.out
    )
    print(f"{path} ({manifest.get('generated_at')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
