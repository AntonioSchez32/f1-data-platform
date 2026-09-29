"""Caché HTTP, CORS, elección de la base de datos y descarga desde la release."""

import asyncio
import contextlib
import hashlib
import io
import json
import os
import urllib.error
from types import SimpleNamespace

import duckdb
import pytest
from fastapi.testclient import TestClient

from api.app import main, release
from api.app.config import Settings
from api.app.database import Database, resolve_database
from api.app.main import create_app


def test_get_responses_carry_etag_and_revalidate_with_304(client):
    first = client.get("/seasons/2024")
    etag = first.headers["etag"]
    assert "max-age=600" in first.headers["cache-control"]
    second = client.get("/seasons/2024", headers={"If-None-Match": etag})
    assert second.status_code == 304
    assert second.content == b""
    # Otra URL, otra ETag.
    assert client.get("/seasons/2023").headers["etag"] != etag


def test_health_is_not_cached(client):
    assert "etag" not in client.get("/health").headers


def test_errors_are_not_cached(client):
    assert "etag" not in client.get("/seasons/1900").headers


def test_cors_allows_only_configured_origin(client):
    allowed = client.get("/health", headers={"Origin": "https://f1.example.org"})
    assert allowed.headers["access-control-allow-origin"] == "https://f1.example.org"
    other = client.get("/health", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in other.headers


def test_database_swap_changes_version(sample_db_path, tmp_path):
    copy = tmp_path / "copy.duckdb"
    copy.write_bytes(sample_db_path.read_bytes())
    database = Database(sample_db_path)
    before = database.version.id
    manifest = {"files": {"f1.duckdb": {"sha256": "ab" * 32}}, "generated_at": "2026-10-05"}
    database.swap(copy, manifest)
    assert database.version.id == "ab" * 6
    assert database.query_one("select count(*) as n from gold.dim_race")["n"] > 1000
    assert database.version.id != before
    database.close()


def test_resolve_prefers_explicit_path(sample_db_path, tmp_path):
    settings = Settings(db_path=sample_db_path, data_repo="user/repo")
    assert resolve_database(settings)[0] == sample_db_path
    with pytest.raises(FileNotFoundError):
        resolve_database(Settings(db_path=tmp_path / "missing.duckdb"))


class FakeRelease:
    """Sustituye a GitHub: sirve un manifiesto y una base de datos desde memoria."""

    def __init__(self, payload: bytes, sha: str | None = None):
        self.payload = payload
        self.manifest = {
            "generated_at": "2026-10-05T06:10:00+00:00",
            "files": {"f1.duckdb": {"sha256": sha or hashlib.sha256(payload).hexdigest()}},
        }
        self.downloads = 0
        self.urls: list[str] = []
        # Errores que se lanzan, en orden, en las próximas peticiones (GitHub caído o lento).
        self.failures: list[Exception] = []
        self.down = False

    def assets(self, repo, tag, token):
        return {
            "manifest.json": {"url": "manifest"},
            "f1.duckdb": {"url": "database"},
        }

    def open(self, url, token, accept, timeout=60):
        self.urls.append(url)
        if self.down:
            raise urllib.error.URLError("sin conexión")
        if self.failures:
            raise self.failures.pop(0)
        if url == "database" or url.endswith("/f1.duckdb"):
            self.downloads += 1
            return io.BytesIO(self.payload)
        return io.BytesIO(json.dumps(self.manifest).encode())


@pytest.fixture
def fake_release(monkeypatch):
    def install(payload: bytes, sha: str | None = None) -> FakeRelease:
        fake = FakeRelease(payload, sha)
        monkeypatch.setattr(release, "_assets", fake.assets)
        monkeypatch.setattr(release, "_open", fake.open)
        monkeypatch.setattr(release.time, "sleep", lambda seconds: None)
        return fake

    return install


def test_download_is_verified_versioned_and_reused(fake_release, tmp_path):
    fake = fake_release(b"duckdb bytes")
    path, manifest = release.ensure_database("user/repo", "data-latest", "token", tmp_path)
    assert path.name == f"f1-{hashlib.sha256(b'duckdb bytes').hexdigest()[:12]}.duckdb"
    assert path.read_bytes() == b"duckdb bytes"
    assert manifest["generated_at"].startswith("2026-10-05")
    # Si ya está descargada y el SHA-256 coincide, no se vuelve a descargar.
    release.ensure_database("user/repo", "data-latest", "token", tmp_path)
    assert fake.downloads == 1


def test_download_with_wrong_checksum_is_discarded(fake_release, tmp_path):
    fake_release(b"corrupted", sha="0" * 64)
    with pytest.raises(ValueError, match="SHA-256"):
        release.ensure_database("user/repo", "data-latest", None, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_old_versions_are_removed(tmp_path):
    keep = tmp_path / "f1-new.duckdb"
    keep.write_bytes(b"new")
    (tmp_path / "f1-old.duckdb").write_bytes(b"old")
    release.remove_old_versions(tmp_path, keep)
    assert [p.name for p in tmp_path.iterdir()] == ["f1-new.duckdb"]


def test_public_repositories_use_direct_download_links(fake_release, tmp_path):
    # Sin token no se usa la API de GitHub (límite de 60 peticiones/hora por IP).
    fake = fake_release(b"public bytes")
    path, _ = release.ensure_database("user/repo", "data-latest", None, tmp_path)
    assert path.read_bytes() == b"public bytes"
    assert fake.urls == [
        "https://github.com/user/repo/releases/download/data-latest/manifest.json",
        "https://github.com/user/repo/releases/download/data-latest/f1.duckdb",
    ]


def test_database_comes_from_the_dated_release_named_in_the_manifest(fake_release, tmp_path):
    # data-latest solo hace de puntero: la base se descarga de la release fechada e inmutable.
    fake = fake_release(b"dated bytes")
    fake.manifest["release_tag"] = "data-2026-10-05"
    path, _ = release.ensure_database("user/repo", "data-latest", None, tmp_path)
    assert fake.urls == [
        "https://github.com/user/repo/releases/download/data-latest/manifest.json",
        "https://github.com/user/repo/releases/download/data-2026-10-05/f1.duckdb",
    ]
    # El manifiesto se guarda junto a la copia y no quedan temporales.
    assert sorted(p.suffix for p in tmp_path.iterdir()) == [".duckdb", ".json"]
    assert json.loads(path.with_suffix(".json").read_text("utf-8"))["release_tag"] == (
        "data-2026-10-05"
    )


def test_transient_errors_are_retried(fake_release, tmp_path):
    fake = fake_release(b"flaky bytes")
    fake.failures = [
        urllib.error.URLError("timeout"),
        urllib.error.HTTPError("url", 502, "Bad Gateway", {}, None),
    ]
    path, _ = release.ensure_database("user/repo", "data-latest", None, tmp_path)
    assert path.read_bytes() == b"flaky bytes"
    assert len(fake.urls) == 4  # dos fallos, el manifiesto y la base


def test_permanent_errors_are_not_retried(fake_release, tmp_path):
    fake = fake_release(b"bytes")
    fake.failures = [urllib.error.HTTPError("url", 404, "Not Found", {}, None)]
    with pytest.raises(urllib.error.HTTPError):
        release.ensure_database("user/repo", "data-missing", None, tmp_path)
    assert len(fake.urls) == 1


def test_seed_copy_avoids_the_download(fake_release, tmp_path):
    fake = fake_release(b"seed bytes")
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / f"f1-{hashlib.sha256(b'seed bytes').hexdigest()[:12]}.duckdb").write_bytes(
        b"seed bytes"
    )
    path, _ = release.ensure_database("user/repo", "data-latest", None, tmp_path / "data", [seed])
    assert path.parent == seed
    assert fake.downloads == 0


def published_copy(fake_release, sample_db_path, data_dir):
    """Descarga una versión (la base de ejemplo) y deja GitHub «caído»."""
    fake = fake_release(sample_db_path.read_bytes())
    release.ensure_database("user/repo", "data-latest", None, data_dir)
    fake.down = True
    return fake


def test_startup_falls_back_to_the_last_verified_copy(fake_release, sample_db_path, tmp_path):
    published_copy(fake_release, sample_db_path, tmp_path)
    resolved = resolve_database(Settings(data_repo="user/repo", data_dir=tmp_path))
    assert resolved.source == "copy"
    assert "URLError" in resolved.error
    assert resolved.manifest["generated_at"].startswith("2026-10-05")


def test_startup_without_github_nor_copies_fails(fake_release, tmp_path):
    fake = fake_release(b"bytes")
    fake.down = True
    with pytest.raises(urllib.error.URLError):
        resolve_database(Settings(data_repo="user/repo", data_dir=tmp_path))


def test_corrupted_copies_are_not_used(fake_release, sample_db_path, tmp_path):
    published_copy(fake_release, sample_db_path, tmp_path)
    for copy in tmp_path.glob("f1-*.duckdb"):
        copy.write_bytes(b"corrupted")
    assert release.latest_copy([tmp_path]) is None


def deny_reading(monkeypatch, directory):
    """Simula copias sin permiso de lectura en `directory` (en Windows no hay chmod real)."""
    real_sha256 = release.sha256

    def sha256(path):
        if path.parent == directory:
            raise PermissionError(13, "Permission denied", str(path))
        return real_sha256(path)

    monkeypatch.setattr(release, "sha256", sha256)


def test_unreadable_copies_do_not_break_the_startup(
    fake_release, sample_db_path, tmp_path, monkeypatch
):
    # La copia de la imagen se descargó como root: si la API no puede leerla, se descarta y se
    # sirve otra copia válida (o se falla con el error original de GitHub, no con el de permisos).
    seed = tmp_path / "seed"
    data = tmp_path / "data"
    published_copy(fake_release, sample_db_path, seed)
    deny_reading(monkeypatch, seed)
    assert release.latest_copy([data, seed]) is None
    with pytest.raises(urllib.error.URLError):
        resolve_database(Settings(data_repo="user/repo", data_dir=data, seed_dir=seed))


def test_unreadable_seed_is_downloaded_again(fake_release, sample_db_path, tmp_path, monkeypatch):
    seed = tmp_path / "seed"
    published_copy(fake_release, sample_db_path, seed).down = False
    deny_reading(monkeypatch, seed)
    path, _ = release.ensure_database("user/repo", "data-latest", None, tmp_path / "data", [seed])
    assert path.parent == tmp_path / "data"


@pytest.mark.skipif(os.name == "nt", reason="permisos POSIX")
def test_downloaded_copies_are_readable_by_other_users(fake_release, tmp_path):
    fake_release(b"bytes for everyone")
    path, _ = release.ensure_database("user/repo", "data-latest", None, tmp_path)
    assert path.stat().st_mode & 0o777 == 0o644


def test_health_queries_the_database_and_reports_the_refresh(client):
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert health["data"]["last_completed_race"]["season"] >= 2024
    assert health["refresh"]["source"] == "file"
    assert health["refresh"]["last_error"] is None


def test_health_is_degraded_when_serving_an_old_copy(fake_release, sample_db_path, tmp_path):
    published_copy(fake_release, sample_db_path, tmp_path)
    settings = Settings(data_repo="user/repo", data_dir=tmp_path, refresh_hours=0)
    with TestClient(create_app(settings=settings)) as api:
        health = api.get("/health").json()
    assert health["status"] == "degraded"
    assert health["refresh"]["source"] == "copy"
    assert health["refresh"]["last_success_at"] is None


def test_health_fails_when_the_database_does_not_answer(sample_db_path, tmp_path):
    copy = tmp_path / "copy.duckdb"
    copy.write_bytes(sample_db_path.read_bytes())
    database = Database(copy)
    with TestClient(create_app(Settings(refresh_hours=0), database=database)) as api:
        database._connection.close()
        assert api.get("/health").status_code == 503


def test_refresher_recovers_when_github_comes_back(
    fake_release, sample_db_path, tmp_path, monkeypatch
):
    # Arranque con una copia porque GitHub no responde.
    fake = published_copy(fake_release, sample_db_path, tmp_path / "data")
    settings = Settings(data_repo="user/repo", data_dir=tmp_path / "data", refresh_hours=6)
    resolved = resolve_database(settings)
    app = SimpleNamespace(
        state=SimpleNamespace(database=Database(resolved.path, resolved.manifest))
    )
    app.state.refresh = main.RefreshState.from_resolved(resolved)
    assert app.state.refresh.last_error is not None

    # GitHub vuelve con una versión nueva (primero un 404 que no se reintenta dentro del ciclo).
    newer = tmp_path / "newer.duckdb"
    newer.write_bytes(sample_db_path.read_bytes())
    with duckdb.connect(str(newer)) as con:
        con.execute("create table gold.extra as select 1 as x")
    fake.payload = newer.read_bytes()
    fake.manifest = {
        "generated_at": "2026-10-12T06:10:00+00:00",
        "files": {"f1.duckdb": {"sha256": hashlib.sha256(fake.payload).hexdigest()}},
    }
    fake.down = False
    fake.failures = [urllib.error.HTTPError("url", 404, "Not Found", {}, None)]
    # Tras un error se reintenta enseguida (en producción, a los 10 minutos).
    monkeypatch.setattr(main, "RETRY_AFTER_ERROR_SECONDS", 0)
    monkeypatch.setattr(main, "RETIRE_AFTER_SECONDS", 0)

    async def run() -> None:
        task = asyncio.create_task(main.refresh_periodically(app, settings))
        for _ in range(500):
            await asyncio.sleep(0.01)
            if app.state.refresh.source == "release":
                break
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    asyncio.run(run())
    state = app.state.refresh
    assert (state.source, state.last_error) == ("release", None)
    assert state.last_success_at is not None
    assert app.state.database.version.id == fake.manifest["files"]["f1.duckdb"]["sha256"][:12]
    assert app.state.database.version.generated_at.startswith("2026-10-12")
    app.state.database.close()
