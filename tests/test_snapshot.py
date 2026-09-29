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
