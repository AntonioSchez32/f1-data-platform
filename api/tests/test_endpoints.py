"""Pruebas de los endpoints sobre los datos de ejemplo (temporadas 2021-2024, Baréin 2024)."""

BAHRAIN_2024 = 1102


def test_health_reports_data_version(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert len(body["data"]["version"]) == 12


def test_quality_lists_checks_with_failures_first(client):
    checks = client.get("/quality").json()
    assert len(checks) == 40
    assert {c["status"] for c in checks} <= {"PASS", "FAIL", "INFO", "NO_DATA"}


def test_seasons_include_champions(client):
    seasons = {s["season"]: s for s in client.get("/seasons").json()}
    assert seasons[2024]["drivers_champion"] == {"id": "max-verstappen", "name": "Max Verstappen"}
    assert seasons[2024]["constructors_champion"]["id"] == "mclaren"
    assert seasons[1950]["drivers_champion"]["id"] == "nino-farina"
    # Antes de 1958 no había campeonato de constructores.
    assert seasons[1950]["constructors_champion"] is None


def test_season_calendar(client):
    season = client.get("/seasons/2024").json()
    assert len(season["races"]) == 24
    opener = season["races"][0]
    assert (opener["round"], opener["grand_prix_id"]) == (1, "bahrain")
    assert opener["winner"]["id"] == "max-verstappen"


def test_driver_standings_final_and_after_round(client):
    final = client.get("/seasons/2024/standings/drivers").json()
    assert (final[0]["driver_id"], final[0]["points"], final[0]["is_champion"]) == (
        "max-verstappen",
        437.0,
        True,
    )
    assert "Red Bull" in final[0]["constructors"]
    after_round_1 = client.get("/seasons/2024/standings/drivers", params={"round": 1}).json()
    assert (after_round_1[0]["driver_id"], after_round_1[0]["points"]) == ("max-verstappen", 26.0)


def test_constructor_standings(client):
    final = client.get("/seasons/2024/standings/constructors").json()
    assert (final[0]["constructor_id"], final[0]["points"]) == ("mclaren", 666.0)


def test_standings_progression_has_one_point_per_round_and_driver(client):
    rows = client.get("/seasons/2024/standings/progression", params={"top": 3}).json()
    assert len({r["id"] for r in rows}) == 3
    assert len(rows) == 3 * 24
    assert rows[-1]["points"] >= rows[0]["points"]


def test_race_detail_results_and_qualifying(client):
    race = client.get(f"/races/{BAHRAIN_2024}").json()
    assert (race["season"], race["round"], race["laps"]) == (2024, 1, 57)
    results = client.get(f"/races/{BAHRAIN_2024}/results").json()
    assert results[0]["driver_id"] == "max-verstappen"
    assert results[0]["position"] == 1
    quali = client.get(f"/races/{BAHRAIN_2024}/qualifying").json()
    assert quali[0]["driver_id"] == "max-verstappen"
    # gap_to_pole_pct se mide frente a la vuelta más rápida de toda la clasificación (Q1-Q3).
    assert 0 <= quali[0]["gap_to_pole_pct"] < 0.1


def test_sprint_weekends_2021_to_2024(client):
    # Italia 2021: sprint, pero sin clasificación sprint propia (F1DB no da la fecha del sprint).
    italy_2021 = client.get("/races/1049").json()
    assert (italy_2021["has_sprint"], italy_2021["has_sprint_qualifying"]) == (True, False)
    assert client.get("/races/1049/results", params={"session": "sprint"}).json()
    china_2024 = client.get("/races/1106").json()
    assert (china_2024["has_sprint"], china_2024["has_sprint_qualifying"]) == (True, True)
    season_2021 = client.get("/seasons/2021").json()["races"]
    assert sum(r["has_sprint"] for r in season_2021) == 3


def test_laps_filtered_by_driver(client):
    laps = client.get(
        f"/races/{BAHRAIN_2024}/laps", params={"drivers": "max-verstappen,lewis-hamilton"}
    ).json()
    assert {lap["driver_id"] for lap in laps} == {"max-verstappen", "lewis-hamilton"}
    verstappen = [lap for lap in laps if lap["driver_id"] == "max-verstappen"]
    assert len(verstappen) == 57
    assert all(lap["position"] == 1 for lap in verstappen[-5:])


def test_stints_follow_pit_stops(client):
    stints = [
        s
        for s in client.get(f"/races/{BAHRAIN_2024}/stints").json()
        if s["driver_id"] == "max-verstappen"
    ]
    stops = [
        p
        for p in client.get(f"/races/{BAHRAIN_2024}/pitstops").json()
        if p["driver_id"] == "max-verstappen"
    ]
    assert len(stops) == 2
    assert len(stints) == 3
    assert sum(s["laps"] for s in stints) == 57
    assert [s["end_lap"] for s in stints[:-1]] == [p["lap"] for p in stops]


def test_pit_lane_passes_are_typed(client):
    passes = client.get(f"/races/{BAHRAIN_2024}/pit-lane-passes").json()
    assert passes
    assert {p["pass_type"] for p in passes} <= {
        "pit_stop",
        "safety_car",
        "red_flag",
        "retirement",
        "penalty_or_other",
        "unclassified",
    }


def test_telemetry_keeps_requested_order_and_limits_drivers(client):
    laps = client.get(
        f"/races/{BAHRAIN_2024}/telemetry", params={"drivers": "charles-leclerc,max-verstappen"}
    ).json()
    assert [lap["driver_id"] for lap in laps] == ["charles-leclerc", "max-verstappen"]
    assert len(laps[0]["distance_m"]) == len(laps[0]["speed_kmh"]) > 100
    too_many = client.get(f"/races/{BAHRAIN_2024}/telemetry", params={"drivers": "a,b,c,d,e"})
    assert too_many.status_code == 422
    assert client.get(f"/races/{BAHRAIN_2024}/telemetry").status_code == 422


def test_drivers_search_detail_and_history(client):
    found = client.get("/drivers", params={"search": "hamil"}).json()
    assert found[0]["driver_id"] == "lewis-hamilton"
    detail = client.get("/drivers/lewis-hamilton").json()
    assert detail["championships"] == 7
    seasons = client.get("/drivers/lewis-hamilton/seasons").json()
    assert seasons[0]["season"] == 2007
    teammates = client.get("/drivers/lewis-hamilton/teammates").json()
    assert any(t["teammate_id"] == "george-russell" for t in teammates)
    results = client.get("/drivers/max-verstappen/results", params={"season": 2024}).json()
    assert {r["season"] for r in results} == {2024}


def test_drivers_search_ignores_accents(client):
    found = client.get("/drivers", params={"search": "perez"}).json()
    assert "sergio-perez" in {d["driver_id"] for d in found}


def test_constructors(client):
    ferrari = client.get("/constructors/ferrari").json()
    assert ferrari["wins"] == 250
    seasons = client.get("/constructors/mclaren/seasons").json()
    season_2024 = next(s for s in seasons if s["season"] == 2024)
    assert season_2024["is_champion"] is True
    assert {d["id"] for d in season_2024["drivers"]} == {"lando-norris", "oscar-piastri"}


def test_records(client):
    drivers = client.get("/records/drivers", params={"metric": "wins", "limit": 2}).json()
    assert [d["id"] for d in drivers] == ["lewis-hamilton", "michael-schumacher"]
    assert drivers[0]["rank"] == 1
    constructors = client.get("/records/constructors", params={"metric": "wins"}).json()
    assert constructors[0]["id"] == "ferrari"
    assert client.get("/records/drivers", params={"metric": "nope"}).status_code == 422


def test_circuits_with_season_range(client):
    circuits = {c["circuit_id"]: c for c in client.get("/circuits").json()}
    assert circuits["monza"]["races"] > 70
    recent = client.get("/circuits", params={"season_from": 2024, "season_to": 2024}).json()
    assert sum(c["races"] for c in recent) == 24


def test_race_control_messages(client):
    messages = client.get(f"/races/{BAHRAIN_2024}/race-control").json()
    assert len(messages) > 20
    assert [m["seq"] for m in messages] == sorted(m["seq"] for m in messages)
    assert {m["source"] for m in messages} == {"fastf1"}
    assert messages[0]["utc"] and messages[0]["session_time_ms"] is not None
    assert any(m["event"] == "chequered_flag" for m in messages)
    # Los mensajes de un coche llevan su piloto.
    car = [m for m in messages if m["driver_number"] is not None and m["driver_id"]]
    assert car and all(isinstance(m["driver_id"], str) for m in car)
    flags = client.get(f"/races/{BAHRAIN_2024}/race-control", params={"category": "Flag"}).json()
    assert flags == [m for m in messages if m["category"] == "Flag"]
    blue = client.get(f"/races/{BAHRAIN_2024}/race-control", params={"flag": "BLUE"}).json()
    assert blue and {m["flag"] for m in blue} == {"BLUE"}


def test_weather_samples(client):
    samples = client.get(f"/races/{BAHRAIN_2024}/weather").json()
    assert len(samples) > 60  # una por minuto durante la sesión
    assert [s["seq"] for s in samples] == list(range(1, len(samples) + 1))
    assert all(10 < s["air_temperature_c"] < 40 for s in samples)
    assert all(s["track_temperature_c"] is not None for s in samples)
    assert not any(s["is_raining"] for s in samples)


def test_race_without_race_control_returns_empty_lists(client):
    # Una carrera que existe sin mensajes ni meteo (fuera de los datos de ejemplo): 200 y [].
    race_id = client.get("/seasons/2023").json()["races"][0]["race_id"]
    assert client.get(f"/races/{race_id}/race-control").json() == []
    assert client.get(f"/races/{race_id}/weather").json() == []


def test_not_found(client):
    assert client.get("/seasons/1900").status_code == 404
    assert client.get("/races/999999").status_code == 404
    assert client.get("/races/999999/laps").status_code == 404
    assert client.get("/races/999999/race-control").status_code == 404
    assert client.get("/races/999999/weather").status_code == 404
    assert client.get("/drivers/nobody").status_code == 404
    assert client.get("/constructors/nobody/seasons").status_code == 404


def test_rankings_match_season_totals(client):
    # Los datos de ejemplo tienen resultados de 2021 a 2024.
    params = {"season_from": 2021, "season_to": 2024}
    drivers = client.get("/rankings/drivers", params={**params, "limit": 3}).json()
    assert drivers[0]["id"] == "max-verstappen"
    seasons = [
        s
        for s in client.get("/drivers/max-verstappen/seasons").json()
        if 2021 <= s["season"] <= 2024
    ]
    assert drivers[0]["wins"] == sum(s["wins"] for s in seasons)
    assert drivers[0]["championships"] == 4
    constructors = client.get(
        "/rankings/constructors", params={**params, "order_by": "championships"}
    ).json()
    assert (constructors[0]["id"], constructors[0]["championships"]) == ("red-bull", 2)


def test_rankings_by_season_range(client):
    season_2024 = client.get(
        "/rankings/drivers", params={"season_from": 2024, "season_to": 2024, "order_by": "points"}
    ).json()
    assert season_2024[0]["id"] == "max-verstappen"
    assert season_2024[0]["championships"] == 1
    assert season_2024[0]["points"] == 437.0
    assert client.get("/rankings/drivers", params={"order_by": "nope"}).status_code == 422
