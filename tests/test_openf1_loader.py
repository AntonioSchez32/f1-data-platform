"""Ingesta de OpenF1: límites de peticiones, huecos conocidos, incremental e idempotente."""

import json
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
import requests

from ingestion import openf1_loader
from ingestion.openf1_loader import Client, NotFound, OpenF1Error

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


class FakeResponse:
    def __init__(self, status: int, payload=None, headers=None):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return self._payload


class FakeHttp:
    """Sesión HTTP falsa: devuelve las respuestas en orden y registra las peticiones."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        self.calls.append((url.rsplit("/", 1)[-1], dict(params or {})))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def client(responses, clock=None):
    clock = clock or FakeClock()
    return Client(FakeHttp(responses), sleep=clock.sleep, clock=clock), clock


def test_client_waits_between_requests_and_sends_its_user_agent():
    c, clock = client([FakeResponse(200, [{"a": 1}]), FakeResponse(200, [])])
    assert c.get("laps", session_key=1) == [{"a": 1}]
    assert c.get("laps", session_key=2) == []
    assert clock.sleeps == [openf1_loader.MIN_INTERVAL_S]  # 30 peticiones/min como mucho
    assert "f1-data-platform" in c.session.headers["User-Agent"]


def test_client_honours_retry_after_and_retries_server_errors():
    c, clock = client(
        [
            FakeResponse(429, headers={"retry-after": "3"}),
            FakeResponse(503),
            requests.ConnectionError("caída"),
            FakeResponse(200, [{"ok": True}]),
        ]
    )
    assert c.get("pit", session_key=1) == [{"ok": True}]
    assert 3.0 in clock.sleeps  # retry-after
    assert c.requests == 4


def test_client_caps_retry_after():
    c, clock = client([FakeResponse(429, headers={"retry-after": "3600"}), FakeResponse(200, [])])
    c.get("pit", session_key=1)
    assert max(clock.sleeps) == 60.0


def test_sustained_rate_limit_gives_up_instead_of_hanging():
    # Un 429 permanente: tope de respuestas 429 seguidas, no un bucle infinito.
    c, clock = client([FakeResponse(429, headers={"retry-after": "5"})] * 100)
    with pytest.raises(OpenF1Error, match="429"):
        c.get("laps", session_key=1)
    assert c.requests == openf1_loader.MAX_RATE_LIMITED


def test_deadline_stops_waiting_on_rate_limit(tmp_path):
    # Con tiempo máximo, ni los 429 ni los reintentos pasan del plazo: la carga para y lo
    # pendiente queda como «sin tiempo» para la siguiente ejecución.
    clock = FakeClock()

    class AlwaysLimited(Router):
        def get(self, url, params=None, timeout=None):
            if url.endswith("sessions") or url.endswith("meetings"):
                return super().get(url, params, timeout)
            self.calls.append(("x", None))
            return FakeResponse(429, headers={"retry-after": "60"})

    router = AlwaysLimited()
    c = Client(router, sleep=clock.sleep, clock=clock)
    summary = openf1_loader.load([2026], client=c, root=tmp_path, now=NOW, max_minutes=2)
    assert summary.out_of_time
    assert clock.now <= 2 * 60 + openf1_loader.MIN_INTERVAL_S * 2
    assert all("sin tiempo" in label for label in summary.failed)


def test_empty_list_is_a_gap_not_an_empty_file(tmp_path):
    class EmptyPit(Router):
        def get(self, url, params=None, timeout=None):
            if url.endswith("/pit"):
                self.calls.append(("pit", params.get("session_key")))
                return FakeResponse(200, [])
            return super().get(url, params, timeout)

    summary = run(EmptyPit(), tmp_path)
    assert not openf1_loader.session_path("pit", 2026, 10, tmp_path).exists()
    assert summary.gaps == ["2026 None Race (10): pit"]


def test_client_reports_404_as_not_found_and_gives_up_on_persistent_errors():
    c, _ = client([FakeResponse(404, {"detail": "No results found."})])
    with pytest.raises(NotFound):
        c.get("pit", session_key=7953)
    c, _ = client([FakeResponse(500)] * openf1_loader.MAX_ATTEMPTS)
    with pytest.raises(OpenF1Error, match="HTTP 500"):
        c.get("pit", session_key=1)


def test_client_does_not_retry_forbidden():
    # 401/403: acceso restringido durante una sesión en directo; se reintenta otro día.
    c, _ = client([FakeResponse(403)])
    with pytest.raises(OpenF1Error, match="HTTP 403"):
        c.get("laps", session_key=1)
    assert c.requests == 1


def test_to_frame_keeps_stable_types():
    df = openf1_loader.to_frame(
        "session_result",
        [
            {"position": 1, "duration": 5125.2, "gap_to_leader": 0, "x": [1, 2]},
            {"position": 2, "duration": None, "gap_to_leader": "+1 LAP", "x": None},
        ],
    )
    assert df["duration"].tolist() == ["5125.2", None]
    assert df["gap_to_leader"].tolist() == ["0", '"+1 LAP"']
    assert df["x"].tolist() == ["[1, 2]", None]
    assert df["position"].tolist() == [1, 2]


def sessions_payload():
    end = (NOW - timedelta(days=10)).isoformat()
    recent = (NOW - timedelta(hours=2)).isoformat()
    return [
        {
            "session_key": 10,
            "session_name": "Race",
            "year": 2026,
            "date_start": end,
            "date_end": end,
            "is_cancelled": False,
        },
        {
            "session_key": 11,
            "session_name": "Qualifying",
            "year": 2026,
            "date_start": end,
            "date_end": end,
            "is_cancelled": False,
        },
        # Libres (no se cargan), una carrera cancelada y otra que acaba de terminar.
        {"session_key": 12, "session_name": "Practice 1", "year": 2026, "date_end": end},
        {"session_key": 13, "session_name": "Race", "date_end": end, "is_cancelled": True},
        {"session_key": 14, "session_name": "Race", "year": 2026, "date_end": recent},
    ]


class Router:
    """Sesión HTTP falsa que responde según el endpoint y la sesión."""

    def __init__(self, missing=(), failing=()):
        self.missing, self.failing = set(missing), set(failing)
        self.calls = []
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        endpoint = url.rsplit("/", 1)[-1]
        self.calls.append((endpoint, params.get("session_key")))
        if endpoint == "sessions":
            return FakeResponse(200, sessions_payload())
        if endpoint == "meetings":
            return FakeResponse(200, [{"meeting_key": 1, "meeting_name": "Test GP"}])
        key = (endpoint, params.get("session_key"))
        if key in self.missing:
            return FakeResponse(404, {"detail": "No results found."})
        if key in self.failing:
            return FakeResponse(502)
        return FakeResponse(200, [{"session_key": params["session_key"], "lap_number": 1}])


def run(router, root, now=NOW, max_minutes=None):
    c = Client(router, sleep=lambda s: None, clock=lambda: 0.0)
    return openf1_loader.load([2026], client=c, root=root, now=now, max_minutes=max_minutes)


def test_load_is_incremental_and_records_known_gaps(tmp_path):
    router = Router(missing={("pit", 10)}, failing={("weather", 10)})
    summary = run(router, tmp_path)

    loaded = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*.parquet")}
    race_endpoints = set(openf1_loader.RACE_ENDPOINTS) - {"pit", "weather"}
    assert loaded == (
        {"sessions/season=2026.parquet", "meetings/season=2026.parquet"}
        | {f"{e}/season=2026/session=10.parquet" for e in race_endpoints}
        | {f"{e}/season=2026/session=11.parquet" for e in openf1_loader.QUALIFYING_ENDPOINTS}
    )
    # Ni libres, ni canceladas, ni sesiones recién terminadas.
    assert {key for _, key in router.calls} <= {None, 10, 11}
    assert summary.gaps == ["2026 None Race (10): pit"]
    assert summary.failed == ["2026 None Race (10): weather"]
    gaps = json.loads((tmp_path / openf1_loader.GAPS_FILE).read_text("utf-8"))
    assert gaps["10"]["pit"]["status"] == 404

    # Segunda ejecución: solo se piden la meteo que falló y el calendario; el 404 comprobado más
    # de 3 días después de la sesión es un hueco conocido y no se vuelve a pedir.
    again = Router(missing={("pit", 10)})
    summary = run(again, tmp_path)
    assert [c for c in again.calls if c[1] is not None] == [("weather", 10)]
    assert summary.loaded == ["2026 None Race (10): weather"]
    assert summary.failed == []
    # El calendario no cambia: no se reescribe (la copia no cambia sin motivo).
    assert "2026 sessions" not in summary.loaded


def test_recent_404_is_retried(tmp_path):
    # Un 404 al día siguiente de la sesión puede ser un retraso de OpenF1: se vuelve a pedir.
    early = NOW - timedelta(days=9)
    run(Router(missing={("pit", 10)}), tmp_path, now=early)
    again = Router()
    summary = run(again, tmp_path)
    assert ("pit", 10) in again.calls
    assert "2026 None Race (10): pit" in summary.loaded
    assert "10" not in json.loads((tmp_path / openf1_loader.GAPS_FILE).read_text("utf-8"))


def test_reloading_never_duplicates_rows(tmp_path):
    run(Router(), tmp_path)
    path = openf1_loader.session_path("laps", 2026, 10, tmp_path)
    path.unlink()
    run(Router(), tmp_path)
    assert len(pd.read_parquet(path)) == 1


def test_time_budget_stops_requests_and_lists_what_is_missing(tmp_path):
    clock = FakeClock()

    class SlowRouter(Router):
        def get(self, url, params=None, timeout=None):
            clock.now += 120  # cada petición tarda dos minutos
            return super().get(url, params, timeout)

    router = SlowRouter()
    c = Client(router, sleep=clock.sleep, clock=clock)
    summary = openf1_loader.load([2026], client=c, root=tmp_path, now=NOW, max_minutes=5)
    assert summary.out_of_time
    assert summary.failed and all("sin tiempo" in label for label in summary.failed)
    assert "Se agotó el tiempo" in openf1_loader.summary_markdown(summary)


def test_cli_never_fails_and_writes_the_summary(tmp_path, monkeypatch, capsys):
    from ingestion import cli

    summary = openf1_loader.LoadSummary(failed=["2026 X Race (1): laps"], requests=3)
    monkeypatch.setattr(openf1_loader, "load", lambda seasons, max_minutes=None: summary)
    out = tmp_path / "summary.md"
    assert cli.main(["openf1", "--summary", str(out)]) == 0
    assert "2026 X Race (1): laps" in out.read_text("utf-8")
    assert "Faltan" in capsys.readouterr().out
