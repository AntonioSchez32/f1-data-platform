"""Descarga de la base de datos desde la GitHub Release que publica el pipeline.

Solo usa la biblioteca estándar.
- Repositorio público (sin token): enlaces directos de descarga de la release, que no consumen
  el límite de 60 peticiones/hora de la API de GitHub (compartido por IP en los servicios cloud).
- Repositorio privado: API de GitHub con un token de lectura de contenidos. La descarga redirige
  a un almacén externo que rechaza la cabecera Authorization, así que la redirección se sigue a
  mano sin ella.

Cada versión se guarda como `f1-<sha256[:12]>.duckdb`: así la versión nueva puede abrirse mientras
la anterior sigue en uso (en Windows un fichero abierto no puede reemplazarse).
"""

import contextlib
import hashlib
import json
import logging
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

API = "https://api.github.com"
DATABASE_ASSET = "f1.duckdb"
MANIFEST_ASSET = "manifest.json"
USER_AGENT = "f1-data-platform-api"


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
    url = _asset_url(repo, tag, MANIFEST_ASSET, token)
    with _open(url, token, "application/octet-stream") as response:
        return json.load(response)


def ensure_database(repo: str, tag: str, token: str | None, data_dir: Path) -> tuple[Path, dict]:
    """Devuelve la base de datos de la versión publicada, descargándola si hace falta.

    Solo se da por buena si su SHA-256 coincide con el del manifiesto.
    """
    manifest = fetch_manifest(repo, tag, token)
    target = versioned_path(data_dir, manifest)
    expected = database_sha(manifest)
    if target.exists() and sha256(target) == expected:
        return target, manifest

    data_dir.mkdir(parents=True, exist_ok=True)
    url = _asset_url(repo, tag, DATABASE_ASSET, token)
    tmp = target.with_suffix(".download")
    with (
        _open(url, token, "application/octet-stream", 600) as response,
        open(tmp, "wb") as f,
    ):
        while chunk := response.read(1 << 20):
            f.write(chunk)
    if sha256(tmp) != expected:
        tmp.unlink(missing_ok=True)
        raise ValueError(f"El SHA-256 de {DATABASE_ASSET} no coincide con el manifiesto")
    tmp.replace(target)
    log.info("Datos descargados de %s@%s (%s)", repo, tag, manifest.get("generated_at"))
    return target, manifest


def remove_old_versions(data_dir: Path, keep: Path) -> None:
    """Borra las versiones descargadas que ya no se usan (si otro proceso las tiene, las deja)."""
    for path in data_dir.glob("f1-*.duckdb"):
        if path != keep:
            with contextlib.suppress(OSError):
                path.unlink()
