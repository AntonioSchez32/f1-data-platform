"""Lógica de la prueba de humo que no necesita un snapshot real."""

import pytest

from api.tests.smoke.test_snapshot_smoke import latest_race_with_laps


def races(season, completed, with_laps):
    return [
        {"race_id": season * 100 + r, "round": r, "is_completed": r <= completed}
        for r in range(1, 25)
    ], {season * 100 + r for r in with_laps}


def finder(*seasons):
    by_season, laps = {}, set()
    for season, completed, with_laps in seasons:
        by_season[season], season_laps = races(season, completed, with_laps)
        laps |= season_laps
    return lambda s: by_season.get(s, []), lambda race_id: race_id in laps


def test_takes_the_last_race_with_laps_of_the_season():
    races_of, has_laps = finder((2026, 15, range(1, 15)))
    assert latest_race_with_laps(races_of, has_laps, 2026, bronze_has_season=True)["round"] == 14


def test_falls_back_to_the_previous_season_only_without_fastf1_for_it():
    # Enero de 2027: F1DB ya trae la primera carrera, pero FastF1 aún no se ha publicado.
    races_of, has_laps = finder((2026, 24, range(1, 25)), (2027, 1, []))
    with pytest.warns(UserWarning, match="Ninguna carrera de 2027"):
        race = latest_race_with_laps(races_of, has_laps, 2027, bronze_has_season=False)
    assert race["race_id"] == 202624


def test_fails_when_bronze_has_the_season_but_the_api_has_no_laps():
    # A mitad de temporada: el bronze trae 2026, pero el modelo ha perdido sus vueltas.
    races_of, has_laps = finder((2025, 24, range(1, 25)), (2026, 15, []))
    assert latest_race_with_laps(races_of, has_laps, 2026, bronze_has_season=True) is None


def test_fails_when_neither_season_has_laps():
    races_of, has_laps = finder((2026, 24, []), (2027, 1, []))
    assert latest_race_with_laps(races_of, has_laps, 2027, bronze_has_season=False) is None
