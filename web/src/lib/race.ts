import "server-only";

import { notFound } from "next/navigation";
import { cache } from "react";

import { apiGet, apiGetRequired, type Schemas } from "@/lib/api/client";

/** Carrera por id (404 si no existe). Memorizada por petición: la usan el layout y cada pestaña. */
export const getRace = cache(async (raceId: string) => {
  if (!/^\d+$/.test(raceId)) notFound();
  const race = await apiGet<Schemas["RaceDetail"]>(`/races/${raceId}`);
  if (!race) notFound();
  return race;
});

export const getResults = cache((raceId: string, session: "race" | "sprint" = "race") =>
  apiGetRequired<Schemas["RaceResult"][]>(`/races/${raceId}/results`, { session }),
);

/** Nombre y orden final de cada piloto (las pestañas de vueltas solo traen identificadores). */
export async function getDriverNames(raceId: string) {
  const results = await getResults(raceId);
  return {
    results,
    names: new Map(results.map((r) => [r.driver_id, r.driver_name])),
    order: new Map(results.map((r, i) => [r.driver_id, i])),
  };
}
