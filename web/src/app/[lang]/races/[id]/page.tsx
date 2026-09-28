import Link from "next/link";

import { SessionSwitch } from "@/components/session-switch";
import { DataTable, Pill, Section } from "@/components/ui";
import { gap, number, raceTime } from "@/lib/format";
import { getDictionary } from "@/lib/i18n";
import { getRace, getResults } from "@/lib/race";

export default async function RaceResultsPage({ params, searchParams }: PageProps<"/[lang]/races/[id]">) {
  const { lang, id } = await params;
  const { locale, t } = await getDictionary(lang);
  const race = await getRace(id);
  const session = race.has_sprint && (await searchParams).session === "sprint" ? "sprint" : "race";
  const results = await getResults(id, session);
  const base = `/${locale}/races/${id}`;

  return (
    <Section
      title={session === "sprint" ? t.race.sprintSession : t.race.tabs.results}
      id="resultado"
      action={
        race.has_sprint && (
          <SessionSwitch
            label={t.race.session}
            current={session}
            options={[
              { value: "race", label: t.race.raceSession, href: base },
              { value: "sprint", label: t.race.sprintSession, href: `${base}?session=sprint` },
            ]}
          />
        )
      }
    >
      <DataTable
        caption={`${race.grand_prix_name} ${race.season} · ${
          session === "sprint" ? t.race.sprintSession : t.race.raceSession
        }`}
        captionHidden
        rows={results}
        rowKey={(r) => `${r.driver_id}-${r.driver_number}`}
        columns={[
          { header: t.common.positionShort, align: "right", cell: (r) => r.position_text },
          { header: "#", align: "right", className: "tabular text-muted", cell: (r) => r.driver_number ?? "" },
          {
            header: t.common.driver,
            rowHeader: true,
            cell: (r) => (
              <>
                <Link href={`/${locale}/drivers/${r.driver_id}`}>{r.driver_name}</Link>
                {r.is_fastest_lap && (
                  <>
                    {" "}
                    <Pill tone="best" title={t.race.fastestLap}>
                      {t.race.fastestLap}
                    </Pill>
                  </>
                )}
                {r.corrected_fields.length > 0 && (
                  <>
                    {" "}
                    <Pill tone="info" title={`${t.common.corrected}: ${r.corrected_fields.join(", ")}`}>
                      {t.common.correctedShort}
                    </Pill>
                  </>
                )}
              </>
            ),
          },
          {
            header: t.common.constructor,
            cell: (r) => <Link href={`/${locale}/constructors/${r.constructor_id}`}>{r.constructor_name}</Link>,
          },
          { header: t.common.laps, align: "right", className: "tabular", cell: (r) => r.laps ?? "—" },
          {
            header: `${t.common.time} / ${t.common.status}`,
            align: "right",
            className: "tabular whitespace-nowrap",
            cell: (r) =>
              r.position === 1
                ? raceTime(r.time_ms)
                : r.position
                  ? gap(r.gap_ms, r.gap_laps, t.common.lapsShort)
                  : (r.reason_retired ?? r.position_text),
          },
          { header: t.common.grid, align: "right", className: "tabular", cell: (r) => r.grid_position_text ?? "—" },
          {
            header: t.common.points,
            align: "right",
            className: "tabular",
            cell: (r) => (r.points ? number(r.points, locale, 1) : ""),
          },
        ]}
      />
    </Section>
  );
}
