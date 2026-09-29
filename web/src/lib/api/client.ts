import "server-only";

import { cache } from "react";

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

/**
 * El plan gratuito de Render duerme la API y el arranque en frío no está acotado (contenedor,
 * descarga de los datos y apertura de DuckDB). El primer intento espera lo suficiente para que
 * despierte; el segundo, más corto, solo se hace ante un error de red o un 502/503/504. Así una API
 * caída no deja la página colgada hasta agotar el límite de la función.
 */
const TIMEOUTS_MS = [60_000, 20_000];
const RETRY_DELAY_MS = 1_000;
const RETRYABLE_STATUS = new Set([502, 503, 504]);

async function fetchWithRetry(url: string, init: RequestInit): Promise<Response> {
  for (let attempt = 0; ; attempt++) {
    const isLast = attempt >= TIMEOUTS_MS.length - 1;
    try {
      const response = await fetch(url, { ...init, signal: AbortSignal.timeout(TIMEOUTS_MS[attempt]) });
      if (isLast || !RETRYABLE_STATUS.has(response.status)) return response;
      // Se libera la conexión antes de reintentar.
      await response.body?.cancel();
    } catch (error) {
      if (isLast) throw error;
    }
    await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
  }
}

/**
 * Cuerpo de la respuesta, memorizado durante la petición con la URL como clave. Pasar `signal` a
 * `fetch` desactiva la deduplicación de Next, así que se hace aquí: generateMetadata y la página
 * piden lo mismo una sola vez. Se guarda el texto y no el objeto para que cada llamada reciba su
 * propia copia (algunas páginas ordenan los datos en el sitio).
 */
const fetchBody = cache(async (url: string): Promise<{ status: number; text: string }> => {
  const response = await fetchWithRetry(url, {
    next: { revalidate: REVALIDATE_SECONDS },
    headers: { Accept: "application/json" },
  });
  if (response.status === 404) {
    await response.body?.cancel();
    return { status: 404, text: "" };
  }
  if (!response.ok) throw new ApiError(response.status, new URL(url).pathname);
  return { status: response.status, text: await response.text() };
});

/** GET a la API con caché de Next (ISR). Devuelve null si el recurso no existe (404). */
export async function apiGet<T>(path: string, query?: Query): Promise<T | null> {
  const { status, text } = await fetchBody(buildUrl(path, query));
  return status === 404 ? null : (JSON.parse(text) as T);
}

/** Como apiGet, pero el recurso debe existir. */
export async function apiGetRequired<T>(path: string, query?: Query): Promise<T> {
  const data = await apiGet<T>(path, query);
  if (data === null) throw new ApiError(404, path);
  return data;
}
