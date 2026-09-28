import pandas as pd

from ingestion import io
from ingestion.fastf1_loader import downsample_by_distance, race_path, timedeltas_to_millis
from ingestion.legacy_loader import clean, snake_case


def test_timedeltas_to_millis_converts_and_renames():
    df = pd.DataFrame({"LapTime": pd.to_timedelta(["0:01:30.123", None]), "Driver": ["VER", "HAM"]})
    out = timedeltas_to_millis(df)
    assert "LapTime" not in out.columns
    assert out["LapTime_ms"].tolist()[0] == 90123
    assert pd.isna(out["LapTime_ms"].tolist()[1])


def test_downsample_keeps_one_sample_per_bin():
    tel = pd.DataFrame({"Distance": [0.0, 3.0, 9.9, 10.0, 15.0, 21.0]})
    assert downsample_by_distance(tel, step=10)["Distance"].tolist() == [0.0, 10.0, 21.0]


def test_race_path_is_partitioned():
    path = race_path("laps", 2024, 3)
    assert path.parts[-3:] == ("laps", "season=2024", "round=03.parquet")


def test_write_parquet_is_idempotent(tmp_path):
    target = tmp_path / "x" / "round=01.parquet"
    df = pd.DataFrame({"a": [1, 2]})
    io.write_parquet(df, target)
    io.write_parquet(df, target)
    assert len(pd.read_parquet(target)) == 2


def test_legacy_clean_drops_exact_duplicates_and_snake_cases():
    df = pd.DataFrame({"Car number": ["1", "1", "2"], "+-": ["-", "-", "+1"]})
    out, dropped = clean(df)
    assert dropped == 1
    assert list(out.columns) == ["car_number", "positions_change"]
    assert snake_case("Tyre Age") == "tyre_age"
