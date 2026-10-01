"""Pruebas de humo de la API contra un snapshot real, antes de publicarlo.

El pipeline las ejecuta sobre el `dist/f1.duckdb` recién generado: si alguna falla, no se publica
nada. Solo se ejecutan si se indica la base de datos (con su `manifest.json` al lado):

    F1_SMOKE_DB=dist/f1.duckdb uv run pytest api/tests/smoke

Con `F1_SMOKE_PREVIOUS_MANIFEST` (el manifiesto publicado hasta ahora) se comprueba además que
ninguna tabla haya desaparecido ni perdido más del 2 % de sus filas. Los cambios intencionados
(una tabla que se elimina, un cambio de grano) se declaran en `cambios_esperados.json`, en el
mismo PR que los introduce; cuando la versión nueva ya está publicada, dejan de tener efecto y
se vacían. En una emergencia, `F1_SMOKE_ALLOW_SHRINK=1` omite solo esta comprobación (input
`allow_shrink` del pipeline).
"""

import json
import os
import warnings
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from api.app.config import Settings
from api.app.main import create_app
from ingestion.snapshot import table_count_regressions

SMOKE_DB = os.environ.get("F1_SMOKE_DB")
PREVIOUS_MANIFEST = os.environ.get("F1_SMOKE_PREVIOUS_MANIFEST")
ALLOW_SHRINK = os.environ.get("F1_SMOKE_ALLOW_SHRINK") == "1"
EXPECTED_CHANGES = Path(__file__).with_name("cambios_esperados.json")

pytestmark = pytest.mark.skipif(not SMOKE_DB, reason="F1_SMOKE_DB no está definida")


@pytest.fixture(scope="module")
def manifest() -> dict:
    path = Path(SMOKE_DB).with_name("manifest.json")
    assert path.exists(), f"Falta {path}: la prueba necesita el snapshot completo"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def api():
    # El mismo arranque que en producción (lifespan y elección de la base de datos).
    settings = Settings(db_path=Path(SMOKE_DB), data_repo=None, refresh_hours=0)
    with TestClient(create_app(settings=settings)) as client:
        yield client


def get(api: TestClient, url: str, **params):
    response = api.get(url, params=params)
    assert response.status_code == 200, f"{url}: {response.status_code} {response.text[:200]}"
    return response.json()


def test_health_reports_the_snapshot_version(api, manifest):
    health = get(api, "/health")
    assert health["status"] == "ok"
    assert health["data"]["version"] == manifest["files"]["f1.duckdb"]["sha256"][:12]
    assert health["data"]["release_tag"] == manifest.get("release_tag")
    race = health["data"]["last_completed_race"]
    assert race is not None
    assert (race["season"], race["round"]) == (
        manifest["last_completed_race"]["season"],
        manifest["last_completed_race"]["round"],
    )


def test_no_quality_check_fails(api):
    checks = get(api, "/quality")
    assert len(checks) >= 30
    assert [c["check_id"] for c in checks if c["status"] == "FAIL"] == []


def test_seasons_and_standings(api, manifest):
    season = manifest["last_completed_race"]["season"]
    seasons = {s["season"]: s for s in get(api, "/seasons")}
    assert min(seasons) == 1950
    assert seasons[season]["completed_races"] >= 1
    assert seasons[1950]["drivers_champion"]["id"] == "nino-farina"
    assert len(get(api, f"/seasons/{season}/standings/drivers")) >= 20
    assert get(api, f"/seasons/{season}/standings/progression", top=5)


def test_last_race_has_results_and_laps(api, manifest):
    last = manifest["last_completed_race"]
    races = get(api, f"/seasons/{last['season']}")["races"]
    race = next(r for r in races if r["round"] == last["round"])
    assert race["is_completed"] and race["winner"] is not None
    results = get(api, f"/races/{race['race_id']}/results")
    assert sum(r["position"] == 1 for r in results) == 1


def test_latest_race_with_lap_data_has_laps(api, manifest):
    """La última carrera con vueltas en bronze (FastF1 u OpenF1) las tiene en la API.

    No se exige en la última carrera del calendario: sus vueltas pueden faltar todavía si OpenF1
    falló (se publica igualmente, decisión 26) y aún no hay FastF1. Pero si el bronze las tiene y
    la API no, el modelo las ha perdido: perder las de una carrera no llega al 2 % de
    fact_laptimes y la prueba de filas no lo vería.
    """
    target = manifest.get("latest_race_with_lap_data")
    assert target, "El bronze no tiene vueltas de FastF1 ni de OpenF1 de ninguna carrera"
    laps = get(api, f"/races/{target['race_id']}/laps")
    assert laps, f"La API no devuelve las vueltas de {target}, que el bronze sí tiene"
    assert get(api, f"/races/{target['race_id']}/stints")
    last = manifest["last_completed_race"]
    if (target["season"], target["round"]) != (last["season"], last["round"]):
        warnings.warn(
            f"La última carrera con resultados ({last['season']} R{last['round']}) aún no tiene "
            f"vueltas; la última con vueltas es {target['season']} R{target['round']}",
            stacklevel=1,
        )


def test_race_control_and_weather(api, manifest):
    # Baréin 2024: con OpenF1 en el bronze (o la copia de FastF1 con mensajes y meteo) tiene
    # dirección de carrera y meteo; sin ellos (snapshots anteriores a D1), listas vacías.
    messages = get(api, "/races/1102/race-control")
    weather = get(api, "/races/1102/weather")
    if manifest.get("openf1_sessions_per_season", {}).get("2024"):
        assert len(messages) > 20
        assert any(m["event"] == "safety_car_deployed" or m["category"] == "Flag" for m in messages)
        assert len(weather) > 60
        assert all(w["air_temperature_c"] is not None for w in weather)
    assert get(api, "/races/1102/race-control", category="Flag") == [
        m for m in messages if m["category"] == "Flag"
    ]


def test_historical_data_is_intact(api):
    # Baréin 2024 (formula1db.com + FastF1) y Mónaco 1950 (solo formula1db.com).
    laps_2024 = get(api, "/races/1102/laps")
    assert len(laps_2024) > 1000
    assert all(lap["lap_time_ms"] for lap in laps_2024 if lap["lap"] > 1)
    assert len(get(api, "/races/2/laps")) > 500
    assert get(api, "/races/1102/telemetry", drivers="max-verstappen")
    assert get(api, "/drivers/lewis-hamilton")["name"] == "Lewis Hamilton"
    assert len(get(api, "/records/drivers")) >= 10
    assert len(get(api, "/circuits")) >= 70


def test_published_tables_have_no_hugeint():
    # Las sumas de DuckDB dan HUGEINT (128 bits), que Parquet, Power BI y la API no esperan.
    with duckdb.connect(SMOKE_DB, read_only=True) as con:
        columns = con.execute(
            "select table_name, column_name from duckdb_columns() "
            "where schema_name in ('gold', 'quality') and data_type in ('HUGEINT', 'UHUGEINT')"
        ).fetchall()
    assert columns == []


def test_tables_do_not_shrink(manifest):
    if ALLOW_SHRINK:
        pytest.skip("F1_SMOKE_ALLOW_SHRINK=1: comprobación omitida a propósito")
    if not PREVIOUS_MANIFEST or not Path(PREVIOUS_MANIFEST).exists():
        pytest.skip("Sin manifiesto anterior con el que comparar")
    previous = json.loads(Path(PREVIOUS_MANIFEST).read_text(encoding="utf-8"))["tables"]
    expected = json.loads(EXPECTED_CHANGES.read_text(encoding="utf-8"))
    problems = table_count_regressions(previous, manifest["tables"], expected)
    assert problems == [], "Cambios no declarados en cambios_esperados.json: " + "; ".join(problems)
