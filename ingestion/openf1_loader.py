"""Carga incremental de OpenF1 (https://openf1.org, 2023+) en bronze.

OpenF1 es el respaldo y el contraste de FastF1 (decisiones 20-26): responde desde GitHub Actions,
así que el pipeline lo carga en cada ejecución y las carreras nuevas tienen vueltas aunque el autor
aún no haya publicado FastF1. Datos CC BY-NC-SA 4.0; no oficial.

- Sesiones de carrera y sprint: `laps`, `position`, `stints`, `pit`, `session_result`,
  `race_control` y `weather`. Clasificación (Q, SQ y la Sprint Shootout de 2023): solo `laps`,
  `stints` y `session_result` (se guardan sin modelar).
- Un Parquet por endpoint y sesión (`openf1/<endpoint>/season=AAAA/session=<key>.parquet`):
  volver a cargar reemplaza, nunca duplica. El calendario (`sessions` y `meetings`) va en un
  Parquet por temporada y solo se reescribe si cambia.
- Incremental: solo se piden los endpoints de las sesiones terminadas cuyo fichero falta.
- Un 404 de OpenF1 («No results found») significa que no hay datos de ese endpoint en esa sesión
  (p. ej. `pit` de Baréin 2023). Se anota en `openf1/_gaps.json` y no se vuelve a pedir, salvo
  si se comprobó poco después de la sesión (puede ser un retraso de publicación).
- Los errores de red o del servidor no se anotan: la sesión queda pendiente y se reintenta en la
  siguiente ejecución. La carga nunca falla por OpenF1; devuelve lo que falta.
- Límites de OpenF1 sin cuenta: 3 peticiones/s y 30/min. Se espera `MIN_INTERVAL_S` entre
  peticiones, se respeta `retry-after` en los 429 y se reintenta con espera creciente en los 5xx.
"""

import json
import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd
import requests

from ingestion.config import BRONZE_DIR, OPENF1_FIRST_SEASON
from ingestion.io import write_parquet

log = logging.getLogger(__name__)

BASE_URL = "https://api.openf1.org/v1/"
USER_AGENT = (
    "f1-data-platform/1.0 (proyecto académico; +https://github.com/AntonioSchez32/f1-data-platform)"
)
OUT_DIR = BRONZE_DIR / "openf1"
GAPS_FILE = "_gaps.json"

# 30 peticiones/min como mucho: una cada 2 s, con margen.
MIN_INTERVAL_S = 2.1
MAX_ATTEMPTS = 4
# 429 seguidos que se aceptan antes de dar la petición por fallida (cada uno espera retry-after).
MAX_RATE_LIMITED = 10
BACKOFF_S = 5.0
TIMEOUT_S = 60
# Margen tras el final de la sesión para pedir sus datos (como FastF1).
SESSION_MARGIN = timedelta(hours=6)
# Un 404 comprobado antes de este plazo tras la sesión se vuelve a pedir en la siguiente
# ejecución; después, es un hueco conocido.
GAP_CONFIRM_AFTER = timedelta(days=3)

RACE_ENDPOINTS = ("laps", "position", "stints", "pit", "session_result", "race_control", "weather")
QUALIFYING_ENDPOINTS = ("laps", "stints", "session_result")
ENDPOINTS_BY_SESSION = {
    "Race": RACE_ENDPOINTS,
    "Sprint": RACE_ENDPOINTS,
    "Qualifying": QUALIFYING_ENDPOINTS,
    "Sprint Qualifying": QUALIFYING_ENDPOINTS,
    "Sprint Shootout": QUALIFYING_ENDPOINTS,
}
ALL_ENDPOINTS = tuple(dict.fromkeys(RACE_ENDPOINTS + QUALIFYING_ENDPOINTS))
# Columnas que OpenF1 devuelve con tipos distintos según la sesión (número o texto como
# «+1 LAP»; en clasificación, una lista Q1/Q2/Q3): siempre como texto JSON.
JSON_COLUMNS = {"session_result": ("duration", "gap_to_leader")}


class NotFound(Exception):
    """OpenF1 no tiene datos para la consulta (404)."""


class OpenF1Error(Exception):
    """OpenF1 no respondió bien tras los reintentos (red, 5xx u otro error)."""


class OutOfTime(OpenF1Error):
    """Se agotó el tiempo máximo de la ejecución (`Client.deadline`)."""


class Client:
    """Cliente HTTP de OpenF1 que respeta sus límites de peticiones."""

    def __init__(
        self,
        session: requests.Session | None = None,
        min_interval: float = MIN_INTERVAL_S,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.min_interval = min_interval
        self.sleep = sleep
        self.clock = clock
        self._last: float | None = None
        self.requests = 0
        # Instante (en `clock`) a partir del cual no se hace ni se espera nada más: ni un 429
        # sostenido ni los reintentos pueden pasar del tiempo máximo de la ejecución.
        self.deadline: float | None = None

    def _check_deadline(self, endpoint: str, params: dict) -> None:
        if self.deadline is not None and self.clock() >= self.deadline:
            raise OutOfTime(f"{endpoint} {params}: sin tiempo en esta ejecución")

    def _pause(self, seconds: float, endpoint: str, params: dict) -> None:
        if self.deadline is not None:
            seconds = min(seconds, max(self.deadline - self.clock(), 0))
        self.sleep(seconds)
        self._check_deadline(endpoint, params)

    def _wait_turn(self) -> None:
        if self._last is not None:
            remaining = self.min_interval - (self.clock() - self._last)
            if remaining > 0:
                self.sleep(remaining)
        self._last = self.clock()

    def get(self, endpoint: str, **params) -> list[dict]:
        """Filas de `endpoint` para `params`. Lanza NotFound (404) u OpenF1Error."""
        last_error = ""
        attempt = 0
        rate_limited = 0
        while attempt < MAX_ATTEMPTS:
            self._check_deadline(endpoint, params)
            self._wait_turn()
            self.requests += 1
            try:
                response = self.session.get(BASE_URL + endpoint, params=params, timeout=TIMEOUT_S)
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code == 200:
                    try:
                        data = response.json()
                    except ValueError as exc:
                        raise OpenF1Error(f"{endpoint} {params}: JSON no válido ({exc})") from exc
                    if not isinstance(data, list):
                        raise OpenF1Error(f"{endpoint} {params}: respuesta inesperada")
                    return data
                if response.status_code == 404:
                    raise NotFound(f"{endpoint} {params}")
                if response.status_code == 429:
                    # No cuenta como intento (es el límite de peticiones, no un fallo), pero un 429
                    # sostenido no puede bloquear la ejecución: tiene su propio tope.
                    rate_limited += 1
                    if rate_limited >= MAX_RATE_LIMITED:
                        raise OpenF1Error(f"{endpoint} {params}: {rate_limited} respuestas 429")
                    wait = _retry_after(response.headers.get("retry-after"))
                    log.info("OpenF1 pide esperar %.0f s (429)", wait)
                    self._pause(wait, endpoint, params)
                    continue
                last_error = f"HTTP {response.status_code}"
                if response.status_code < 500:
                    # 401/403: OpenF1 restringe el acceso sin cuenta durante las sesiones en
                    # directo; el resto de 4xx no se arregla reintentando. Ninguno es un hueco
                    # conocido: queda pendiente para la siguiente ejecución.
                    break
            attempt += 1
            if attempt < MAX_ATTEMPTS:
                self._pause(BACKOFF_S * 2 ** (attempt - 1), endpoint, params)
        raise OpenF1Error(f"{endpoint} {params}: {last_error}")


def _retry_after(value: str | None, default: float = 5.0, maximum: float = 60.0) -> float:
    """Segundos de `retry-after` (número o fecha HTTP), entre 1 s y `maximum`."""
    if not value:
        return default
    try:
        seconds = float(value)
    except ValueError:
        try:
            seconds = (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()
        except (TypeError, ValueError):
            return default
    return min(max(seconds, 1.0), maximum)


def _is_missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def to_frame(endpoint: str, rows: list[dict]) -> pd.DataFrame:
    """Filas de OpenF1 como DataFrame con tipos estables entre sesiones.

    Las listas (segmentos de las vueltas, tiempos Q1/Q2/Q3), las columnas con tipos mezclados y
    las de `JSON_COLUMNS` se guardan como texto JSON: un Parquet por sesión debe poder leerse
    junto a los demás (`union_by_name`) aunque una sesión traiga un tipo distinto.
    """
    df = pd.DataFrame.from_records(rows)
    forced = JSON_COLUMNS.get(endpoint, ())
    for column in df.columns:
        values = [v for v in df[column] if not _is_missing(v)]
        kinds = {type(v) for v in values}
        numeric = kinds <= {int, float}
        if (
            column in forced
            or any(k in (list, dict) for k in kinds)
            or (len(kinds) > 1 and not numeric)
        ):
            df[column] = [None if _is_missing(v) else json.dumps(v) for v in df[column]]
    return df


def session_path(endpoint: str, season: int, session_key: int, root: Path | None = None) -> Path:
    root = root or OUT_DIR
    return root / endpoint / f"season={season}" / f"session={session_key}.parquet"


def calendar_path(kind: str, season: int, root: Path | None = None) -> Path:
    return (root or OUT_DIR) / kind / f"season={season}.parquet"


def read_gaps(root: Path | None = None) -> dict:
    path = (root or OUT_DIR) / GAPS_FILE
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_gaps(gaps: dict, root: Path | None = None) -> None:
    root = root or OUT_DIR
    root.mkdir(parents=True, exist_ok=True)
    path = root / GAPS_FILE
    tmp = path.with_suffix(".tmp")
    payload = {key: gaps[key] for key in sorted(gaps, key=int)}
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _parse_date(value) -> datetime | None:
    if _is_missing(value):
        return None
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def is_known_gap(entry: dict | None, session_end: datetime | None) -> bool:
    """Un 404 es un hueco conocido si se comprobó pasado `GAP_CONFIRM_AFTER` tras la sesión."""
    if not entry:
        return False
    checked = _parse_date(entry.get("checked_at"))
    if checked is None or session_end is None:
        return False
    return checked >= session_end + GAP_CONFIRM_AFTER


@dataclass
class LoadSummary:
    requests: int = 0
    # Ficheros escritos en esta ejecución («2025 Race 9939: laps»).
    loaded: list[str] = field(default_factory=list)
    # 404 nuevos o reconfirmados en esta ejecución.
    gaps: list[str] = field(default_factory=list)
    # Errores (red, 5xx): se reintentan en la siguiente ejecución.
    failed: list[str] = field(default_factory=list)
    # Temporadas cuyo calendario no se pudo leer.
    calendar_failed: list[int] = field(default_factory=list)
    # Se agotó el tiempo máximo de la ejecución: lo pendiente queda para la siguiente.
    out_of_time: bool = False

    @property
    def changed(self) -> bool:
        return bool(self.loaded or self.gaps)


def _write_calendar_if_changed(df: pd.DataFrame, path: Path) -> bool:
    if path.exists():
        try:
            current = pd.read_parquet(path)
            if current.equals(df.reset_index(drop=True)):
                return False
        except Exception:  # fichero dañado: se reescribe
            pass
    write_parquet(df, path)
    return True


def _label(session: dict) -> str:
    return (
        f"{session.get('year')} {session.get('location') or session.get('circuit_short_name')} "
        f"{session.get('session_name')} ({session.get('session_key')})"
    )


def load_season(
    season: int,
    client: Client,
    summary: LoadSummary,
    gaps: dict,
    root: Path | None = None,
    now: datetime | None = None,
    out_of_time: Callable[[], bool] = lambda: False,
) -> None:
    """Calendario y endpoints pendientes de las sesiones terminadas de `season`."""
    root = root or OUT_DIR
    now = now or datetime.now(UTC)
    try:
        sessions = client.get("sessions", year=season)
    except NotFound:
        log.info("OpenF1 no tiene sesiones de %s", season)
        return
    except OpenF1Error as exc:
        log.error("No se pudo leer el calendario de %s: %s", season, exc)
        summary.calendar_failed.append(season)
        summary.out_of_time = summary.out_of_time or isinstance(exc, OutOfTime)
        return
    if _write_calendar_if_changed(
        to_frame("sessions", sessions), calendar_path("sessions", season, root)
    ):
        summary.loaded.append(f"{season} sessions")
    try:
        meetings = client.get("meetings", year=season)
        if _write_calendar_if_changed(
            to_frame("meetings", meetings), calendar_path("meetings", season, root)
        ):
            summary.loaded.append(f"{season} meetings")
    except (NotFound, OpenF1Error) as exc:  # solo descriptivo: no impide cargar las sesiones
        log.warning("No se pudieron leer los meetings de %s: %s", season, exc)

    for session in sorted(sessions, key=lambda s: str(s.get("date_start"))):
        endpoints = ENDPOINTS_BY_SESSION.get(session.get("session_name"))
        end = _parse_date(session.get("date_end"))
        if (
            not endpoints
            or session.get("is_cancelled")
            or end is None
            or end + SESSION_MARGIN > now
        ):
            continue
        key = int(session["session_key"])
        session_gaps = gaps.get(str(key), {})
        for endpoint in endpoints:
            path = session_path(endpoint, season, key, root)
            if path.exists() or is_known_gap(session_gaps.get(endpoint), end):
                continue
            label = f"{_label(session)}: {endpoint}"
            if summary.out_of_time or out_of_time():
                summary.out_of_time = True
                summary.failed.append(f"{label} (sin tiempo en esta ejecución)")
                continue
            try:
                rows = client.get(endpoint, session_key=key)
                if not rows:
                    # Un 200 con la lista vacía es «sin datos», como el 404: un Parquet vacío
                    # quedaría como cargado para siempre.
                    raise NotFound(f"{endpoint} session_key={key}: lista vacía")
            except OutOfTime:
                summary.out_of_time = True
                summary.failed.append(f"{label} (sin tiempo en esta ejecución)")
                continue
            except NotFound:
                session_gaps[endpoint] = {
                    "status": 404,
                    "checked_at": now.isoformat(timespec="seconds"),
                    "session_end": end.isoformat(timespec="seconds"),
                }
                gaps[str(key)] = session_gaps
                summary.gaps.append(label)
                continue
            except OpenF1Error as exc:
                log.error("OpenF1: %s", exc)
                summary.failed.append(label)
                continue
            write_parquet(to_frame(endpoint, rows), path)
            if session_gaps.pop(endpoint, None) is not None and not session_gaps:
                gaps.pop(str(key), None)
            summary.loaded.append(label)
        # Tras cada sesión: si la ejecución se corta, lo cargado y los huecos quedan anotados.
        write_gaps(gaps, root)


def default_seasons(today: datetime | None = None) -> list[int]:
    today = today or datetime.now(UTC)
    return list(range(OPENF1_FIRST_SEASON, today.year + 1))


def load(
    seasons: list[int] | None = None,
    client: Client | None = None,
    root: Path | None = None,
    now: datetime | None = None,
    max_minutes: float | None = None,
) -> LoadSummary:
    """Carga las temporadas. Con `max_minutes`, deja de pedir sesiones al agotar ese tiempo (lo
    cargado se conserva y lo pendiente se lista): el pipeline no debe morir por su límite de
    tiempo antes de guardar la copia, o el atraso no avanzaría nunca."""
    root = root or OUT_DIR
    seasons = seasons or default_seasons(now)
    if any(season < OPENF1_FIRST_SEASON for season in seasons):
        raise ValueError(f"OpenF1 solo tiene datos desde {OPENF1_FIRST_SEASON}")
    client = client or Client()
    started = client.clock()
    if max_minutes is not None:
        client.deadline = started + max_minutes * 60

    def out_of_time() -> bool:
        return max_minutes is not None and client.clock() - started > max_minutes * 60

    summary = LoadSummary()
    gaps = read_gaps(root)
    for season in seasons:
        load_season(season, client, summary, gaps, root, now, out_of_time)
    summary.requests = client.requests
    return summary


def known_gaps(root: Path | None = None) -> list[str]:
    """Huecos conocidos («2023 session 7953: pit»), para el manifiesto y el resumen."""
    gaps = read_gaps(root)
    return [
        f"session {key}: {endpoint}"
        for key, endpoints in sorted(gaps.items(), key=lambda item: int(item[0]))
        for endpoint in sorted(endpoints)
    ]


def summary_markdown(summary: LoadSummary) -> str:
    """Resumen para `$GITHUB_STEP_SUMMARY`: lo que falta y se reintentará."""
    lines = [
        f"### OpenF1: {len(summary.loaded)} ficheros nuevos, {summary.requests} peticiones",
    ]
    if summary.out_of_time:
        lines.append("")
        lines.append("Se agotó el tiempo de esta ejecución: lo pendiente se carga en la siguiente.")
    if summary.failed or summary.calendar_failed:
        lines.append("")
        lines.append("Faltan (se reintentan en la siguiente ejecución):")
        lines += [f"- calendario de {season}" for season in summary.calendar_failed]
        lines += [f"- {label}" for label in summary.failed]
    if summary.gaps:
        lines.append("")
        lines.append("Sin datos en OpenF1 (404; se anotan como huecos):")
        lines += [f"- {label}" for label in summary.gaps]
    return "\n".join(lines) + "\n"
