import { ChartFigure } from "@/components/charts/chart-figure";
import { LapTimesChart, type LapTimesDriver } from "@/components/charts/lap-times-chart";
import { ViolinChart, type ViolinDriver } from "@/components/charts/violin-chart";
import { DataTable, EmptyState, Section } from "@/components/ui";
import { apiGetRequired, type Schemas } from "@/lib/api/client";
import { carOf, groupByCar, raceCars } from "@/lib/cars";
import { lapTime } from "@/lib/format";
import { getDictionary } from "@/lib/i18n";
import { getRace, getResults } from "@/lib/race";
import { fill } from "@/lib/text";

/** Densidad por núcleos gaussianos (ancho de Silverman) en 60 puntos entre el mínimo y el máximo. */
function density(values: number[]): [number, number][] {
  const n = values.length;
  const mean = values.reduce((a, b) => a + b, 0) / n;
  const sd = Math.sqrt(values.reduce((a, b) => a + (b - mean) ** 2, 0) / Math.max(n - 1, 1));
  const h = Math.max(1.06 * sd * n ** -0.2, 50);
  const [min, max] = [values[0], values[n - 1]];
  return Array.from({ length: 60 }, (_, i) => {
    const t = min + ((max - min) * i) / 59;
    const d = values.reduce((sum, v) => sum + Math.exp(-0.5 * ((t - v) / h) ** 2), 0) / (n * h);
    return [t, d];
  });
}

function quantile(sorted: number[], q: number): number {
  const pos = (sorted.length - 1) * q;
  const low = Math.floor(pos);
  const high = Math.ceil(pos);
  return sorted[low] + (sorted[high] - sorted[low]) * (pos - low);
}

/**
 * Vueltas representativas del ritmo: sin vuelta 1, sin boxes, sin neutralizaciones ni bandera roja.
 * Además se descartan las vueltas un 50 % más lentas que la mediana de la carrera: cubren las
 * neutralizaciones que la fuente no marca (p. ej. la vuelta 33 de São Paulo 2024, con bandera roja).
 */
function isRacingLap(lap: Schemas["Lap"], limitMs: number): boolean {
  return (
    lap.lap > 1 &&
    lap.lap_time_ms !== null &&
    lap.lap_time_ms <= limitMs &&
    !lap.is_pit_in_lap &&
    !lap.is_pit_out_lap &&
    !lap.is_safety_car &&
    !lap.is_virtual_safety_car &&
    !lap.is_red_flag
  );
}

export default async function PacePage({ params }: PageProps<"/[lang]/races/[id]/pace">) {
  const { lang, id } = await params;
  const { t } = await getDictionary(lang);
  const race = await getRace(id);
  const [laps, results] = await Promise.all([
    apiGetRequired<Schemas["Lap"][]>(`/races/${id}/laps`),
    getResults(id),
  ]);
  // Una serie por coche (piloto y dorsal): en los años 50 un piloto podía llevar dos coches.
  const cars = raceCars(laps, results);

  const allTimes = laps.map((l) => l.lap_time_ms).filter((v): v is number => v !== null).sort((a, b) => a - b);
  const limitMs = allTimes.length ? 1.5 * quantile(allTimes, 0.5) : Infinity;
  const racing = (lap: Schemas["Lap"]) => isRacingLap(lap, limitMs);
  const stats = groupByCar(laps.filter(racing), cars)
    .map(([car, items]) => {
      const times = items.map((l) => l.lap_time_ms!).sort((a, b) => a - b);
      const [q1, median, q3] = [0.25, 0.5, 0.75].map((q) => quantile(times, q));
      const fence = 1.5 * (q3 - q1);
      const inside = times.filter((v) => v >= q1 - fence && v <= q3 + fence);
      return {
        driverId: car.key,
        name: car.name,
        code: car.code,
        count: times.length,
        best: times[0],
        q1,
        median,
        q3,
        whiskerLow: inside[0],
        whiskerHigh: inside[inside.length - 1],
        density: density(times),
      };
    })
    // Con menos de 5 vueltas válidas la distribución no es representativa.
    .filter((s) => s.count >= 5)
    .sort((a, b) => a.median - b.median);

  // Tiempos vuelta a vuelta de cada piloto, en orden de llegada (gráfico de líneas del TFG).
  const totalLaps = Math.max(0, ...laps.map((l) => l.lap));
  const lapDrivers: (LapTimesDriver & { code: string })[] = groupByCar(laps, cars).map(([car, items]) => {
    const times: (number | null)[] = Array(totalLaps).fill(null);
    for (const lap of items) times[lap.lap - 1] = lap.lap_time_ms;
    return {
      id: car.key,
      name: car.name,
      code: car.code,
      times,
      neutralized: items.filter((l) => l.lap === 1 || !racing(l)).map((l) => l.lap),
    };
  });
  const fastestLap = laps
    .filter((l) => l.lap_time_ms !== null)
    .reduce<Schemas["Lap"] | null>((best, l) => (!best || l.lap_time_ms! < best.lap_time_ms! ? l : best), null);

  if (stats.length === 0) {
    return (
      <Section title={t.race.paceTitle} id="ritmo">
        <EmptyState>{t.race.noLaps}</EmptyState>
      </Section>
    );
  }

  return (
    <>
      <Section title={t.race.lapTimesTitle} id="tiempos" lede={t.race.lapTimesLede}>
        <ChartFigure
          title={`${t.race.lapTimesTitle} · ${race.grand_prix_name} ${race.season}`}
          summary={
            fastestLap
              ? fill(t.race.lapTimesSummary, {
                  fastest: carOf(fastestLap, cars)?.name ?? fastestLap.driver_id,
                  time: lapTime(fastestLap.lap_time_ms),
                  lap: fastestLap.lap,
                })
              : ""
          }
          tableLabel={t.common.viewTable}
          table={
            <DataTable
              caption={t.race.lapTimesTitle}
              rows={Array.from({ length: totalLaps }, (_, i) => i + 1)}
              rowKey={(lap) => lap}
              compact
              columns={[
                { header: t.common.lap, rowHeader: true, align: "right", className: "tabular", cell: (lap) => lap },
                ...lapDrivers.map((d) => ({
                  header: <abbr title={d.name}>{d.code}</abbr>,
                  align: "right" as const,
                  className: "tabular whitespace-nowrap",
                  cell: (lap: number) => lapTime(d.times[lap - 1]),
                })),
              ]}
            />
          }
        >
          <LapTimesChart
            drivers={lapDrivers}
            hideNeutralizedByDefault={allTimes.some((v) => v > limitMs)}
            labels={{
              title: t.race.lapTimesTitle,
              lap: t.common.lap,
              time: t.common.time,
              drivers: t.common.drivers,
              all: t.race.all,
              none: t.race.none,
              hideNeutralized: t.race.hideNeutralized,
            }}
          />
        </ChartFigure>
      </Section>
    <Section title={t.race.paceTitle} id="ritmo" lede={t.race.paceLede}>
      <ChartFigure
        title={`${t.race.paceTitle} · ${race.grand_prix_name} ${race.season}`}
        summary={fill(t.race.paceSummary, { fastest: stats[0].name, median: lapTime(stats[0].median) })}
        tableLabel={t.common.viewTable}
        table={
          <DataTable
            caption={t.race.paceTitle}
            rows={stats}
            rowKey={(s) => s.driverId}
            compact
            columns={[
              { header: t.common.driver, rowHeader: true, cell: (s) => s.name },
              { header: t.race.median, align: "right", className: "tabular", cell: (s) => lapTime(s.median) },
              { header: t.race.bestLap, align: "right", className: "tabular", cell: (s) => lapTime(s.best) },
              {
                header: t.race.spread,
                align: "right",
                className: "tabular",
                cell: (s) => `${lapTime(s.q1)} – ${lapTime(s.q3)}`,
              },
              { header: t.race.lapsCounted, align: "right", className: "tabular", cell: (s) => s.count },
            ]}
          />
        }
      >
        <ViolinChart
          drivers={stats.map(
            (s): ViolinDriver => ({
              id: s.driverId,
              name: s.name,
              code: s.code,
              colorIndex: lapDrivers.findIndex((d) => d.id === s.driverId),
              density: s.density,
              q1: s.q1,
              median: s.median,
              q3: s.q3,
              whiskerLow: s.whiskerLow,
              whiskerHigh: s.whiskerHigh,
            }),
          )}
          labels={{
            title: t.race.paceTitle,
            time: t.common.time,
            drivers: t.common.drivers,
            all: t.race.all,
            none: t.race.none,
            median: t.race.median,
          }}
        />
      </ChartFigure>
    </Section>
    </>
  );
}
