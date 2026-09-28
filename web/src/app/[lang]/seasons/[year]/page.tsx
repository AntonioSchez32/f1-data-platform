import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ChartFigure } from "@/components/charts/chart-figure";
import { ProgressionChart } from "@/components/charts/progression-chart";
import { SeasonPicker } from "@/components/season-picker";
import { DataTable, EmptyState, Highlight, PageHeader, Pill, Section } from "@/components/ui";
import { apiGet, apiGetRequired, type Schemas } from "@/lib/api/client";
import { date, number } from "@/lib/format";
import { getDictionary } from "@/lib/i18n";
import { fill } from "@/lib/text";

export async function generateMetadata({ params }: PageProps<"/[lang]/seasons/[year]">): Promise<Metadata> {
  const { year } = await params;
  return { title: year };
}

export default async function SeasonPage({ params }: PageProps<"/[lang]/seasons/[year]">) {
  const { lang, year } = await params;
  const { locale, t } = await getDictionary(lang);
  if (!/^\d{4}$/.test(year)) notFound();

  const [season, allSeasons] = await Promise.all([
    apiGet<Schemas["SeasonDetail"]>(`/seasons/${year}`),
    apiGetRequired<Schemas["SeasonSummary"][]>("/seasons"),
  ]);
  if (!season) notFound();
  const completed = season.races.filter((r) => r.is_completed);
  const [drivers, constructors, progression] = await Promise.all([
    completed.length ? apiGet<Schemas["DriverStanding"][]>(`/seasons/${year}/standings/drivers`) : null,
    completed.length
      ? apiGet<Schemas["ConstructorStanding"][]>(`/seasons/${year}/standings/constructors`)
      : null,
    completed.length
      ? apiGet<Schemas["StandingsProgression"][]>(`/seasons/${year}/standings/progression`, { top: 10 })
      : null,
  ]);
  const finished = completed.length === season.races.length;
  const [leader, second] = drivers ?? [];
  const leadingTeam = constructors?.[0];

  return (
    <>
      <PageHeader
        eyebrow={t.common.season}
        title={year}
        lede={finished ? undefined : fill(t.seasons.inProgress, { completed: completed.length, total: season.races.length })}
      >
        <SeasonPicker
          action={`/${locale}/seasons`}
          seasons={allSeasons.map((s) => s.season)}
          current={Number(year)}
          label={t.seasons.choose}
          buttonLabel={t.seasons.go}
        />
      </PageHeader>

      {leader && (
        <dl className="mb-12 grid gap-3 sm:grid-cols-3">
          <Highlight
            label={finished ? t.seasons.championDriver : t.seasons.leaderDriver}
            value={leader.name}
            href={`/${locale}/drivers/${leader.driver_id}`}
          />
          <Highlight
            label={finished ? t.seasons.championTeam : t.seasons.leaderTeam}
            value={leadingTeam ? leadingTeam.name : leader.constructors.join(", ")}
            href={leadingTeam ? `/${locale}/constructors/${leadingTeam.constructor_id}` : undefined}
          />
          <Highlight label={finished ? t.seasons.championWins : t.seasons.leaderWins} value={leader.wins} />
        </dl>
      )}

      {progression && progression.length > 0 && leader && second && (
        <Section title={t.seasons.progression} id="evolucion" lede={t.seasons.progressionLede}>
          <ChartFigure
            title={t.seasons.progression}
            summary={fill(finished ? t.seasons.progressionSummary : t.seasons.progressionSummaryInProgress, {
              leader: leader.name,
              points: number(leader.points, locale, 1),
              second: second.name,
              secondPoints: number(second.points, locale, 1),
            })}
            tableLabel={t.common.viewTable}
            table={<ProgressionTable rows={progression} t={t} locale={locale} />}
          >
            <ProgressionChart
              rows={progression}
              label={t.seasons.progression}
              roundLabel={t.common.round}
              pointsLabel={t.common.points}
            />
          </ChartFigure>
        </Section>
      )}

      <div className="grid gap-8 lg:grid-cols-2">
        <Section title={t.seasons.driverStandings} id="pilotos">
          {drivers ? (
            <DataTable
              caption={t.seasons.driverStandings}
              captionHidden
              rows={drivers}
              rowKey={(r) => r.driver_id}
              compact
              columns={[
                { header: t.common.positionShort, align: "right", cell: (r) => r.position_text },
                {
                  header: t.common.driver,
                  rowHeader: true,
                  cell: (r) => (
                    <>
                      <Link href={`/${locale}/drivers/${r.driver_id}`}>{r.name}</Link>
                      {r.is_champion && (
                        <>
                          {" "}
                          <Pill tone="best">{t.common.champion}</Pill>
                        </>
                      )}
                    </>
                  ),
                },
                { header: t.common.constructors, cell: (r) => r.constructors.join(", ") },
                { header: t.common.wins, align: "right", className: "tabular", cell: (r) => r.wins },
                {
                  header: t.common.points,
                  align: "right",
                  className: "tabular",
                  cell: (r) => number(r.points, locale, 1),
                },
              ]}
            />
          ) : (
            <EmptyState>{t.common.noData}</EmptyState>
          )}
        </Section>

        <Section title={t.seasons.constructorStandings} id="constructores">
          {constructors && constructors.length > 0 ? (
            <DataTable
              caption={t.seasons.constructorStandings}
              captionHidden
              rows={constructors}
              rowKey={(r) => r.constructor_id}
              compact
              columns={[
                { header: t.common.positionShort, align: "right", cell: (r) => r.position_text },
                {
                  header: t.common.constructor,
                  rowHeader: true,
                  cell: (r) => (
                    <>
                      <Link href={`/${locale}/constructors/${r.constructor_id}`}>{r.name}</Link>
                      {r.is_champion && (
                        <>
                          {" "}
                          <Pill tone="best">{t.common.champion}</Pill>
                        </>
                      )}
                    </>
                  ),
                },
                { header: t.common.engine, cell: (r) => r.engine ?? "—" },
                { header: t.common.wins, align: "right", className: "tabular", cell: (r) => r.wins },
                {
                  header: t.common.points,
                  align: "right",
                  className: "tabular",
                  cell: (r) => number(r.points, locale, 1),
                },
              ]}
            />
          ) : (
            <EmptyState>{fill(t.seasons.noConstructors, { season: year })}</EmptyState>
          )}
        </Section>
      </div>

      <Section title={t.seasons.calendar} id="calendario">
        <DataTable
          caption={t.seasons.calendar}
          captionHidden
          rows={season.races}
          rowKey={(r) => r.race_id}
          columns={[
            { header: t.common.roundShort, align: "right", className: "tabular", cell: (r) => r.round },
            {
              header: t.common.grandPrix,
              rowHeader: true,
              cell: (r) =>
                r.is_completed ? (
                  <Link href={`/${locale}/races/${r.race_id}`}>{r.grand_prix_name}</Link>
                ) : (
                  r.grand_prix_name
                ),
            },
            { header: t.common.circuit, cell: (r) => `${r.circuit_name} (${r.country})` },
            { header: t.common.date, className: "tabular whitespace-nowrap", cell: (r) => date(r.date, locale) },
            {
              header: t.common.winner,
              cell: (r) =>
                r.winner ? (
                  <Link href={`/${locale}/drivers/${r.winner.id}`}>{r.winner.name}</Link>
                ) : (
                  <Pill>{t.common.upcoming}</Pill>
                ),
            },
          ]}
        />
      </Section>
    </>
  );
}

function ProgressionTable({
  rows,
  t,
  locale,
}: {
  rows: Schemas["StandingsProgression"][];
  t: Awaited<ReturnType<typeof getDictionary>>["t"];
  locale: string;
}) {
  const rounds = [...new Set(rows.map((r) => r.round))].sort((a, b) => a - b);
  const lastRound = rounds[rounds.length - 1];
  const final = rows.filter((r) => r.round === lastRound);
  const pointsOf = (id: string, round: number) => rows.find((r) => r.id === id && r.round === round)?.points;
  return (
    <DataTable
      caption={t.seasons.progression}
      rows={final}
      rowKey={(r) => r.id}
      compact
      columns={[
        { header: t.common.driver, rowHeader: true, cell: (r) => r.name },
        ...rounds.map((round) => ({
          header: `${t.common.roundShort}${round}`,
          align: "right" as const,
          className: "tabular",
          cell: (r: Schemas["StandingsProgression"]) => number(pointsOf(r.id, round), locale, 1),
        })),
      ]}
    />
  );
}
