import Link from "next/link";

import { parseYear, SeasonRangeForm } from "@/components/season-range-form";
import { SessionSwitch } from "@/components/session-switch";
import { DataTable, PageHeader, Section } from "@/components/ui";
import { type MapPoint, WorldMap } from "@/components/world-map";
import { apiGetRequired, type Schemas } from "@/lib/api/client";
import { gap, number, raceTime } from "@/lib/format";
import { getDictionary } from "@/lib/i18n";
import { fill } from "@/lib/text";

type CountryEvents = { country: string; races: number; circuits: string[]; latitude: number; longitude: number };

/** Eventos por país: centro ponderado por carreras de sus circuitos (página de inicio del TFG). */
function byCountry(circuits: Schemas["Circuit"][]): CountryEvents[] {
  return [...Map.groupBy(circuits, (c) => c.country)]
    .map(([country, items]) => {
      const located = items.filter((c) => c.latitude !== null && c.longitude !== null);
      const weight = located.reduce((sum, c) => sum + c.races, 0) || 1;
      return {
        country,
        races: items.reduce((sum, c) => sum + c.races, 0),
        circuits: items.map((c) => c.name),
        latitude: located.reduce((sum, c) => sum + c.latitude! * c.races, 0) / weight,
        longitude: located.reduce((sum, c) => sum + c.longitude! * c.races, 0) / weight,
      };
    })
    .sort((a, b) => b.races - a.races);
}

export default async function Home({ params, searchParams }: PageProps<"/[lang]">) {
  const { locale, t } = await getDictionary((await params).lang);
  const query = await searchParams;

  const seasons = await apiGetRequired<Schemas["SeasonSummary"][]>("/seasons");
  const current = seasons.find((s) => s.completed_races > 0)!;
  const firstSeason = seasons[seasons.length - 1].season;
  let from = parseYear(query.from, firstSeason, firstSeason, current.season);
  let to = parseYear(query.to, current.season, firstSeason, current.season);
  if (from > to) [from, to] = [to, from];

  const [calendar, drivers, constructors, circuits] = await Promise.all([
    apiGetRequired<Schemas["SeasonDetail"]>(`/seasons/${current.season}`),
    apiGetRequired<Schemas["DriverStanding"][]>(`/seasons/${current.season}/standings/drivers`),
    apiGetRequired<Schemas["ConstructorStanding"][]>(
      `/seasons/${current.season}/standings/constructors`,
    ).catch(() => []),
    apiGetRequired<Schemas["Circuit"][]>("/circuits", { season_from: from, season_to: to }),
  ]);
  const lastRace = [...calendar.races].reverse().find((r) => r.is_completed)!;
  const results = await apiGetRequired<Schemas["RaceResult"][]>(`/races/${lastRace.race_id}/results`);
  const view = query.view === "circuit" ? "circuit" : "country";
  const countries = byCountry(circuits);
  const points: MapPoint[] =
    view === "country"
      ? countries.map((c) => ({ ...c, id: c.country, label: `${c.country}: ${c.races} GP` }))
      : circuits
          .filter((c) => c.latitude !== null && c.longitude !== null)
          .map((c) => ({
            id: c.circuit_id,
            label: `${c.name} (${c.country}): ${c.races} GP`,
            latitude: c.latitude!,
            longitude: c.longitude!,
            races: c.races,
          }));
  const caption = fill(t.home.mapCaption, { circuits: circuits.length, countries: countries.length });
  const mapHref = (v: string) => `/${locale}?${new URLSearchParams({ view: v, from: String(from), to: String(to) })}#mapa`;

  return (
    <>
      <PageHeader eyebrow={t.home.eyebrow} title={t.home.title} lede={t.home.lede}>
        <form action={`/${locale}/drivers`} role="search" className="mt-2 flex max-w-md gap-2">
          <label htmlFor="buscar-piloto" className="sr-only">
            {t.home.searchLabel}
          </label>
          <input
            id="buscar-piloto"
            name="q"
            type="search"
            minLength={2}
            placeholder={t.home.searchPlaceholder}
            className="min-w-0 flex-1 rounded-md border border-line bg-surface px-3 py-2"
          />
          <button type="submit" className="rounded-md bg-ink px-4 py-2 font-semibold text-surface">
            {t.common.search}
          </button>
        </form>
      </PageHeader>

      <div className="grid gap-8 lg:grid-cols-2">
        <Section
          title={t.home.lastRace}
          id="ultima-carrera"
          action={
            <Link href={`/${locale}/races/${lastRace.race_id}`} className="text-sm font-semibold">
              {t.home.fullResult}
            </Link>
          }
        >
          <p className="-mt-2 text-muted">
            {lastRace.grand_prix_name} · {t.common.roundShort}
            {lastRace.round} {lastRace.season}
          </p>
          <DataTable
            caption={`${lastRace.grand_prix_name} ${lastRace.season}`}
            captionHidden
            rows={results.slice(0, 10)}
            rowKey={(r) => r.driver_id}
            columns={[
              { header: t.common.positionShort, cell: (r) => r.position_text, align: "right" },
              {
                header: t.common.driver,
                rowHeader: true,
                cell: (r) => <Link href={`/${locale}/drivers/${r.driver_id}`}>{r.driver_name}</Link>,
              },
              { header: t.common.constructor, cell: (r) => r.constructor_name },
              {
                header: t.common.time,
                align: "right",
                className: "tabular",
                cell: (r, i) =>
                  i === 0 ? raceTime(r.time_ms) : gap(r.gap_ms, r.gap_laps, t.common.lapsShort),
              },
            ]}
          />
        </Section>

        <Section
          title={fill(t.home.standings, { season: current.season })}
          id="campeonato"
          action={
            <Link href={`/${locale}/seasons/${current.season}`} className="text-sm font-semibold">
              {t.home.fullStandings}
            </Link>
          }
        >
          <p className="-mt-2 text-muted">
            {fill(t.home.afterRound, { round: lastRace.round, total: calendar.races.length })}
          </p>
          <DataTable
            caption={t.seasons.driverStandings}
            rows={drivers.slice(0, 5)}
            rowKey={(r) => r.driver_id}
            compact
            columns={[
              { header: t.common.positionShort, cell: (r) => r.position_text, align: "right" },
              {
                header: t.common.driver,
                rowHeader: true,
                cell: (r) => <Link href={`/${locale}/drivers/${r.driver_id}`}>{r.name}</Link>,
              },
              {
                header: t.common.points,
                align: "right",
                className: "tabular",
                cell: (r) => number(r.points, locale, 1),
              },
            ]}
          />
          {constructors.length > 0 && (
            <DataTable
              caption={t.seasons.constructorStandings}
              rows={constructors.slice(0, 5)}
              rowKey={(r) => r.constructor_id}
              compact
              columns={[
                { header: t.common.positionShort, cell: (r) => r.position_text, align: "right" },
                {
                  header: t.common.constructor,
                  rowHeader: true,
                  cell: (r) => (
                    <Link href={`/${locale}/constructors/${r.constructor_id}`}>{r.name}</Link>
                  ),
                },
                {
                  header: t.common.points,
                  align: "right",
                  className: "tabular",
                  cell: (r) => number(r.points, locale, 1),
                },
              ]}
            />
          )}
        </Section>
      </div>

      <Section
        title={t.home.mapTitle}
        id="mapa"
        lede={fill(view === "country" ? t.home.mapLede : t.home.mapLedeCircuit, { from, to })}
      >
        <div className="flex flex-wrap items-end justify-between gap-4">
          <SessionSwitch
            label={t.home.mapView}
            current={view}
            options={[
              { value: "country", label: t.home.byCountry, href: mapHref("country") },
              { value: "circuit", label: t.home.byCircuit, href: mapHref("circuit") },
            ]}
          />
          <SeasonRangeForm
            label={t.home.mapTitle}
            fromLabel={t.home.mapFrom}
            toLabel={t.home.mapTo}
            applyLabel={t.common.apply}
            min={firstSeason}
            max={current.season}
            from={from}
            to={to}
            hidden={{ view }}
          />
        </div>
        <figure className="grid gap-3 rounded-lg border border-line bg-surface p-4">
          <WorldMap points={points} title={t.home.mapTitle} description={caption} />
          <figcaption className="text-sm text-muted">{caption}</figcaption>
          <details>
            <summary className="cursor-pointer text-sm font-semibold text-muted hover:text-ink">
              {t.common.viewTable}
            </summary>
            <div className="mt-3">
              {view === "country" ? (
                <DataTable
                  caption={t.home.mapTableCaptionCountry}
                  rows={countries}
                  rowKey={(c) => c.country}
                  compact
                  columns={[
                    { header: t.common.country, rowHeader: true, cell: (c) => c.country },
                    { header: "GP", align: "right", className: "tabular", cell: (c) => c.races },
                    { header: t.home.circuits, cell: (c) => c.circuits.join(", ") },
                  ]}
                />
              ) : (
                <DataTable
                  caption={t.home.mapTableCaption}
                  rows={circuits}
                  rowKey={(c) => c.circuit_id}
                  compact
                  columns={[
                    { header: t.common.circuit, rowHeader: true, cell: (c) => c.name },
                    { header: t.common.country, cell: (c) => c.country },
                    { header: "GP", align: "right", className: "tabular", cell: (c) => c.races },
                    {
                      header: t.common.season,
                      className: "tabular",
                      cell: (c) =>
                        c.first_season === c.last_season ? c.first_season : `${c.first_season}–${c.last_season}`,
                    },
                  ]}
                />
              )}
            </div>
          </details>
        </figure>
      </Section>
    </>
  );
}
