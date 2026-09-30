import { ChartFigure } from "@/components/charts/chart-figure";
import { LapChart, type LapChartDriver } from "@/components/charts/lap-chart";
import { DataTable, EmptyState, Section } from "@/components/ui";
import { apiGetRequired, type Schemas } from "@/lib/api/client";
import { groupByCar, raceCars } from "@/lib/cars";
import { getDictionary } from "@/lib/i18n";
import { getRace, getResults } from "@/lib/race";
import { fill } from "@/lib/text";

export default async function LapChartPage({ params }: PageProps<"/[lang]/races/[id]/lap-chart">) {
  const { lang, id } = await params;
  const { t } = await getDictionary(lang);
  const race = await getRace(id);
  const [laps, results] = await Promise.all([
    apiGetRequired<Schemas["Lap"][]>(`/races/${id}/laps`),
    getResults(id),
  ]);

  if (laps.length === 0) {
    return (
      <Section title={t.race.lapChartTitle} id="vueltas">
        <EmptyState>{t.race.noLaps}</EmptyState>
      </Section>
    );
  }

  const totalLaps = Math.max(...laps.map((l) => l.lap));
  // Una serie por coche (piloto y dorsal): en los años 50 un piloto podía llevar dos coches.
  const cars = raceCars(laps, results);
  const drivers: (LapChartDriver & { finish: string; best: number | null; led: number; start: number | null })[] =
    groupByCar(laps, cars).map(([car, carLaps]) => {
      const positions: (number | null)[] = Array(totalLaps + 1).fill(null);
      positions[0] = car.result?.grid_position ?? null;
      for (const lap of carLaps) positions[lap.lap] = lap.position;
      const valid = carLaps.map((l) => l.position).filter((p): p is number => p !== null);
      return {
        id: car.key,
        name: car.name,
        code: car.code,
        positions,
        start: car.result?.grid_position ?? null,
        finish: car.result?.position_text ?? "—",
        best: valid.length ? Math.min(...valid) : null,
        led: carLaps.filter((l) => l.position === 1).length,
      };
    });
  const winner = drivers[0];

  return (
    <Section title={t.race.lapChartTitle} id="vueltas" lede={t.race.lapChartLede}>
      <ChartFigure
        title={`${t.race.lapChartTitle} · ${race.grand_prix_name} ${race.season}`}
        summary={fill(t.race.lapChartSummary, {
          winner: winner.name,
          grid: winner.start ?? "—",
          ledLaps: winner.led,
          laps: totalLaps,
        })}
        tableLabel={t.common.viewTable}
        table={
          <DataTable
            caption={t.race.lapChartTable}
            rows={drivers}
            rowKey={(d) => d.id}
            compact
            columns={[
              { header: t.common.driver, rowHeader: true, cell: (d) => d.name },
              { header: t.race.start, align: "right", className: "tabular", cell: (d) => d.start ?? "—" },
              { header: t.race.finish, align: "right", className: "tabular", cell: (d) => d.finish },
              { header: t.race.best, align: "right", className: "tabular", cell: (d) => d.best ?? "—" },
              { header: t.race.lapsLed, align: "right", className: "tabular", cell: (d) => d.led },
            ]}
          />
        }
      >
        <LapChart
          drivers={drivers.map(({ id: driverId, name, code, positions }) => ({ id: driverId, name, code, positions }))}
          label={t.race.lapChartTitle}
          lapLabel={t.common.lap}
          gridLabel={t.race.start}
        />
      </ChartFigure>
    </Section>
  );
}
