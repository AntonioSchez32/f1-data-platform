import { geoEqualEarth, geoPath } from "d3-geo";
import type { FeatureCollection } from "geojson";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import world from "world-atlas/countries-110m.json";

const WIDTH = 960;
const HEIGHT = 470;

const topology = world as unknown as Topology<{ countries: GeometryCollection }>;
const countries = feature(topology, topology.objects.countries) as FeatureCollection;
const projection = geoEqualEarth().fitExtent(
  [
    [8, 8],
    [WIDTH - 8, HEIGHT - 8],
  ],
  countries,
);
const path = geoPath(projection);
// Los contornos no dependen de los datos: se calculan una vez.
const countryPaths = countries.features.map((f) => path(f) ?? "");

export type MapPoint = { id: string; label: string; latitude: number; longitude: number; races: number };

/** Mapa mundial de eventos dibujado en el servidor (SVG estático, sin JavaScript). */
export function WorldMap({
  points: input,
  title,
  description,
}: {
  points: MapPoint[];
  title: string;
  description: string;
}) {
  const maxRaces = Math.max(1, ...input.map((p) => p.races));
  const points = input
    .map((point) => ({ point, xy: projection([point.longitude, point.latitude]) }))
    .filter((p): p is { point: MapPoint; xy: [number, number] } => p.xy !== null)
    // Los grandes primero, para que los pequeños queden encima y se vean.
    .sort((a, b) => b.point.races - a.point.races);

  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-labelledby="mapa-titulo mapa-desc"
      className="h-auto w-full"
    >
      <title id="mapa-titulo">{title}</title>
      <desc id="mapa-desc">{description}</desc>
      <g className="fill-surface-2 stroke-line" strokeWidth={0.6}>
        {countryPaths.map((d, i) => (
          <path key={i} d={d} />
        ))}
      </g>
      <g className="fill-red stroke-surface" fillOpacity={0.7} strokeWidth={1}>
        {points.map(({ point, xy }) => (
          <circle key={point.id} cx={xy[0]} cy={xy[1]} r={3 + 15 * Math.sqrt(point.races / maxRaces)}>
            <title>{point.label}</title>
          </circle>
        ))}
      </g>
    </svg>
  );
}
