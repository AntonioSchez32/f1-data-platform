import fastf1
import pandas as pd
import pytest

from ingestion import fastf1_loader, io
from ingestion.fastf1_loader import (
    downsample_by_distance,
    race_path,
    timedeltas_to_millis,
    tolerate_tyre_info_errors,
)
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


def test_fastf1_tyre_info_errors_fall_back_to_uncorrected_data(monkeypatch):
    # Italia 2018: FastF1 3.8.3 lanza IndexError al corregir los neumáticos y pierde las vueltas.
    calls = []

    def failing_fix(self, df, stint_split_times):
        calls.append(len(df))
        df.loc[0, "Stint"] = 99  # la corrección modifica los datos antes de fallar
        raise IndexError("list index out of range")

    monkeypatch.setattr(fastf1.core.Session, "_Session__fix_tyre_info", failing_fix)
    tolerate_tyre_info_errors()
    tolerate_tyre_info_errors()  # idempotente: no se envuelve dos veces
    patched = fastf1.core.Session._Session__fix_tyre_info
    df = pd.DataFrame({"Stint": [0, 1], "Compound": ["SOFT", "MEDIUM"]})
    out = patched(object(), df, [])
    assert out["Stint"].tolist() == [0, 1]  # sin la corrección a medias
    assert calls == [2]


def test_fastf1_tyre_info_other_errors_are_not_hidden(monkeypatch):
    def failing_fix(self, df, stint_split_times):
        raise KeyError("Stint")

    monkeypatch.setattr(fastf1.core.Session, "_Session__fix_tyre_info", failing_fix)
    tolerate_tyre_info_errors()
    with pytest.raises(KeyError):
        fastf1.core.Session._Session__fix_tyre_info(object(), pd.DataFrame({"Stint": [0]}), [])


def test_fastf1_without_the_private_method_keeps_loading(monkeypatch, caplog):
    # Si una versión nueva de FastF1 renombra el método, el rodeo no se instala y no rompe nada.
    monkeypatch.delattr(fastf1.core.Session, "_Session__fix_tyre_info")
    with caplog.at_level("WARNING"):
        assert tolerate_tyre_info_errors() is False
    assert "no se instala el rodeo" in caplog.text


def test_load_season_skips_old_telemetry_and_reports_tyre_fixes(monkeypatch, tmp_path):
    monkeypatch.setattr(fastf1_loader, "OUT_DIR", tmp_path)
    monkeypatch.setattr(fastf1_loader, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(fastf1.Cache, "enable_cache", lambda *args, **kwargs: None)
    monkeypatch.setattr(fastf1_loader, "tolerate_tyre_info_errors", lambda: True)
    schedule = pd.DataFrame({"RoundNumber": [13, 14], "EventName": ["Belgian GP", "Italian GP"]})
    monkeypatch.setattr(fastf1_loader, "completed_races", lambda season: schedule)
    calls = []

    def load_race(event, season):
        calls.append(("race", int(event["RoundNumber"])))
        if event["RoundNumber"] == 14:  # como Italia 2018: FastF1 no corrige los neumáticos
            fastf1_loader.tyre_fix_skipped.append("Italian GP")

    monkeypatch.setattr(fastf1_loader, "_load_race", load_race)
    monkeypatch.setattr(
        fastf1_loader,
        "_load_qualifying",
        lambda event, season, telemetry: calls.append(("quali", telemetry)),
    )
    summary = fastf1_loader.load_season(2018, telemetry=True)
    # 2018 < TELEMETRY_FIRST_SEASON: la clasificación se carga sin telemetría.
    assert calls == [("race", 13), ("quali", False), ("race", 14), ("quali", False)]
    assert summary.tyre_fix_skipped == ["2018-R14 Italian GP"]
    assert len(summary.loaded) == 2
