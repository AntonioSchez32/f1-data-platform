import json
import tarfile
import zipfile

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
