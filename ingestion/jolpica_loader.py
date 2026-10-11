"""Carga de Jolpica-F1 (https://jolpi.ca, sucesor de Ergast, 1996+ para vueltas) en bronze.

Jolpica sustituye a Ergast en el modelo (decisiones 49-54): vota en la fusión de vueltas,
rellena vueltas sueltas, contrasta las carreras que solo tienen OpenF1 y sirve de respaldo. Sus
paradas, resultados y clasificación solo se usan como controles de calidad frente a F1DB. Datos
CC BY-NC-SA 4.0 (no comercial, compartir igual); proyecto no oficial.

Acceso mixto (decisión 51):

- **Volcado *delayed* en CSV** para toda la historia (gratuito, 14 días de retraso). Se consulta
  el índice (`/data/dumps/download/`) y solo si su SHA-256 cambió se descarga el zip (una
  descarga por ejecución, decisión 3), se comprueba el hash y se convierte.
- **API compatible con Ergast** solo para las carreras disputadas más nuevas que el volcado:
  resultados, sprint, clasificación, paradas y vueltas (paginadas). Se vuelven a pedir en cada
  ejecución, porque Jolpica completa y corrige sus datos, hasta que entran en el volcado, que
  entonces las sustituye. La decisión se toma por carrera y por tabla: desde 2025 las vueltas
  salen de los PDF de la FIA y pueden llegar al volcado después que los resultados.

El volcado no tiene el formato de Ergast: es la base de datos interna de Jolpica (tablas
`formula_one_*`, columnas sin orden garantizado, tiempos como `interval` de Postgres). Este
cargador lo convierte a un **esquema plano propio, el de la API de Ergast** (su contrato
estable), común a las dos vías y con la columna `origin` ('dump' o 'api'): un Parquet por tabla
en `bronze/jolpica/<tabla>.parquet` (ver `SCHEMA`). La conversión replica los serializers de la
API de Jolpica (`jolpica_api/ergastapi/serializers.py`): texto de la posición, estado, tiempo
solo de los clasificados, Q1-Q3 a partir de la vuelta más rápida de cada sesión, etc.

Nunca deja bronze a medias: las tablas se escriben primero en temporales, se sustituyen al final
y `_metadata.json` va el último. Si algo falla, se conserva lo que había (el Jolpica del snapshot
anterior) y se reintenta en la siguiente ejecución (decisión 53).

Límites de Jolpica sin cuenta: 4 peticiones/s y 500/h. Se espera `MIN_INTERVAL_S` entre
peticiones, se respeta `retry-after` en los 429, se reintenta con espera creciente en los 5xx y
hay un tope de peticiones y un tiempo máximo por ejecución.
"""

import hashlib
import io
import json
import logging
import os
import re
import tempfile
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests

from ingestion.config import BRONZE_DIR
from ingestion.openf1_loader import USER_AGENT, _retry_after

log = logging.getLogger(__name__)

API_HOST = "api.jolpi.ca"
API_URL = f"https://{API_HOST}/ergast/f1/"
DUMPS_URL = f"https://{API_HOST}/data/dumps/download/"
OUT_DIR = BRONZE_DIR / "jolpica"

# Versión del esquema plano: si cambia, se vuelve a descargar y convertir el volcado aunque su
# hash no haya cambiado (y D2b puede detectar el cambio en `_metadata.json`).
SCHEMA_VERSION = 1

# 4 peticiones/s como mucho: una cada 0,5 s, con margen.
MIN_INTERVAL_S = 0.5
# 500/h: tope por ejecución, con margen para otras consultas desde la misma IP.
MAX_REQUESTS = 450
MAX_ATTEMPTS = 4
MAX_RATE_LIMITED = 10
BACKOFF_S = 5.0
TIMEOUT_S = 60
DOWNLOAD_TIMEOUT_S = 300
PAGE_LIMIT = 100
# Vueltas del volcado (respecto a las que suman los resultados) para dar una carrera por cubierta.
MIN_LAP_COVERAGE = 0.95
# Tiempo tras la salida de la carrera a partir del cual se piden sus datos a la API.
RACE_MARGIN = timedelta(hours=3)

# Volcado: miembros que se leen (lista blanca) y topes contra un zip anómalo.
DUMP_MEMBER = re.compile(r"formula_one_[a-z]+\.csv")
MAX_DUMP_BYTES = 200 * 1024**2
MAX_MEMBER_BYTES = 500 * 1024**2

# Columnas que se leen de cada tabla del volcado. Si Jolpica cambia su esquema y falta alguna, la
# carga falla con un error claro y se conserva el Jolpica anterior.
DUMP_COLUMNS = {
    "season": ["id", "year"],
    "circuit": ["id", "reference", "name", "locality", "country"],
    "round": ["id", "season_id", "circuit_id", "number", "name", "is_cancelled"],
    "session": ["id", "round_id", "type", "number", "timestamp", "has_time_data"],
    "driver": [
        "id",
        "reference",
        "forename",
        "surname",
        "abbreviation",
        "permanent_car_number",
        "date_of_birth",
        "nationality",
    ],
    "team": ["id", "reference", "name", "nationality"],
    "teamdriver": ["id", "team_id", "driver_id"],
    "roundentry": ["id", "round_id", "team_driver_id", "car_number"],
    "sessionentry": [
        "id",
        "session_id",
        "round_entry_id",
        "position",
        "is_classified",
        "status",
        "detail",
        "points",
        "grid",
        "time",
        "fastest_lap_rank",
        "laps_completed",
    ],
    "lap": [
        "id",
        "session_entry_id",
        "number",
        "position",
        "time",
        "is_entry_fastest_lap",
        "is_deleted",
    ],
    "pitstop": ["id", "session_entry_id", "lap_id", "number", "duration", "local_timestamp"],
}

# Esquema plano de bronze/jolpica: el de la API de Ergast, con tiempos en milisegundos.
SCHEMA = {
    "races": pa.schema(
        [
            ("season", pa.int32()),
            ("round", pa.int32()),
            ("race_name", pa.string()),
            ("race_date", pa.date32()),
            ("race_time", pa.string()),
            ("circuit_ref", pa.string()),
            ("circuit_name", pa.string()),
            ("locality", pa.string()),
            ("country", pa.string()),
            ("origin", pa.string()),
        ]
    ),
    "drivers": pa.schema(
        [
            ("driver_ref", pa.string()),
            ("forename", pa.string()),
            ("surname", pa.string()),
            ("code", pa.string()),
            ("permanent_number", pa.int32()),
            ("date_of_birth", pa.date32()),
            ("nationality", pa.string()),
            ("origin", pa.string()),
        ]
    ),
    "constructors": pa.schema(
        [
            ("constructor_ref", pa.string()),
            ("name", pa.string()),
            ("nationality", pa.string()),
            ("origin", pa.string()),
        ]
    ),
    "results": pa.schema(
        [
            ("season", pa.int32()),
            ("round", pa.int32()),
            # 'R' (carrera) o 'SR' (sprint).
            ("session_type", pa.string()),
            ("driver_ref", pa.string()),
            ("constructor_ref", pa.string()),
            ("car_number", pa.int32()),
            ("position", pa.int32()),
            # Posición o, si no se clasificó: R (retirado), D (descalificado), W (no tomó la
            # salida), F (no se clasificó para la carrera).
            ("position_text", pa.string()),
            ("points", pa.float64()),
            ("grid", pa.int32()),
            ("laps", pa.int32()),
            ("status", pa.string()),
            # Tiempo total, solo de los clasificados (como la API).
            ("time_ms", pa.int64()),
            ("fastest_lap_rank", pa.int32()),
            ("fastest_lap_number", pa.int32()),
            ("fastest_lap_ms", pa.int64()),
            ("origin", pa.string()),
        ]
    ),
    "qualifying": pa.schema(
        [
            ("season", pa.int32()),
            ("round", pa.int32()),
            ("driver_ref", pa.string()),
            ("constructor_ref", pa.string()),
            ("car_number", pa.int32()),
            ("position", pa.int32()),
            ("q1_ms", pa.int64()),
            ("q2_ms", pa.int64()),
            ("q3_ms", pa.int64()),
            ("origin", pa.string()),
        ]
    ),
    "lap_times": pa.schema(
        [
            ("season", pa.int32()),
            ("round", pa.int32()),
            ("driver_ref", pa.string()),
            ("lap", pa.int32()),
            ("position", pa.int32()),
            ("time_ms", pa.int64()),
            ("origin", pa.string()),
        ]
    ),
    "pit_stops": pa.schema(
        [
            ("season", pa.int32()),
            ("round", pa.int32()),
            ("driver_ref", pa.string()),
            ("stop", pa.int32()),
            ("lap", pa.int32()),
            # Hora local de la parada (texto, como la da Jolpica).
            ("local_time", pa.string()),
            ("duration_ms", pa.int64()),
            ("origin", pa.string()),
        ]
    ),
}
# Clave de cada tabla (sin duplicados) y orden de las filas al escribir. En los resultados y la
# clasificación entra el dorsal: en los años 50 y 60 un piloto podía llevar dos coches en la misma
# carrera (Bettenhausen en 1950 R3, Fagioli en 1951 R4: 86 pilotos y carreras en el volcado del
# 25/09/2026), con una fila por coche tanto en el volcado como en la API (`number`). El dorsal
# puede faltar en algún no participante (W) de 1961-1963; como clave, el nulo vale como valor.
# Las vueltas y las paradas no lo necesitan (desde 1996 y 2011, sin coches compartidos) y la API
# no lo da en ellas.
KEYS = {
    "races": ["season", "round"],
    "drivers": ["driver_ref"],
    "constructors": ["constructor_ref"],
    "results": ["season", "round", "session_type", "driver_ref", "car_number"],
    "qualifying": ["season", "round", "driver_ref", "car_number"],
    "lap_times": ["season", "round", "driver_ref", "lap"],
    "pit_stops": ["season", "round", "driver_ref", "stop"],
}
# Tablas por carrera que se piden a la API para las carreras más nuevas que el volcado.
RACE_TABLES = ("results", "qualifying", "lap_times", "pit_stops")

# Estado de una entrada de sesión (SessionStatus de Jolpica) → texto de la API.
STATUS_NAMES = {
    0: "Finished",
    1: "Lapped",
    10: "Accident",
    11: "Retired",
    20: "Disqualified",
    30: "Did_not_start",
    40: "Did_not_qualify",
    41: "Did_not_prequalify",
}
POSITION_TEXT_UNCLASSIFIED = {30: "W", 20: "D", 40: "F", 41: "F"}


class JolpicaError(Exception):
    """Jolpica no respondió bien tras los reintentos, o su respuesta no es la esperada."""


class OutOfTime(JolpicaError):
    """Se agotó el tiempo o el tope de peticiones de la ejecución."""


# --- Cliente HTTP -----------------------------------------------------------------------------


class Client:
    """Cliente HTTP de Jolpica que respeta sus límites de peticiones (como el de OpenF1)."""

    def __init__(
        self,
        session: requests.Session | None = None,
        min_interval: float = MIN_INTERVAL_S,
        max_requests: int = MAX_REQUESTS,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.min_interval = min_interval
        self.max_requests = max_requests
        self.sleep = sleep
        self.clock = clock
        self._last: float | None = None
        self.requests = 0
        self.deadline: float | None = None

    def _check_budget(self, what: str) -> None:
        if self.deadline is not None and self.clock() >= self.deadline:
            raise OutOfTime(f"{what}: sin tiempo en esta ejecución")
        if self.requests >= self.max_requests:
            raise OutOfTime(f"{what}: alcanzado el tope de {self.max_requests} peticiones")

    def _pause(self, seconds: float, what: str) -> None:
        if self.deadline is not None:
            seconds = min(seconds, max(self.deadline - self.clock(), 0))
        self.sleep(seconds)
        if self.deadline is not None and self.clock() >= self.deadline:
            raise OutOfTime(f"{what}: sin tiempo en esta ejecución")

    def _wait_turn(self) -> None:
        if self._last is not None:
            remaining = self.min_interval - (self.clock() - self._last)
            if remaining > 0:
                self.sleep(remaining)
        self._last = self.clock()

    def _request(self, url: str, params: dict | None = None, **kwargs) -> requests.Response:
        """Respuesta 200 de `url`, con los reintentos de 429 y 5xx. Lanza JolpicaError."""
        what = f"{url} {params or ''}".strip()
        last_error = ""
        attempt = 0
        rate_limited = 0
        while attempt < MAX_ATTEMPTS:
            self._check_budget(what)
            self._wait_turn()
            self.requests += 1
            try:
                response = self.session.get(url, params=params, **kwargs)
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code == 200:
                    return response
                if response.status_code == 429:
                    rate_limited += 1
                    if rate_limited >= MAX_RATE_LIMITED:
                        raise JolpicaError(f"{what}: {rate_limited} respuestas 429")
                    wait = _retry_after(response.headers.get("retry-after"))
                    log.info("Jolpica pide esperar %.0f s (429)", wait)
                    self._pause(wait, what)
                    continue
                last_error = f"HTTP {response.status_code}"
                if response.status_code < 500:
                    break  # 4xx: no se arregla reintentando
            attempt += 1
            if attempt < MAX_ATTEMPTS:
                self._pause(BACKOFF_S * 2 ** (attempt - 1), what)
        raise JolpicaError(f"{what}: {last_error}")

    def get_json(self, url: str, params: dict | None = None) -> dict:
        response = self._request(url, params, timeout=TIMEOUT_S)
        try:
            data = response.json()
        except ValueError as exc:
            raise JolpicaError(f"{url}: JSON no válido ({exc})") from exc
        if not isinstance(data, dict):
            raise JolpicaError(f"{url}: respuesta inesperada")
        return data

    def download(self, url: str, dest: Path, max_bytes: int = MAX_DUMP_BYTES) -> str:
        """Descarga `url` en `dest` y devuelve su SHA-256. Jolpica redirige a un enlace firmado
        de su almacenamiento (S3): se siguen las redirecciones, pero solo por https."""
        response = self._request(url, stream=True, timeout=DOWNLOAD_TIMEOUT_S)
        if any(urlparse(r.url).scheme != "https" for r in [*response.history, response]):
            raise JolpicaError(f"{url}: la descarga pasa por una URL que no es https")
        digest = hashlib.sha256()
        size = 0
        try:
            with open(dest, "wb") as f:
                for chunk in response.iter_content(chunk_size=1 << 20):
                    size += len(chunk)
                    if size > max_bytes:
                        raise JolpicaError(f"{url}: el volcado supera {max_bytes} bytes")
                    digest.update(chunk)
                    f.write(chunk)
        except (requests.RequestException, OSError) as exc:
            # Lectura cortada a mitad del fichero o error de disco: como cualquier otro fallo del
            # volcado (se sigue con el anterior), no un traceback que se salte la API.
            raise JolpicaError(
                f"{url}: descarga interrumpida ({type(exc).__name__}: {exc})"
            ) from exc
        return digest.hexdigest()


# --- Conversión de tiempos y tipos ------------------------------------------------------------


def text_to_ms(value) -> int | None:
    """Milisegundos de un tiempo en texto: `1:32.123`, `23.456`, `1:02:03.5` o el `interval` de
    Postgres del volcado (`00:01:32.123`). None si está vacío o no es un tiempo."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    days = 0
    match = re.fullmatch(r"(\d+) days? (.*)", text)
    if match:
        days, text = int(match[1]), match[2]
    parts = text.split(":")
    if len(parts) > 3:
        return None
    try:
        seconds = Decimal(parts[-1] or "0")
        minutes = int(parts[-2]) if len(parts) >= 2 else 0
        hours = int(parts[-3]) if len(parts) == 3 else 0
    except (InvalidOperation, ValueError):
        return None
    if seconds < 0:
        return None
    total = Decimal(days * 86400 + hours * 3600 + minutes * 60) + seconds
    return int(total * 1000)  # el volcado trae microsegundos: se trunca, como la API


def _int(value) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return None
    try:
        return int(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        return None


def _float(value) -> float | None:
    if value is None or value == "" or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _bool(value) -> bool | None:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return None
    return str(value).lower() in ("t", "true", "1")


def _true(values: pd.Series) -> pd.Series:
    """Máscara de los booleanos de Postgres (`t`/`f`) que son verdaderos."""
    return values.astype("string").str.lower().isin(["t", "true", "1"]).fillna(False).astype(bool)


def _text(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value)
    return text if text != "" else None


def _date(value) -> date | None:
    text = _text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def to_table(rows: list[dict] | pd.DataFrame, table: str) -> pa.Table:
    """Filas con las columnas y tipos de `SCHEMA[table]`, sin duplicados y ordenadas."""
    schema = SCHEMA[table]
    df = pd.DataFrame(rows) if not isinstance(rows, pd.DataFrame) else rows.copy()
    for name in schema.names:
        if name not in df.columns:
            df[name] = None
    df = df[schema.names]
    if len(df):
        keys = KEYS[table]
        duplicated = df.duplicated(keys, keep=False)
        if duplicated.any():
            sample = df.loc[duplicated, keys].head(3).to_dict("records")
            raise JolpicaError(f"{table}: filas duplicadas por {keys}, p. ej. {sample}")
        df = df.sort_values(keys, kind="stable").reset_index(drop=True)
    arrays = []
    for name, kind in zip(schema.names, schema.types, strict=True):
        column = df[name]
        if pa.types.is_integer(kind) or pa.types.is_floating(kind):
            # Vectorizado (las vueltas son cientos de miles): texto, enteros o NaN a número.
            numbers = pd.to_numeric(column.astype(object), errors="coerce")
            arrays.append(pa.array(numbers, type=kind, from_pandas=True))
        elif pa.types.is_date(kind):
            arrays.append(pa.array([_date(v) for v in column.tolist()], type=kind))
        else:
            arrays.append(pa.array([_text(v) for v in column.tolist()], type=kind))
    return pa.Table.from_arrays(arrays, schema=schema)


def interval_ms(values: pd.Series) -> pd.Series:
    """`text_to_ms` vectorizado para los `interval` de Postgres del volcado (`HH:MM:SS.ffffff`,
    con horas que pueden pasar de 24): milisegundos truncados, como la API; NaN si no es un
    tiempo."""
    deltas = pd.to_timedelta(values, errors="coerce")
    nanoseconds = deltas.to_numpy(dtype="timedelta64[ns]").astype("int64")
    return pd.Series(nanoseconds // 1_000_000, index=values.index).where(deltas.notna())


# --- Volcado ----------------------------------------------------------------------------------


def read_dump(zip_path: Path) -> dict[str, pd.DataFrame]:
    """Lee las tablas `formula_one_*` que hacen falta, sin extraer nada al disco.

    Solo admite miembros de la lista blanca (`formula_one_<tabla>.csv`, sin carpetas) y con un
    tamaño descomprimido acotado; columnas por nombre, todo como texto.
    """
    frames: dict[str, pd.DataFrame] = {}
    with zipfile.ZipFile(zip_path) as zf:
        # Por el nombre del fichero (en la raíz, como hoy, o dentro de una carpeta): nada se
        # extrae al disco, así que una ruta con `..` no puede escribir fuera de ningún sitio.
        members = {
            info.filename.rsplit("/", 1)[-1]: info
            for info in zf.infolist()
            if not info.is_dir() and DUMP_MEMBER.fullmatch(info.filename.rsplit("/", 1)[-1])
        }
        for table, columns in DUMP_COLUMNS.items():
            name = f"formula_one_{table}.csv"
            info = members.get(name)
            if info is None:
                raise JolpicaError(f"El volcado no trae {name}")
            if info.file_size > MAX_MEMBER_BYTES:
                raise JolpicaError(f"{name}: tamaño descomprimido anómalo ({info.file_size} B)")
            with zf.open(info) as fh:
                header = pd.read_csv(fh, nrows=0).columns
                missing = [c for c in columns if c not in header]
                if missing:
                    raise JolpicaError(
                        f"{name}: faltan las columnas {missing}; Jolpica ha cambiado el esquema "
                        "del volcado y hay que revisar DUMP_COLUMNS"
                    )
            with zf.open(info) as fh:
                frames[table] = pd.read_csv(
                    io.TextIOWrapper(fh, encoding="utf-8"),
                    usecols=columns,
                    dtype=str,
                    keep_default_na=False,
                    na_values=[""],
                )
    return frames


def convert_dump(raw: dict[str, pd.DataFrame]) -> dict[str, pa.Table]:
    """Tablas del esquema plano a partir de las del volcado (lógica de los serializers)."""
    season = raw["season"].rename(columns={"id": "season_id", "year": "season"})
    circuit = raw["circuit"].rename(
        columns={"id": "circuit_id", "reference": "circuit_ref", "name": "circuit_name"}
    )
    rounds = raw["round"].rename(columns={"id": "round_id", "number": "round", "name": "race_name"})
    rounds = rounds.merge(season, on="season_id", how="left").merge(
        circuit, on="circuit_id", how="left"
    )
    # Como la API: sin las rondas canceladas ni las que no tienen número.
    rounds = rounds[~rounds["is_cancelled"].map(lambda v: _bool(v) is True)]
    rounds = rounds[rounds["round"].notna()].copy()
    rounds["season"] = rounds["season"].map(_int)
    rounds["round"] = rounds["round"].map(_int)

    sessions = raw["session"].rename(columns={"id": "session_id", "type": "session_type"})
    sessions = sessions.merge(rounds[["round_id", "season", "round"]], on="round_id", how="inner")

    # Fecha y hora de la carrera: las de la sesión de carrera (en UTC), como la API.
    race_sessions = sessions[sessions["session_type"] == "R"]
    stamps = pd.to_datetime(race_sessions["timestamp"], utc=True, errors="coerce")
    race_when = pd.DataFrame(
        {
            "round_id": race_sessions["round_id"],
            "race_date": [None if pd.isna(s) else s.date() for s in stamps],
            "race_time": [
                None if pd.isna(s) or _bool(t) is not True else f"{s.strftime('%H:%M:%S')}Z"
                for s, t in zip(stamps, race_sessions["has_time_data"], strict=True)
            ],
        }
    ).drop_duplicates("round_id")
    races = rounds.merge(race_when, on="round_id", how="left")
    races["origin"] = "dump"

    drivers = raw["driver"].rename(
        columns={
            "reference": "driver_ref",
            "abbreviation": "code",
            "permanent_car_number": "permanent_number",
        }
    )
    drivers = drivers[drivers["driver_ref"].notna()].copy()
    drivers["permanent_number"] = drivers["permanent_number"].map(_int)
    drivers["date_of_birth"] = drivers["date_of_birth"].map(_date)
    drivers["origin"] = "dump"
    teams = raw["team"].rename(columns={"reference": "constructor_ref"})
    teams = teams[teams["constructor_ref"].notna()].copy()
    teams["origin"] = "dump"

    # Entrada de cada piloto en cada ronda: piloto, equipo y dorsal.
    entries = (
        raw["roundentry"]
        .rename(columns={"id": "round_entry_id"})
        .merge(
            raw["teamdriver"].rename(columns={"id": "team_driver_id"}),
            on="team_driver_id",
            how="left",
        )
        .merge(
            raw["driver"][["id", "reference"]].rename(
                columns={"id": "driver_id", "reference": "driver_ref"}
            ),
            on="driver_id",
            how="left",
        )
        .merge(
            raw["team"][["id", "reference"]].rename(
                columns={"id": "team_id", "reference": "constructor_ref"}
            ),
            on="team_id",
            how="left",
        )
    )
    session_entries = (
        raw["sessionentry"]
        .rename(columns={"id": "session_entry_id"})
        .merge(
            sessions[["session_id", "session_type", "number", "season", "round"]],
            on="session_id",
            how="inner",
        )
        .merge(
            entries[["round_entry_id", "driver_ref", "constructor_ref", "car_number"]],
            on="round_entry_id",
            how="left",
        )
    )
    laps = raw["lap"].rename(columns={"id": "lap_id", "number": "lap", "time": "lap_time"})
    laps = laps.merge(
        session_entries[["session_entry_id", "session_type", "season", "round", "driver_ref"]],
        on="session_entry_id",
        how="inner",
    )

    return {
        "races": to_table(races, "races"),
        "drivers": to_table(drivers, "drivers"),
        "constructors": to_table(teams, "constructors"),
        "results": to_table(_dump_results(session_entries, laps), "results"),
        "qualifying": to_table(_dump_qualifying(session_entries, laps), "qualifying"),
        "lap_times": to_table(_dump_laps(laps), "lap_times"),
        "pit_stops": to_table(_dump_pit_stops(raw["pitstop"], session_entries, laps), "pit_stops"),
    }


def _fastest_laps(laps: pd.DataFrame, skip_deleted: bool) -> pd.DataFrame:
    """Vuelta más rápida de cada entrada de sesión (`is_entry_fastest_lap`)."""
    fastest = laps[_true(laps["is_entry_fastest_lap"])]
    if skip_deleted:
        fastest = fastest[~_true(fastest["is_deleted"])]
    # Como `fastest_lap_list[0]` en la API: si hubiera varias, la primera por id.
    fastest = fastest.assign(_id=fastest["lap_id"].map(_int)).sort_values("_id")
    return fastest.drop_duplicates("session_entry_id")[["session_entry_id", "lap", "lap_time"]]


def _dump_results(session_entries: pd.DataFrame, laps: pd.DataFrame) -> list[dict]:
    """Resultados de carrera y sprint (ListResultsSerializer)."""
    races = session_entries[session_entries["session_type"].isin(["R", "SR"])]
    fastest = _fastest_laps(laps, skip_deleted=False).set_index("session_entry_id")
    rows = []
    for entry in races.itertuples(index=False):
        position = _int(entry.position)
        classified = _bool(entry.is_classified)
        status = _int(entry.status)
        if classified:
            position_text = str(position) if position is not None else None
        else:
            position_text = POSITION_TEXT_UNCLASSIFIED.get(status, "R")
        lap = (
            fastest.loc[entry.session_entry_id] if entry.session_entry_id in fastest.index else None
        )
        rows.append(
            {
                "season": entry.season,
                "round": entry.round,
                "session_type": entry.session_type,
                "driver_ref": entry.driver_ref,
                "constructor_ref": entry.constructor_ref,
                "car_number": _int(entry.car_number),
                "position": position,
                "position_text": position_text,
                "points": _float(entry.points),
                "grid": _int(entry.grid),
                "laps": _int(entry.laps_completed),
                "status": _text(entry.detail) or STATUS_NAMES.get(status),
                "time_ms": text_to_ms(entry.time) if classified else None,
                "fastest_lap_rank": _int(entry.fastest_lap_rank) if lap is not None else None,
                "fastest_lap_number": _int(lap["lap"]) if lap is not None else None,
                "fastest_lap_ms": text_to_ms(lap["lap_time"]) if lap is not None else None,
                "origin": "dump",
            }
        )
    return rows


def _dump_qualifying(session_entries: pd.DataFrame, laps: pd.DataFrame) -> list[dict]:
    """Clasificación (ListQualifyingSerializer): las entradas de las sesiones Q* con posición,
    por número de sesión; la posición es la de la última y cada tiempo, la vuelta más rápida no
    borrada de su sesión. Las sesiones Q1-Q3 van a su columna; las demás (QA, QO, QB: formatos
    antiguos de una o dos sesiones), a Q1 y después a Q2."""
    quali = session_entries[
        session_entries["session_type"].str.startswith("Q", na=False)
        & session_entries["position"].notna()
    ].copy()
    fastest = _fastest_laps(laps, skip_deleted=True).set_index("session_entry_id")["lap_time"]
    quali["_number"] = quali["number"].map(_int)
    quali = quali.sort_values(["round_entry_id", "_number"], kind="stable")
    rows = []
    for _, group in quali.groupby("round_entry_id", sort=False):
        first = group.iloc[0]
        row = {
            "season": first["season"],
            "round": first["round"],
            "driver_ref": first["driver_ref"],
            "constructor_ref": first["constructor_ref"],
            "car_number": _int(first["car_number"]),
            "position": _int(group.iloc[-1]["position"]),
            "origin": "dump",
        }
        for entry in group.itertuples(index=False):
            ms = text_to_ms(fastest.get(entry.session_entry_id))
            if entry.session_type in ("Q1", "Q2", "Q3"):
                row[f"{entry.session_type.lower()}_ms"] = ms
            elif "q1_ms" not in row:
                row["q1_ms"] = ms
            else:
                row["q2_ms"] = ms
        rows.append(row)
    return rows


def _dump_laps(laps: pd.DataFrame) -> pd.DataFrame:
    """Vueltas de carrera (LapViewSet: solo la sesión R, sin filtrar las borradas)."""
    race = laps[(laps["session_type"] == "R") & laps["lap"].notna()]
    return pd.DataFrame(
        {
            "season": race["season"],
            "round": race["round"],
            "driver_ref": race["driver_ref"],
            "lap": race["lap"],
            "position": race["position"],
            "time_ms": interval_ms(race["lap_time"]),
            "origin": "dump",
        }
    )


def _dump_pit_stops(
    pitstops: pd.DataFrame, session_entries: pd.DataFrame, laps: pd.DataFrame
) -> pd.DataFrame:
    """Paradas de carrera (PitStopViewSet: solo la sesión R)."""
    race_entries = session_entries[session_entries["session_type"] == "R"]
    stops = pitstops.merge(
        race_entries[["session_entry_id", "season", "round", "driver_ref"]],
        on="session_entry_id",
        how="inner",
    ).merge(laps[["lap_id", "lap"]], on="lap_id", how="left")
    return pd.DataFrame(
        {
            "season": stops["season"],
            "round": stops["round"],
            "driver_ref": stops["driver_ref"],
            "stop": stops["number"],
            "lap": stops["lap"],
            "local_time": stops["local_timestamp"].map(_text),
            "duration_ms": interval_ms(stops["duration"]),
            "origin": "dump",
        }
    )


# --- API (carreras más nuevas que el volcado) -------------------------------------------------


def _paged_races(client: Client, path: str) -> list[dict]:
    """Todas las páginas de `path` (lista `Races` de la API de Ergast).

    `limit` cuenta filas (vueltas de un piloto, paradas…), no carreras ni vueltas: una vuelta
    puede quedar partida entre dos páginas. Se devuelven las carreras de todas las páginas sin
    fusionar; quien las convierte junta sus filas. Comprueba que se recibe `MRData.total`.
    """
    races: list[dict] = []
    offset = 0
    total = None
    received = 0
    while total is None or offset < total:
        data = client.get_json(API_URL + path, {"limit": PAGE_LIMIT, "offset": offset})
        mr = data.get("MRData") or {}
        try:
            total = int(mr.get("total", 0))
        except (TypeError, ValueError) as exc:
            raise JolpicaError(f"{path}: total no válido") from exc
        page = (mr.get("RaceTable") or {}).get("Races") or []
        races += page
        received += _count_rows(page)
        offset += PAGE_LIMIT
        if not page:
            break
    if total and received != total:
        raise JolpicaError(f"{path}: {received} filas de {total}")
    return races


def _count_rows(races: list[dict]) -> int:
    n = 0
    for race in races:
        for key in ("Results", "SprintResults", "QualifyingResults", "PitStops"):
            n += len(race.get(key) or [])
        n += sum(len(lap.get("Timings") or []) for lap in race.get("Laps") or [])
    return n


def _driver_and_constructor(row: dict) -> tuple[str | None, str | None]:
    return (row.get("Driver") or {}).get("driverId"), (row.get("Constructor") or {}).get(
        "constructorId"
    )


def api_results(races: list[dict], season: int, round_number: int, session_type: str) -> list[dict]:
    key = "Results" if session_type == "R" else "SprintResults"
    rows = []
    for race in races:
        for r in race.get(key) or []:
            driver, constructor = _driver_and_constructor(r)
            fastest = r.get("FastestLap") or {}
            rows.append(
                {
                    "season": season,
                    "round": round_number,
                    "session_type": session_type,
                    "driver_ref": driver,
                    "constructor_ref": constructor,
                    "car_number": _int(r.get("number")),
                    "position": _int(r.get("position")),
                    "position_text": _text(r.get("positionText")),
                    "points": _float(r.get("points")),
                    "grid": _int(r.get("grid")),
                    "laps": _int(r.get("laps")),
                    "status": _text(r.get("status")),
                    "time_ms": _int((r.get("Time") or {}).get("millis")),
                    "fastest_lap_rank": _int(fastest.get("rank")),
                    "fastest_lap_number": _int(fastest.get("lap")),
                    "fastest_lap_ms": text_to_ms((fastest.get("Time") or {}).get("time")),
                    "origin": "api",
                }
            )
    return rows


def api_qualifying(races: list[dict], season: int, round_number: int) -> list[dict]:
    rows = []
    for race in races:
        for r in race.get("QualifyingResults") or []:
            driver, constructor = _driver_and_constructor(r)
            rows.append(
                {
                    "season": season,
                    "round": round_number,
                    "driver_ref": driver,
                    "constructor_ref": constructor,
                    "car_number": _int(r.get("number")),
                    "position": _int(r.get("position")),
                    "q1_ms": text_to_ms(r.get("Q1")),
                    "q2_ms": text_to_ms(r.get("Q2")),
                    "q3_ms": text_to_ms(r.get("Q3")),
                    "origin": "api",
                }
            )
    return rows


def api_laps(races: list[dict], season: int, round_number: int) -> list[dict]:
    """Vueltas de todas las páginas, juntas por (piloto, vuelta). Una vuelta partida entre dos
    páginas aparece dos veces en `Laps` con pilotos distintos; un mismo piloto y vuelta repetido
    (la API cambió entre dos páginas) es un error y se reintenta en la siguiente ejecución."""
    rows: dict[tuple[str, int], dict] = {}
    for race in races:
        for lap in race.get("Laps") or []:
            number = _int(lap.get("number"))
            for timing in lap.get("Timings") or []:
                key = (timing.get("driverId"), number)
                if key in rows:
                    raise JolpicaError(f"{season} R{round_number}: vuelta repetida {key}")
                rows[key] = {
                    "season": season,
                    "round": round_number,
                    "driver_ref": key[0],
                    "lap": number,
                    "position": _int(timing.get("position")),
                    "time_ms": text_to_ms(timing.get("time")),
                    "origin": "api",
                }
    return list(rows.values())


def api_pit_stops(races: list[dict], season: int, round_number: int) -> list[dict]:
    rows = []
    for race in races:
        for p in race.get("PitStops") or []:
            rows.append(
                {
                    "season": season,
                    "round": round_number,
                    "driver_ref": p.get("driverId"),
                    "stop": _int(p.get("stop")),
                    "lap": _int(p.get("lap")),
                    "local_time": _text(p.get("time")),
                    "duration_ms": text_to_ms(p.get("duration")),
                    "origin": "api",
                }
            )
    return rows


def api_people(races: list[dict]) -> tuple[list[dict], list[dict]]:
    """Pilotos y equipos que aparecen en los resultados de la API."""
    drivers, constructors = {}, {}
    for race in races:
        for key in ("Results", "SprintResults", "QualifyingResults"):
            for r in race.get(key) or []:
                d = r.get("Driver") or {}
                if d.get("driverId"):
                    drivers[d["driverId"]] = {
                        "driver_ref": d["driverId"],
                        "forename": d.get("givenName"),
                        "surname": d.get("familyName"),
                        "code": d.get("code"),
                        "permanent_number": _int(d.get("permanentNumber")),
                        "date_of_birth": _date(d.get("dateOfBirth")),
                        "nationality": d.get("nationality"),
                        "origin": "api",
                    }
                c = r.get("Constructor") or {}
                if c.get("constructorId"):
                    constructors[c["constructorId"]] = {
                        "constructor_ref": c["constructorId"],
                        "name": c.get("name"),
                        "nationality": c.get("nationality"),
                        "origin": "api",
                    }
    return list(drivers.values()), list(constructors.values())


def schedule_row(race: dict) -> dict:
    circuit = race.get("Circuit") or {}
    location = circuit.get("Location") or {}
    return {
        "season": _int(race.get("season")),
        "round": _int(race.get("round")),
        "race_name": race.get("raceName"),
        "race_date": _date(race.get("date")),
        "race_time": _text(race.get("time")),
        "circuit_ref": circuit.get("circuitId"),
        "circuit_name": circuit.get("circuitName"),
        "locality": location.get("locality"),
        "country": location.get("country"),
        "origin": "api",
    }


def race_start(race: dict) -> datetime | None:
    day = _date(race.get("date"))
    if day is None:
        return None
    clock = (_text(race.get("time")) or "23:59:59Z").rstrip("Z")
    try:
        parsed = datetime.fromisoformat(f"{day.isoformat()}T{clock}")
    except ValueError:
        parsed = datetime.combine(day, datetime.max.time())
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


# --- Combinación de volcado y API -------------------------------------------------------------


def _frame(table: pa.Table | None, name: str) -> pd.DataFrame:
    if table is None:
        return pd.DataFrame(columns=SCHEMA[name].names)
    return table.to_pandas(date_as_object=True, integer_object_nulls=True)


def race_row_counts(table: pa.Table | None, name: str) -> dict[tuple[int, int], int]:
    """Filas por (temporada, ronda)."""
    df = _frame(table, name)
    if df.empty:
        return {}
    counts = df.groupby([df["season"].astype(int), df["round"].astype(int)]).size()
    return {(int(k[0]), int(k[1])): int(n) for k, n in counts.items()}


def dump_coverage(dump: dict[str, pa.Table]) -> dict[str, set[tuple[int, int]]]:
    """Carreras que el volcado ya cubre, por tabla (decisión por carrera y por tabla).

    Resultados: los de la carrera (R). Vueltas: solo si están completas, con al menos
    `MIN_LAP_COVERAGE` de las que suman los resultados (`laps`): desde 2025 salen de los PDF de la
    FIA y pueden llegar tarde o a medias. Clasificación y paradas: con alguna fila.
    """
    results = _frame(dump.get("results"), "results")
    race_results = results[results["session_type"] == "R"]
    coverage = {
        "results": set(
            zip(race_results["season"].astype(int), race_results["round"].astype(int), strict=True)
        )
    }
    expected: dict[tuple[int, int], float] = {}
    for row in race_results.itertuples(index=False):
        key = (int(row.season), int(row.round))
        laps = row.laps if row.laps is not None and not pd.isna(row.laps) else 0
        expected[key] = expected.get(key, 0) + int(laps)
    coverage["lap_times"] = {
        key
        for key, n in race_row_counts(dump.get("lap_times"), "lap_times").items()
        if n >= MIN_LAP_COVERAGE * expected.get(key, 0)
    }
    for name in ("qualifying", "pit_stops"):
        coverage[name] = set(race_row_counts(dump.get(name), name))
    return coverage


def last_dump_race(dump: dict[str, pa.Table]) -> tuple[date, int, int] | None:
    """Última carrera del volcado con resultados de carrera (fecha, temporada, ronda)."""
    races = _frame(dump.get("races"), "races")
    covered = dump_coverage(dump)["results"]
    races = races[races["race_date"].notna()]
    best = None
    for row in races.itertuples(index=False):
        key = (int(row.season), int(row.round))
        if key in covered and (best is None or row.race_date > best[0]):
            best = (row.race_date, *key)
    return best


@dataclass
class ApiRace:
    season: int
    round: int
    name: str
    has_sprint: bool
    schedule: dict
    # Filas obtenidas por tabla ('results' incluye las del sprint). None: no se pudo obtener.
    tables: dict[str, list[dict] | None] = field(default_factory=dict)
    drivers: list[dict] = field(default_factory=list)
    constructors: list[dict] = field(default_factory=list)
    # Carrera de la ejecución anterior que no se vuelve a pedir (calendario ilegible).
    placeholder: bool = False

    @property
    def label(self) -> str:
        return f"{self.season} R{self.round} ({self.name})"


def previous_api_races(previous: dict[str, pa.Table], seasons: list[int]) -> list[ApiRace]:
    """Carreras con filas de la API en la ejecución anterior de las temporadas `seasons`."""
    if not seasons:
        return []
    keys = set()
    for name in RACE_TABLES:
        df = _frame(previous.get(name), name)
        df = df[(df["origin"] == "api") & df["season"].isin(seasons)]
        keys |= set(zip(df["season"].astype(int), df["round"].astype(int), strict=True))
    races = _frame(previous.get("races"), "races")
    out = []
    for season, round_number in sorted(keys):
        row = races[(races["season"] == season) & (races["round"] == round_number)]
        schedule = row.iloc[0].to_dict() if len(row) else {"season": season, "round": round_number}
        out.append(
            ApiRace(
                season=season,
                round=round_number,
                name=schedule.get("race_name") or "",
                has_sprint=False,
                schedule=schedule,
                placeholder=True,
            )
        )
    return out


def fetch_race(client: Client, race: ApiRace) -> list[str]:
    """Pide a la API las tablas de una carrera. Devuelve las que fallaron (no lanza, salvo si se
    agota el tiempo o el tope de peticiones)."""
    failed = []
    base = f"{race.season}/{race.round}/"
    payloads: list[dict] = []

    def get(path: str) -> list[dict] | None:
        try:
            data = _paged_races(client, base + path)
        except OutOfTime:
            raise
        except JolpicaError as exc:
            log.error("Jolpica: %s", exc)
            failed.append(path.rstrip("/"))
            return None
        payloads.extend(data)
        return data

    results = get("results/")
    sprint = get("sprint/") if race.has_sprint else []
    if results is None or sprint is None:
        race.tables["results"] = None
    else:
        race.tables["results"] = api_results(results, race.season, race.round, "R") + api_results(
            sprint, race.season, race.round, "SR"
        )
    quali = get("qualifying/")
    race.tables["qualifying"] = (
        None if quali is None else api_qualifying(quali, race.season, race.round)
    )
    stops = get("pitstops/")
    race.tables["pit_stops"] = (
        None if stops is None else api_pit_stops(stops, race.season, race.round)
    )
    laps = get("laps/")
    if laps is None:
        race.tables["lap_times"] = None
    else:
        try:
            race.tables["lap_times"] = api_laps(laps, race.season, race.round)
        except JolpicaError as exc:
            log.error("Jolpica: %s", exc)
            failed.append("laps")
            race.tables["lap_times"] = None
    race.drivers, race.constructors = api_people(payloads)
    return failed


def merge(
    dump: dict[str, pa.Table],
    previous: dict[str, pa.Table],
    api_races: list[ApiRace],
    warnings: list[str],
) -> tuple[dict[str, pa.Table], list[dict]]:
    """Tablas finales: el volcado más, por carrera y tabla, lo de la API que el volcado no cubre.

    Para cada carrera más nueva que el volcado y cada tabla: si el volcado ya la cubre, gana el
    volcado; si no, las filas nuevas de la API o, si la API falló o devolvió menos filas que en la
    ejecución anterior, las anteriores (con aviso). Devuelve también el detalle por carrera.
    """
    coverage = dump_coverage(dump)
    dump_counts = {name: race_row_counts(dump.get(name), name) for name in RACE_TABLES}
    replaced: dict[str, set[tuple[int, int]]] = {name: set() for name in RACE_TABLES}
    out_frames = {name: [_frame(dump.get(name), name)] for name in SCHEMA}
    previous_frames = {name: _frame(previous.get(name), name) for name in SCHEMA}
    detail = []
    known_drivers = set(out_frames["drivers"][0]["driver_ref"])
    known_teams = set(out_frames["constructors"][0]["constructor_ref"])
    known_races = set(
        zip(
            out_frames["races"][0]["season"].astype(int),
            out_frames["races"][0]["round"].astype(int),
            strict=True,
        )
    )
    # Pilotos y equipos que solo conoce la API (p. ej. un debutante aún fuera del volcado): los de
    # la ejecución anterior se conservan, porque sus filas pueden mantenerse sin volver a pedirse.
    new_drivers = {
        d["driver_ref"]: d
        for d in previous_frames["drivers"].to_dict("records")
        if d["origin"] == "api" and d["driver_ref"] not in known_drivers
    }
    new_teams = {
        c["constructor_ref"]: c
        for c in previous_frames["constructors"].to_dict("records")
        if c["origin"] == "api" and c["constructor_ref"] not in known_teams
    }
    for race in api_races:
        key = (race.season, race.round)
        rows_used = {}
        for name in RACE_TABLES:
            if key in coverage[name]:
                continue
            old = previous_frames[name]
            old = old[
                (old["origin"] == "api")
                & (old["season"].astype(int) == race.season)
                & (old["round"].astype(int) == race.round)
            ]
            new = race.tables.get(name)
            if new is None:
                if len(old):
                    warnings.append(f"{race.label}: {name} se conserva de la ejecución anterior")
                chosen = old
            elif len(new) < len(old):
                warnings.append(
                    f"{race.label}: la API devuelve {len(new)} filas de {name} y antes "
                    f"{len(old)}; se conservan las anteriores"
                )
                chosen = old
            else:
                chosen = pd.DataFrame(new, columns=SCHEMA[name].names)
            # El volcado puede tener parte de la carrera (p. ej. el sprint sin la carrera, o
            # vueltas a medias): la API la sustituye entera en esa tabla solo si trae más filas.
            if len(chosen) and len(chosen) > dump_counts[name].get(key, 0):
                out_frames[name].append(chosen)
                replaced[name].add(key)
                rows_used[name] = len(chosen)
        if rows_used:
            detail.append({"season": race.season, "round": race.round, "rows": rows_used})
            if key not in known_races:
                out_frames["races"].append(pd.DataFrame([race.schedule]))
                known_races.add(key)
        for d in race.drivers:
            if d["driver_ref"] not in known_drivers:
                new_drivers[d["driver_ref"]] = d
        for c in race.constructors:
            if c["constructor_ref"] not in known_teams:
                new_teams[c["constructor_ref"]] = c
    # Carreras que ya no se piden a la API (el volcado cubre sus resultados y vueltas) pero cuyas
    # paradas o clasificación aún no están en el volcado: se conservan las filas de la API.
    asked = {(race.season, race.round) for race in api_races}
    for name in RACE_TABLES:
        old = previous_frames[name]
        old = old[old["origin"] == "api"]
        if old.empty:
            continue
        old_keys = pd.Series(
            list(zip(old["season"].astype(int), old["round"].astype(int), strict=True)),
            index=old.index,
            dtype=object,
        )
        for key, rows in old.groupby(old_keys):
            if key in asked or key in coverage[name]:
                continue
            if len(rows) > dump_counts[name].get(key, 0):
                out_frames[name].append(rows)
                replaced[name].add(key)
    for name, keys in replaced.items():
        if keys:
            base = out_frames[name][0]
            races = pd.Series(
                list(zip(base["season"].astype(int), base["round"].astype(int), strict=True)),
                index=base.index,
                dtype=object,
            )
            out_frames[name][0] = base[~races.isin(keys)]
    if new_drivers:
        out_frames["drivers"].append(pd.DataFrame(list(new_drivers.values())))
    if new_teams:
        out_frames["constructors"].append(pd.DataFrame(list(new_teams.values())))
    tables = {
        name: to_table(
            pd.concat([f for f in frames if len(f)], ignore_index=True)
            if any(len(f) for f in frames)
            else frames[0],
            name,
        )
        for name, frames in out_frames.items()
    }
    return tables, detail


# --- Lectura y escritura de bronze/jolpica ----------------------------------------------------


def _read_metadata(root: Path) -> dict:
    """`_metadata.json`, o {} si falta o está dañado (la carga lo rehace todo)."""
    try:
        data = json.loads((root / "_metadata.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_metadata(root: Path, **fields) -> None:
    """Como `io.write_metadata`, pero atómico: un corte deja los metadatos anteriores."""
    root.mkdir(parents=True, exist_ok=True)
    path = root / "_metadata.json"
    payload = {"loaded_at": datetime.now(UTC).isoformat(timespec="seconds"), **fields}
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def table_path(name: str, root: Path | None = None) -> Path:
    return (root or OUT_DIR) / f"{name}.parquet"


def read_tables(root: Path | None = None) -> dict[str, pa.Table]:
    """Tablas actuales de bronze/jolpica (las que existan y tengan el esquema vigente)."""
    tables = {}
    for name, schema in SCHEMA.items():
        path = table_path(name, root)
        if not path.exists():
            continue
        try:
            table = pq.read_table(path)
        except Exception:  # fichero dañado: como si no existiera
            continue
        if table.schema.equals(schema, check_metadata=False):
            tables[name] = table.replace_schema_metadata(None)
    return tables


def only_dump(tables: dict[str, pa.Table]) -> dict[str, pa.Table]:
    out = {}
    for name, table in tables.items():
        df = _frame(table, name)
        out[name] = to_table(df[df["origin"] == "dump"], name)
    return out


def write_tables(
    tables: dict[str, pa.Table], metadata: dict, root: Path | None = None
) -> list[str]:
    """Escribe las tablas que cambian y, la última, `_metadata.json`. Primero todos los
    temporales y después las sustituciones: un corte deja los metadatos anteriores y la
    siguiente ejecución vuelve a descargar y convertir. Devuelve las tablas reescritas."""
    root = root or OUT_DIR
    root.mkdir(parents=True, exist_ok=True)
    # Temporales de un corte anterior: no deben viajar en bronze.tar.gz.
    for stale in root.glob("*.tmp"):
        stale.unlink(missing_ok=True)
    current = read_tables(root)
    pending = []
    for name, table in tables.items():
        if name in current and current[name].equals(table):
            continue
        path = table_path(name, root)
        tmp = path.with_suffix(".parquet.tmp")
        pq.write_table(table, tmp)
        pending.append((name, tmp, path))
    for _, tmp, path in pending:
        os.replace(tmp, path)
    _write_metadata(root, **metadata)
    return [name for name, _, _ in pending]


def write_empty_if_missing(root: Path | None = None) -> list[str]:
    """Tablas vacías con el esquema para las que falten (solo para que dbt pueda ejecutarse la
    primera vez si no se pudo cargar Jolpica). Se marcan en `_metadata.json` con
    `empty_placeholder` y sin `dump_hash`, así que la siguiente carga lo hace todo de nuevo."""
    root = root or OUT_DIR
    missing = [name for name in SCHEMA if not table_path(name, root).exists()]
    if not missing:
        return []
    root.mkdir(parents=True, exist_ok=True)
    for name in missing:
        pq.write_table(SCHEMA[name].empty_table(), table_path(name, root))
    _write_metadata(
        root,
        schema_version=SCHEMA_VERSION,
        empty_placeholder=True,
        dump_hash=None,
        note="Tablas vacías: no se pudo cargar Jolpica; la siguiente carga lo rehace todo.",
    )
    return missing


# --- Carga ------------------------------------------------------------------------------------


@dataclass
class LoadSummary:
    requests: int = 0
    dump_uploaded_at: str | None = None
    dump_downloaded: bool = False
    # El volcado no se pudo actualizar y no hay uno anterior utilizable: no se escribe nada.
    dump_failed: str | None = None
    # El volcado no se pudo actualizar, pero se sigue con el anterior (y con la API).
    dump_error: str | None = None
    last_dump_race: str | None = None
    api_races: list[str] = field(default_factory=list)
    api_failed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    written: list[str] = field(default_factory=list)
    out_of_time: bool = False

    @property
    def ok(self) -> bool:
        return not (self.dump_failed or self.dump_error or self.api_failed or self.out_of_time)


def _dump_info(client: Client) -> dict:
    index = client.get_json(DUMPS_URL)
    info = (index.get("delayed_dumps") or {}).get("csv") or {}
    url = info.get("download_url") or ""
    digest = (info.get("file_hash") or "").lower()
    # Solo https: la integridad la garantiza el SHA-256 del índice. No se exige el host
    # (api.jolpi.ca redirige a un enlace firmado de su almacenamiento, y el índice podría darlo
    # directamente).
    if urlparse(url).scheme != "https" or not urlparse(url).hostname:
        raise JolpicaError(f"URL de descarga inesperada: {url!r}")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise JolpicaError(f"file_hash no es un SHA-256: {digest!r}")
    return {
        "url": url,
        "hash": digest,
        "size": info.get("file_size"),
        "uploaded_at": info.get("uploaded_at"),
    }


def load(
    client: Client | None = None,
    root: Path | None = None,
    now: datetime | None = None,
    max_minutes: float | None = None,
) -> LoadSummary:
    """Volcado (si cambió) más las carreras nuevas por la API. Nunca deja bronze a medias: si el
    volcado falla, se sigue con el anterior (o, si no hay ninguno utilizable, no se toca nada); si
    falla alguna carrera de la API, se conservan sus filas anteriores."""
    root = root or OUT_DIR
    now = now or datetime.now(UTC)
    client = client or Client()
    if max_minutes is not None:
        client.deadline = client.clock() + max_minutes * 60
    summary = LoadSummary()
    metadata = _read_metadata(root)
    previous = read_tables(root)

    # 1. Volcado. Si falla (índice, descarga, hash, esquema), se sigue con el volcado anterior
    # (decisión 51) y la parte de la API se hace igualmente: el contraste de las carreras nuevas no
    # puede depender de que el volcado se pueda leer. La descarga se reintenta en la siguiente
    # ejecución, porque los metadatos conservan el hash del volcado anterior.
    dump = None
    info = None
    try:
        info = _dump_info(client)
        summary.dump_uploaded_at = info["uploaded_at"]
        unchanged = (
            metadata.get("dump_hash") == info["hash"]
            and metadata.get("schema_version") == SCHEMA_VERSION
            and not metadata.get("empty_placeholder")
            and set(previous) == set(SCHEMA)
        )
        if unchanged:
            dump = only_dump(previous)
        else:
            with tempfile.TemporaryDirectory(prefix="jolpica-") as tmp:
                zip_path = Path(tmp) / "jolpica-f1-csv.zip"
                digest = client.download(info["url"], zip_path)
                if digest != info["hash"]:
                    raise JolpicaError(
                        f"El SHA-256 del volcado ({digest[:12]}) no coincide con el del índice "
                        f"({info['hash'][:12]})"
                    )
                dump = convert_dump(read_dump(zip_path))
            summary.dump_downloaded = True
    except (JolpicaError, zipfile.BadZipFile, ValueError, KeyError) as exc:
        log.error("Jolpica (volcado): %s", exc)
        summary.out_of_time = summary.out_of_time or isinstance(exc, OutOfTime)
        usable = (
            metadata.get("schema_version") == SCHEMA_VERSION
            and metadata.get("dump_hash")
            and not metadata.get("empty_placeholder")
            and set(previous) == set(SCHEMA)
        )
        if not usable:
            summary.dump_failed = str(exc)
            summary.requests = client.requests
            return summary
        summary.dump_error = str(exc)
        dump = only_dump(previous)
        info = {
            "hash": metadata.get("dump_hash"),
            "uploaded_at": metadata.get("dump_uploaded_at"),
            "size": metadata.get("dump_size"),
        }
        summary.dump_uploaded_at = info["uploaded_at"]

    last = last_dump_race(dump)
    if last is None:
        summary.dump_failed = "el volcado no trae ninguna carrera con resultados"
        summary.requests = client.requests
        return summary
    summary.last_dump_race = f"{last[1]} R{last[2]} ({last[0].isoformat()})"

    # 2. API: carreras disputadas, desde la temporada de la última del volcado, a las que el
    # volcado aún no les da resultados o vueltas (decisión por carrera y tabla: desde 2025 las
    # vueltas salen de los PDF de la FIA y pueden llegar después que los resultados).
    coverage = dump_coverage(dump)
    api_races: list[ApiRace] = []
    unread_seasons = []
    for season in range(last[1], now.year + 1):
        try:
            schedule = _paged_races_schedule(client, season)
        except OutOfTime:
            summary.out_of_time = True
            unread_seasons += list(range(season, now.year + 1))
            break
        except JolpicaError as exc:
            log.error("Jolpica (calendario %s): %s", season, exc)
            summary.api_failed.append(f"calendario de {season}")
            unread_seasons.append(season)
            continue
        for race in schedule:
            start = race_start(race)
            key = (_int(race.get("season")), _int(race.get("round")))
            if None in key or start is None or start + RACE_MARGIN > now:
                continue
            if key in coverage["results"] and key in coverage["lap_times"]:
                continue
            api_races.append(
                ApiRace(
                    season=key[0],
                    round=key[1],
                    name=race.get("raceName") or "",
                    has_sprint="Sprint" in race,
                    schedule=schedule_row(race),
                )
            )
    # Temporadas cuyo calendario no se pudo leer: sus carreras de la API de la ejecución anterior
    # se conservan tal cual (sin tablas nuevas, `merge` mantiene las anteriores).
    api_races += previous_api_races(previous, unread_seasons)
    for race in api_races:
        if race.placeholder:
            continue
        if summary.out_of_time:
            race.tables = {}
            summary.api_failed.append(f"{race.label} (sin tiempo en esta ejecución)")
            continue
        try:
            failed = fetch_race(client, race)
        except OutOfTime:
            summary.out_of_time = True
            summary.api_failed.append(f"{race.label} (sin tiempo en esta ejecución)")
            continue
        if failed:
            summary.api_failed.append(f"{race.label}: {', '.join(failed)}")

    # 3. Combinar y escribir.
    try:
        tables, detail = merge(dump, previous, api_races, summary.warnings)
    except JolpicaError as exc:
        log.error("Jolpica: %s", exc)
        summary.dump_failed = str(exc)
        summary.requests = client.requests
        return summary
    summary.api_races = [f"{d['season']} R{d['round']}" for d in detail]
    summary.requests = client.requests
    summary.written = write_tables(
        tables,
        {
            "source": "Jolpica-F1 (https://jolpi.ca), CC BY-NC-SA 4.0",
            "schema_version": SCHEMA_VERSION,
            "dump_hash": info["hash"],
            "dump_uploaded_at": info["uploaded_at"],
            "dump_size": info["size"],
            "last_dump_race": {
                "season": last[1],
                "round": last[2],
                "race_date": last[0].isoformat(),
            },
            "api_races": detail,
            "api_failed": summary.api_failed,
            "warnings": summary.warnings,
            "requests": summary.requests,
            "tables": {name: table.num_rows for name, table in tables.items()},
        },
        root,
    )
    return summary


def _paged_races_schedule(client: Client, season: int) -> list[dict]:
    data = client.get_json(f"{API_URL}{season}/races/", {"limit": PAGE_LIMIT})
    return ((data.get("MRData") or {}).get("RaceTable") or {}).get("Races") or []


def summary_markdown(summary: LoadSummary) -> str:
    """Resumen para `$GITHUB_STEP_SUMMARY`."""
    if summary.dump_failed:
        head = (
            "### Jolpica: no se pudo actualizar; se usa el Jolpica del snapshot anterior "
            f"({summary.requests} peticiones)"
        )
        lines = [head, "", f"Motivo: {summary.dump_failed}"]
        return "\n".join(lines) + "\n"
    state = (
        "nuevo" if summary.dump_downloaded else "anterior" if summary.dump_error else "sin cambios"
    )
    lines = [
        f"### Jolpica: volcado del {summary.dump_uploaded_at} "
        f"({state}), "
        f"{len(summary.api_races)} carrera(s) por la API, {summary.requests} peticiones",
        "",
        f"- Última carrera del volcado: {summary.last_dump_race}",
        "- Carreras por la API: " + (", ".join(summary.api_races) or "ninguna"),
        "- Tablas reescritas: " + (", ".join(summary.written) or "ninguna"),
    ]
    if summary.dump_error:
        lines += [
            "",
            "**Aviso:** no se pudo actualizar el volcado; se sigue con el anterior y se reintenta "
            f"en la siguiente ejecución. Motivo: {summary.dump_error}",
        ]
    if summary.out_of_time:
        lines += ["", "Se agotó el tiempo o el tope de peticiones: lo pendiente, en la siguiente."]
    if summary.api_failed:
        lines += ["", "Faltan (se reintentan en la siguiente ejecución):"]
        lines += [f"- {label}" for label in summary.api_failed]
    if summary.warnings:
        lines += ["", "Avisos:"]
        lines += [f"- {w}" for w in summary.warnings]
    return "\n".join(lines) + "\n"


# --- Comparación del volcado con la API -------------------------------------------------------


def compare_race(
    client: Client, season: int, round_number: int, root: Path | None = None
) -> dict[str, dict]:
    """Compara, para una carrera, las filas convertidas del volcado (en bronze/jolpica) con las
    que devuelve la API (unas 6 peticiones). Sirve para comprobar que la conversión del volcado
    replica la API. Devuelve, por tabla, filas de cada lado, claves solo en uno y filas con
    algún valor distinto (con hasta 5 ejemplos)."""
    tables = read_tables(root)
    race = ApiRace(season, round_number, "", has_sprint=True, schedule={})
    failed = fetch_race(client, race)
    if failed:
        raise JolpicaError(f"{season} R{round_number}: la API falló en {', '.join(failed)}")
    report = {}
    for name in RACE_TABLES:
        df = _frame(tables.get(name), name)
        dump_rows = df[
            (df["origin"] == "dump")
            & (df["season"].astype(int) == season)
            & (df["round"].astype(int) == round_number)
        ]
        api_rows = pd.DataFrame(race.tables[name] or [], columns=SCHEMA[name].names)
        keys, values = KEYS[name], [c for c in SCHEMA[name].names if c not in KEYS[name]]
        values.remove("origin")
        left = to_table(dump_rows, name).to_pylist()
        right = to_table(api_rows, name).to_pylist()
        by_key = {tuple(r[k] for k in keys): r for r in left}
        api_by_key = {tuple(r[k] for k in keys): r for r in right}
        differences = []
        for key in sorted(set(by_key) & set(api_by_key), key=str):
            diff = {
                c: (by_key[key][c], api_by_key[key][c])
                for c in values
                if by_key[key][c] != api_by_key[key][c]
            }
            if diff:
                differences.append({"key": key, "diff": diff})
        report[name] = {
            "dump": len(left),
            "api": len(right),
            "only_dump": len(set(by_key) - set(api_by_key)),
            "only_api": len(set(api_by_key) - set(by_key)),
            "different": len(differences),
            "examples": differences[:5],
        }
    return report
