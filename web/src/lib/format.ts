/** Formatos de cronometraje y números. Sin dependencias de servidor: los usan también los gráficos. */

export function lapTime(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  const minutes = Math.floor(ms / 60000);
  const seconds = (ms % 60000) / 1000;
  return minutes > 0 ? `${minutes}:${seconds.toFixed(3).padStart(6, "0")}` : seconds.toFixed(3);
}

export function raceTime(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  const hours = Math.floor(ms / 3600000);
  const rest = lapTime(ms % 3600000);
  return hours > 0 ? `${hours}:${rest.padStart(9, "0")}` : rest;
}

export function gap(ms: number | null | undefined, laps?: number | null, lapsLabel = "v."): string {
  if (laps) return `+${laps} ${lapsLabel}`;
  if (ms === null || ms === undefined) return "";
  return `+${(ms / 1000).toFixed(3)}`;
}

export function number(value: number | null | undefined, locale: string, digits = 0): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat(locale, {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  }).format(value);
}

export function date(value: string | null | undefined, locale: string): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", year: "numeric" }).format(
    new Date(`${value}T12:00:00Z`),
  );
}

/**
 * Código de piloto de 3 letras a partir del identificador («max-verstappen» -> «VER»). Solo es el
 * último recurso: puede repetirse en una carrera (los dos Schumacher darían «SCH»), así que los
 * gráficos usan el `driver_code` de la API, único en cada carrera (ver `lib/cars.ts`).
 */
export function driverCode(driverId: string): string {
  const parts = driverId.split("-");
  const last = parts[parts.length - 1] === "jr" ? parts[parts.length - 2] : parts[parts.length - 1];
  return last.slice(0, 3).toUpperCase();
}
