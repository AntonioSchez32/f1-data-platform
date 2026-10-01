"""Dirección de carrera y meteo de FastF1 (D1): se añaden sin tocar las vueltas ya cargadas."""

import fastf1
import pandas as pd

from ingestion import fastf1_loader, io
from ingestion.fastf1_loader import race_control_frame, race_path, session_t0

# Página RaceControlMessages tal como la devuelve fetch_page: [tiempo de sesión, contenido].
RESPONSE = [
    [
        "00:13:32.225",
        {"Messages": [{"Utc": "2025-07-27T12:19:00", "Lap": 1, "Category": "Other"}]},
    ],
    [
        "00:56:30.182",
        {
            "Messages": {
                "3": {
                    "Utc": "2025-07-27T13:01:58",
                    "Lap": 1,
                    "Category": "Flag",
                    "Flag": "RED",
                    "Scope": "Track",
                    "Message": "RED FLAG",
                }
            }
        },
    ],
    ["00:57:00.000"],  # línea sin contenido: se ignora
]


def test_race_control_frame_keeps_utc_and_session_time():
    df = race_control_frame(RESPONSE)
    assert len(df) == 2
    assert df["SessionTime_ms"].tolist() == [812225, 3390182]
    assert df["Time"].tolist() == [
        pd.Timestamp("2025-07-27 12:19:00"),
        pd.Timestamp("2025-07-27 13:01:58"),
    ]
    assert df.loc[1, "Flag"] == "RED" and df.loc[1, "Message"] == "RED FLAG"
    assert pd.isna(df.loc[0, "Flag"])
    assert df["Lap"].tolist() == [1, 1]


def test_session_t0_takes_the_message_with_least_delay():
    t0 = session_t0(race_control_frame(RESPONSE))
    # 12:19:00 - 13:32.225 = 12:05:27.775; 13:01:58 - 56:30.182 = 12:05:27.818 (menos retraso).
    assert t0 == pd.Timestamp("2025-07-27 12:05:27.818")
    assert session_t0(race_control_frame([])) is None


def test_extras_are_added_without_rewriting_existing_laps(monkeypatch, tmp_path):
    monkeypatch.setattr(fastf1_loader, "OUT_DIR", tmp_path)
    monkeypatch.setattr(fastf1_loader, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(fastf1.Cache, "enable_cache", lambda *args, **kwargs: None)
    monkeypatch.setattr(fastf1_loader, "tolerate_tyre_info_errors", lambda: True)
    schedule = pd.DataFrame({"RoundNumber": [13], "EventName": ["Belgian Grand Prix"]})
    monkeypatch.setattr(fastf1_loader, "completed_races", lambda season: schedule)
    for kind in ("laps", "quali_results"):
        io.write_parquet(pd.DataFrame({"a": [1]}), race_path(kind, 2025, 13))
    laps_before = race_path("laps", 2025, 13).read_bytes()

    class Api:
        @staticmethod
        def fetch_page(path, name):
            return RESPONSE

        @staticmethod
        def weather_data(path):
            return {"Time": [pd.Timedelta(seconds=36.172)], "AirTemp": [18.8]}

    class Session:
        api_path = "/static/2025/x/"

    class Event(dict):
        def get_session(self, name):
            assert name == "R"
            return Session()

    monkeypatch.setattr(fastf1_loader, "_live_timing_api", lambda: Api)
    monkeypatch.setattr(
        fastf1_loader, "_load_race", lambda *a: (_ for _ in ()).throw(AssertionError("laps"))
    )
    rows = [Event(RoundNumber=13, EventName="Belgian Grand Prix")]
    monkeypatch.setattr(pd.DataFrame, "iterrows", lambda self: enumerate(rows))

    summary = fastf1_loader.load_season(2025)

    assert summary.loaded == ["2025-R13 Belgian Grand Prix"]
    assert race_path("laps", 2025, 13).read_bytes() == laps_before
    messages = pd.read_parquet(race_path("messages", 2025, 13))
    assert list(messages.columns[:3]) == ["season", "round", "event_name"]
    assert len(messages) == 2
    weather = pd.read_parquet(race_path("weather", 2025, 13))
    assert weather.loc[0, "Time_ms"] == 36172
    assert weather.loc[0, "Date"] == pd.Timestamp("2025-07-27 12:06:03.990")

    # Segunda ejecución: todo está cargado, no se pide nada.
    monkeypatch.setattr(
        fastf1_loader,
        "_load_race_extras",
        lambda *a: (_ for _ in ()).throw(AssertionError("extras")),
    )
    assert fastf1_loader.load_season(2025).skipped == ["2025-R13 Belgian Grand Prix"]


def test_missing_extras_do_not_fail_the_race(monkeypatch, tmp_path):
    monkeypatch.setattr(fastf1_loader, "OUT_DIR", tmp_path)
    monkeypatch.setattr(fastf1_loader, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(fastf1.Cache, "enable_cache", lambda *args, **kwargs: None)
    monkeypatch.setattr(fastf1_loader, "tolerate_tyre_info_errors", lambda: True)
    schedule = pd.DataFrame({"RoundNumber": [1], "EventName": ["Australian Grand Prix"]})
    monkeypatch.setattr(fastf1_loader, "completed_races", lambda season: schedule)
    calls = []
    monkeypatch.setattr(fastf1_loader, "_load_race", lambda *a: calls.append("race"))
    monkeypatch.setattr(fastf1_loader, "_load_qualifying", lambda *a, **k: calls.append("quali"))

    def no_feed(*args):
        raise ValueError("el cronometraje no tiene mensajes de dirección de carrera")

    monkeypatch.setattr(fastf1_loader, "_load_race_extras", no_feed)
    summary = fastf1_loader.load_season(2018)
    assert calls == ["race", "quali"]
    assert summary.failed == []
    assert summary.loaded == ["2018-R01 Australian Grand Prix"]
    assert summary.extras_failed == ["2018-R01 Australian Grand Prix"]
