"""Esquemas de respuesta. Los tiempos van en milisegundos y los identificadores son los de F1DB."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class Ref(BaseModel):
    id: str
    name: str


class RaceRef(BaseModel):
    season: int
    round: int
    name: str


class DataInfo(BaseModel):
    version: str = Field(description="Cambia con cada publicación de datos (se usa en las ETag)")
    generated_at: str | None = Field(description="Fecha de generación de los datos (pipeline)")
    f1db_release: str | None
    release_tag: str | None = Field(
        default=None, description="Release fechada e inmutable de la que proceden los datos"
    )
    last_completed_race: RaceRef | None = Field(
        description="Última carrera con resultados, consultada en la base de datos"
    )


class RefreshInfo(BaseModel):
    source: Literal["release", "copy", "file"] = Field(
        description=(
            "release: la versión publicada; copy: una copia anterior porque GitHub no respondía; "
            "file: un fichero local"
        )
    )
    started_at: str = Field(description="Arranque del proceso (UTC)")
    last_check_at: str | None = Field(description="Última comprobación de datos nuevos (UTC)")
    last_success_at: str | None = Field(description="Última comprobación correcta (UTC)")
    last_error: str | None = Field(description="Error de la última comprobación, si falló")


class Health(BaseModel):
    status: Literal["ok", "degraded"] = Field(
        description="degraded: se sirven datos, pero no se pudo comprobar la versión publicada"
    )
    data: DataInfo
    refresh: RefreshInfo


class QualityCheck(BaseModel):
    check_id: str
    description: str
    compared: int
    matched: int
    match_pct: float | None
    min_match_pct: float | None
    status: str = Field(description="PASS, FAIL, INFO o NO_DATA")


# ---- Temporadas -------------------------------------------------------------------------------


class SeasonSummary(BaseModel):
    season: int
    races: int
    completed_races: int
    drivers_champion: Ref | None
    constructors_champion: Ref | None


class RaceSummary(BaseModel):
    race_id: int
    season: int
    round: int
    date: date
    grand_prix_id: str
    grand_prix_name: str
    official_name: str
    circuit_id: str
    circuit_name: str
    country: str
    country_alpha2: str | None
    has_sprint: bool
    is_completed: bool
    winner: Ref | None


class SeasonDetail(BaseModel):
    season: int
    races: list[RaceSummary]


class DriverStanding(BaseModel):
    position: int | None
    position_text: str
    driver_id: str
    name: str
    nationality_alpha2: str | None
    constructors: list[str]
    points: float
    wins: int
    is_champion: bool


class ConstructorStanding(BaseModel):
    position: int | None
    position_text: str
    constructor_id: str
    name: str
    country_alpha2: str | None
    engine: str | None
    points: float
    wins: int
    is_champion: bool


class StandingsProgression(BaseModel):
    round: int
    race_id: int
    grand_prix_name: str
    id: str
    name: str
    points: float
    position: int | None


# ---- Carreras ---------------------------------------------------------------------------------


def car_number_field():
    """Dorsal en las filas de vueltas (campo nuevo: opcional para no romper clientes anteriores)."""
    return Field(
        default=None,
        description=(
            "Dorsal del coche. En los años 50-60 un piloto pudo conducir dos coches en la misma "
            "carrera: sus vueltas se distinguen por el dorsal"
        ),
    )


class RaceDetail(RaceSummary):
    race_time_utc: str | None
    laps: int | None
    distance_km: float | None
    circuit_type: str | None
    direction: str | None
    course_length_km: float | None
    turns: int | None
    latitude: float | None
    longitude: float | None
    is_season_final_race: bool
    has_sprint_qualifying: bool = Field(
        description=(
            "Hay clasificación sprint propia (desde 2023). En 2021-2022 la parrilla del sprint "
            "salía de la clasificación del viernes"
        )
    )


class RaceResult(BaseModel):
    position: int | None
    position_text: str
    driver_number: str | None
    driver_id: str
    driver_name: str
    constructor_id: str
    constructor_name: str
    grid_position: int | None
    grid_position_text: str | None
    laps: int | None
    time_ms: int | None
    gap_ms: int | None
    gap_laps: int | None
    points: float
    positions_gained: int | None
    pit_stops: int | None
    reason_retired: str | None
    is_fastest_lap: bool
    corrected_fields: list[str] = Field(
        description="Campos corregidos respecto a F1DB con evidencia documentada"
    )
    driver_code: str | None = Field(
        default=None,
        description=(
            "Código único en la carrera, normalmente de 3 letras: la abreviatura de F1DB y, si dos "
            "pilotos que tomaron la salida la comparten, la inicial del nombre y dos letras de la "
            "abreviatura (MSC y RSC; TMO y FMO). En los choques restantes, 4 letras o un número"
        ),
    )


class QualifyingResult(BaseModel):
    position: int | None
    position_text: str
    driver_number: str | None
    driver_id: str
    driver_name: str
    constructor_id: str
    constructor_name: str
    q1_ms: int | None
    q2_ms: int | None
    q3_ms: int | None
    best_time_ms: int | None
    gap_to_pole_pct: float | None


class Lap(BaseModel):
    driver_id: str
    driver_number: str | None = car_number_field()
    lap: int
    position: int | None
    lap_time_ms: int | None
    gap_to_leader_ms: int | None
    sector_1_ms: int | None
    sector_2_ms: int | None
    sector_3_ms: int | None
    compound: str | None = Field(description="Compuesto relativo si se conoce; si no, el publicado")
    compound_pirelli: str | None
    tyre_age_laps: int | None
    is_pit_in_lap: bool | None
    is_pit_out_lap: bool | None
    is_yellow_flag: bool | None
    is_safety_car: bool | None
    is_virtual_safety_car: bool | None
    is_red_flag: bool | None
    source: str
    validation_status: str


class Stint(BaseModel):
    driver_id: str
    driver_number: str | None = car_number_field()
    stint: int
    compound: str | None
    start_lap: int
    end_lap: int
    laps: int
    tyre_age_at_start: int | None


class RaceControlMessage(BaseModel):
    seq: int = Field(description="Orden del mensaje en la carrera")
    source: Literal["fastf1", "openf1"] = Field(
        description="fastf1 (preferente, 2018+) u openf1 (2023+, CC BY-NC-SA 4.0)"
    )
    utc: datetime | None = Field(description="Hora UTC del mensaje")
    session_time_ms: int | None = Field(
        description="Tiempo de sesión en que se publicó (solo FastF1; comparable con las vueltas)"
    )
    lap: int | None = Field(description="Vuelta del líder cuando se publicó")
    category: str | None = Field(
        description="Flag, SafetyCar, Drs, CarEvent, SessionStatus u Other"
    )
    flag: str | None = Field(description="GREEN, YELLOW, DOUBLE YELLOW, RED, BLUE, CHEQUERED...")
    scope: str | None = Field(description="Track, Sector o Driver")
    sector: int | None
    driver_number: int | None = Field(description="Dorsal del coche afectado")
    driver_id: str | None = Field(description="Piloto afectado (por su dorsal en la carrera)")
    message: str
    event: str | None = Field(
        description=(
            "Estado de pista: red_flag, safety_car_deployed, safety_car_in, vsc_deployed, "
            "vsc_ending, track_clear o chequered_flag"
        )
    )


class WeatherSample(BaseModel):
    seq: int = Field(description="Orden de la muestra en la carrera (una por minuto)")
    source: Literal["fastf1", "openf1"] = Field(
        description="fastf1 (preferente, 2018+) u openf1 (2023+, CC BY-NC-SA 4.0)"
    )
    utc: datetime | None = Field(
        description="Hora UTC (en FastF1, estimada a partir del tiempo de sesión, ~1 s)"
    )
    session_time_ms: int | None = Field(description="Tiempo de sesión (solo FastF1)")
    air_temperature_c: float | None
    track_temperature_c: float | None
    humidity_pct: float | None
    pressure_mbar: float | None
    is_raining: bool | None
    wind_direction_deg: int | None
    wind_speed_ms: float | None = Field(description="Velocidad del viento en m/s")


class PitStop(BaseModel):
    driver_id: str
    driver_name: str
    constructor_id: str | None
    stop: int
    lap: int
    duration_ms: int | None


class PitLanePass(BaseModel):
    driver_id: str
    driver_number: str | None = car_number_field()
    lap: int
    pass_type: str = Field(
        description="pit_stop, safety_car, red_flag, retirement, penalty_or_other o unclassified"
    )
    stop: int | None


class TelemetryLap(BaseModel):
    """Vuelta más rápida de clasificación, muestreada cada 10 m (listas paralelas)."""

    driver_id: str
    driver_code: str | None
    lap_time_ms: int | None
    tyre_compound: str | None
    distance_m: list[float]
    speed_kmh: list[float | None]
    throttle_pct: list[float | None]
    is_braking: list[bool | None]
    gear: list[int | None]
    x: list[float | None]
    y: list[float | None]


# ---- Pilotos y constructores ------------------------------------------------------------------


class DriverSummary(BaseModel):
    driver_id: str
    name: str
    nationality_alpha2: str | None
    first_season: int | None
    last_season: int | None
    race_starts: int
    wins: int
    podiums: int
    championships: int


class DriverDetail(DriverSummary):
    full_name: str | None
    abbreviation: str | None
    permanent_number: str | None
    date_of_birth: date | None
    date_of_death: date | None
    place_of_birth: str | None
    nationality: str | None
    race_entries: int
    pole_positions: int
    fastest_laps: int
    grand_slams: int
    points: float
    best_race_result: int | None
    best_championship_position: int | None
    laps_completed: int | None
    win_rate_pct: float | None
    podium_rate_pct: float | None


class DriverSeason(BaseModel):
    season: int
    constructor_id: str | None
    constructor_name: str | None
    championship_position: int | None
    championship_position_text: str | None
    points: float | None
    is_champion: bool
    races: int
    wins: int
    podiums: int
    pole_positions: int
    fastest_laps: int
    best_result: int | None


class TeammateComparison(BaseModel):
    season: int
    constructor_id: str
    constructor_name: str
    teammate_id: str
    teammate_name: str
    races_together: int
    race_ahead: int
    race_ahead_pct: float | None
    qualifyings_together: int
    quali_ahead: int
    quali_ahead_pct: float | None
    points: float | None
    teammate_points: float | None


class DriverRaceResult(BaseModel):
    race_id: int
    season: int
    round: int
    grand_prix_name: str
    session: str
    constructor_id: str
    position: int | None
    position_text: str
    grid_position: int | None
    points: float


class ConstructorSummary(BaseModel):
    constructor_id: str
    name: str
    country_alpha2: str | None
    first_season: int | None
    last_season: int | None
    race_entries: int
    wins: int
    championships: int


class ConstructorDetail(ConstructorSummary):
    full_name: str | None
    country: str | None
    podiums: int
    one_two_finishes: int
    pole_positions: int
    fastest_laps: int
    race_points: float
    best_championship_position: int | None


class ConstructorSeason(BaseModel):
    season: int
    championship_position: int | None
    championship_position_text: str | None
    points: float | None
    is_champion: bool
    wins: int
    drivers: list[Ref]


# ---- Récords y circuitos ----------------------------------------------------------------------


class RecordEntry(BaseModel):
    rank: int
    id: str
    name: str
    country_alpha2: str | None
    value: float


class ConstructorRanking(BaseModel):
    rank: int
    id: str
    name: str
    country: str | None
    country_alpha2: str | None
    entries: int
    wins: int
    podiums: int
    pole_positions: int
    fastest_laps: int
    points: float
    championships: int


class DriverRanking(ConstructorRanking):
    starts: int


class Circuit(BaseModel):
    circuit_id: str
    name: str
    place: str | None
    country: str
    country_alpha2: str | None
    latitude: float | None
    longitude: float | None
    races: int
    first_season: int
    last_season: int
    grands_prix: list[str]
