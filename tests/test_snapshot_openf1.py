"""Copia de OpenF1 (release bronze-openf1) y datos de OpenF1 en el manifiesto del snapshot."""

import io as io_module
import json
import tarfile

import duckdb
import pandas as pd
import pytest

from ingestion import io, snapshot
from tests.test_snapshot import make_data_dir


def add_openf1(data, endpoint, season, session_key, rows=1):
    io.write_parquet(
        pd.DataFrame({"a": range(rows)}),
        data
        / "bronze"
        / "openf1"
        / endpoint
        / f"season={season}"
        / f"session={session_key}.parquet",
    )


def test_openf1_archive_round_trip(tmp_path):
    data = make_data_dir(tmp_path / "data")
    add_openf1(data, "laps", 2026, 10, rows=3)
    add_openf1(data, "pit", 2026, 10)
    add_openf1(data, "laps", 2025, 9)
    io.write_parquet(
        pd.DataFrame({"a": [1]}), data / "bronze" / "openf1" / "sessions" / "season=2026.parquet"
    )
    (data / "bronze" / "openf1" / "_gaps.json").write_text(
        json.dumps({"7953": {"pit": {"status": 404}}}), "utf-8"
    )
    manifest = snapshot.pack_openf1(data / "bronze", tmp_path / "copia")

    assert manifest["sessions_per_season"] == {"2025": 1, "2026": 1}
    assert manifest["known_gaps"] == ["session 7953: pit"]
    assert len(manifest["content"]) == 5
    archive = tmp_path / "copia" / snapshot.OPENF1_ARCHIVE
    assert manifest["files"][snapshot.OPENF1_ARCHIVE]["sha256"] == snapshot.sha256(archive)
    # Volver a empaquetar lo mismo da otro tar.gz, pero el mismo contenido.
    again = snapshot.pack_openf1(data / "bronze", tmp_path / "copia2")
    assert again["content_sha256"] == manifest["content_sha256"]

    ci = make_data_dir(tmp_path / "ci")
    add_openf1(ci, "laps", 2024, 8)  # del snapshot: se conserva
    assert snapshot.restore_openf1(archive, data_dir=ci) == {"2025": 1, "2026": 1}
    assert len(pd.read_parquet(ci / "bronze/openf1/laps/season=2026/session=10.parquet")) == 3
    assert (ci / "bronze/openf1/laps/season=2024/session=8.parquet").exists()


@pytest.mark.parametrize(
    "arcname",
    [
        "bronze/openf1/laps/season=2026/session=10.parquet/../../../../formula1db/x.parquet",
        "bronze/openf1/laps/season=2026/evil.sh",
        "bronze/fastf1/laps/season=2026/round=01.parquet",
        "bronze/openf1/notas.json",
    ],
)
def test_openf1_restore_rejects_foreign_members(tmp_path, arcname):
    data = make_data_dir(tmp_path / "data")
    evil = tmp_path / "evil.tar.gz"
    with tarfile.open(evil, "w:gz") as tar:
        for name in ("bronze/openf1/laps/season=2026/session=3.parquet", arcname):
            member = tarfile.TarInfo(name)
            member.size = 1
            tar.addfile(member, io_module.BytesIO(b"x"))
    with pytest.raises(ValueError, match="no es una copia de OpenF1"):
        snapshot.restore_openf1(evil, data_dir=data)
    assert not (data / "bronze" / "openf1").exists()


def test_openf1_pack_rejects_unexpected_files(tmp_path):
    data = make_data_dir(tmp_path / "data")
    add_openf1(data, "laps", 2026, 10)
    (data / "bronze" / "openf1" / "notas.txt").write_text("x")
    with pytest.raises(ValueError, match="notas.txt"):
        snapshot.pack_openf1(data / "bronze", tmp_path / "copia")
    with pytest.raises(FileNotFoundError):
        snapshot.pack_openf1(tmp_path / "vacio", tmp_path / "copia")


def content(**files):
    listing = {f"bronze/openf1/{name}": digest for name, digest in files.items()}
    return {"content": listing, "content_sha256": json.dumps(listing, sort_keys=True)}


def test_openf1_upload_decision():
    session_1 = "laps/season=2026/session=1.parquet"
    session_2 = "laps/season=2026/session=2.parquet"
    old = content(**{session_1: "a", "_gaps.json": "g"})
    # Los huecos y el calendario sí pueden cambiar.
    grown = content(**{session_1: "a", session_2: "b", "_gaps.json": "g2"})
    assert snapshot.openf1_upload_decision("missing", None, old)[0] is True
    assert snapshot.openf1_upload_decision("verified", old, grown) == (True, "1 ficheros nuevos")
    assert snapshot.openf1_upload_decision("verified", old, old) == (False, "sin cambios")
    # La release existe pero no se verificó ni se pudo leer su manifiesto: no se sobrescribe.
    upload, reason = snapshot.openf1_upload_decision("unverified", None, grown)
    assert upload is False and "borra la release" in reason
    # Sin verificar (subida a medias), pero la copia nueva contiene lo que lista su manifiesto.
    upload, reason = snapshot.openf1_upload_decision("unverified", old, grown)
    assert upload is True and "no cuadraba" in reason
    # Sin verificar y la copia nueva pierde algo: no.
    lost_one = content(**{session_2: "b", "_gaps.json": "g"})
    assert snapshot.openf1_upload_decision("unverified", old, lost_one)[0] is False
    # La copia nueva pierde una sesión o cambia un fichero de sesión: no se sube.
    lost = content(**{session_2: "b", "_gaps.json": "g"})
    upload, reason = snapshot.openf1_upload_decision("verified", old, lost)
    assert upload is False and "faltan 1" in reason and session_1 in reason
    changed = content(**{session_1: "z", "_gaps.json": "g"})
    upload, reason = snapshot.openf1_upload_decision("verified", old, changed)
    assert upload is False and "cambian 1" in reason
    # Un manifiesto publicado sin la lista de contenido no se puede comprobar.
    assert snapshot.openf1_upload_decision("verified", {"content_sha256": "x"}, grown)[0] is False


def test_cli_pack_openf1_writes_github_outputs(tmp_path, monkeypatch):
    from ingestion import cli, config

    data = make_data_dir(tmp_path / "data")
    add_openf1(data, "laps", 2026, 10)
    monkeypatch.setattr(config, "BRONZE_DIR", data / "bronze")
    outputs = tmp_path / "outputs"
    monkeypatch.setenv("GITHUB_OUTPUT", str(outputs))
    out = tmp_path / "copia"
    args = ["snapshot", "pack-openf1", "--out", str(out), "--release-state", "missing"]
    assert cli.main(args) == 0
    assert outputs.read_text("utf-8").splitlines() == ["upload=true", "reference=new"]

    # Misma copia que la publicada (verificada): no se sube y el bronze corresponde a la anterior.
    outputs.unlink()
    args = ["snapshot", "pack-openf1", "--out", str(tmp_path / "otra"), "--release-state"]
    args += ["verified", "--previous", str(out / snapshot.OPENF1_MANIFEST)]
    assert cli.main(args) == 0
    assert outputs.read_text("utf-8").splitlines() == ["upload=false", "reference=previous"]

    # Sin datos de OpenF1 (la primera carga no obtuvo nada): no falla.
    outputs.unlink()
    monkeypatch.setattr(config, "BRONZE_DIR", tmp_path / "vacio")
    args = ["snapshot", "pack-openf1", "--out", str(out), "--release-state", "missing"]
    assert cli.main(args) == 0
    assert outputs.read_text("utf-8").splitlines() == ["upload=false", "reference=none"]


def test_manifest_records_lap_data_races_and_openf1(tmp_path):
    data = make_data_dir(tmp_path / "data")
    con = duckdb.connect(str(data / "gold" / "f1.duckdb"))
    con.execute(
        "insert into gold.dim_race values (2, 2026, 2, 'Second GP', date '2026-03-15', true), "
        "(3, 2026, 3, 'Third GP', date '2026-03-22', true)"
    )
    con.execute(
        "create table silver.int_openf1_sessions as select * from (values "
        "(20::bigint, true, 2), (21::bigint, false, 2), (30::bigint, true, null)) "
        "as t(session_key, is_race, race_id)"
    )
    con.execute(
        "create or replace table quality.qa_summary as select * from (values "
        "('x', 'PASS', 1, 1), ('openf1_lap_driver_attribution', 'INFO', 100, 97)) "
        "as t(check_id, status, compared, matched)"
    )
    con.close()
    add_openf1(data, "laps", 2026, 20)  # R2, solo OpenF1
    add_openf1(data, "laps", 2026, 30)  # sesión sin carrera de F1DB: no cuenta
    copy = snapshot.pack_openf1(data / "bronze", tmp_path / "copia")
    manifest = snapshot.pack(tmp_path / "dist", data_dir=data, openf1_copy=copy)

    # R3 es la última carrera disputada, pero sin vueltas: la prueba de humo mira la R2.
    assert manifest["latest_race_with_lap_data"] == {
        "race_id": 2,
        "season": 2026,
        "round": 2,
        "name": "Second GP",
        "sources": ["openf1"],
    }
    assert [r["round"] for r in manifest["openf1_only_races"]] == [2]
    assert manifest["openf1_sessions_per_season"] == {"2026": 2}
    assert manifest["quality_notices"] == {"openf1_lap_driver_attribution": 3}
    sha = copy["files"][snapshot.OPENF1_ARCHIVE]["sha256"]
    assert manifest["openf1_copy"] == {"generated_at": copy["generated_at"], "sha256": sha}
    notes = snapshot.release_notes(manifest)
    assert f"sha256 {sha[:12]}" in notes
    assert "2026 R2 (Second GP)" in notes
    assert "fastf1-publish" in notes
    assert "**Aviso:** 3 vueltas de OpenF1 sin piloto de F1DB" in notes
    assert "CC BY-NC-SA 4.0" in notes


def test_manifest_without_openf1(tmp_path):
    # Snapshots anteriores a D1: sin OpenF1 ni int_openf1_sessions; FastF1 da la última carrera.
    data = make_data_dir(tmp_path / "data")
    manifest = snapshot.pack(tmp_path / "dist", data_dir=data)
    assert manifest["latest_race_with_lap_data"]["sources"] == ["fastf1"]
    assert manifest["openf1_only_races"] == []
    assert manifest["openf1_copy"] is None
    assert manifest["quality_notices"] == {}
    assert "Copia de OpenF1 (release bronze-openf1): ninguna publicada" in snapshot.release_notes(
        manifest
    )
