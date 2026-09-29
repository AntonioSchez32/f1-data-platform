"""`f1-ingest fastf1-publish` sin llamar a GitHub: `gh` se sustituye por un doble."""

import json
import subprocess
import tarfile
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from ingestion import cli, fastf1_publish, io, snapshot


@pytest.fixture
def bronze(tmp_path, monkeypatch):
    bronze = tmp_path / "data" / "bronze"
    for season, round_number in [(2018, 14), (2026, 1), (2026, 2)]:
        io.write_parquet(
            pd.DataFrame({"a": [1]}),
            bronze / "fastf1" / "laps" / f"season={season}" / f"round={round_number:02d}.parquet",
        )
    io.write_parquet(pd.DataFrame({"a": [1]}), bronze / "formula1db" / "lap_times.parquet")
    monkeypatch.setattr(fastf1_publish, "BRONZE_DIR", bronze)

    def no_ingest(*args, **kwargs):
        raise AssertionError("no debería cargar nada")

    monkeypatch.setattr(fastf1_publish, "ingest", no_ingest)
    return bronze


class FakeGh:
    """Doble de `gh`: registra las órdenes y simula la release publicada."""

    def __init__(self, logged_in=True, release=None, fail=None):
        self.logged_in = logged_in
        # Manifiesto publicado (dict, o texto tal cual), o None si la release no existe.
        self.release = release
        # {"release upload": "stderr"}: órdenes que fallan con ese mensaje.
        self.fail = fail or {}
        self.calls = []

    def __call__(self, args, check=False, **kwargs):
        assert args[0] == "gh"
        self.calls.append(args[1:])
        command = " ".join(args[1:3])
        code, stderr = 0, ""
        if command in self.fail:
            code, stderr = 1, self.fail[command]
        elif command == "auth status":
            code = 0 if self.logged_in else 1
        elif command in ("release view", "release download") and self.release is None:
            code, stderr = 1, "release not found"
        elif command == "release download":
            content = self.release if isinstance(self.release, str) else json.dumps(self.release)
            target = Path(args[args.index("--dir") + 1]) / snapshot.FASTF1_MANIFEST
            target.write_text(content, encoding="utf-8")
        if check and code:
            raise subprocess.CalledProcessError(code, args, stderr=stderr)
        return subprocess.CompletedProcess(args, code, "", stderr)

    def commands(self):
        return [" ".join(c[:2]) for c in self.calls]


def test_without_gh_leaves_the_archive_in_dist(bronze, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fastf1_publish.shutil, "which", lambda name: None)
    gh = FakeGh()
    out = tmp_path / "dist"
    code = fastf1_publish.publish(out_dir=out, do_ingest=False, run=gh)

    assert code == 3
    assert gh.calls == []
    err = capsys.readouterr().err
    assert "no está instalada" in err
    assert "winget install GitHub.cli" in err and "gh auth login" in err
    with tarfile.open(out / snapshot.FASTF1_ARCHIVE) as tar:
        assert "bronze/fastf1/laps/season=2018/round=14.parquet" in tar.getnames()
        assert all(name.startswith("bronze/fastf1/") for name in tar.getnames())
    assert (out / snapshot.FASTF1_MANIFEST).exists()


def test_without_session_says_so(bronze, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fastf1_publish.shutil, "which", lambda name: "gh")
    gh = FakeGh(logged_in=False)
    assert fastf1_publish.publish(out_dir=tmp_path / "dist", do_ingest=False, run=gh) == 3
    assert gh.commands() == ["auth status"]
    assert "no tiene una sesión iniciada" in capsys.readouterr().err


def test_dry_run_does_not_touch_github(bronze, tmp_path, monkeypatch):
    monkeypatch.setattr(fastf1_publish.shutil, "which", pytest.fail)
    gh = FakeGh()
    assert (
        fastf1_publish.publish(out_dir=tmp_path / "dist", do_ingest=False, do_upload=False, run=gh)
        == 0
    )
    assert gh.calls == []
    assert (tmp_path / "dist" / snapshot.FASTF1_ARCHIVE).exists()


def test_first_publication_creates_the_release(bronze, tmp_path, monkeypatch):
    monkeypatch.setattr(fastf1_publish.shutil, "which", lambda name: "gh")
    gh = FakeGh(release=None)
    code = fastf1_publish.publish(
        out_dir=tmp_path / "dist", do_ingest=False, run_pipeline=True, repo="u/r", run=gh
    )

    assert code == 0
    assert gh.commands() == [
        "auth status",
        "release download",
        "release view",
        "release create",
        "release upload",
        "release upload",
        "release edit",
        "workflow run",
    ]
    uploads = [c[3] for c in gh.calls if c[:2] == ["release", "upload"]]
    # El manifiesto, el último: el pipeline compara con él el SHA-256 del tarball.
    assert [Path(u).name for u in uploads] == [snapshot.FASTF1_ARCHIVE, snapshot.FASTF1_MANIFEST]
    assert all(c[-2:] == ["--repo", "u/r"] for c in gh.calls[1:])
    assert all("--clobber" in c for c in gh.calls if c[:2] == ["release", "upload"])


def test_republishing_uploads_again_without_creating(bronze, tmp_path, monkeypatch):
    monkeypatch.setattr(fastf1_publish.shutil, "which", lambda name: "gh")
    gh = FakeGh(release={"generated_at": "x", "races_per_season": {"2018": 1, "2026": 2}})
    assert fastf1_publish.publish(out_dir=tmp_path / "dist", do_ingest=False, run=gh) == 0
    assert "release create" not in gh.commands()
    assert "workflow run" not in gh.commands()
    assert gh.commands().count("release upload") == 2


def test_refuses_to_publish_fewer_races_than_published(bronze, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fastf1_publish.shutil, "which", lambda name: "gh")
    published = {"generated_at": "2026-09-28T20:00:00+00:00", "races_per_season": {"2026": 3}}
    gh = FakeGh(release=published)
    assert fastf1_publish.publish(out_dir=tmp_path / "dist", do_ingest=False, run=gh) == 4
    assert "release upload" not in gh.commands()
    assert "2026: 2 de 3" in capsys.readouterr().err


def test_cli_publish_without_gh(bronze, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fastf1_publish.shutil, "which", lambda name: None)
    code = cli.main(["fastf1-publish", "--skip-ingest", "--out", str(tmp_path / "dist")])
    assert code == 3
    assert (tmp_path / "dist" / snapshot.FASTF1_ARCHIVE).exists()
    assert "winget install GitHub.cli" in capsys.readouterr().err


def test_ingest_failures_still_publish_the_rest(bronze, tmp_path, monkeypatch):
    monkeypatch.setattr(fastf1_publish, "ingest", lambda seasons: ["2026-R03 Test GP"])
    out = tmp_path / "dist"
    assert fastf1_publish.publish([2026], out_dir=out, do_upload=False) == 1
    manifest = json.loads((out / snapshot.FASTF1_MANIFEST).read_text(encoding="utf-8"))
    assert manifest["seasons_ingested"] == [2026]
    assert manifest["races_per_season"] == {"2018": 1, "2026": 2}


def test_default_seasons_include_the_previous_one_in_january():
    assert fastf1_publish.default_seasons(date(2027, 1, 15)) == [2026, 2027]
    assert fastf1_publish.default_seasons(date(2026, 9, 30)) == [2026]


def test_cli_restore_warns_when_the_copy_has_fewer_races(tmp_path, monkeypatch, capsys):
    previous = tmp_path / "manifest.json"
    previous.write_text(json.dumps({"fastf1_races_per_season": {"2026": 15}}), encoding="utf-8")
    monkeypatch.setattr(snapshot, "restore_fastf1", lambda archive: {"2026": 14})
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    code = cli.main(
        ["snapshot", "restore-fastf1", str(tmp_path / "x.tar.gz"), "--previous", str(previous)]
    )
    assert code == 0  # se avisa y se sigue: la superposición conserva las del snapshot
    assert "::warning::La copia de FastF1 trae menos carreras" in capsys.readouterr().out


def test_relative_out_dir_uploads_the_new_archive(bronze, tmp_path, monkeypatch):
    # gh se ejecuta desde la raíz del repositorio: las rutas que recibe deben ser absolutas.
    workdir = tmp_path / "transform"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.setattr(fastf1_publish.shutil, "which", lambda name: "gh")
    gh = FakeGh(release=None)
    assert fastf1_publish.publish(out_dir=Path("dist"), do_ingest=False, run=gh) == 0
    uploads = [Path(c[3]) for c in gh.calls if c[:2] == ["release", "upload"]]
    assert uploads == [
        workdir / "dist" / snapshot.FASTF1_ARCHIVE,
        workdir / "dist" / snapshot.FASTF1_MANIFEST,
    ]
    assert all(path.is_absolute() and path.exists() for path in uploads)


@pytest.mark.parametrize(
    ("gh", "message"),
    [
        (FakeGh(fail={"release download": "HTTP 502: Bad Gateway"}), "HTTP 502"),
        (FakeGh(release="{no es json"), "no es un JSON válido"),
    ],
)
def test_github_errors_stop_before_uploading(bronze, tmp_path, monkeypatch, capsys, gh, message):
    monkeypatch.setattr(fastf1_publish.shutil, "which", lambda name: "gh")
    assert fastf1_publish.publish(out_dir=tmp_path / "dist", do_ingest=False, run=gh) == 5
    assert "release upload" not in gh.commands()
    err = capsys.readouterr().err
    assert "No se pudo consultar la copia publicada" in err and message in err


def test_failed_upload_says_how_to_retry(bronze, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fastf1_publish.shutil, "which", lambda name: "gh")
    gh = FakeGh(release=None, fail={"release upload": "connection reset"})
    assert fastf1_publish.publish(out_dir=tmp_path / "dist", do_ingest=False, run=gh) == 6
    err = capsys.readouterr().err
    assert "La subida a la release bronze-fastf1 falló" in err and "--skip-ingest" in err


def test_failed_pipeline_launch_says_the_copy_is_published(bronze, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fastf1_publish.shutil, "which", lambda name: "gh")
    gh = FakeGh(release=None, fail={"workflow run": "HTTP 403"})
    code = fastf1_publish.publish(
        out_dir=tmp_path / "dist", do_ingest=False, run_pipeline=True, run=gh
    )
    assert code == 7
    assert gh.commands().count("release upload") == 2
    assert "La copia SÍ está publicada" in capsys.readouterr().err


def test_missing_gh_is_reported_before_loading(bronze, tmp_path, monkeypatch):
    monkeypatch.setattr(fastf1_publish.shutil, "which", lambda name: None)
    events = []
    monkeypatch.setattr(fastf1_publish, "_error", lambda message: events.append("error"))
    monkeypatch.setattr(fastf1_publish, "ingest", lambda seasons: events.append("ingest") or [])
    assert fastf1_publish.publish([2026], out_dir=tmp_path / "dist", run=FakeGh()) == 3
    # Se avisa antes de cargar, y se carga y empaqueta igual para subirla a mano.
    assert events == ["error", "ingest", "error"]
    assert (tmp_path / "dist" / snapshot.FASTF1_ARCHIVE).exists()


def test_cli_restore_warns_when_the_copy_is_older(tmp_path, monkeypatch, capsys):
    previous = tmp_path / "manifest.json"
    previous.write_text(
        json.dumps(
            {
                "fastf1_races_per_season": {"2026": 15},
                "fastf1_copy": {"generated_at": "2026-09-28T20:00:00+00:00", "sha256": "x"},
            }
        ),
        encoding="utf-8",
    )
    copy = tmp_path / "bronze-fastf1.json"
    copy.write_text(json.dumps({"generated_at": "2026-09-21T20:00:00+00:00"}), encoding="utf-8")
    monkeypatch.setattr(snapshot, "restore_fastf1", lambda archive: {"2026": 15})
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    args = ["snapshot", "restore-fastf1", str(tmp_path / "x.tar.gz"), "--previous", str(previous)]
    assert cli.main([*args, "--copy-manifest", str(copy)]) == 0
    assert "Aviso: La copia de FastF1 (2026-09-21" in capsys.readouterr().out


def test_empty_release_is_treated_as_not_published(bronze, tmp_path, monkeypatch):
    # Release creada a mano, o primera subida fallida: existe, pero sin ficheros.
    monkeypatch.setattr(fastf1_publish.shutil, "which", lambda name: "gh")
    gh = FakeGh(release={}, fail={"release download": "no assets to download"})
    assert fastf1_publish.publish(out_dir=tmp_path / "dist", do_ingest=False, run=gh) == 0
    assert "release create" not in gh.commands()
    assert gh.commands().count("release upload") == 2
