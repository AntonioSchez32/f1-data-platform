import { ChartFigure } from "@/components/charts/chart-figure";
import { StintChart, type StintRow } from "@/components/charts/stint-chart";
import { CompoundMatrix, type MatrixRow } from "@/components/compound-matrix";
import { DataTable, EmptyState, Section } from "@/components/ui";
import { apiGetRequired, type Schemas } from "@/lib/api/client";
import { groupByCar, raceCars } from "@/lib/cars";
import { getDictionary } from "@/lib/i18n";
import { getRace, getResults } from "@/lib/race";
import { fill } from "@/lib/text";
import { compoundStyle } from "@/lib/tyres";

export default async function TyresPage({ params }: PageProps<"/[lang]/races/[id]/tyres">) {
  const { lang, id } = await params;
  const { t } = await getDictionary(lang);
  const race = await getRace(id);
  const [stints, laps, results] = await Promise.all([
    apiGetRequired<Schemas["Stint"][]>(`/races/${id}/stints`),
    apiGetRequired<Schemas["Lap"][]>(`/races/${id}/laps`),
    getResults(id),
  ]);
  // Una fila por coche (piloto y dorsal): en los años 50 un piloto podía llevar dos coches.
  const cars = raceCars([...stints, ...laps], results);
  const compounds = t.race.compounds as Record<string, string>;
  const compoundName = (c: string | null) => (c ? (compounds[c] ?? c) : compounds.UNKNOWN);

  if (stints.length === 0 || stints.every((s) => !s.compound)) {
    return (
      <Section title={t.race.tyresTitle} id="neumaticos">
        <EmptyState>{t.race.noTyres}</EmptyState>
      </Section>
    );
  }

  const rows: StintRow[] = groupByCar(stints, cars).map(([car, items]) => ({
    driverId: car.key,
    name: car.name,
    stints: items.map((s) => ({
      stint: s.stint,
      compound: s.compound,
      label: compoundName(s.compound),
      start: s.start_lap,
      end: s.end_lap,
      laps: s.laps,
    })),
  }));
  const totalLaps = Math.max(0, ...laps.map((l) => l.lap));
  const matrix: MatrixRow[] = groupByCar(laps, cars).map(([car, items]) => {
    const cells: MatrixRow["laps"] = Array(totalLaps).fill(null);
    for (const lap of items) cells[lap.lap - 1] = { compound: lap.compound, pit: Boolean(lap.is_pit_in_lap) };
    return { driverId: car.key, name: car.name, laps: cells };
  });
  const stopCounts = rows.map((r) => r.stints.length - 1);
  const commonStops = [...Map.groupBy(stopCounts, (n) => n)].sort((a, b) => b[1].length - a[1].length)[0][0];
  const used = [...new Set(stints.map((s) => s.compound).filter((c): c is string => Boolean(c)))];

  return (
    <>
    <Section title={t.race.tyresTitle} id="neumaticos" lede={t.race.tyresLede}>
      <ChartFigure
        title={`${t.race.tyresTitle} · ${race.grand_prix_name} ${race.season}`}
        summary={fill(t.race.tyresSummary, {
          winner: rows[0].name,
          stops: stopCounts[0],
          commonStops,
        })}
        tableLabel={t.common.viewTable}
        table={
          <DataTable
            caption={t.race.tyresTitle}
            rows={rows}
            rowKey={(r) => r.driverId}
            compact
            columns={[
              { header: t.common.driver, rowHeader: true, cell: (r) => r.name },
              {
                header: t.race.stints,
                cell: (r) =>
                  r.stints
                    .map((s) => `${s.label} (${t.common.lap.toLowerCase()} ${s.start}–${s.end})`)
                    .join(" · "),
              },
              { header: t.race.pitStops, align: "right", className: "tabular", cell: (r) => r.stints.length - 1 },
            ]}
          />
        }
      >
        <ul aria-label={t.race.compound} className="mb-2 flex flex-wrap gap-4 text-sm">
          {used.map((compound) => {
            const style = compoundStyle(compound);
            return (
              <li key={compound} className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className="inline-flex h-5 min-w-6 items-center justify-center rounded border border-line px-1 text-xs font-semibold"
                  style={{ backgroundColor: style.color, color: style.text }}
                >
                  {style.letter}
                </span>
                {compoundName(compound)}
              </li>
            );
          })}
        </ul>
        <StintChart rows={rows} label={t.race.tyresTitle} lapLabel={t.common.lap} stintLabel={t.race.stint} />
      </ChartFigure>
    </Section>
    <Section title={t.race.matrixTitle} id="matriz" lede={t.race.matrixLede}>
      <CompoundMatrix
        rows={matrix}
        caption={t.race.matrixTitle}
        driverLabel={t.common.driver}
        lapLabel={t.common.lap}
        pitLabel={t.race.pitLap}
        compoundName={compoundName}
      />
    </Section>
    </>
  );
}
