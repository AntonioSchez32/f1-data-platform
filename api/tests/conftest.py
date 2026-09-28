from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from api.app.config import Settings
from api.app.database import Database
from api.app.main import create_app

FIXTURES = Path(__file__).parent / "fixtures" / "sample"


@pytest.fixture(scope="session")
def sample_db_path(tmp_path_factory) -> Path:
    """Base de datos DuckDB construida con los Parquet de ejemplo (scripts/make_api_fixture.py)."""
    path = tmp_path_factory.mktemp("data") / "sample.duckdb"
    con = duckdb.connect(str(path))
    for parquet in sorted(FIXTURES.glob("*.parquet")):
        schema, table = parquet.stem.split(".")
        con.execute(f"create schema if not exists {schema}")
        con.execute(f"create table {schema}.{table} as select * from '{parquet.as_posix()}'")
    con.close()
    return path


@pytest.fixture(scope="session")
def client(sample_db_path):
    settings = Settings(cors_origins=["https://f1.example.org"], refresh_hours=0)
    app = create_app(settings=settings, database=Database(sample_db_path))
    with TestClient(app) as test_client:
        yield test_client
