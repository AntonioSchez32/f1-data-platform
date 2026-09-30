/**
 * Coches de una carrera: cada serie de los gráficos es un piloto con un dorsal. En los años 50-60 un
 * piloto podía conducir dos coches en la misma carrera (Behra en Bélgica 1955 llevó el #20 y el
 * #24): agrupar solo por piloto mezclaba las vueltas de los dos. Sin dependencias de servidor.
 */
import type { Schemas } from "@/lib/api/client";
import { driverCode } from "@/lib/format";

/** Fila con piloto y, desde la API de C1, dorsal (opcional: la API anterior no lo envía). */
export type CarRow = { driver_id: string; driver_number?: string | null };

export type Car = {
  /** Clave de la serie: el piloto o, si llevó dos coches, «piloto_dorsal». */
  key: string;
  driverId: string;
  number: string | null;
  /** Nombre del piloto, con el dorsal si llevó más de un coche («Jean Behra (#24)»). */
  name: string;
  /** Código único en la carrera (API) o deducido del identificador, con el dorsal si hace falta. */
  code: string;
  /** Resultado de ese coche (parrilla, llegada), si existe. */
  result: Schemas["RaceResult"] | undefined;
  /** Orden del resultado oficial (los coches sin resultado, al final). */
  order: number;
};

/**
 * Coches presentes en `rows` (vueltas, tramos o pasos por boxes), con nombre, código y resultado.
 * Las claves solo llevan dorsal cuando el piloto aparece con más de uno, así que con la API
 * anterior (sin dorsal) todo sigue agrupándose por piloto.
 */
export function raceCars(rows: CarRow[], results: Schemas["RaceResult"][]): Map<string, Car> {
  const numbers = new Map<string, Set<string | null>>();
  for (const row of rows) {
    const set = numbers.get(row.driver_id) ?? new Set();
    set.add(row.driver_number ?? null);
    numbers.set(row.driver_id, set);
  }
  const cars = new Map<string, Car>();
  for (const [driverId, set] of numbers) {
    const shared = set.size > 1;
    for (const number of set) {
      const index = results.findIndex(
        (r) => r.driver_id === driverId && (number === null || r.driver_number === number),
      );
      // Sin dorsal (API anterior) o sin resultado con ese dorsal, el del piloto; pero no si llevó
      // dos coches: se le prestaría la parrilla y la llegada del otro.
      const fallback = index === -1 && !shared ? results.findIndex((r) => r.driver_id === driverId) : index;
      const result = fallback === -1 ? undefined : results[fallback];
      // El nombre y el código son del piloto: valen los de cualquiera de sus resultados.
      const driver = result ?? results.find((r) => r.driver_id === driverId);
      const name = driver?.driver_name ?? driverId;
      const code = driver?.driver_code ?? driverCode(driverId);
      const key = carKey({ driver_id: driverId, driver_number: number }, shared);
      cars.set(key, {
        key,
        driverId,
        number,
        name: shared && number ? `${name} (#${number})` : name,
        code: shared && number ? `${code} #${number}` : code,
        result,
        order: fallback === -1 ? Number.MAX_SAFE_INTEGER : fallback,
      });
    }
  }
  return new Map([...cars].sort(([, a], [, b]) => a.order - b.order || a.key.localeCompare(b.key)));
}

function carKey(row: CarRow, shared: boolean): string {
  return shared && row.driver_number ? `${row.driver_id}_${row.driver_number}` : row.driver_id;
}

/** Coche de una fila (vuelta, tramo o paso por boxes). */
export function carOf(row: CarRow, cars: Map<string, Car>): Car | undefined {
  return cars.get(carKey(row, true)) ?? cars.get(row.driver_id);
}

/** Agrupa las filas por coche, en el orden de `cars` (el del resultado oficial). */
export function groupByCar<T extends CarRow>(rows: T[], cars: Map<string, Car>): [Car, T[]][] {
  const groups = Map.groupBy(rows, (row) => carOf(row, cars)?.key ?? row.driver_id);
  return [...cars.values()].filter((car) => groups.has(car.key)).map((car) => [car, groups.get(car.key)!]);
}
