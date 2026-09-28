import "server-only";

import type { components } from "./schema";

export type Schemas = components["schemas"];

const API_URL = process.env.F1_API_URL ?? "http://127.0.0.1:8000";

/** Los datos cambian como mucho una vez por semana (pipeline de los lunes). */
const REVALIDATE_SECONDS = 3600;

export class ApiError extends Error {
  constructor(
    public status: number,
    public path: string,
  ) {
    super(`La API respondió ${status} en ${path}`);
  }
}

type Query = Record<string, string | number | undefined | null>;

function buildUrl(path: string, query?: Query): string {
  const url = new URL(path, API_URL);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
  }
  return url.toString();
}

/** GET a la API con caché de Next (ISR). Devuelve null si el recurso no existe (404). */
export async function apiGet<T>(path: string, query?: Query): Promise<T | null> {
  const response = await fetch(buildUrl(path, query), {
    next: { revalidate: REVALIDATE_SECONDS },
    headers: { Accept: "application/json" },
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new ApiError(response.status, path);
  return (await response.json()) as T;
}

/** Como apiGet, pero el recurso debe existir. */
export async function apiGetRequired<T>(path: string, query?: Query): Promise<T> {
  const data = await apiGet<T>(path, query);
  if (data === null) throw new ApiError(404, path);
  return data;
}
