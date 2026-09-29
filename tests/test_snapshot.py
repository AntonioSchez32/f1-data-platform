import io as io_module
import json
import tarfile
import zipfile
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from ingestion import io, snapshot


def make_data_dir(root):
    """Árbol de datos mínimo: bronze con las cuatro fuentes y un almacén con gold y quality."""
    bronze = root / "bronze"
    io.write_parquet(pd.DataFrame({"a": [1]}), bronze / "formula1db" / "lap_times.parquet")
    io.write_parquet(pd.DataFrame({"a": [1]}), bronze / "ergast" / "lap_times.parquet")
    io.write_parquet(
        pd.DataFrame({"a": [1, 2]}), bronze / "fastf1" / "laps" / "season=2026" / "round=01.parquet"
    )
    io.write_metadata(bronze / "f1db", release="v2026.15.1")
    warehouse = root / "gold" / "f1.duckdb"
    warehouse.parent.mkdir(parents=True)
    con = duckdb.connect(str(warehouse))
    con.execute("create schema gold; create schema quality; create schema silver")
    con.execute(
        "create table gold.dim_race as select 1 as race_id, 2026 as season, 1 as round, "
        "'Test GP' as official_name, date '2026-03-08' as race_date, true as is_completed"
    )
    con.execute("create table quality.qa_summary as select 'x' as check_id, 'PASS' as status")
    con.execute("create table silver.int_laptimes as select 1 as lap")
    con.close()
    return root


def test_pack_and_restore_round_trip(tmp_path):
    data = make_data_dir(tmp_path / "data")
    manifest = snapshot.pack(tmp_path / "dist", data_dir=data)

    assert manifest["f1db_release"] == "v2026.15.1"
    assert manifest["fastf1_races_per_season"] == {"2026": 1}
    assert manifest["last_completed_race"]["name"] == "Test GP"
    assert set(manifest["files"]) == {"bronze.tar.gz", "f1.duckdb", "gold-parquet.zip"}

    restored = tmp_path / "restored"
    sources = snapshot.restore_bronze(tmp_path / "dist" / "bronze.tar.gz", data_dir=restored)
    assert sources == ["ergast", "f1db", "fastf1", "formula1db"]
    assert (restored / "gold").is_dir()
    assert len(pd.read_parquet(restored / "bronze/fastf1/laps/season=2026/round=01.parquet")) == 2


def test_api_database_keeps_only_gold_and_quality_summary(tmp_path):
    data = make_data_dir(tmp_path / "data")
    snapshot.pack(tmp_path / "dist", data_dir=data)
    con = duckdb.connect(str(tmp_path / "dist" / "f1.duckdb"), read_only=True)
    schemas = {r[0] for r in con.execute("select schema_name from duckdb_tables()").fetchall()}
    assert schemas == {"gold", "quality"}
    with zipfile.ZipFile(tmp_path / "dist" / "gold-parquet.zip") as zf:
        assert zf.namelist() == ["dim_race.parquet"]


def test_pack_requires_static_sources(tmp_path):
    data = make_data_dir(tmp_path / "data")
    for path in (data / "bronze" / "ergast").iterdir():
        path.unlink()
    (data / "bronze" / "ergast").rmdir()
    with pytest.raises(FileNotFoundError, match="ergast"):
        snapshot.pack(tmp_path / "dist", data_dir=data)


def test_restore_rejects_foreign_archives(tmp_path):
    evil = tmp_path / "evil.tar.gz"
    payload = tmp_path / "x.txt"
    payload.write_text("x")
    with tarfile.open(evil, "w:gz") as tar:
        tar.add(payload, arcname="../x.txt")
    with pytest.raises(ValueError):
        snapshot.restore_bronze(evil, data_dir=tmp_path / "data")


def test_release_notes_summarize_manifest(tmp_path):
    data = make_data_dir(tmp_path / "data")
    manifest = snapshot.pack(tmp_path / "dist", data_dir=data)
    notes = snapshot.release_notes(json.loads(json.dumps(manifest)))
    assert "2026 R1 (Test GP)" in notes
    assert "F1DB: v2026.15.1" in notes
    assert "PASS 1" in notes


def test_manifest_points_to_the_dated_release(tmp_path):
    data = make_data_dir(tmp_path / "data")
    manifest = snapshot.pack(tmp_path / "dist", data_dir=data, release_tag="data-2026-10-05")
    assert manifest["release_tag"] == "data-2026-10-05"
    assert "(release data-2026-10-05)" in snapshot.release_notes(manifest)
    assert "Licencia:" in snapshot.release_notes(manifest)


def test_declared_table_changes_are_allowed():
    previous = {"gold.a": 100, "gold.b": 1000, "gold.c": 50}
    current = {"gold.b": 700, "gold.c": 49}
    # Sin declarar: la tabla eliminada y la pérdida del 30 % fallan; la del 2 % se tolera.
    assert snapshot.table_count_regressions(previous, current) == [
        "gold.a desaparece",
        "gold.b pasa de 1000 a 700 filas (límite 2%)",
    ]
    declared = {"removed": ["gold.a"], "shrink": {"gold.b": 0.35}}
    assert snapshot.table_count_regressions(previous, current, declared) == []


def test_expected_changes_file_is_valid():
    path = Path(__file__).parents[1] / "api" / "tests" / "smoke" / "cambios_esperados.json"
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert set(expected) == {"removed", "shrink"}
    assert all(0 < fraction < 1 for fraction in expected["shrink"].values())


def test_static_restore_replaces_the_sources(tmp_path):
    data = make_data_dir(tmp_path / "data")
    archive = snapshot.pack_static(data / "bronze", tmp_path / "bronze-static.tar.gz")
    stray = data / "bronze" / "ergast" / "sobrante.parquet"
    stray.write_bytes(b"x")
    snapshot.restore_bronze(archive, data_dir=data)
    assert stray.exists()  # sin replace solo se superpone
    snapshot.restore_bronze(archive, data_dir=data, replace=True)
    assert not stray.exists()
    assert (data / "bronze" / "fastf1").is_dir()  # las demás fuentes no se tocan


def test_static_archive_holds_only_the_static_sources(tmp_path):
    data = make_data_dir(tmp_path / "data")
    archive = snapshot.pack_static(data / "bronze", tmp_path / "bronze-static.tar.gz")
    with tarfile.open(archive) as tar:
        sources = {name.split("/")[1] for name in tar.getnames()}
    assert sources == {"formula1db", "ergast"}
    # Se restaura con el mismo comando que el snapshot completo.
    restored = snapshot.restore_bronze(archive, data_dir=tmp_path / "restored")
    assert restored == ["ergast", "formula1db"]


def test_static_archive_requires_non_empty_sources(tmp_path):
    data = make_data_dir(tmp_path / "data")
    for path in (data / "bronze" / "formula1db").iterdir():
        path.unlink()
    with pytest.raises(FileNotFoundError, match="formula1db"):
        snapshot.pack_static(data / "bronze", tmp_path / "bronze-static.tar.gz")


def test_restore_rejects_source_names_that_escape_bronze(tmp_path):
    data = make_data_dir(tmp_path / "data")
    evil = tmp_path / "evil.tar.gz"
    payload = tmp_path / "x.txt"
    payload.write_text("x")
    with tarfile.open(evil, "w:gz") as tar:
        tar.add(payload, arcname="bronze/../gold/x.txt")
    with pytest.raises(ValueError):
        snapshot.restore_bronze(evil, data_dir=data, replace=True)
    assert (data / "gold" / "f1.duckdb").exists()


def add_fastf1_race(data, kind, season, round_number, rows=1):
    io.write_parquet(
        pd.DataFrame({"a": range(rows)}),
        data
        / "bronze"
        / "fastf1"
        / kind
        / f"season={season}"
        / f"round={round_number:02d}.parquet",
    )


def test_fastf1_archive_holds_exactly_bronze_fastf1(tmp_path):
    data = make_data_dir(tmp_path / "data")
    add_fastf1_race(data, "laps", 2018, 14)
    add_fastf1_race(data, "quali_results", 2018, 14)
    # Restos de una escritura a medias: no se publican.
    (data / "bronze" / "fastf1" / "laps" / "season=2018" / "round=15.parquet.tmp").write_bytes(b"x")
    manifest = snapshot.pack_fastf1(data / "bronze", tmp_path / "dist", [2018])

    archive = tmp_path / "dist" / snapshot.FASTF1_ARCHIVE
    with tarfile.open(archive) as tar:
        names = sorted(tar.getnames())
    assert names == [
        "bronze/fastf1/laps/season=2018/round=14.parquet",
        "bronze/fastf1/laps/season=2026/round=01.parquet",
        "bronze/fastf1/quali_results/season=2018/round=14.parquet",
    ]
    assert manifest["races_per_season"] == {"2018": 1, "2026": 1}
    assert manifest["seasons_ingested"] == [2018]
    assert manifest["files"][snapshot.FASTF1_ARCHIVE]["sha256"] == snapshot.sha256(archive)
    written = json.loads((tmp_path / "dist" / snapshot.FASTF1_MANIFEST).read_text("utf-8"))
    assert written == manifest


def test_fastf1_pack_rejects_unexpected_files(tmp_path):
    data = make_data_dir(tmp_path / "data")
    (data / "bronze" / "fastf1" / "notas.txt").write_text("x")
    with pytest.raises(ValueError, match="notas.txt"):
        snapshot.pack_fastf1(data / "bronze", tmp_path / "dist")
    empty = tmp_path / "vacio" / "bronze"
    (empty / "fastf1").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        snapshot.pack_fastf1(empty, tmp_path / "dist")


def test_fastf1_restore_overlays_the_snapshot(tmp_path):
    local = make_data_dir(tmp_path / "local")
    add_fastf1_race(local, "laps", 2018, 14, rows=5)
    add_fastf1_race(local, "laps", 2026, 1, rows=7)  # recargada: sustituye a la del snapshot
    snapshot.pack_fastf1(local / "bronze", tmp_path / "dist")
    # El snapshot del pipeline tiene una carrera que la copia local no trae.
    ci = make_data_dir(tmp_path / "ci")
    add_fastf1_race(ci, "laps", 2026, 2, rows=3)
    stray = ci / "bronze" / "ergast" / "lap_times.parquet"

    races = snapshot.restore_fastf1(tmp_path / "dist" / snapshot.FASTF1_ARCHIVE, data_dir=ci)

    assert races == {"2018": 1, "2026": 1}
    laps = ci / "bronze" / "fastf1" / "laps"
    assert len(pd.read_parquet(laps / "season=2018" / "round=14.parquet")) == 5
    assert len(pd.read_parquet(laps / "season=2026" / "round=01.parquet")) == 7
    assert len(pd.read_parquet(laps / "season=2026" / "round=02.parquet")) == 3  # se conserva
    assert stray.exists()  # las demás fuentes no se tocan
    assert snapshot.fastf1_races_per_season(ci / "bronze") == {"2018": 1, "2026": 2}


@pytest.mark.parametrize(
    "arcname",
    [
        "bronze/formula1db/lap_times.parquet",
        "bronze/f1db/_metadata.json",
        "bronze/fastf1/laps/season=2026/round=01.parquet/../../../../formula1db/x.parquet",
        "bronze/fastf1/laps/season=2026/evil.sh",
        "bronze/fastf1/laps/season=26/round=01.parquet",
        "../fastf1/laps/season=2026/round=01.parquet",
        "/bronze/fastf1/laps/season=2026/round=01.parquet",
    ],
)
def test_fastf1_restore_rejects_foreign_members(tmp_path, arcname):
    data = make_data_dir(tmp_path / "data")
    original = (data / "bronze" / "formula1db" / "lap_times.parquet").read_bytes()
    evil = tmp_path / "evil.tar.gz"
    with tarfile.open(evil, "w:gz") as tar:
        # Con TarInfo, no con tar.add, que quitaría la barra inicial de las rutas absolutas.
        for name in ("bronze/fastf1/laps/season=2026/round=03.parquet", arcname):
            member = tarfile.TarInfo(name)
            member.size = 1
            tar.addfile(member, io_module.BytesIO(b"x"))
    with pytest.raises(ValueError, match="no es una copia de FastF1"):
        snapshot.restore_fastf1(evil, data_dir=data)
    # Se rechaza antes de extraer nada.
    assert not (data / "bronze" / "fastf1" / "laps" / "season=2026" / "round=03.parquet").exists()
    assert (data / "bronze" / "formula1db" / "lap_times.parquet").read_bytes() == original


def test_fastf1_restore_rejects_links(tmp_path):
    data = make_data_dir(tmp_path / "data")
    evil = tmp_path / "evil.tar.gz"
    with tarfile.open(evil, "w:gz") as tar:
        link = tarfile.TarInfo("bronze/fastf1/laps/season=2026/round=03.parquet")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../../formula1db/lap_times.parquet"
        tar.addfile(link)
    with pytest.raises(ValueError, match="no es una copia de FastF1"):
        snapshot.restore_fastf1(evil, data_dir=data)


def test_fewer_races_lists_the_seasons_that_lose_races():
    assert snapshot.fewer_races({"2025": 24, "2026": 15}, {"2025": 24, "2026": 16}) == []
    assert snapshot.fewer_races({"2025": 24, "2026": 15}, {"2026": 14}) == [
        "2025: 0 de 24",
        "2026: 14 de 15",
    ]


def test_manifest_and_notes_record_the_fastf1_copy(tmp_path):
    data = make_data_dir(tmp_path / "data")
    copy = snapshot.pack_fastf1(data / "bronze", tmp_path / "copia")
    manifest = snapshot.pack(tmp_path / "dist", data_dir=data, fastf1_copy=copy)
    sha = copy["files"][snapshot.FASTF1_ARCHIVE]["sha256"]
    assert manifest["fastf1_copy"] == {"generated_at": copy["generated_at"], "sha256": sha}
    assert f"sha256 {sha[:12]}" in snapshot.release_notes(manifest)

    without = snapshot.pack(tmp_path / "dist2", data_dir=data)
    assert without["fastf1_copy"] is None
    assert "Copia de FastF1 (release bronze-fastf1): no usada" in snapshot.release_notes(without)


def test_fastf1_copy_warnings():
    previous = {
        "fastf1_races_per_season": {"2026": 15},
        "fastf1_copy": {"generated_at": "2026-09-28T20:00:00+00:00", "sha256": "x"},
    }
    newer = {"generated_at": "2026-10-05T20:00:00+00:00"}
    older = {"generated_at": "2026-09-21T20:00:00+00:00"}
    assert snapshot.fastf1_copy_warnings(previous, {"2026": 16}, newer) == []
    fewer, old = snapshot.fastf1_copy_warnings(previous, {"2026": 14}, older)
    assert "menos carreras" in fewer and "2026: 14 de 15" in fewer
    assert "más antigua que la usada" in old
    # Manifiestos anteriores a este cambio (sin fastf1_copy) o copia sin manifiesto: sin avisos.
    legacy = {"fastf1_races_per_season": {"2026": 15}}
    assert snapshot.fastf1_copy_warnings(legacy, {"2026": 15}, older) == []
    assert snapshot.fastf1_copy_warnings({**previous, "fastf1_copy": None}, {"2026": 15}, {}) == []
    assert snapshot.fastf1_copy_warnings({}, {"2026": 15}, {}) == []


def test_fastf1_copy_warnings_tolerate_unreadable_dates():
    previous = {"fastf1_copy": {"generated_at": "2026-09-28T20:00:00+00:00"}}
    for generated_at in ("2026-09-21T20:00:00", "ayer", 20260921):  # sin zona, texto, número
        assert snapshot.fastf1_copy_warnings(previous, {}, {"generated_at": generated_at}) == []
