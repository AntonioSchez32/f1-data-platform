import Link from "next/link";

import { BarChart } from "@/components/charts/bar-chart";
import { ChartFigure } from "@/components/charts/chart-figure";
import { SessionSwitch } from "@/components/session-switch";
import { DataTable, EmptyState, Pill, Section } from "@/components/ui";
import { apiGetRequired, type Schemas } from "@/lib/api/client";
import { lapTime, number } from "@/lib/format";
import { getDictionary } from "@/lib/i18n";
import { getRace } from "@/lib/race";
import { fill } from "@/lib/text";

type Row = Schemas["QualifyingResult"];

export default async function QualifyingPage({
  params,
  searchParams,
}: PageProps<"/[lang]/races/[id]/qualifying">) {
  const { lang, id } = await params;
  const { locale, t } = await getDictionary(lang);
  const race = await getRace(id);
  const query = await searchParams;
  // En 2021-2022 no había clasificación sprint propia (la del viernes daba la parrilla del sprint).
  const sprint = race.has_sprint_qualifying && query.session === "sprint_qualifying";
  const session = sprint ? "sprint_qualifying" : "qualifying";
  const by = query.by === "constructors" ? "constructors" : "drivers";
  const rows = await apiGetRequired<Row[]>(`/races/${id}/qualifying`, { session });
  const base = `/${locale}/races/${id}/qualifying`;
  const href = (extra: Record<string, string>) =>
    `${base}?${new URLSearchParams({ ...(sprint ? { session } : {}), by, ...extra })}`;
  const hasSegments = rows.some((r) => r.q1_ms !== null);

  // Mejor tiempo de cada segmento: en morado, como en las pantallas de cronometraje.
  const best = (key: "q1_ms" | "q2_ms" | "q3_ms") => Math.min(...rows.map((r) => r[key] ?? Infinity));
  const bests = { q1_ms: best("q1_ms"), q2_ms: best("q2_ms"), q3_ms: best("q3_ms") };
  const segment = (key: "q1_ms" | "q2_ms" | "q3_ms", label: string) => ({
    header: label,
    align: "right" as const,
    className: "tabular",
    cell: (r: Row) =>
      r[key] !== null && r[key] === bests[key] ? (
        <span className="font-semibold text-purple" title={t.race.bestLap}>
          {lapTime(r[key])}
        </span>
      ) : (
        lapTime(r[key])
      ),
  });

  // Página «Rendimiento en clasificación» del TFG: % respecto al mejor tiempo de la sesión.
  const withGap = rows.filter((r) => r.gap_to_pole_pct !== null);
  const gapItems =
    by === "drivers"
      ? withGap.map((r) => ({ id: r.driver_id, label: r.driver_name, value: r.gap_to_pole_pct! }))
      : [...Map.groupBy(withGap, (r) => r.constructor_id)].map(([teamId, items]) => ({
          id: teamId,
          label: items[0].constructor_name,
          value: items.reduce((sum, r) => sum + r.gap_to_pole_pct!, 0) / items.length,
        }));
  gapItems.sort((a, b) => a.value - b.value);

  return (
    <>
      {gapItems.length > 1 && (
        <Section
          title={t.race.qualiGapTitle}
          id="rendimiento"
          lede={t.race.qualiGapLede}
          action={
            <SessionSwitch
              label={t.records.entity}
              current={by}
              options={[
                { value: "drivers", label: t.race.byDrivers, href: href({ by: "drivers" }) },
                { value: "constructors", label: t.race.byConstructors, href: href({ by: "constructors" }) },
              ]}
            />
          }
        >
          <ChartFigure
            title={`${t.race.qualiGapTitle} · ${race.grand_prix_name} ${race.season}`}
            summary={fill(t.race.qualiGapSummary, {
              best: gapItems[0].label,
              last: gapItems[gapItems.length - 1].label,
              gap: number(gapItems[gapItems.length - 1].value, locale, 2),
            })}
            tableLabel={t.common.viewTable}
            table={
              <DataTable
                caption={t.race.qualiGapTitle}
                rows={gapItems}
                rowKey={(i) => i.id}
                compact
                columns={[
                  {
                    header: by === "drivers" ? t.common.driver : t.common.constructor,
                    rowHeader: true,
                    cell: (i) => i.label,
                  },
                  {
                    header: t.race.gapPct,
                    align: "right",
                    className: "tabular",
                    cell: (i) => `${number(i.value, locale, 3)} %`,
                  },
                ]}
              />
            }
          >
            <BarChart
              items={gapItems.map((i, index) => ({ label: i.label, value: i.value, highlight: index === 0 }))}
              label={t.race.qualiGapTitle}
              valueLabel={t.race.gapPct}
              unit=" %"
              decimals={2}
            />
          </ChartFigure>
        </Section>
      )}

      <Section
        title={sprint ? t.race.sprintQualifyingSession : t.race.qualifyingSession}
        id="clasificacion"
        action={
          race.has_sprint_qualifying && (
            <SessionSwitch
              label={t.race.session}
              current={session}
              options={[
                { value: "qualifying", label: t.race.qualifyingSession, href: base },
                {
                  value: "sprint_qualifying",
                  label: t.race.sprintQualifyingSession,
                  href: `${base}?session=sprint_qualifying`,
                },
              ]}
            />
          )
        }
      >
        {rows.length === 0 ? (
          <EmptyState>{t.common.noData}</EmptyState>
        ) : (
          <DataTable
            caption={`${race.grand_prix_name} ${race.season} · ${t.race.qualifyingSession}`}
            captionHidden
            rows={rows}
            rowKey={(r) => `${r.driver_id}-${r.driver_number}`}
            columns={[
              { header: t.common.positionShort, align: "right", cell: (r) => r.position_text },
              {
                header: t.common.driver,
                rowHeader: true,
                cell: (r) => (
                  <>
                    <Link href={`/${locale}/drivers/${r.driver_id}`}>{r.driver_name}</Link>
                    {r.position === 1 && (
                      <>
                        {" "}
                        <Pill tone="best">Pole</Pill>
                      </>
                    )}
                  </>
                ),
              },
              { header: t.common.constructor, cell: (r) => r.constructor_name },
              ...(hasSegments
                ? [segment("q1_ms", "Q1"), segment("q2_ms", "Q2"), segment("q3_ms", "Q3")]
                : [
                    {
                      header: t.common.time,
                      align: "right" as const,
                      className: "tabular",
                      cell: (r: Row) => lapTime(r.best_time_ms),
                    },
                  ]),
              {
                header: t.race.gapPct,
                align: "right",
                className: "tabular",
                cell: (r) => (r.gap_to_pole_pct === null ? "" : `+${number(r.gap_to_pole_pct, locale, 3)} %`),
              },
            ]}
          />
        )}
      </Section>
    </>
  );
}
