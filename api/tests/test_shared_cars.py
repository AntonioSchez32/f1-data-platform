"""Coches compartidos (un piloto con dos dorsales en la carrera) y códigos de piloto únicos.

Los datos de ejemplo solo traen vueltas de Baréin 2024, así que estas pruebas añaden a una copia
filas sintéticas de Bélgica 1955 (Behra condujo los coches #20 y #24) y de Australia 2005 (los dos
Schumacher, Monteiro y Montagny).
"""

import shutil
from collections import Counter

import duckdb
import pytest
from fastapi.testclient import TestClient

from api.app.codes import race_driver_codes
from api.app.config import Settings
from api.app.database import Database
from api.app.main import create_app

BELGIUM_1955 = 45
AUSTRALIA_2005 = 732


@pytest.fixture(scope="module")
def shared_client(sample_db_path, tmp_path_factory):
    path = tmp_path_factory.mktemp("shared") / "shared.duckdb"
    shutil.copy(sample_db_path, path)
    con = duckdb.connect(str(path))
    # Behra: #20 en las vueltas 1-3 y #24 (el coche de Mieres) desde la 3; la vuelta 3 está en los
    # dos coches, como en los datos reales de los años 50.
    laps = [
        ("jean-behra", "20", 1, "SOFT", False),
        ("jean-behra", "20", 2, "SOFT", False),
        ("jean-behra", "20", 3, "SOFT", False),
        ("jean-behra", "24", 3, "HARD", False),
        ("jean-behra", "24", 4, "HARD", True),
        ("jean-behra", "24", 5, "MEDIUM", False),
        ("roberto-mieres", "24", 1, "HARD", False),
        ("roberto-mieres", "24", 2, "HARD", False),
    ]
    for driver_id, number, lap, compound, pit_in in laps:
        con.execute(
            """
            insert into gold.fact_laptimes by name
            select ? as race_id, ? as driver_id, ? as driver_number, ? as lap_number,
                   ? as position, 180000 + ? as lap_time_ms, ? as tyre_compound,
                   ? as is_pit_in_lap, false as is_incomplete_lap, 'formula1db' as source,
                   'single_source' as validation_status
            """,
            [BELGIUM_1955, driver_id, number, lap, lap, lap, compound, pit_in],
        )
        if pit_in:
            con.execute(
                """
                insert into gold.fact_pit_lane_passes by name
                select ? as race_id, ? as driver_id, ? as driver_number, ? as lap_number,
                       'unclassified' as pass_type, 'formula1db' as source
                """,
                [BELGIUM_1955, driver_id, number, lap],
            )
    results = [
        (AUSTRALIA_2005, "michael-schumacher", "1", "ferrari", 1),
        (AUSTRALIA_2005, "ralf-schumacher", "17", "toyota", 2),
        (AUSTRALIA_2005, "tiago-monteiro", "18", "jordan", 3),
        (AUSTRALIA_2005, "franck-montagny", "19", "jordan", 4),
    ]
    con.execute("delete from gold.fact_race_result where race_id = ?", [AUSTRALIA_2005])
    for race_id, driver_id, number, constructor_id, order in results:
        con.execute(
            """
            insert into gold.fact_race_result by name
            select ? as race_id, 'RACE' as session_type, ? as position_display_order,
                   ? as position_number, ?::varchar as position_text, ? as driver_number,
                   ? as driver_id, ? as constructor_id, 0.0 as points, false as is_fastest_lap
            """,
            [race_id, order, order, order, number, driver_id, constructor_id],
        )
    con.close()
    settings = Settings(cors_origins=["https://f1.example.org"], refresh_hours=0)
    app = create_app(settings=settings, database=Database(path))
    with TestClient(app) as test_client:
        yield test_client


def test_laps_keep_both_cars_of_a_driver(shared_client):
    laps = shared_client.get(f"/races/{BELGIUM_1955}/laps").json()
    keys = Counter((lap["driver_id"], lap["driver_number"], lap["lap"]) for lap in laps)
    assert max(keys.values()) == 1
    behra = {(lap["driver_number"], lap["lap"]) for lap in laps if lap["driver_id"] == "jean-behra"}
    assert behra == {("20", 1), ("20", 2), ("20", 3), ("24", 3), ("24", 4), ("24", 5)}


def test_stints_are_split_by_car(shared_client):
    stints = [
        (s["driver_number"], s["stint"], s["start_lap"], s["end_lap"], s["compound"])
        for s in shared_client.get(f"/races/{BELGIUM_1955}/stints").json()
        if s["driver_id"] == "jean-behra"
    ]
    # Con la ventana solo por piloto, la vuelta 3 del #24 abría un tramo a mitad del #20.
    assert stints == [
        ("20", 1, 1, 3, "SOFT"),
        ("24", 1, 3, 4, "HARD"),
        ("24", 2, 5, 5, "MEDIUM"),
    ]


def test_pit_lane_passes_carry_the_car_number(shared_client):
    passes = shared_client.get(f"/races/{BELGIUM_1955}/pit-lane-passes").json()
    assert [(p["driver_id"], p["driver_number"], p["lap"]) for p in passes] == [
        ("jean-behra", "24", 4)
    ]


def test_results_have_unique_driver_codes(shared_client):
    results = shared_client.get(f"/races/{AUSTRALIA_2005}/results").json()
    codes = {r["driver_id"]: r["driver_code"] for r in results}
    assert codes == {
        "michael-schumacher": "MSC",
        "ralf-schumacher": "RSC",
        "tiago-monteiro": "TMO",
        "franck-montagny": "FMO",
    }


def test_driver_codes_rules():
    codes = race_driver_codes(
        [
            ("alberto-ascari", "ASC", "Alberto", True),
            ("adolfo-schwelm-cruz", "SCH", "Adolfo", True),
            ("harry-schell", "SCH", "Harry", True),
            ("max-verstappen", None, None, True),
            ("carlos-sainz-jr", None, None, True),
        ]
    )
    # ASC ya es de Ascari: Schwelm Cruz pasa a la inicial con la abreviatura completa.
    assert codes == {
        "alberto-ascari": "ASC",
        "adolfo-schwelm-cruz": "ASCH",
        "harry-schell": "HSC",
        "max-verstappen": "VER",
        "carlos-sainz-jr": "SAI",
    }


def test_driver_codes_keep_the_abbreviation_of_the_only_starter():
    # Berger corrió y el otro BER no se clasificó: Berger conserva BER. Si salen los dos, cambian.
    codes = race_driver_codes(
        [("gerhard-berger", "BER", "Gerhard", True), ("other-ber", "BER", "Bruno", False)]
    )
    assert codes == {"gerhard-berger": "BER", "other-ber": "BBE"}
    both = race_driver_codes(
        [("gerhard-berger", "BER", "Gerhard", True), ("other-ber", "BER", "Bruno", True)]
    )
    assert both == {"gerhard-berger": "GBE", "other-ber": "BBE"}


def test_driver_codes_are_stable_and_unique():
    drivers = [(f"driver-{i}", "ABC", "Ana", True) for i in range(4)]
    codes = race_driver_codes(drivers)
    assert codes == race_driver_codes(list(reversed(drivers)))
    assert len(set(codes.values())) == 4
    assert codes["driver-0"] == "AAB"
