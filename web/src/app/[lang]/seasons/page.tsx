import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { SeasonPicker } from "@/components/season-picker";
import { PageHeader } from "@/components/ui";
import { apiGetRequired, type Schemas } from "@/lib/api/client";
import { getDictionary } from "@/lib/i18n";
import { fill } from "@/lib/text";

export async function generateMetadata({ params }: PageProps<"/[lang]/seasons">): Promise<Metadata> {
  const { t } = await getDictionary((await params).lang);
  return { title: t.seasons.title };
}

export default async function SeasonsPage({ params, searchParams }: PageProps<"/[lang]/seasons">) {
  const { locale, t } = await getDictionary((await params).lang);
  const year = (await searchParams).year;
  if (typeof year === "string" && /^\d{4}$/.test(year)) redirect(`/${locale}/seasons/${year}`);
  const seasons = await apiGetRequired<Schemas["SeasonSummary"][]>("/seasons");
  const decades = Map.groupBy(seasons, (s) => Math.floor(s.season / 10) * 10);

  return (
    <>
      <PageHeader title={t.seasons.title} lede={t.seasons.lede}>
        <SeasonPicker
          action={`/${locale}/seasons`}
          seasons={seasons.map((s) => s.season)}
          label={t.seasons.choose}
          buttonLabel={t.seasons.go}
        />
      </PageHeader>
      <div className="grid gap-10">
        {[...decades].map(([decade, items]) => (
          <section key={decade} aria-labelledby={`decada-${decade}`} className="grid gap-3">
            <h2 id={`decada-${decade}`} className="text-xl font-bold">
              {fill(t.seasons.decade, { decade })}
            </h2>
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((s) => (
                <li key={s.season}>
                  <Link
                    href={`/${locale}/seasons/${s.season}`}
                    className="grid h-full gap-1 rounded-lg border border-line bg-surface px-4 py-3 no-underline hover:border-ink"
                  >
                    <span className="font-display text-2xl font-bold tabular-nums">{s.season}</span>
                    <span className="text-sm">
                      <span className="text-muted">{t.common.champion}: </span>
                      {s.drivers_champion?.name ??
                        fill(t.seasons.inProgress, { completed: s.completed_races, total: s.races })}
                    </span>
                    {s.constructors_champion && (
                      <span className="text-sm">
                        <span className="text-muted">{t.common.constructor}: </span>
                        {s.constructors_champion.name}
                      </span>
                    )}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </>
  );
}
