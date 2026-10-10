"""Ingesta de Jolpica: conversión del volcado, API por carrera y tabla, idempotencia y fallos."""

import csv
import hashlib
import io
import json
import zipfile
from datetime import UTC, date, datetime

import pyarrow.parquet as pq
import pytest
import requests

from ingestion import jolpica_loader as jl
from ingestion.jolpica_loader import Client, JolpicaError

NOW = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
DUMP_URL = "https://api.jolpi.ca/data/dumps/download/delayed/?dump_type=csv"


# --- Volcado sintético ------------------------------------------------------------------------
# 2026 R1: carrera completa (resultados, vueltas, paradas y Q1-Q3). 2026 R2: cancelada. 2026 R3:
# con sprint y solo resultados en el volcado (sin vueltas: llegan por la API). 2005 R1: formato
# antiguo de clasificación (QO y QB) y sin hora de carrera.


def lap(id_, entry, number, time, position=None, fastest="f", deleted="f"):
    return {
        "id": id_,
        "session_entry_id": entry,
        "number": number,
        "position": position or "",
        "time": time,
        "is_entry_fastest_lap": fastest,
        "is_deleted": deleted,
    }


def entry(id_, session, round_entry, position="", classified="t", status="0", **extra):
    row = {
        "id": id_,
        "session_id": session,
        "round_entry_id": round_entry,
        "position": position,
        "is_classified": classified,
        "status": status,
    }
    row.update(extra)
    return row


DUMP = {
    "season": [{"id": 1, "year": 2026}, {"id": 2, "year": 2005}],
    "circuit": [
        {"id": 1, "reference": "albert_park", "name": "Albert Park", "locality": "Melbourne"},
        {"id": 2, "reference": "sepang", "name": "Sepang", "country": "Malaysia"},
    ],
    "round": [
        {"id": 10, "season_id": 1, "circuit_id": 1, "number": 1, "name": "Australian GP"},
        {"id": 11, "season_id": 1, "circuit_id": 1, "number": 2, "is_cancelled": "t"},
        {"id": 12, "season_id": 1, "circuit_id": 2, "number": 3, "name": "Chinese GP"},
        {"id": 20, "season_id": 2, "circuit_id": 2, "number": 1, "name": "Malaysian GP"},
    ],
    "session": [
        {"id": 100, "round_id": 10, "type": "R", "timestamp": "2026-03-08 04:00:00+00"}
        | {"has_time_data": "t", "number": 1},
        {"id": 101, "round_id": 10, "type": "Q1", "number": 1},
        {"id": 102, "round_id": 10, "type": "Q2", "number": 2},
        {"id": 103, "round_id": 10, "type": "Q3", "number": 3},
        {"id": 110, "round_id": 11, "type": "R", "timestamp": "2026-03-15 04:00:00+00"},
        {"id": 120, "round_id": 12, "type": "R", "timestamp": "2026-03-22 07:00:00+00"}
        | {"has_time_data": "t"},
        {"id": 121, "round_id": 12, "type": "SR", "timestamp": "2026-03-21 03:00:00+00"},
        {"id": 200, "round_id": 20, "type": "R", "timestamp": "2005-03-20 00:00:00+00"}
        | {"has_time_data": "f"},
        {"id": 201, "round_id": 20, "type": "QO", "number": 1},
        {"id": 202, "round_id": 20, "type": "QB", "number": 2},
    ],
    "driver": [
        {"id": 1, "reference": "max_verstappen", "forename": "Max", "surname": "Verstappen"}
        | {"abbreviation": "VER", "permanent_car_number": 3, "date_of_birth": "1997-09-30"},
        {"id": 2, "reference": "hamilton", "forename": "Lewis", "surname": "Hamilton"},
        {"id": 3, "reference": "alonso", "forename": "Fernando", "surname": "Alonso"},
    ],
    "team": [
        {"id": 1, "reference": "red_bull", "name": "Red Bull"},
        {"id": 2, "reference": "ferrari", "name": "Ferrari"},
        {"id": 3, "reference": "renault", "name": "Renault"},
    ],
    "teamdriver": [
        {"id": 1, "team_id": 1, "driver_id": 1},
        {"id": 2, "team_id": 2, "driver_id": 2},
        {"id": 3, "team_id": 3, "driver_id": 3},
    ],
    "roundentry": [
        {"id": 1000, "round_id": 10, "team_driver_id": 1, "car_number": 3},
        {"id": 1001, "round_id": 10, "team_driver_id": 2, "car_number": 44},
        {"id": 1002, "round_id": 10, "team_driver_id": 3, "car_number": 14},
        {"id": 1200, "round_id": 12, "team_driver_id": 1, "car_number": 3},
        {"id": 2000, "round_id": 20, "team_driver_id": 3, "car_number": 5},
    ],
    "sessionentry": [
        entry(5000, 100, 1000, 1, points=25, grid=1, time="01:30:00.123", laps_completed=2)
        | {"fastest_lap_rank": 1},
        entry(5001, 100, 1001, 2, status="1", points=18, grid=2, time="01:31:00")
        | {"laps_completed": 2, "fastest_lap_rank": 2},
        entry(5002, 100, 1002, 3, classified="f", status="30", time="00:10:00", points=0),
        entry(5100, 101, 1000, 1),
        entry(5101, 102, 1000, 1),
        entry(5102, 103, 1000, 1),
        entry(5103, 101, 1001, 2),
        entry(5104, 101, 1002, "", detail="no time"),
        entry(5200, 120, 1200, 1, points=25, detail="Finished"),
        entry(5201, 121, 1200, 1, points=8),
        entry(6000, 200, 2000, 1, points=10),
        entry(6001, 201, 2000, 3),
        entry(6002, 202, 2000, 1),
    ],
    "lap": [
        lap(1, 5000, 1, "00:01:35.5", 1),
        lap(2, 5000, 2, "00:01:32.123456", 1, fastest="t"),
        lap(3, 5001, 1, "00:01:36", 2),
        lap(4, 5001, 2, "00:01:33.000", 2, fastest="t"),
        lap(5, 5100, None, "00:01:30.000", fastest="t"),
        lap(6, 5101, None, "00:01:29.000", fastest="t", deleted="t"),
        lap(7, 5102, None, "00:01:28.250", fastest="t"),
        lap(8, 5201, 1, "00:01:40.000", 1),
        lap(9, 6001, None, "00:01:25.000", fastest="t"),
        lap(10, 6002, None, "00:01:24.500", fastest="t"),
    ],
    "pitstop": [
        {"id": 1, "session_entry_id": 5000, "lap_id": 1, "number": 1}
        | {"duration": "00:00:23.456", "local_timestamp": "15:05:00"},
    ],
}


def make_dump(path, tables=DUMP, drop_column=None):
    with zipfile.ZipFile(path, "w") as zf:
        for table, columns in jl.DUMP_COLUMNS.items():
            # Columnas del volcado en orden alfabético con `id` primero (como Jolpica) y una de
            # más, para comprobar que se leen por nombre.
            names = ["id"] + sorted([c for c in columns if c != "id"] + ["zz_extra"])
            if drop_column and drop_column[0] == table:
                names.remove(drop_column[1])
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=names, extrasaction="ignore")
            writer.writeheader()
            for row in tables[table]:
                writer.writerow({name: row.get(name, "") for name in names})
            zf.writestr(f"formula_one_{table}.csv", buffer.getvalue())
    return path


def rows(table, **filters):
    df = table.to_pandas(date_as_object=True, integer_object_nulls=True)
    for column, value in filters.items():
        df = df[df[column] == value]
    return df.to_dict("records")


@pytest.fixture(scope="module")
def dump(tmp_path_factory):
    path = make_dump(tmp_path_factory.mktemp("dump") / "dump.zip")
    return jl.convert_dump(jl.read_dump(path))


# --- Conversión -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "ms"),
    [
        ("1:32.123", 92123),
        ("23.456", 23456),
        ("16:44.718", 1004718),
        ("1:02:03.5", 3723500),
        ("00:01:32.123456", 92123),
        ("26:00:00", 93600000),
        ("1 day 02:00:00", 93600000),
        ("", None),
        (None, None),
        ("N", None),
        (".500", 500),
    ],
)
def test_text_to_ms(text, ms):
    assert jl.text_to_ms(text) == ms


def test_races_skip_cancelled_rounds_and_take_the_race_session_time(dump):
    races = {(r["season"], r["round"]): r for r in rows(dump["races"])}
    assert set(races) == {(2026, 1), (2026, 3), (2005, 1)}
    assert races[(2026, 1)]["race_date"] == date(2026, 3, 8)
    assert races[(2026, 1)]["race_time"] == "04:00:00Z"
    assert races[(2026, 1)]["circuit_ref"] == "albert_park"
    assert races[(2005, 1)]["race_time"] is None  # sin has_time_data
    assert {r["origin"] for r in races.values()} == {"dump"}


def test_results_follow_the_api_serializer(dump):
    results = {r["driver_ref"]: r for r in rows(dump["results"], season=2026, round=1)}
    ver, ham, alo = results["max_verstappen"], results["hamilton"], results["alonso"]
    assert (ver["position_text"], ver["status"], ver["time_ms"]) == ("1", "Finished", 5400123)
    assert (ver["fastest_lap_rank"], ver["fastest_lap_number"], ver["fastest_lap_ms"]) == (
        1,
        2,
        92123,
    )
    assert (ver["car_number"], ver["constructor_ref"], ver["points"]) == (3, "red_bull", 25.0)
    assert (ham["status"], ham["time_ms"]) == ("Lapped", 5460000)
    # Sin clasificar: no tomó la salida (W), sin tiempo aunque lo tenga el volcado.
    assert (alo["position"], alo["position_text"], alo["time_ms"]) == (3, "W", None)
    assert alo["status"] == "Did_not_start"
    sprint = rows(dump["results"], season=2026, round=3, session_type="SR")
    assert [(r["driver_ref"], r["points"]) for r in sprint] == [("max_verstappen", 8.0)]


def test_qualifying_takes_the_fastest_valid_lap_of_each_session(dump):
    quali = {r["driver_ref"]: r for r in rows(dump["qualifying"], season=2026, round=1)}
    # La vuelta más rápida de Q2 está borrada: Q2 sin tiempo, como en la API.
    assert (quali["max_verstappen"]["q1_ms"], quali["max_verstappen"]["q2_ms"]) == (90000, None)
    assert quali["max_verstappen"]["q3_ms"] == 88250
    assert quali["hamilton"]["position"] == 2
    assert "alonso" not in quali  # sin posición en ninguna sesión Q*
    # Formato antiguo (QO y QB): la primera sesión va a Q1 y la segunda a Q2; posición de la última.
    old = rows(dump["qualifying"], season=2005)
    assert [(r["position"], r["q1_ms"], r["q2_ms"], r["q3_ms"]) for r in old] == [
        (1, 85000, 84500, None)
    ]


def test_lap_times_and_pit_stops_only_of_the_race(dump):
    laps = rows(dump["lap_times"])
    assert {(r["season"], r["round"]) for r in laps} == {(2026, 1)}  # ni sprint ni clasificación
    assert [r["time_ms"] for r in laps if r["driver_ref"] == "max_verstappen"] == [95500, 92123]
    stops = rows(dump["pit_stops"])
    assert stops == [
        {
            "season": 2026,
            "round": 1,
            "driver_ref": "max_verstappen",
            "stop": 1,
            "lap": 1,
            "local_time": "15:05:00",
            "duration_ms": 23456,
            "origin": "dump",
        }
    ]


def test_dump_with_a_missing_column_fails_clearly(tmp_path):
    path = make_dump(tmp_path / "dump.zip", drop_column=("lap", "is_deleted"))
    with pytest.raises(JolpicaError, match="is_deleted"):
        jl.read_dump(path)


def test_dump_without_a_table_fails(tmp_path):
    path = tmp_path / "dump.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("../formula_one_lap.csv", "id\n")
    with pytest.raises(JolpicaError, match="formula_one_season.csv"):
        jl.read_dump(path)


def test_duplicated_keys_are_an_error():
    row = {"season": 2026, "round": 1, "driver_ref": "x", "lap": 1, "origin": "api"}
    with pytest.raises(JolpicaError, match="duplicadas"):
        jl.to_table([row, row], "lap_times")


# --- API --------------------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, status, payload=None, content=b"", url="https://api.jolpi.ca/x"):
        self.status_code = status
        self._payload = payload
        self.content = content
        self.headers = {}
        self.url = url
        self.history = []

    def json(self):
        if self._payload is None:
            raise ValueError("sin JSON")
        return self._payload

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i : i + chunk_size]


class FakeJolpica:
    """Sesión HTTP falsa que responde según la ruta (y el offset) y registra las peticiones."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []
        self.headers = {}

    def get(self, url, params=None, **kwargs):
        path = url.replace(jl.API_URL, "")
        offset = (params or {}).get("offset", 0)
        self.calls.append((path, offset))
        response = self.routes.get((path, offset), self.routes.get(path))
        if response is None:
            return FakeResponse(404)
        if isinstance(response, Exception):
            raise response
        return response


def page(races, total):
    return FakeResponse(200, {"MRData": {"total": str(total), "RaceTable": {"Races": races}}})


def driver(ref, given="X", family="Y"):
    return {"driverId": ref, "givenName": given, "familyName": family, "dateOfBirth": "2008-03-08"}


def result(ref, team, position, **extra):
    row = {
        "number": "1",
        "position": str(position),
        "positionText": str(position),
        "points": "25",
        "Driver": driver(ref),
        "Constructor": {"constructorId": team, "name": team},
        "grid": "1",
        "laps": "56",
        "status": "Finished",
    }
    row.update(extra)
    return row


def laps_race(timings_by_lap):
    return {
        "season": "2026",
        "round": "4",
        "Laps": [
            {"number": str(n), "Timings": [{"driverId": d, "position": "1", "time": t}]}
            for n, d, t in timings_by_lap
        ],
    }


def schedule(*races):
    return page(list(races), len(races))


def sched_race(round_, day, sprint=False):
    race = {
        "season": "2026",
        "round": str(round_),
        "raceName": f"GP {round_}",
        "date": day,
        "time": "05:00:00Z",
        "Circuit": {"circuitId": f"c{round_}", "Location": {"country": "X"}},
    }
    if sprint:
        race["Sprint"] = {"date": day}
    return race


def dump_routes(zip_bytes, digest=None):
    digest = digest or hashlib.sha256(zip_bytes).hexdigest()
    index = {
        "delayed_dumps": {
            "csv": {
                "file_hash": digest,
                "file_size": len(zip_bytes),
                "uploaded_at": "2026-03-27T10:00:00Z",
                "download_url": DUMP_URL,
            }
        }
    }
    return {
        jl.DUMPS_URL.replace(jl.API_URL, ""): FakeResponse(200, index),
        DUMP_URL.replace(jl.API_URL, ""): FakeResponse(200, content=zip_bytes),
    }


def race_routes(r3_laps=1, r4_laps=None):
    """API para 2026: R1 (en el volcado), R3 (con sprint; el volcado no tiene sus vueltas), R4
    (fuera del volcado) y R5 (sin disputar)."""
    r4_laps = r4_laps or [(1, "max_verstappen", "1:40.000"), (1, "arvid_lindblad", "1:41.000")]
    return {
        "2026/races/": schedule(
            sched_race(1, "2026-03-08"),
            sched_race(3, "2026-03-22", sprint=True),
            sched_race(4, "2026-04-05"),
            sched_race(5, "2026-04-19"),
        ),
        "2026/3/results/": page([{"Results": [result("max_verstappen", "red_bull", 1)]}], 1),
        "2026/3/sprint/": page([{"SprintResults": [result("max_verstappen", "red_bull", 1)]}], 1),
        "2026/3/qualifying/": page([], 0),
        "2026/3/pitstops/": page([], 0),
        "2026/3/laps/": page(
            [laps_race([(n, "max_verstappen", "1:35.000") for n in range(1, r3_laps + 1)])],
            r3_laps,
        ),
        "2026/4/results/": page(
            [
                {
                    "Results": [
                        result("max_verstappen", "red_bull", 1, Time={"millis": "5400000"}),
                        result("arvid_lindblad", "racing_bulls", 2, positionText="R"),
                    ]
                }
            ],
            2,
        ),
        "2026/4/qualifying/": page(
            [{"QualifyingResults": [result("max_verstappen", "red_bull", 1, Q1="1:30.500")]}], 1
        ),
        "2026/4/pitstops/": page(
            [{"PitStops": [{"driverId": "max_verstappen", "lap": "20", "stop": "1"}]}], 1
        ),
        "2026/4/laps/": page([laps_race(r4_laps)], len(r4_laps)),
    }


def fake_client(routes):
    http = FakeJolpica(routes)
    return Client(http, sleep=lambda s: None, clock=lambda: 0.0), http


@pytest.fixture
def zip_bytes(tmp_path):
    return make_dump(tmp_path / "dump.zip").read_bytes()


def test_load_combines_dump_and_api_by_race_and_table(tmp_path, zip_bytes):
    c, http = fake_client(dump_routes(zip_bytes) | race_routes())
    summary = jl.load(client=c, root=tmp_path, now=NOW)
    assert summary.ok, summary
    assert summary.dump_downloaded
    tables = jl.read_tables(tmp_path)
    assert set(tables) == set(jl.SCHEMA)
    # R3: resultados del volcado (los cubre), vueltas y nada más de la API.
    r3 = rows(tables["results"], season=2026, round=3)
    assert {(r["session_type"], r["origin"]) for r in r3} == {("R", "dump"), ("SR", "dump")}
    assert {r["origin"] for r in rows(tables["lap_times"], season=2026, round=3)} == {"api"}
    # R4: todo de la API, con el piloto nuevo y la carrera añadidos.
    r4 = {r["driver_ref"]: r for r in rows(tables["results"], season=2026, round=4)}
    assert r4["max_verstappen"]["time_ms"] == 5400000
    assert r4["arvid_lindblad"]["position_text"] == "R"
    assert rows(tables["qualifying"], season=2026, round=4)[0]["q1_ms"] == 90500
    assert rows(tables["drivers"], driver_ref="arvid_lindblad")[0]["origin"] == "api"
    assert rows(tables["constructors"], constructor_ref="racing_bulls")[0]["origin"] == "api"
    assert rows(tables["races"], season=2026, round=4)[0]["origin"] == "api"
    # R1 lo cubre el volcado (no se pide) y R5 no se ha disputado.
    paths = {path for path, _ in http.calls}
    assert not any(p.startswith(("2026/1/", "2026/5/")) for p in paths)
    meta = json.loads((tmp_path / "_metadata.json").read_text(encoding="utf-8"))
    assert meta["schema_version"] == jl.SCHEMA_VERSION
    assert meta["dump_hash"] == hashlib.sha256(zip_bytes).hexdigest()
    assert [(r["season"], r["round"]) for r in meta["api_races"]] == [(2026, 3), (2026, 4)]
    assert summary.api_races == ["2026 R3", "2026 R4"]


def test_load_is_idempotent_and_skips_an_unchanged_dump(tmp_path, zip_bytes):
    c, _ = fake_client(dump_routes(zip_bytes) | race_routes())
    jl.load(client=c, root=tmp_path, now=NOW)
    before = {name: pq.read_table(jl.table_path(name, tmp_path)) for name in jl.SCHEMA}
    c, http = fake_client(dump_routes(zip_bytes) | race_routes())
    summary = jl.load(client=c, root=tmp_path, now=NOW)
    assert summary.ok and not summary.dump_downloaded
    assert DUMP_URL.replace(jl.API_URL, "") not in {path for path, _ in http.calls}
    assert summary.written == []
    for name, table in before.items():
        assert pq.read_table(jl.table_path(name, tmp_path)).equals(table)


def test_a_broken_dump_falls_back_to_the_previous_one_and_still_asks_the_api(tmp_path, zip_bytes):
    # Primera ejecución: el volcado y la API sin la carrera 4 (aún sin resultados).
    routes = dump_routes(zip_bytes) | race_routes()
    for path in [p for p in routes if isinstance(p, str) and p.startswith("2026/4/")]:
        routes[path] = page([], 0)
    c, _ = fake_client(routes)
    jl.load(client=c, root=tmp_path, now=NOW)
    old_hash = json.loads((tmp_path / "_metadata.json").read_text(encoding="utf-8"))["dump_hash"]
    # Segunda: un volcado nuevo cuyo SHA-256 no cuadra; la API ya tiene la carrera 4.
    c, _ = fake_client(dump_routes(zip_bytes + b"x", digest="0" * 64) | race_routes())
    summary = jl.load(client=c, root=tmp_path, now=NOW)
    assert not summary.ok and "SHA-256" in summary.dump_error and summary.dump_failed is None
    meta = json.loads((tmp_path / "_metadata.json").read_text(encoding="utf-8"))
    assert meta["dump_hash"] == old_hash  # se reintenta la descarga en la siguiente ejecución
    assert len(rows(jl.read_tables(tmp_path)["results"], season=2026, round=4)) == 2
    text = jl.summary_markdown(summary)
    assert "(anterior)" in text and "no se pudo actualizar el volcado" in text


def test_a_broken_dump_without_a_previous_one_writes_nothing(tmp_path, zip_bytes):
    c, _ = fake_client(dump_routes(zip_bytes + b"x", digest="0" * 64) | race_routes())
    summary = jl.load(client=c, root=tmp_path, now=NOW)
    assert "SHA-256" in summary.dump_failed
    assert not (tmp_path / "_metadata.json").exists()
    assert "no se pudo actualizar" in jl.summary_markdown(summary)


def test_damaged_metadata_and_leftover_temporaries_do_not_block_the_load(tmp_path, zip_bytes):
    tmp_path.joinpath("_metadata.json").write_text("{corte", encoding="utf-8")
    tmp_path.joinpath("lap_times.parquet.tmp").write_bytes(b"x")
    c, _ = fake_client(dump_routes(zip_bytes) | race_routes())
    summary = jl.load(client=c, root=tmp_path, now=NOW)
    assert summary.ok and summary.dump_downloaded
    assert not list(tmp_path.glob("*.tmp"))


def test_dump_members_inside_a_folder_are_read(tmp_path):
    flat = make_dump(tmp_path / "flat.zip")
    nested = tmp_path / "nested.zip"
    with zipfile.ZipFile(flat) as src, zipfile.ZipFile(nested, "w") as dst:
        for info in src.infolist():
            dst.writestr(f"dump/{info.filename}", src.read(info))
    assert jl.read_dump(nested)["lap"].shape == jl.read_dump(flat)["lap"].shape


def test_an_unexpected_download_url_is_rejected(tmp_path, zip_bytes):
    routes = dump_routes(zip_bytes)
    index_path = jl.DUMPS_URL.replace(jl.API_URL, "")
    routes[index_path]._payload["delayed_dumps"]["csv"]["download_url"] = "http://evil/x.zip"
    c, _ = fake_client(routes)
    summary = jl.load(client=c, root=tmp_path, now=NOW)
    assert "URL de descarga inesperada" in summary.dump_failed
    assert not (tmp_path / "_metadata.json").exists()


def test_api_failures_and_smaller_answers_keep_the_previous_rows(tmp_path, zip_bytes):
    c, _ = fake_client(dump_routes(zip_bytes) | race_routes(r3_laps=3))
    jl.load(client=c, root=tmp_path, now=NOW)
    # Siguiente ejecución: R3 devuelve menos vueltas que antes y las de R4 fallan (500).
    routes = dump_routes(zip_bytes) | race_routes(r3_laps=1)
    routes["2026/4/laps/"] = FakeResponse(500)
    c, _ = fake_client(routes)
    summary = jl.load(client=c, root=tmp_path, now=NOW)
    assert not summary.ok
    assert summary.api_failed == ["2026 R4 (GP 4): laps"]
    assert any("2026 R3" in w and "se conservan" in w for w in summary.warnings)
    tables = jl.read_tables(tmp_path)
    assert len(rows(tables["lap_times"], season=2026, round=3)) == 3
    assert len(rows(tables["lap_times"], season=2026, round=4)) == 2


def test_lap_pages_split_a_lap_between_pages(tmp_path, zip_bytes, monkeypatch):
    # `limit` cuenta filas: con 2 por página, la vuelta 1 de R4 queda partida.
    monkeypatch.setattr(jl, "PAGE_LIMIT", 2)
    routes = dump_routes(zip_bytes) | race_routes()
    routes["2026/4/laps/"] = page(
        [laps_race([(1, "max_verstappen", "1:40.000"), (1, "hamilton", "1:41.000")])], 3
    )
    routes[("2026/4/laps/", 2)] = page([laps_race([(1, "arvid_lindblad", "1:42.000")])], 3)
    c, _ = fake_client(routes)
    summary = jl.load(client=c, root=tmp_path, now=NOW)
    assert summary.ok, summary
    laps = rows(jl.read_tables(tmp_path)["lap_times"], season=2026, round=4)
    assert sorted((r["driver_ref"], r["lap"]) for r in laps) == [
        ("arvid_lindblad", 1),
        ("hamilton", 1),
        ("max_verstappen", 1),
    ]


def test_pages_must_add_up_to_the_total():
    routes = {"2026/4/laps/": page([laps_race([(1, "max_verstappen", "1:40.000")])], 5)}
    routes[("2026/4/laps/", 100)] = page([], 5)
    c, _ = fake_client(routes)
    with pytest.raises(JolpicaError, match="1 filas de 5"):
        jl._paged_races(c, "2026/4/laps/")


def test_repeated_lap_is_an_error():
    race = laps_race([(1, "max_verstappen", "1:40.000"), (1, "max_verstappen", "1:41.000")])
    with pytest.raises(JolpicaError, match="repetida"):
        jl.api_laps([race], 2026, 4)


def test_races_already_in_the_dump_drop_their_api_rows(tmp_path, zip_bytes):
    c, _ = fake_client(dump_routes(zip_bytes) | race_routes())
    jl.load(client=c, root=tmp_path, now=NOW)
    # Un volcado nuevo trae R3 con sus vueltas: sustituye a las de la API.
    tables = {k: list(v) for k, v in DUMP.items()}
    tables["lap"] = tables["lap"] + [lap(50, 5200, 1, "00:01:39.000", 1)]
    new_zip = make_dump(tmp_path / "dump2.zip", tables).read_bytes()
    c, _ = fake_client(dump_routes(new_zip) | race_routes())
    jl.load(client=c, root=tmp_path, now=NOW)
    r3 = rows(jl.read_tables(tmp_path)["lap_times"], season=2026, round=3)
    assert [(r["origin"], r["time_ms"]) for r in r3] == [("dump", 99000)]


def test_unreadable_calendar_keeps_the_previous_api_races(tmp_path, zip_bytes):
    c, _ = fake_client(dump_routes(zip_bytes) | race_routes())
    jl.load(client=c, root=tmp_path, now=NOW)
    routes = dump_routes(zip_bytes)
    routes["2026/races/"] = FakeResponse(503)
    c, _ = fake_client(routes)
    summary = jl.load(client=c, root=tmp_path, now=NOW)
    assert summary.api_failed == ["calendario de 2026"]
    tables = jl.read_tables(tmp_path)
    assert len(rows(tables["results"], season=2026, round=4)) == 2
    assert rows(tables["drivers"], driver_ref="arvid_lindblad")


def test_request_cap_stops_the_run_without_writing(tmp_path, zip_bytes):
    c, _ = fake_client(dump_routes(zip_bytes) | race_routes())
    c.max_requests = 1  # solo el índice
    summary = jl.load(client=c, root=tmp_path, now=NOW)
    assert summary.out_of_time and not summary.ok
    assert not (tmp_path / "_metadata.json").exists()


def test_empty_placeholder_tables_are_redone_by_the_next_load(tmp_path, zip_bytes):
    assert set(jl.write_empty_if_missing(tmp_path)) == set(jl.SCHEMA)
    assert jl.write_empty_if_missing(tmp_path) == []
    tables = jl.read_tables(tmp_path)
    assert set(tables) == set(jl.SCHEMA) and all(t.num_rows == 0 for t in tables.values())
    meta = json.loads((tmp_path / "_metadata.json").read_text(encoding="utf-8"))
    assert meta["empty_placeholder"] is True and meta["dump_hash"] is None
    c, _ = fake_client(dump_routes(zip_bytes) | race_routes())
    summary = jl.load(client=c, root=tmp_path, now=NOW)
    assert summary.dump_downloaded
    assert "empty_placeholder" not in json.loads(
        (tmp_path / "_metadata.json").read_text(encoding="utf-8")
    )


def test_client_waits_retries_and_sends_its_user_agent():
    responses = [
        FakeResponse(429),
        FakeResponse(503),
        requests.ConnectionError("caída"),
        FakeResponse(200, {"ok": True}),
    ]

    class Http:
        headers = {}

        def get(self, url, params=None, **kwargs):
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

    sleeps = []
    clock = [0.0]

    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds

    c = Client(Http(), sleep=sleep, clock=lambda: clock[0])
    assert c.get_json("https://api.jolpi.ca/x") == {"ok": True}
    assert c.requests == 4
    assert "f1-data-platform" in c.session.headers["User-Agent"]
    assert min(sleeps) >= 0 and len(sleeps) >= 3


def test_client_respects_the_minimum_interval():
    class Http:
        headers = {}

        def get(self, url, params=None, **kwargs):
            return FakeResponse(200, {})

    sleeps = []
    c = Client(Http(), sleep=sleeps.append, clock=lambda: 0.0)
    c.get_json("https://api.jolpi.ca/a")
    c.get_json("https://api.jolpi.ca/b")
    assert sleeps == [jl.MIN_INTERVAL_S]  # 4 peticiones/s como mucho (aquí, 2/s)


def test_compare_race_reports_differences_between_dump_and_api(tmp_path, zip_bytes):
    c, _ = fake_client(dump_routes(zip_bytes) | race_routes())
    jl.load(client=c, root=tmp_path, now=NOW)
    routes = {
        "2026/1/results/": page(
            [
                {
                    "Results": [
                        result(
                            "max_verstappen",
                            "red_bull",
                            1,
                            number="3",
                            grid="1",
                            laps="2",
                            Time={"millis": "5400123"},
                            FastestLap={"rank": "1", "lap": "2", "Time": {"time": "1:32.123"}},
                        ),
                        result("hamilton", "ferrari", 2, points="19"),
                    ]
                }
            ],
            2,
        ),
        "2026/1/sprint/": page([], 0),
        "2026/1/qualifying/": page([], 0),
        "2026/1/pitstops/": page(
            [
                {
                    "PitStops": [
                        {
                            "driverId": "max_verstappen",
                            "lap": "1",
                            "stop": "1",
                            "time": "15:05:00",
                            "duration": "23.456",
                        }
                    ]
                }
            ],
            1,
        ),
        "2026/1/laps/": page([], 0),
    }
    c, _ = fake_client(routes)
    report = jl.compare_race(c, 2026, 1, root=tmp_path)
    assert report["pit_stops"] == {
        "dump": 1,
        "api": 1,
        "only_dump": 0,
        "only_api": 0,
        "different": 0,
        "examples": [],
    }
    results = report["results"]
    assert (results["dump"], results["api"], results["only_dump"]) == (3, 2, 1)
    # Verstappen coincide; Hamilton difiere en los puntos (y en lo que el fixture no rellena).
    assert [e["key"] for e in results["examples"]] == [(2026, 1, "R", "hamilton")]
    assert results["examples"][0]["diff"]["points"] == (18.0, 19.0)
    assert report["lap_times"]["only_dump"] == 4


def test_partial_dump_races_are_completed_by_the_api(tmp_path):
    tables = {k: list(v) for k, v in DUMP.items()}
    # R3: el volcado tiene 1 de las 3 vueltas que suman sus resultados (vueltas a medias).
    tables["sessionentry"] = [
        dict(e, laps_completed=3) if e["id"] == 5200 else e for e in tables["sessionentry"]
    ]
    tables["lap"] = tables["lap"] + [lap(50, 5200, 1, "00:01:39.000", 1)]
    # R4: el volcado se hizo entre el sprint y la carrera (solo resultados del sprint).
    tables["round"] = tables["round"] + [
        {"id": 13, "season_id": 1, "circuit_id": 1, "number": 4, "name": "GP 4"}
    ]
    tables["session"] = tables["session"] + [
        {"id": 130, "round_id": 13, "type": "SR", "timestamp": "2026-04-04 05:00:00+00"}
    ]
    tables["roundentry"] = tables["roundentry"] + [
        {"id": 1300, "round_id": 13, "team_driver_id": 1, "car_number": 3}
    ]
    tables["sessionentry"] = tables["sessionentry"] + [entry(5300, 130, 1300, 1, points=8)]
    zip_bytes = make_dump(tmp_path / "dump.zip", tables).read_bytes()
    routes = dump_routes(zip_bytes) | race_routes(r3_laps=3)
    routes["2026/races/"] = schedule(
        sched_race(1, "2026-03-08"),
        sched_race(3, "2026-03-22", sprint=True),
        sched_race(4, "2026-04-05", sprint=True),
    )
    routes["2026/4/sprint/"] = page(
        [{"SprintResults": [result("max_verstappen", "red_bull", 1, points="8")]}], 1
    )
    c, _ = fake_client(routes)
    summary = jl.load(client=c, root=tmp_path / "bronze", now=NOW)
    assert summary.ok, summary
    out = jl.read_tables(tmp_path / "bronze")
    r3 = rows(out["lap_times"], season=2026, round=3)
    assert sorted((r["lap"], r["origin"]) for r in r3) == [(1, "api"), (2, "api"), (3, "api")]
    r4 = rows(out["results"], season=2026, round=4)
    assert sorted((r["session_type"], r["driver_ref"], r["origin"]) for r in r4) == [
        ("R", "arvid_lindblad", "api"),
        ("R", "max_verstappen", "api"),
        ("SR", "max_verstappen", "api"),
    ]


def test_api_rows_of_tables_the_dump_still_lacks_are_kept(tmp_path, zip_bytes):
    routes = dump_routes(zip_bytes) | race_routes()
    routes["2026/3/pitstops/"] = page(
        [{"PitStops": [{"driverId": "max_verstappen", "lap": "1", "stop": "1"}]}], 1
    )
    c, _ = fake_client(routes)
    jl.load(client=c, root=tmp_path, now=NOW)
    # El volcado nuevo trae las vueltas de R3 (ya no se pide a la API), pero no sus paradas.
    tables = {k: list(v) for k, v in DUMP.items()}
    tables["lap"] = tables["lap"] + [lap(50, 5200, 1, "00:01:39.000", 1)]
    new_zip = make_dump(tmp_path / "dump2.zip", tables).read_bytes()
    c, http = fake_client(dump_routes(new_zip) | race_routes())
    jl.load(client=c, root=tmp_path, now=NOW)
    assert not any(path.startswith("2026/3/") for path, _ in http.calls)
    stops = rows(jl.read_tables(tmp_path)["pit_stops"], season=2026, round=3)
    assert [(r["driver_ref"], r["origin"]) for r in stops] == [("max_verstappen", "api")]


def test_a_download_cut_midway_falls_back_to_the_previous_dump(tmp_path, zip_bytes):
    routes = dump_routes(zip_bytes) | race_routes()
    for path in [p for p in routes if isinstance(p, str) and p.startswith("2026/4/")]:
        routes[path] = page([], 0)
    c, _ = fake_client(routes)
    jl.load(client=c, root=tmp_path, now=NOW)
    old_hash = json.loads((tmp_path / "_metadata.json").read_text(encoding="utf-8"))["dump_hash"]

    class CutResponse(FakeResponse):
        def iter_content(self, chunk_size=1):
            yield b"PK"
            raise requests.exceptions.ChunkedEncodingError("lectura cortada")

    routes = dump_routes(zip_bytes + b"x", digest="1" * 64) | race_routes()
    routes[DUMP_URL.replace(jl.API_URL, "")] = CutResponse(200)
    c, _ = fake_client(routes)
    summary = jl.load(client=c, root=tmp_path, now=NOW)
    assert "descarga interrumpida" in summary.dump_error and summary.dump_failed is None
    meta = json.loads((tmp_path / "_metadata.json").read_text(encoding="utf-8"))
    assert meta["dump_hash"] == old_hash
    assert len(rows(jl.read_tables(tmp_path)["results"], season=2026, round=4)) == 2
