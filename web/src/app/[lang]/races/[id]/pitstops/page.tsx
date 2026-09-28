import Link from "next/link";

import { BarChart } from "@/components/charts/bar-chart";
import { ChartFigure } from "@/components/charts/chart-figure";
import { DataTable, EmptyState, Section } from "@/components/ui";
import { apiGetRequired, type Schemas } from "@/lib/api/client";
import { number } from "@/lib/format";
import { getDictionary } from "@/lib/i18n";
import { getDriverNames, getRace } from "@/lib/race";
import { fill } from "@/lib/text";

export default async function PitStopsPage({ params }: PageProps<"/[lang]/races/[id]/pitstops">) {
  const { lang, id } = await params;
  const { locale, t } = await getDictionary(lang);
  const race = await getRace(id);
  const [stops, passes, { names, results }] = await Promise.all([
    apiGetRequired<Schemas["PitStop"][]>(`/races/${id}/pitstops`),
    apiGetRequired<Schemas["PitLanePass"][]>(`/races/${id}/pit-lane-passes`),
    getDriverNames(id),
  ]);
  const others = passes.filter((p) => p.pass_type !== "pit_stop");
  const passTypes = t.race.passTypes as Record<string, string>;
  const fastest = Math.min(...stops.map((s) => s.duration_ms ?? Infinity));
  const teamNames = new Map(results.map((r) => [r.constructor_id, r.constructor_name]));
  // Página «Tiempos de parada en boxes» del TFG: media por equipo sin paradas de más de 60 s.
  const byTeam = [...Map.groupBy(
    stops.filter((s) => s.duration_ms !== null && s.duration_ms <= 60000 && s.constructor_id),
    (s) => s.constructor_id!,
  )]
    .map(([teamId, items]) => ({
      id: teamId,
      name: teamNames.get(teamId) ?? teamId,
      stops: items.length,
      average: items.reduce((sum, s) => sum + s.duration_ms!, 0) / items.length / 1000,
    }))
    .sort((a, b) => a.average - b.average);

  return (
    <>
      {byTeam.length > 1 && (
        <Section title={t.race.pitAvgTitle} id="media-equipos" lede={t.race.pitAvgLede}>
          <ChartFigure
            title={`${t.race.pitAvgTitle} · ${race.grand_prix_name} ${race.season}`}
            summary={fill(t.race.pitAvgSummary, {
              fastest: byTeam[0].name,
              time: number(byTeam[0].average, locale, 2),
              slowest: byTeam[byTeam.length - 1].name,
              slowTime: number(byTeam[byTeam.length - 1].average, locale, 2),
            })}
            tableLabel={t.common.viewTable}
            table={
              <DataTable
                caption={t.race.pitAvgTitle}
                rows={byTeam}
                rowKey={(r) => r.id}
                compact
                columns={[
                  { header: t.common.constructor, rowHeader: true, cell: (r) => r.name },
                  { header: t.race.stops, align: "right", className: "tabular", cell: (r) => r.stops },
                  { header: t.race.average, align: "right", className: "tabular", cell: (r) => number(r.average, locale, 3) },
                ]}
              />
            }
          >
            <BarChart
              items={byTeam.map((r, i) => ({ label: r.name, value: r.average, highlight: i === 0 }))}
              label={t.race.pitAvgTitle}
              valueLabel={t.race.duration}
              unit=" s"
              decimals={2}
            />
          </ChartFigure>
        </Section>
      )}
      <Section title={t.race.pitstopsTitle} id="paradas" lede={t.race.pitstopsLede}>
        {stops.length === 0 ? (
          <EmptyState>{t.race.noPitstops}</EmptyState>
        ) : (
          <DataTable
            caption={t.race.pitstopsTitle}
            captionHidden
            rows={stops}
            rowKey={(s) => `${s.driver_id}-${s.stop}`}
            compact
            columns={[
              { header: t.common.lap, align: "right", className: "tabular", cell: (s) => s.lap },
              {
                header: t.common.driver,
                rowHeader: true,
                cell: (s) => <Link href={`/${locale}/drivers/${s.driver_id}`}>{s.driver_name}</Link>,
              },
              { header: t.race.stop, align: "right", className: "tabular", cell: (s) => s.stop },
              {
                header: t.race.duration,
                align: "right",
                className: "tabular",
                cell: (s) =>
                  s.duration_ms === null ? (
                    "—"
                  ) : (
                    <span className={s.duration_ms === fastest ? "font-semibold text-purple" : undefined}>
                      {number(s.duration_ms / 1000, locale, 3)} s
                    </span>
                  ),
              },
            ]}
          />
        )}
      </Section>
      {others.length > 0 && (
        <Section title={t.race.passesTitle} id="pit-lane" lede={t.race.passesLede}>
          <DataTable
            caption={t.race.passesTitle}
            captionHidden
            rows={others}
            rowKey={(p) => `${p.driver_id}-${p.lap}`}
            compact
            columns={[
              { header: t.common.lap, align: "right", className: "tabular", cell: (p) => p.lap },
              { header: t.common.driver, rowHeader: true, cell: (p) => names.get(p.driver_id) ?? p.driver_id },
              { header: t.common.status, cell: (p) => passTypes[p.pass_type] ?? p.pass_type },
            ]}
          />
        </Section>
      )}
    </>
  );
}
