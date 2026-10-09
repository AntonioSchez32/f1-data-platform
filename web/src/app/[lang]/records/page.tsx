import type { Metadata } from "next";
import Link from "next/link";

import { BarChart } from "@/components/charts/bar-chart";
import { ChartFigure } from "@/components/charts/chart-figure";
import { parseYear, SeasonRangeForm } from "@/components/season-range-form";
import { SessionSwitch } from "@/components/session-switch";
import { DataTable, EmptyState, PageHeader, Section, type Column } from "@/components/ui";
import { apiGetRequired, type Schemas } from "@/lib/api/client";
import { number } from "@/lib/format";
import { getDictionary } from "@/lib/i18n";
import { fill } from "@/lib/text";

type Ranking = Schemas["DriverRanking"] | Schemas["ConstructorRanking"];
const ORDERS = [
  "wins",
  "championships",
  "podiums",
  "pole_positions",
  "fastest_laps",
  "points",
  "points_historical",
  "entries",
] as const;
type Order = (typeof ORDERS)[number];

export async function generateMetadata({ params }: PageProps<"/[lang]/records">): Promise<Metadata> {
  const { t } = await getDictionary((await params).lang);
  return { title: t.records.title };
}

export default async function RecordsPage({ params, searchParams }: PageProps<"/[lang]/records">) {
  const { locale, t } = await getDictionary((await params).lang);
  const query = await searchParams;
  const entity = query.entity === "constructors" ? "constructors" : "drivers";
  // «Puntos históricos» solo existe para los constructores (decisión 37).
  const valid = (o: Order) => ORDERS.includes(o) && (o !== "points_historical" || entity === "constructors");
  const order: Order = valid(query.order as Order) ? (query.order as Order) : "wins";

  const seasons = await apiGetRequired<Schemas["SeasonSummary"][]>("/seasons");
  const last = seasons.find((s) => s.completed_races > 0)!.season;
  const first = seasons[seasons.length - 1].season;
  let from = parseYear(query.from, first, first, last);
  let to = parseYear(query.to, last, first, last);
  if (from > to) [from, to] = [to, from];

  const range = { season_from: from, season_to: to };
  const [table, titles] = await Promise.all([
    apiGetRequired<Ranking[]>(`/rankings/${entity}`, { ...range, order_by: order, limit: 50 }),
    apiGetRequired<Ranking[]>(`/rankings/${entity}`, { ...range, order_by: "championships", limit: 25 }),
  ]);
  const champions = titles.filter((r) => r.championships > 0);
  const base = `/${locale}/records`;
  const keep = (extra: Record<string, string>) =>
    `${base}?${new URLSearchParams({ entity, from: String(from), to: String(to), order, ...extra })}`;
  const isDrivers = entity === "drivers";
  const detail = (id: string) => `/${locale}/${isDrivers ? "drivers" : "constructors"}/${id}`;

  const sortable = (key: Order, header: string): Column<Ranking> => ({
    header: (
      <Link href={keep({ order: key })} className="no-underline hover:underline" aria-label={fill(t.records.sortBy, { column: header })}>
        {header}
        {order === key ? " ▼" : ""}
      </Link>
    ),
    sort: order === key ? "descending" : undefined,
    align: "right",
    className: "tabular",
    cell: (r) => {
      if (key === "points_historical") return "points_historical" in r ? number(r.points_historical, locale, 1) : "—";
      if (key !== "points") return r[key];
      // Constructores sin carreras desde 1958 en el rango: sin campeonato, sin «Puntos».
      if (r.points === null)
        return (
          <>
            —<span aria-hidden="true">*</span>
            <span className="sr-only"> ({t.records.noConstructorsChampionship})</span>
          </>
        );
      return number(r.points, locale, 1);
    },
  });
  const pointsColumns = isDrivers
    ? [sortable("points", t.common.points)]
    : [sortable("points", t.common.points), sortable("points_historical", t.records.pointsHistorical)];
  const hasNullPoints = table.some((r) => r.points === null);

  return (
    <>
      <PageHeader title={t.records.title} lede={t.records.lede}>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <SessionSwitch
            label={t.records.entity}
            current={entity}
            options={[
              { value: "drivers", label: t.records.driversView, href: keep({ entity: "drivers" }) },
              { value: "constructors", label: t.records.constructorsView, href: keep({ entity: "constructors" }) },
            ]}
          />
          <SeasonRangeForm
            label={t.records.range}
            fromLabel={t.home.mapFrom}
            toLabel={t.home.mapTo}
            applyLabel={t.common.apply}
            min={first}
            max={last}
            from={from}
            to={to}
            hidden={{ entity, order }}
          />
        </div>
      </PageHeader>

      <div className="grid gap-8 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Section title={isDrivers ? t.records.titlesByDriver : t.records.titlesByConstructor} id="titulos">
          {champions.length === 0 ? (
            <EmptyState>{t.records.noTitles}</EmptyState>
          ) : (
            <ChartFigure
              title={`${isDrivers ? t.records.titlesByDriver : t.records.titlesByConstructor} · ${from}–${to}`}
              summary={fill(t.records.titlesSummary, {
                name: champions[0].name,
                from,
                to,
                count: champions[0].championships,
              })}
              tableLabel={t.common.viewTable}
              table={
                <DataTable
                  caption={isDrivers ? t.records.titlesByDriver : t.records.titlesByConstructor}
                  rows={champions}
                  rowKey={(r) => r.id}
                  compact
                  columns={[
                    { header: isDrivers ? t.common.driver : t.common.constructor, rowHeader: true, cell: (r) => r.name },
                    { header: t.common.championships, align: "right", className: "tabular", cell: (r) => r.championships },
                  ]}
                />
              }
            >
              <BarChart
                horizontal
                items={champions.map((r) => ({ label: r.name, value: r.championships }))}
                label={isDrivers ? t.records.titlesByDriver : t.records.titlesByConstructor}
                valueLabel={t.common.championships}
              />
            </ChartFigure>
          )}
        </Section>

        <Section title={isDrivers ? t.records.topDrivers : t.records.topConstructors} id="laureados">
          <DataTable
            caption={`${isDrivers ? t.records.topDrivers : t.records.topConstructors} · ${from}–${to}`}
            captionHidden
            rows={table}
            rowKey={(r) => r.id}
            compact
            columns={[
              { header: t.records.rank, align: "right", className: "tabular text-muted", cell: (r) => r.rank },
              {
                header: isDrivers ? t.common.driver : t.common.constructor,
                rowHeader: true,
                className: "whitespace-nowrap",
                cell: (r) => <Link href={detail(r.id)}>{r.name}</Link>,
              },
              { header: t.common.country, className: "whitespace-nowrap", cell: (r) => r.country ?? "—" },
              sortable("entries", t.records.races),
              sortable("wins", t.common.wins),
              sortable("podiums", t.common.podiums),
              sortable("pole_positions", t.common.poles),
              sortable("fastest_laps", t.common.fastestLaps),
              sortable("championships", t.common.championships),
              ...pointsColumns,
            ]}
          />
          {!isDrivers && (
            <div className="mt-3 grid gap-1 text-sm text-muted">
              {hasNullPoints && <p>{t.records.pointsNullNote}</p>}
              <p>{t.records.pointsNote}</p>
            </div>
          )}
        </Section>
      </div>
    </>
  );
}
