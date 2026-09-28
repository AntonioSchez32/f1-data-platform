import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ChartFigure } from "@/components/charts/chart-figure";
import { SeasonPointsChart } from "@/components/charts/season-points-chart";
import { TeammatePointsChart, TeammateShareChart, type TeammateSeason } from "@/components/charts/teammate-charts";
import { DataTable, EmptyState, PageHeader, Pill, Section, Stat } from "@/components/ui";
import { apiGet, apiGetRequired, type Schemas } from "@/lib/api/client";
import { date, number } from "@/lib/format";
import { getDictionary } from "@/lib/i18n";
import { fill } from "@/lib/text";

const getDriver = (id: string) =>
  /^[a-z0-9-]+$/.test(id) ? apiGet<Schemas["DriverDetail"]>(`/drivers/${id}`) : Promise.resolve(null);

export async function generateMetadata({ params }: PageProps<"/[lang]/drivers/[id]">): Promise<Metadata> {
  const driver = await getDriver((await params).id);
  return { title: driver?.name };
}

export default async function DriverPage({ params }: PageProps<"/[lang]/drivers/[id]">) {
  const { lang, id } = await params;
  const { locale, t } = await getDictionary(lang);
  const driver = await getDriver(id);
  if (!driver) notFound();
  const [seasons, teammates] = await Promise.all([
    apiGetRequired<Schemas["DriverSeason"][]>(`/drivers/${id}/seasons`),
    apiGetRequired<Schemas["TeammateComparison"][]>(`/drivers/${id}/teammates`),
  ]);
  const pct = (value: number | null) => (value === null ? "—" : `${number(value, locale, 1)} %`);

  // Página «Detalle de rendimiento de piloto» del TFG: comparativa con los compañeros por temporada.
  const bySeason: (TeammateSeason & { races: number; raceAhead: number; qualis: number; qualiAhead: number })[] = [
    ...Map.groupBy(teammates, (m) => m.season),
  ].map(([season, rows]) => {
    const sum = (key: "races_together" | "race_ahead" | "qualifyings_together" | "quali_ahead") =>
      rows.reduce((total, r) => total + r[key], 0);
    const races = sum("races_together");
    const qualis = sum("qualifyings_together");
    return {
      season,
      points: rows.reduce((total, r) => total + (r.points ?? 0), 0),
      teammatePoints: rows.reduce((total, r) => total + (r.teammate_points ?? 0), 0),
      races,
      raceAhead: sum("race_ahead"),
      qualis,
      qualiAhead: sum("quali_ahead"),
      raceShare: races ? (100 * sum("race_ahead")) / races : null,
      qualiShare: qualis ? (100 * sum("quali_ahead")) / qualis : null,
    };
  });
  const totals = bySeason.reduce(
    (acc, s) => ({
      races: acc.races + s.races,
      raceAhead: acc.raceAhead + s.raceAhead,
      qualis: acc.qualis + s.qualis,
      qualiAhead: acc.qualiAhead + s.qualiAhead,
    }),
    { races: 0, raceAhead: 0, qualis: 0, qualiAhead: 0 },
  );
  const seasonTable = (
    <DataTable
      caption={t.drivers.teammatesTitle}
      rows={bySeason}
      rowKey={(s) => s.season}
      compact
      columns={[
        { header: t.common.season, rowHeader: true, className: "tabular", cell: (s) => s.season },
        { header: driver.name, align: "right", className: "tabular", cell: (s) => number(s.points, locale, 1) },
        { header: t.drivers.teammatesSeries, align: "right", className: "tabular", cell: (s) => number(s.teammatePoints, locale, 1) },
        { header: t.drivers.qualiAhead, align: "right", className: "tabular", cell: (s) => `${s.qualiAhead}/${s.qualis} · ${pct(s.qualiShare)}` },
        { header: t.drivers.raceAhead, align: "right", className: "tabular", cell: (s) => `${s.raceAhead}/${s.races} · ${pct(s.raceShare)}` },
      ]}
    />
  );

  return (
    <>
      <PageHeader
        eyebrow={[driver.nationality, driver.permanent_number && `#${driver.permanent_number}`]
          .filter(Boolean)
          .join(" · ")}
        title={driver.name}
        lede={
          <>
            {driver.full_name}
            {driver.date_of_birth && (
              <>
                {" · "}
                {t.drivers.born}: {date(driver.date_of_birth, locale)}
                {driver.place_of_birth ? `, ${driver.place_of_birth}` : ""}
              </>
            )}
            {driver.date_of_death && (
              <>
                {" · "}
                {t.drivers.died}: {date(driver.date_of_death, locale)}
              </>
            )}
          </>
        }
      />

      <dl className="mb-12 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label={t.common.championships} value={driver.championships} />
        <Stat label={t.common.wins} value={driver.wins} />
        <Stat label={t.common.podiums} value={driver.podiums} />
        <Stat label={t.common.poles} value={driver.pole_positions} />
        <Stat label={t.common.fastestLaps} value={driver.fastest_laps} />
        <Stat label={t.common.starts} value={driver.race_starts} />
      </dl>

      <Section title={t.drivers.seasonsTitle} id="temporadas">
        <ChartFigure
          title={t.drivers.seasonsChart}
          summary={fill(t.drivers.seasonsSummary, {
            name: driver.name,
            seasons: seasons.length,
            best: driver.best_championship_position ? `${driver.best_championship_position}.º` : "—",
          })}
          tableLabel={t.common.viewTable}
          table={
            <DataTable
              caption={t.drivers.seasonsTitle}
              rows={seasons}
              rowKey={(s) => `${s.season}-${s.constructor_id}`}
              compact
              columns={[
                {
                  header: t.common.season,
                  rowHeader: true,
                  cell: (s) => <Link href={`/${locale}/seasons/${s.season}`}>{s.season}</Link>,
                },
                { header: t.common.constructor, cell: (s) => s.constructor_name ?? "—" },
                {
                  header: t.common.positionShort,
                  align: "right",
                  cell: (s) =>
                    s.is_champion ? <Pill tone="best">{t.common.champion}</Pill> : (s.championship_position_text ?? "—"),
                },
                { header: t.common.points, align: "right", className: "tabular", cell: (s) => number(s.points, locale, 1) },
                { header: t.common.wins, align: "right", className: "tabular", cell: (s) => s.wins },
                { header: t.common.podiums, align: "right", className: "tabular", cell: (s) => s.podiums },
                { header: t.common.poles, align: "right", className: "tabular", cell: (s) => s.pole_positions },
              ]}
            />
          }
        >
          <SeasonPointsChart
            rows={seasons.map((s) => ({
              season: s.season,
              points: s.points ?? 0,
              position: s.championship_position_text,
              champion: s.is_champion,
            }))}
            label={t.drivers.seasonsChart}
            pointsLabel={t.common.points}
          />
        </ChartFigure>
      </Section>

      {bySeason.length > 0 && (
        <Section title={t.drivers.teammatesTitle} id="companeros" lede={t.drivers.teammatesLede}>
          <ChartFigure
            title={t.drivers.pointsVsTeammates}
            summary={fill(t.drivers.pointsVsSummary, {
              better: bySeason.filter((s) => s.points > s.teammatePoints).length,
              seasons: bySeason.length,
            })}
            tableLabel={t.common.viewTable}
            table={seasonTable}
          >
            <TeammatePointsChart
              rows={bySeason}
              label={t.drivers.pointsVsTeammates}
              driverLabel={driver.name}
              teammateLabel={t.drivers.teammatesSeries}
            />
          </ChartFigure>
          <div className="grid gap-4 lg:grid-cols-2">
            <ChartFigure
              title={t.drivers.qualiVsTeammates}
              summary={fill(t.drivers.shareSummary, {
                pct: pct(totals.qualis ? (100 * totals.qualiAhead) / totals.qualis : null),
                what: `${totals.qualis} ${t.drivers.qualifyings}`,
              })}
              tableLabel={t.common.viewTable}
              table={seasonTable}
            >
              <TeammateShareChart
                rows={bySeason}
                field="qualiShare"
                label={t.drivers.qualiVsTeammates}
                driverLabel={driver.name}
                teammateLabel={t.drivers.teammatesSeries}
              />
            </ChartFigure>
            <ChartFigure
              title={t.drivers.raceVsTeammates}
              summary={fill(t.drivers.shareSummary, {
                pct: pct(totals.races ? (100 * totals.raceAhead) / totals.races : null),
                what: `${totals.races} ${t.drivers.races}`,
              })}
              tableLabel={t.common.viewTable}
              table={seasonTable}
            >
              <TeammateShareChart
                rows={bySeason}
                field="raceShare"
                label={t.drivers.raceVsTeammates}
                driverLabel={driver.name}
                teammateLabel={t.drivers.teammatesSeries}
              />
            </ChartFigure>
          </div>
        </Section>
      )}

      <Section title={t.drivers.teammatesDetail} id="detalle-companeros">
        {teammates.length === 0 ? (
          <EmptyState>{t.common.noData}</EmptyState>
        ) : (
          <DataTable
            caption={t.drivers.teammatesDetail}
            captionHidden
            rows={teammates}
            rowKey={(m) => `${m.season}-${m.constructor_id}-${m.teammate_id}`}
            compact
            columns={[
              { header: t.common.season, className: "tabular", cell: (m) => m.season },
              { header: t.common.constructor, cell: (m) => m.constructor_name },
              {
                header: t.drivers.teammate,
                rowHeader: true,
                cell: (m) => <Link href={`/${locale}/drivers/${m.teammate_id}`}>{m.teammate_name}</Link>,
              },
              {
                header: t.drivers.raceAhead,
                align: "right",
                className: "tabular",
                cell: (m) => `${m.race_ahead}/${m.races_together} · ${pct(m.race_ahead_pct)}`,
              },
              {
                header: t.drivers.qualiAhead,
                align: "right",
                className: "tabular",
                cell: (m) => `${m.quali_ahead}/${m.qualifyings_together} · ${pct(m.quali_ahead_pct)}`,
              },
              {
                header: t.common.points,
                align: "right",
                className: "tabular",
                cell: (m) => `${number(m.points, locale, 1)} – ${number(m.teammate_points, locale, 1)}`,
              },
            ]}
          />
        )}
      </Section>
    </>
  );
}
