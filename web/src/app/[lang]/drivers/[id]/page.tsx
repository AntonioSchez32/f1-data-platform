import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ChartFigure } from "@/components/charts/chart-figure";
import { SeasonPointsChart } from "@/components/charts/season-points-chart";
import {
  TeammateCumulativeChart,
  TeammatePointsChart,
  TeammateShareChart,
  type TeammateSeason,
} from "@/components/charts/teammate-charts";
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
  const [seasons, teammates, teammateSeasons, teammateRaces] = await Promise.all([
    apiGetRequired<Schemas["DriverSeason"][]>(`/drivers/${id}/seasons`),
    apiGetRequired<Schemas["TeammateComparison"][]>(`/drivers/${id}/teammates`),
    apiGetRequired<Schemas["TeammateSeason"][]>(`/drivers/${id}/teammates/seasons`),
    apiGetRequired<Schemas["TeammateRace"][]>(`/drivers/${id}/teammates/races`),
  ]);
  const pct = (value: number | null) => (value === null ? "—" : `${number(value, locale, 1)} %`);
  const share = (ahead: number, total: number) => (total ? (100 * ahead) / total : null);

  // Página «Detalle de rendimiento de piloto» del TFG: comparativa con los compañeros por temporada.
  // El resumen viene de la API (decisiones 45 y 46): los puntos se cuentan carrera a carrera frente
  // al mejor compañero de cada carrera (sumar los de cada pareja repetía los del piloto, p. ej. 106
  // en vez de 41 para Fangio en 1955) y el duelo en carrera solo compara las carreras en que acaban
  // los dos.
  const bySeason: (TeammateSeason & Schemas["TeammateSeason"])[] = teammateSeasons.map((s) => ({
    ...s,
    teammatePoints: s.teammate_points,
    raceShare: s.race_ahead_pct,
    qualiShare: s.quali_ahead_pct,
  }));
  const totals = teammateSeasons.reduce(
    (acc, s) => ({
      points: acc.points + s.points,
      teammatePoints: acc.teammatePoints + s.teammate_points,
      raceAhead: acc.raceAhead + s.race_ahead,
      bothFinished: acc.bothFinished + s.races_both_classified,
      qualiAhead: acc.qualiAhead + s.quali_ahead,
      qualis: acc.qualis + s.qualifyings_together,
    }),
    { points: 0, teammatePoints: 0, raceAhead: 0, bothFinished: 0, qualiAhead: 0, qualis: 0 },
  );
  const raceAheadHeader = (
    <>
      {t.drivers.raceAhead}
      <span className="block text-xs font-normal text-muted">{t.drivers.bothFinished}</span>
    </>
  );
  type SeasonRow = { key: string; season: string; points: number; teammatePoints: number } & Pick<
    Schemas["TeammateSeason"],
    "race_ahead" | "races_both_classified" | "race_ahead_pct" | "quali_ahead" | "qualifyings_together" | "quali_ahead_pct"
  >;
  const seasonRows: SeasonRow[] = [
    ...bySeason.map((s) => ({ ...s, key: String(s.season), season: String(s.season) })),
    {
      key: "total",
      season: t.common.total,
      points: totals.points,
      teammatePoints: totals.teammatePoints,
      race_ahead: totals.raceAhead,
      races_both_classified: totals.bothFinished,
      race_ahead_pct: share(totals.raceAhead, totals.bothFinished),
      quali_ahead: totals.qualiAhead,
      qualifyings_together: totals.qualis,
      quali_ahead_pct: share(totals.qualiAhead, totals.qualis),
    },
  ];
  const seasonTable = (
    <DataTable
      caption={t.drivers.teammatesTitle}
      rows={seasonRows}
      rowKey={(s) => s.key}
      rowClassName={(s) => (s.key === "total" ? "font-semibold" : undefined)}
      compact
      columns={[
        { header: t.common.season, rowHeader: true, className: "tabular", cell: (s) => s.season },
        { header: driver.name, align: "right", className: "tabular", cell: (s) => number(s.points, locale, 1) },
        { header: t.drivers.bestTeammate, align: "right", className: "tabular", cell: (s) => number(s.teammatePoints, locale, 1) },
        {
          header: t.drivers.qualiAhead,
          align: "right",
          className: "tabular",
          cell: (s) => `${s.quali_ahead}/${s.qualifyings_together} · ${pct(s.quali_ahead_pct)}`,
        },
        {
          header: raceAheadHeader,
          align: "right",
          className: "tabular",
          cell: (s) => `${s.race_ahead}/${s.races_both_classified} · ${pct(s.race_ahead_pct)}`,
        },
      ]}
    />
  );

  // Acumulados carrera a carrera frente al mejor compañero de cada carrera (decisión 45).
  const round2 = (value: number) => Math.round(value * 100) / 100;
  const cumulative = teammateRaces.reduce<
    (Schemas["TeammateRace"] & { label: string; race: string; cumulativePoints: number; cumulativeTeammate: number })[]
  >((acc, r) => {
    const previous = acc.at(-1);
    acc.push({
      ...r,
      label: `${r.season} ${t.common.roundShort}${r.round}`,
      race: r.grand_prix_name,
      cumulativePoints: round2((previous?.cumulativePoints ?? 0) + r.points),
      cumulativeTeammate: round2((previous?.cumulativeTeammate ?? 0) + r.teammate_points),
    });
    return acc;
  }, []);
  const cumulativeTable = (
    <DataTable
      caption={t.drivers.cumulativeTitle}
      rows={cumulative}
      rowKey={(r) => r.race_id}
      compact
      columns={[
        { header: t.common.race, rowHeader: true, className: "whitespace-nowrap", cell: (r) => `${r.label} · ${r.race}` },
        { header: t.drivers.bestTeammate, cell: (r) => r.best_teammates.map((m) => m.name).join(" / ") },
        { header: driver.name, align: "right", className: "tabular", cell: (r) => number(r.points, locale, 1) },
        { header: t.drivers.teammate, align: "right", className: "tabular", cell: (r) => number(r.teammate_points, locale, 1) },
        {
          header: `${t.drivers.cumulative} · ${driver.name}`,
          align: "right",
          className: "tabular",
          cell: (r) => number(r.cumulativePoints, locale, 1),
        },
        {
          header: `${t.drivers.cumulative} · ${t.drivers.teammate}`,
          align: "right",
          className: "tabular",
          cell: (r) => number(r.cumulativeTeammate, locale, 1),
        },
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
                    s.is_champion ? (
                      <Pill tone="best">{t.common.champion}</Pill>
                    ) : (
                      (s.championship_position_text ?? <span className="text-muted">{t.common.unclassified}</span>)
                    ),
                },
                {
                  header: t.drivers.entriesStarts,
                  align: "right",
                  className: "tabular whitespace-nowrap",
                  cell: (s) => (
                    <>
                      <span aria-hidden="true">
                        {s.race_entries} / {s.race_starts}
                      </span>
                      <span className="sr-only">
                        {fill(t.drivers.entriesStartsLabel, { entries: s.race_entries, starts: s.race_starts })}
                      </span>
                    </>
                  ),
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
        {seasons.some((s) => s.championship_position_text === null) && (
          <p className="mt-2 text-sm text-muted">{t.drivers.unclassifiedNote}</p>
        )}
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
              teammateLabel={t.drivers.bestTeammate}
            />
          </ChartFigure>
          <ChartFigure
            title={t.drivers.cumulativeTitle}
            summary={fill(t.drivers.cumulativeSummary, {
              name: driver.name,
              points: number(totals.points, locale, 1),
              races: cumulative.length,
              teammatePoints: number(totals.teammatePoints, locale, 1),
            })}
            tableLabel={t.common.viewTable}
            table={cumulativeTable}
          >
            <TeammateCumulativeChart
              rows={cumulative.map((r) => ({
                label: r.label,
                race: r.race,
                points: r.cumulativePoints,
                teammatePoints: r.cumulativeTeammate,
              }))}
              label={t.drivers.cumulativeTitle}
              driverLabel={driver.name}
              teammateLabel={t.drivers.bestTeammate}
            />
          </ChartFigure>
          <div className="grid gap-4 lg:grid-cols-2">
            <ChartFigure
              title={t.drivers.qualiVsTeammates}
              summary={fill(t.drivers.shareSummary, {
                pct: pct(share(totals.qualiAhead, totals.qualis)),
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
                pct: pct(share(totals.raceAhead, totals.bothFinished)),
                what: `${totals.bothFinished} ${t.drivers.racesBothFinished}`,
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
              { header: t.drivers.racesTogether, align: "right", className: "tabular", cell: (m) => m.races_together },
              {
                header: raceAheadHeader,
                align: "right",
                className: "tabular",
                cell: (m) => `${m.race_ahead}/${m.races_both_classified} · ${pct(m.race_ahead_pct)}`,
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
