import { ChartFigure } from "@/components/charts/chart-figure";
import { LapChart, type LapChartDriver } from "@/components/charts/lap-chart";
import { DataTable, EmptyState, Section } from "@/components/ui";
import { apiGetRequired, type Schemas } from "@/lib/api/client";
import { driverCode } from "@/lib/format";
import { getDictionary } from "@/lib/i18n";
import { getDriverNames, getRace } from "@/lib/race";
import { fill } from "@/lib/text";

export default async function LapChartPage({ params }: PageProps<"/[lang]/races/[id]/lap-chart">) {
  const { lang, id } = await params;
  const { t } = await getDictionary(lang);
  const race = await getRace(id);
  const [laps, { results, names, order }] = await Promise.all([
    apiGetRequired<Schemas["Lap"][]>(`/races/${id}/laps`),
    getDriverNames(id),
  ]);

  if (laps.length === 0) {
    return (
      <Section title={t.race.lapChartTitle} id="vueltas">
        <EmptyState>{t.race.noLaps}</EmptyState>
      </Section>
    );
  }

  const totalLaps = Math.max(...laps.map((l) => l.lap));
  const byDriver = Map.groupBy(laps, (l) => l.driver_id);
  const grid = new Map(results.map((r) => [r.driver_id, r.grid_position]));
  const drivers: (LapChartDriver & { finish: string; best: number | null; led: number; start: number | null })[] =
    [...byDriver.keys()]
      .sort((a, b) => (order.get(a) ?? 99) - (order.get(b) ?? 99))
      .map((driverId) => {
        const driverLaps = byDriver.get(driverId)!;
        const positions: (number | null)[] = Array(totalLaps + 1).fill(null);
        positions[0] = grid.get(driverId) ?? null;
        for (const lap of driverLaps) positions[lap.lap] = lap.position;
        const valid = driverLaps.map((l) => l.position).filter((p): p is number => p !== null);
        return {
          id: driverId,
          name: names.get(driverId) ?? driverId,
          code: driverCode(driverId),
          positions,
          start: grid.get(driverId) ?? null,
          finish: results.find((r) => r.driver_id === driverId)?.position_text ?? "—",
          best: valid.length ? Math.min(...valid) : null,
          led: driverLaps.filter((l) => l.position === 1).length,
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
