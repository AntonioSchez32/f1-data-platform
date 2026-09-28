"""Caché HTTP, CORS, elección de la base de datos y descarga desde la release."""

import hashlib
import io
import json

import pytest

from api.app import release
from api.app.config import Settings
from api.app.database import Database, resolve_database


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

    def assets(self, repo, tag, token):
        return {
            "manifest.json": {"url": "manifest"},
            "f1.duckdb": {"url": "database"},
        }

    def open(self, url, token, accept, timeout=60):
        if url == "database":
            self.downloads += 1
            return io.BytesIO(self.payload)
        return io.BytesIO(json.dumps(self.manifest).encode())


@pytest.fixture
def fake_release(monkeypatch):
    def install(payload: bytes, sha: str | None = None) -> FakeRelease:
        fake = FakeRelease(payload, sha)
        monkeypatch.setattr(release, "_assets", fake.assets)
        monkeypatch.setattr(release, "_open", fake.open)
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
