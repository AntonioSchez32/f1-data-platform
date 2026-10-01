"""Genera `api/tests/fixtures/sample/`, los datos de las pruebas de la API (un Parquet por tabla).

Copia de la base de datos de la API (`dist/f1.duckdb`, generada con `f1-ingest snapshot pack`) con
las dimensiones y los agregados completos, los resultados y clasificaciones de 2021 a 2024 y, de
las tablas más grandes, solo el Gran Premio de Baréin 2024 (vueltas, paradas y la telemetría de
tres pilotos; dirección de carrera y meteo). Las pruebas construyen con ellos una base de
datos temporal (api/tests/conftest.py).
Uso, desde la raíz del proyecto:

    uv run python scripts/make_api_fixture.py
"""

from pathlib import Path

import duckdb

SOURCE = Path("dist/f1.duckdb")
TARGET = Path("api/tests/fixtures/sample")
SAMPLE_RACE = "(select race_id from warehouse.gold.dim_race where season = 2024 and round = 1)"
RECENT_RACES = "(select race_id from warehouse.gold.dim_race where season between 2021 and 2024)"
FILTERS = {
    "fact_race_result": f"race_id in {RECENT_RACES}",
    "fact_qualifying_result": f"race_id in {RECENT_RACES}",
    "fact_driver_standing": f"race_id in {RECENT_RACES}",
    "fact_constructor_standing": f"race_id in {RECENT_RACES}",
    "fact_laptimes": f"race_id = {SAMPLE_RACE}",
    "fact_pit_stops": f"race_id = {SAMPLE_RACE}",
    "fact_pit_lane_passes": f"race_id = {SAMPLE_RACE}",
    "fact_race_control_message": f"race_id = {SAMPLE_RACE}",
    "fact_weather_sample": f"race_id = {SAMPLE_RACE}",
    "fact_quali_telemetry": (
        f"race_id = {SAMPLE_RACE} "
        "and driver_id in ('max-verstappen', 'charles-leclerc', 'lewis-hamilton')"
    ),
}

TARGET.mkdir(parents=True, exist_ok=True)
for old in TARGET.glob("*.parquet"):
    old.unlink()
con = duckdb.connect()
con.execute(f"attach '{SOURCE.as_posix()}' as warehouse (read_only)")
tables = con.execute(
    "select schema_name, table_name from duckdb_tables() "
    "where database_name = 'warehouse' order by 1, 2"
).fetchall()
for schema, table in tables:
    where = FILTERS.get(table, "true")
    target = (TARGET / f"{schema}.{table}.parquet").as_posix()
    con.execute(
        f"copy (select * from warehouse.{schema}.{table} where {where}) "
        f"to '{target}' (format parquet, compression zstd)"
    )
con.close()
size = sum(p.stat().st_size for p in TARGET.glob("*.parquet"))
print(f"{TARGET}: {len(tables)} tablas, {size / 1e6:.1f} MB")
