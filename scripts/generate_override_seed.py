"""Genera `transform/seeds/race_data_overrides.csv` a partir de las hojas de evidencia de
`docs/revision_divergencias` (decisiones A3, A4, A5, N1 y N2 de la revisión de 2026).

Cada corrección se localiza en F1DB sin modificar (race_id, sesión, position_display_order) y se
comprueba que el valor original sigue siendo el revisado; si algo no encaja, el script falla.
Necesita un `dbt build` previo. Uso, desde `transform/`:

    uv run python ../scripts/generate_override_seed.py
"""

import csv
import sys
from collections import Counter
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path("..")
EVIDENCE = ROOT / "docs" / "revision_divergencias"
SEED = Path("seeds") / "race_data_overrides.csv"

con = duckdb.connect(str(ROOT / "data/gold/f1.duckdb"), read_only=True)
RACES_SQL = "select race_id, season, round from gold.dim_race"
RACES = {(season, rnd): race_id for race_id, season, rnd in con.sql(RACES_SQL).fetchall()}
ROWS = con.sql("""
    select race_id, session_type, position_display_order, driver_id, driver_number, d.name,
           position_number, position_text, race_laps, race_grid_position_number,
           race_grid_position_text, race_positions_gained, fastest_lap_lap,
           fastest_lap_time_millis, qualifying_q3_millis, qualifying_gap_millis
    from silver.stg_f1db__race_data
    join silver.stg_f1db__drivers as d using (driver_id)
""").df()

overrides: list[dict] = []
errors: list[str] = []


def evidence_sheet(name: str) -> list[dict]:
    with open(EVIDENCE / name, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


def find(race_id, session, driver_id=None, name=None, number=None):
    m = ROWS[(ROWS.race_id == race_id) & (ROWS.session_type == session)]
    if driver_id is not None:
        m = m[m.driver_id == driver_id]
    if name is not None:
        m = m[m.name == name]
    if number is not None:
        m = m[m.driver_number == str(number)]
    if len(m) != 1:
        errors.append(f"{race_id} {session} {driver_id or name} #{number}: {len(m)} filas")
        return None
    return m.iloc[0]


def add(row, column, new, decision, evidence, action="set"):
    old = row[column]
    old = "" if pd.isna(old) else old if isinstance(old, str) else str(int(old))
    new = "" if new is None else str(new)
    if action == "set" and old == new:
        errors.append(f"{row.race_id} {row.driver_id} {column}: el valor ya es {new}")
    overrides.append(
        {
            "race_id": int(row.race_id),
            "session_type": row.session_type,
            "position_display_order": int(row.position_display_order),
            "driver_id": row.driver_id,
            "column_name": column,
            "f1db_value": old,
            "corrected_value": new,
            "action": action,
            "decision": decision,
            "evidence": evidence,
        }
    )


# N1 · Brasil 2018: clasificación oficial de la FIA.
race = RACES[(2018, 20)]
ev = (
    "Clasificación oficial FIA: 14. Vandoorne 1:28:14.332, 15. Ocon 1:28:15.651 "
    "(coinciden FastF1, Ergast y formula1db)"
)
for driver_id, position, grid in (("esteban-ocon", 15, 18), ("stoffel-vandoorne", 14, 20)):
    row = find(race, "RACE_RESULT", driver_id)
    add(row, "position_display_order", position, "N1", ev)
    add(row, "position_number", position, "N1", ev)
    add(row, "position_text", position, "N1", ev)
    add(row, "race_positions_gained", grid - position, "N1", ev)

# A5 · B5: parrillas. La sesión STARTING_GRID_POSITION de F1DB ya tiene el orden oficial.
for rec in evidence_sheet("B5_parrillas.csv"):
    if rec["decision_propuesta"] != "corregir F1DB":
        continue
    row = find(RACES[(int(rec["temporada"]), int(rec["ronda"]))], "RACE_RESULT", rec["piloto"])
    assert int(rec["parrilla_f1db"]) == row.race_grid_position_number, rec
    grid = int(rec["parrilla_fia"])
    ev = f"{rec['fuente_fia']} (FIA): parrilla {grid}; igual que STARTING_GRID_POSITION de F1DB"
    add(row, "race_grid_position_number", grid, "A5", ev)
    add(row, "race_grid_position_text", grid, "A5", ev)
    if not pd.isna(row.position_number):
        add(row, "race_positions_gained", grid - int(row.position_number), "A5", ev)

# N2 · Verstappen, Qatar 2021: Q3 oficial 1:21.282 (F1DB guardó su primer intento, 1:21.424).
race = RACES[(2021, 20)]
row = find(race, "QUALIFYING_RESULT", "max-verstappen")
session = ROWS[(ROWS.race_id == race) & (ROWS.session_type == "QUALIFYING_RESULT")]
pole_ms = int(session[session.position_number == 1].qualifying_q3_millis.iloc[0])
ev = "FIA Qualifying Session Lap Times: Q3 vuelta 15 1:21.424, vuelta 18 1:21.282 (mejor)"
add(row, "qualifying_q3_millis", 81282, "N2", ev)
add(row, "qualifying_gap_millis", 81282 - pole_ms, "N2", ev)

# A4 · B1: vuelta de la vuelta rápida (Stats F1 coincide con formula1db y Ergast).
for rec in evidence_sheet("B1_numero_vuelta_rapida.csv"):
    if rec["veredicto"] != "formula1db+Ergast":
        continue
    race = RACES[(int(rec["temporada"]), int(rec["ronda"]))]
    row = find(race, "FASTEST_LAP", name=rec["piloto"])
    if row is None:
        continue
    assert int(rec["vuelta_f1db"]) == row.fastest_lap_lap, rec
    assert int(rec["tiempo_ms"]) == row.fastest_lap_time_millis, rec
    lap = int(float(rec["vuelta_formula1db_ergast"]))
    assert lap == int(rec["vuelta_statsf1"]), rec
    ev = f"Stats F1 (meilleur tour): vuelta {lap}; formula1db y Ergast: vuelta {lap}"
    add(row, "fastest_lap_lap", lap, "A4", ev)

# A3 · V7: vueltas completadas (Stats F1 como árbitro).
for rec in evidence_sheet("V7_vueltas_completadas_historicas.csv"):
    race = RACES[(int(rec["temporada"]), int(rec["ronda"]))]
    row = find(race, "RACE_RESULT", name=rec["piloto"], number=rec["dorsales"])
    if row is None:
        continue
    assert int(rec["vueltas_f1db"]) == row.race_laps, rec
    if rec["coincide_statsf1_con"] == "formula1db+Ergast":
        laps = int(rec["vueltas_formula1db"])
        assert laps == int(rec["vueltas_ergast"]) == int(rec["vueltas_statsf1"]), rec
        add(row, "race_laps", laps, "A3", f"Stats F1: {laps} vueltas; formula1db y Ergast: {laps}")
    elif rec["coincide_statsf1_con"] == "ninguna":
        ev = (
            f"Sin acuerdo: F1DB {rec['vueltas_f1db']}, formula1db/Ergast "
            f"{rec['vueltas_formula1db']}, Stats F1 {rec['vueltas_statsf1']}"
        )
        add(row, "race_laps", None, "A3", ev, action="flag")

if errors:
    print("\n".join(errors))
    sys.exit(1)

with open(SEED, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, list(overrides[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(
        sorted(
            overrides,
            key=lambda o: (
                o["decision"],
                o["race_id"],
                o["position_display_order"],
                o["column_name"],
            ),
        )
    )
print(len(overrides), dict(Counter((o["decision"], o["action"]) for o in overrides)))
