import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ChartFigure } from "@/components/charts/chart-figure";
import { SeasonPointsChart } from "@/components/charts/season-points-chart";
import { DataTable, PageHeader, Pill, Section, Stat } from "@/components/ui";
import { apiGet, apiGetRequired, type Schemas } from "@/lib/api/client";
import { number } from "@/lib/format";
import { getDictionary } from "@/lib/i18n";
import { fill } from "@/lib/text";

const getConstructor = (id: string) =>
  /^[a-z0-9-]+$/.test(id) ? apiGet<Schemas["ConstructorDetail"]>(`/constructors/${id}`) : Promise.resolve(null);

export async function generateMetadata({ params }: PageProps<"/[lang]/constructors/[id]">): Promise<Metadata> {
  const team = await getConstructor((await params).id);
  return { title: team?.name };
}

export default async function ConstructorPage({ params }: PageProps<"/[lang]/constructors/[id]">) {
  const { lang, id } = await params;
  const { locale, t } = await getDictionary(lang);
  const team = await getConstructor(id);
  if (!team) notFound();
  const seasons = await apiGetRequired<Schemas["ConstructorSeason"][]>(`/constructors/${id}/seasons`);
  const titles = seasons.filter((s) => s.is_champion).map((s) => s.season);

  return (
    <>
      <PageHeader
        eyebrow={team.country}
        title={team.name}
        lede={team.full_name && team.full_name !== team.name ? team.full_name : undefined}
      />
      <dl className="mb-12 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label={t.common.championships} value={team.championships} />
        <Stat label={t.common.wins} value={team.wins} />
        <Stat label={t.common.podiums} value={team.podiums} />
        <Stat label={t.common.poles} value={team.pole_positions} />
        <Stat label={t.constructors.oneTwo} value={team.one_two_finishes} />
        <Stat label={t.records.races} value={team.race_entries} />
      </dl>
      <Section title={t.constructors.seasonsTitle} id="temporadas">
        <ChartFigure
          title={t.drivers.seasonsChart}
          summary={fill(t.constructors.seasonsSummary, {
            name: team.name,
            first: team.first_season ?? "—",
            last: team.last_season ?? "—",
            titles: titles.length ? titles.join(", ") : "—",
          })}
          tableLabel={t.common.viewTable}
          table={
            <DataTable
              caption={t.constructors.seasonsTitle}
              rows={seasons}
              rowKey={(s) => s.season}
              compact
              columns={[
                {
                  header: t.common.season,
                  rowHeader: true,
                  cell: (s) => <Link href={`/${locale}/seasons/${s.season}`}>{s.season}</Link>,
                },
                {
                  header: t.common.positionShort,
                  align: "right",
                  cell: (s) =>
                    s.is_champion ? <Pill tone="best">{t.common.champion}</Pill> : (s.championship_position_text ?? "—"),
                },
                {
                  header: t.common.points,
                  align: "right",
                  className: "tabular",
                  cell: (s) => number(s.points, locale, 1),
                },
                { header: t.common.wins, align: "right", className: "tabular", cell: (s) => s.wins },
                {
                  header: t.constructors.driversOfSeason,
                  cell: (s) =>
                    s.drivers.map((d, i) => (
                      <span key={d.id}>
                        {i > 0 && ", "}
                        <Link href={`/${locale}/drivers/${d.id}`}>{d.name}</Link>
                      </span>
                    )),
                },
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
    </>
  );
}
