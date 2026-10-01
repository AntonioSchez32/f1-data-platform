"""Carga incremental de FastF1 (vueltas, neumáticos, resultados, dirección de carrera, meteo y
telemetría) en bronze.

Evoluciona `PYTHON/fastf1-main.py` y `PYTHON/fastf1-telemetry.py` del TFG:
- Un fichero Parquet por carrera (`season=YYYY/round=RR.parquet`), de modo que volver a
  cargar una carrera la reemplaza en lugar de duplicar filas.
- Solo se descargan las carreras que faltan (salvo `force=True`), y de cada carrera solo las
  tablas que faltan: añadir `messages` y `weather` a las carreras ya cargadas no toca sus vueltas.
- La telemetría se submuestrea por distancia para no repetir los 364 MB de `quali_laps.csv`.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import fastf1
import pandas as pd
from fastf1.exceptions import RateLimitExceededError

from ingestion.config import BRONZE_DIR, CACHE_DIR, FASTF1_FIRST_SEASON, TELEMETRY_FIRST_SEASON
from ingestion.io import write_parquet

log = logging.getLogger(__name__)

OUT_DIR = BRONZE_DIR / "fastf1"
TELEMETRY_STEP_METERS = 10

TELEMETRY_COLUMNS = [
    "Distance",
    "Speed",
    "RPM",
    "nGear",
    "Throttle",
    "Brake",
    "DRS",
    "X",
    "Y",
    "Z",
]


@dataclass
class LoadSummary:
    loaded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    # Se alcanzó el límite de peticiones de la API: la siguiente ejecución continúa donde se quedó.
    rate_limited: bool = False
    # Carreras cargadas con los neumáticos sin la corrección de FastF1 (tolerate_tyre_info_errors).
    tyre_fix_skipped: list[str] = field(default_factory=list)
    # Carreras sin dirección de carrera o meteo (no cuentan como fallidas; se reintentan).
    extras_failed: list[str] = field(default_factory=list)


def race_path(kind: str, season: int, round_number: int) -> Path:
    return OUT_DIR / kind / f"season={season}" / f"round={round_number:02d}.parquet"


def timedeltas_to_millis(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte las columnas timedelta a milisegundos enteros (Parquet/DuckDB-friendly)."""
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_timedelta64_dtype(df[col]):
            df[f"{col}_ms"] = (df[col].dt.total_seconds() * 1000).round().astype("Int64")
            df = df.drop(columns=col)
    return df


def downsample_by_distance(tel: pd.DataFrame, step: float = TELEMETRY_STEP_METERS) -> pd.DataFrame:
    """Conserva una muestra de telemetría cada `step` metros recorridos."""
    bins = (tel["Distance"] // step).astype("int64")
    return tel.loc[~bins.duplicated()].reset_index(drop=True)


# Sesiones en las que FastF1 no pudo corregir los neumáticos (ver tolerate_tyre_info_errors).
tyre_fix_skipped: list[str] = []


def tolerate_tyre_info_errors() -> bool:
    """Rodeo de un fallo de FastF1 (3.8.3) que impide cargar Italia 2018. Devuelve si está activo.

    `Session.__fix_tyre_info` corrige los mensajes de neumáticos agrupados al principio de la
    carrera, pero lanza `IndexError` cuando hay más tramos agrupados que entradas a boxes (Monza
    2018, siempre, también con la caché vacía). FastF1 lo captura y se queda sin vueltas
    («Failed to load timing data!»). Si falla, se usan los datos de neumáticos sin esa corrección;
    el resto de carreras no cambia, porque solo actúa cuando FastF1 lanza la excepción.

    Es un método privado: si una versión nueva de FastF1 lo renombra, el rodeo no se instala (con
    un aviso) y la ingesta sigue. Se puede retirar cuando `f1-ingest fastf1 --season 2018 --round
    14 --force` cargue Italia 2018 sin él.
    """
    session_cls = fastf1.core.Session
    original = getattr(session_cls, "_Session__fix_tyre_info", None)
    if original is None:
        log.warning(
            "FastF1 %s ya no tiene Session.__fix_tyre_info: no se instala el rodeo de Italia 2018",
            fastf1.__version__,
        )
        return False
    if getattr(original, "tolerant", False):
        return True

    def fix_tyre_info(self, df: pd.DataFrame, *args, **kwargs) -> pd.DataFrame:
        try:
            # Sobre una copia: si falla a medias, los datos originales quedan intactos.
            return original(self, df.copy(), *args, **kwargs)
        except IndexError:
            log.warning("FastF1 no pudo corregir los neumáticos de %s; se usan sin corregir", self)
            tyre_fix_skipped.append(str(self))
            return df

    fix_tyre_info.tolerant = True
    session_cls._Session__fix_tyre_info = fix_tyre_info
    return True


def _with_keys(df: pd.DataFrame, event, season: int) -> pd.DataFrame:
    df = df.copy()
    df.insert(0, "season", season)
    df.insert(1, "round", int(event["RoundNumber"]))
    df.insert(2, "event_name", event["EventName"])
    return df


def _load_race(event, season: int) -> None:
    session = event.get_session("R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)

    laps = _with_keys(timedeltas_to_millis(pd.DataFrame(session.laps)), event, season)
    results = _with_keys(timedeltas_to_millis(pd.DataFrame(session.results)), event, season)
    write_parquet(laps, race_path("laps", season, int(event["RoundNumber"])))
    write_parquet(results, race_path("results", season, int(event["RoundNumber"])))


def _live_timing_api():
    """Módulo de bajo nivel de FastF1 que lee las páginas del cronometraje (`fetch_page`).

    FastF1 lo publica como `fastf1.api`, con un aviso de que pasará a ser privado (`_api`). Se
    prefiere `_api` y, si una versión lo cambia, el error se ve al cargar la primera carrera.
    """
    try:
        from fastf1 import _api
    except ImportError:  # versiones anteriores
        from fastf1 import api as _api
    return _api


def race_control_frame(response: list) -> pd.DataFrame:
    """Mensajes de dirección de carrera con su instante de sesión.

    FastF1 (`Session.race_control_messages`) solo da la hora UTC de cada mensaje, y el resto de
    datos del cronometraje usa el tiempo de sesión: sin la telemetría (car_data/position, cientos
    de MB por carrera) no se puede convertir de uno a otro. La página del feed (jsonStream) trae
    ambos: cada línea empieza con el tiempo de sesión en que se publicó y lleva los mensajes con
    su `Utc`. Se guardan los dos (`SessionTime_ms` y `Time`).
    """
    fields = ("Category", "Message", "Status", "Flag", "Scope", "Sector", "RacingNumber", "Lap")
    rows = []
    for line in response or []:
        if len(line) < 2 or not isinstance(line[1], dict):
            continue
        session_time = pd.to_timedelta(line[0])
        messages = line[1].get("Messages") or []
        if isinstance(messages, dict):
            messages = list(messages.values())
        for entry in messages:
            row = {
                "Time": pd.to_datetime(entry.get("Utc")),
                "SessionTime_ms": round(session_time.total_seconds() * 1000),
            }
            row.update({key: entry.get(key) for key in fields})
            rows.append(row)
    df = pd.DataFrame(rows, columns=["Time", "SessionTime_ms", *fields])
    for column in ("Sector", "Lap"):
        df[column] = pd.to_numeric(df[column], errors="coerce").astype("Int64")
    for column in ("Category", "Message", "Status", "Flag", "Scope", "RacingNumber"):
        df[column] = df[column].astype("string")
    return df


def session_t0(messages: pd.DataFrame) -> pd.Timestamp | None:
    """Hora UTC del tiempo de sesión cero, estimada con los mensajes de dirección de carrera.

    Cada mensaje da `Time - SessionTime` (hora menos tiempo de sesión) con el retraso de su
    publicación; como FastF1 con la telemetría (`_calculate_t0_date`), se toma el mayor, el de
    menor retraso. Precisión de ~1 s (el `Utc` de los mensajes va en segundos).
    """
    valid = messages.dropna(subset=["Time", "SessionTime_ms"])
    if valid.empty:
        return None
    offsets = valid["Time"] - pd.to_timedelta(valid["SessionTime_ms"].astype("int64"), unit="ms")
    return offsets.max()


def _load_race_extras(event, season: int, kinds: set[str]) -> None:
    """Dirección de carrera (`messages`) y meteo (`weather`) de la carrera.

    No pasa por `Session.load(messages=True)`: FastF1 usaría los mensajes para reescribir la
    columna `Deleted` de las vueltas, y las vueltas ya cargadas deben quedar como están. Dos
    peticiones por carrera (más las de la información de la sesión, ya en la caché).
    """
    api = _live_timing_api()
    session = event.get_session("R")
    round_number = int(event["RoundNumber"])
    response = api.fetch_page(session.api_path, "race_control_messages")
    if response is None:
        raise ValueError("el cronometraje no tiene mensajes de dirección de carrera")
    messages = race_control_frame(response)
    if "messages" in kinds:
        write_parquet(
            _with_keys(messages, event, season), race_path("messages", season, round_number)
        )
    if "weather" in kinds:
        weather = pd.DataFrame(api.weather_data(session.api_path))
        weather = timedeltas_to_millis(weather)
        t0 = session_t0(messages)
        weather.insert(
            1,
            "Date",
            (t0 + pd.to_timedelta(weather["Time_ms"], unit="ms")) if t0 is not None else pd.NaT,
        )
        write_parquet(
            _with_keys(weather, event, season), race_path("weather", season, round_number)
        )


def _load_qualifying(event, season: int, telemetry: bool) -> None:
    """Resultados de clasificación (Q1/Q2/Q3) y, opcionalmente, telemetría de la vuelta rápida."""
    session = event.get_session("Q")
    session.load(laps=telemetry, telemetry=telemetry, weather=False, messages=False)
    round_number = int(event["RoundNumber"])

    results = _with_keys(timedeltas_to_millis(pd.DataFrame(session.results)), event, season)
    write_parquet(results, race_path("quali_results", season, round_number))
    if not telemetry:
        return

    frames = []
    for driver in session.drivers:
        try:
            lap = session.laps.pick_drivers(driver).pick_fastest()
            if lap is None or pd.isna(lap["LapTime"]):
                continue
            tel = downsample_by_distance(lap.get_telemetry())[TELEMETRY_COLUMNS].copy()
            tel["Driver"] = lap["Driver"]
            tel["DriverNumber"] = lap["DriverNumber"]
            tel["Compound"] = lap["Compound"]
            tel["LapTime_ms"] = round(lap["LapTime"].total_seconds() * 1000)
            frames.append(tel)
        except Exception as exc:  # un piloto sin datos no debe tumbar la carrera entera
            log.warning("Sin telemetría para %s en %s: %s", driver, event["EventName"], exc)
    if frames:
        telemetry_df = _with_keys(pd.concat(frames, ignore_index=True), event, season)
        write_parquet(telemetry_df, race_path("quali_telemetry", season, round_number))


def completed_races(season: int) -> pd.DataFrame:
    schedule = fastf1.get_event_schedule(season, include_testing=False)
    now = pd.Timestamp.now(tz="UTC")
    race_dates = pd.to_datetime(schedule["Session5DateUtc"], utc=True)
    # Margen de 6 h para que el cronometraje oficial esté publicado.
    return schedule[race_dates + pd.Timedelta(hours=6) < now]


def load_season(
    season: int,
    rounds: list[int] | None = None,
    telemetry: bool = False,
    force: bool = False,
) -> LoadSummary:
    if season < FASTF1_FIRST_SEASON:
        raise ValueError(f"FastF1 solo tiene datos completos desde {FASTF1_FIRST_SEASON}")
    if telemetry and season < TELEMETRY_FIRST_SEASON:
        # Recargar una temporada antigua (p. ej. 2018 por Italia) no debe traer la telemetría de
        # todas sus carreras: el modelo solo la guarda desde TELEMETRY_FIRST_SEASON.
        log.warning(
            "Sin telemetría para %s: solo se carga desde %s", season, TELEMETRY_FIRST_SEASON
        )
        telemetry = False

    cache_dir = CACHE_DIR / "fastf1"
    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_dir))
    logging.getLogger("fastf1").setLevel(logging.WARNING)
    tolerate_tyre_info_errors()

    summary = LoadSummary()
    try:
        schedule = completed_races(season)
    except RateLimitExceededError:
        log.warning("Límite de peticiones alcanzado antes de leer el calendario de %s", season)
        summary.rate_limited = True
        return summary

    for _, event in schedule.iterrows():
        round_number = int(event["RoundNumber"])
        if rounds and round_number not in rounds:
            continue
        label = f"{season}-R{round_number:02d} {event['EventName']}"

        kinds = ["laps", "messages", "weather", "quali_results"]
        kinds += ["quali_telemetry"] if telemetry else []
        pending = {k for k in kinds if force or not race_path(k, season, round_number).exists()}
        if not pending:
            summary.skipped.append(label)
            continue

        try:
            skipped_before = len(tyre_fix_skipped)
            if "laps" in pending:
                _load_race(event, season)
            if len(tyre_fix_skipped) > skipped_before:
                summary.tyre_fix_skipped.append(label)
            if pending & {"quali_results", "quali_telemetry"}:
                _load_qualifying(event, season, telemetry="quali_telemetry" in pending)
            if pending & {"messages", "weather"}:
                # Aparte: si falta el feed de mensajes o de meteo de una carrera, no se pierde ni
                # se marca como fallida la carrera (vueltas y clasificación ya están cargadas).
                try:
                    _load_race_extras(event, season, pending & {"messages", "weather"})
                except RateLimitExceededError:
                    raise
                except Exception as exc:
                    summary.extras_failed.append(label)
                    log.warning("Sin dirección de carrera o meteo de %s: %s", label, exc)
            summary.loaded.append(label)
            log.info("Cargada %s", label)
        except RateLimitExceededError:
            log.warning("Límite de peticiones alcanzado en %s; se reanudará después", label)
            summary.rate_limited = True
            break
        except Exception as exc:
            summary.failed.append(label)
            log.error("Error cargando %s: %s", label, exc)
    return summary
