"""Códigos de piloto únicos dentro de una carrera (etiquetas de los gráficos y tablas de la web)."""

import unicodedata
from collections import defaultdict


def _initial(first_name: str | None, driver_id: str) -> str:
    """Inicial del nombre sin tildes («Érik» -> «E»); si falta, la del identificador."""
    text = unicodedata.normalize("NFKD", first_name or driver_id)
    letters = [c for c in text if c.isalpha()]
    return letters[0].upper() if letters else "X"


def _fallback(driver_id: str) -> str:
    """Tres primeras letras del apellido del identificador («max-verstappen» -> «VER»)."""
    parts = driver_id.split("-")
    last = parts[-2] if parts[-1] == "jr" and len(parts) > 1 else parts[-1]
    return last[:3].upper()


def race_driver_codes(
    drivers: list[tuple[str, str | None, str | None, bool]],
) -> dict[str, str]:
    """Código de cada piloto de una carrera, sin repetidos.

    `drivers` son tuplas (driver_id, abreviatura de F1DB, nombre, tomó la salida). Se usa la
    abreviatura de F1DB (MSC, RSC, DLR...). Si dos pilotos de la carrera la comparten:
    - si solo uno tomó la salida, él la conserva (es el único que sale en los gráficos de vueltas;
      Berger sigue siendo BER aunque otro BER no se clasificara);
    - los demás siguen la convención de la F1 para los hermanos Schumacher: inicial del nombre y
      dos primeras letras de la abreviatura (Tiago Monteiro TMO y Franck Montagny FMO); si aún
      choca, inicial y abreviatura completa, y como último recurso la abreviatura con un número.
    El resultado no depende del orden de entrada: los empates se resuelven por identificador.
    """
    groups: dict[str, list[tuple[str, str | None, bool]]] = defaultdict(list)
    for driver_id, abbreviation, first_name, started in drivers:
        groups[(abbreviation or _fallback(driver_id)).upper()].append(
            (driver_id, first_name, started)
        )
    codes: dict[str, str] = {}
    pending: list[tuple[str, str, str | None]] = []
    for code, members in groups.items():
        starters = [member for member in members if member[2]]
        keeper = members[0] if len(members) == 1 else starters[0] if len(starters) == 1 else None
        for driver_id, first_name, _ in members:
            if keeper and driver_id == keeper[0]:
                codes[driver_id] = code
            else:
                pending.append((driver_id, code, first_name))
    taken = set(codes.values())
    for driver_id, code, first_name in sorted(pending):
        initial = _initial(first_name, driver_id)
        candidates = [initial + code[:2], initial + code]
        chosen = next((c for c in candidates if c not in taken), None)
        suffix = 2
        while chosen is None:
            if f"{code}{suffix}" not in taken:
                chosen = f"{code}{suffix}"
            suffix += 1
        codes[driver_id] = chosen
        taken.add(chosen)
    return codes
