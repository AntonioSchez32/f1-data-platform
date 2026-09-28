import Link from "next/link";

import { TabNav } from "@/components/tab-nav";
import { PageHeader } from "@/components/ui";
import { apiGetRequired, type Schemas } from "@/lib/api/client";
import { date, number } from "@/lib/format";
import { getDictionary } from "@/lib/i18n";
import { getRace } from "@/lib/race";
import { fill } from "@/lib/text";

export async function generateMetadata({ params }: LayoutProps<"/[lang]/races/[id]">) {
  const race = await getRace((await params).id);
  return { title: `${race.grand_prix_name} ${race.season}` };
}

export default async function RaceLayout({ children, params }: LayoutProps<"/[lang]/races/[id]">) {
  const { lang, id } = await params;
  const { locale, t } = await getDictionary(lang);
  const race = await getRace(id);
  const calendar = await apiGetRequired<Schemas["SeasonDetail"]>(`/seasons/${race.season}`);
  const index = calendar.races.findIndex((r) => r.race_id === race.race_id);
  const previous = calendar.races[index - 1];
  const next = calendar.races[index + 1];
  const base = `/${locale}/races/${race.race_id}`;
  const tabs = [
    { href: base, label: t.race.tabs.results },
    { href: `${base}/qualifying`, label: t.race.tabs.qualifying },
    { href: `${base}/lap-chart`, label: t.race.tabs.lapChart },
    { href: `${base}/tyres`, label: t.race.tabs.tyres },
    { href: `${base}/pace`, label: t.race.tabs.pace },
    { href: `${base}/pitstops`, label: t.race.tabs.pitstops },
    ...(race.season >= 2024 ? [{ href: `${base}/telemetry`, label: t.race.tabs.telemetry }] : []),
  ];

  return (
    <>
      <PageHeader
        eyebrow={
          <Link href={`/${locale}/seasons/${race.season}`} className="text-muted">
            {t.common.season} {race.season} · {t.common.round} {race.round}
          </Link>
        }
        title={race.official_name}
        lede={
          <>
            {date(race.date, locale)} · {race.circuit_name}, {race.country}
            {race.laps && race.distance_km
              ? ` · ${fill(t.race.distance, { laps: race.laps, km: number(race.distance_km, locale, 1) })}`
              : ""}
          </>
        }
      >
        <nav aria-label={t.common.season} className="flex flex-wrap gap-4 text-sm">
          {previous && (
            <Link href={`/${locale}/races/${previous.race_id}`} rel="prev">
              ← {t.race.previousRace}: {previous.grand_prix_name}
            </Link>
          )}
          {next?.is_completed && (
            <Link href={`/${locale}/races/${next.race_id}`} rel="next">
              {t.race.nextRace}: {next.grand_prix_name} →
            </Link>
          )}
        </nav>
      </PageHeader>
      {race.is_completed ? (
        <>
          <TabNav label={t.race.tabs.label} tabs={tabs} />
          {children}
        </>
      ) : (
        <p className="text-muted">{t.race.upcomingRace}</p>
      )}
    </>
  );
}
