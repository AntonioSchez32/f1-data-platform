import type { Metadata } from "next";
import Link from "next/link";

import { SearchForm } from "@/components/search-form";
import { DataTable, EmptyState, PageHeader, Section } from "@/components/ui";
import { apiGetRequired, type Schemas } from "@/lib/api/client";
import { getDictionary } from "@/lib/i18n";
import { fill } from "@/lib/text";

export async function generateMetadata({ params }: PageProps<"/[lang]/constructors">): Promise<Metadata> {
  const { t } = await getDictionary((await params).lang);
  return { title: t.constructors.title };
}

export default async function ConstructorsPage({ params, searchParams }: PageProps<"/[lang]/constructors">) {
  const { locale, t } = await getDictionary((await params).lang);
  const raw = (await searchParams).q;
  const query = typeof raw === "string" && raw.trim().length >= 2 ? raw.trim() : undefined;
  const teams = await apiGetRequired<Schemas["ConstructorSummary"][]>("/constructors", {
    search: query,
    limit: query ? 100 : 50,
  });
  const caption = query ? fill(t.drivers.resultsFor, { query }) : t.constructors.topByWins;

  return (
    <>
      <PageHeader title={t.constructors.title} lede={t.constructors.lede}>
        <SearchForm
          action={`/${locale}/constructors`}
          label={t.constructors.searchLabel}
          buttonLabel={t.common.search}
          defaultValue={query}
        />
      </PageHeader>
      <Section title={caption} id="lista">
        {teams.length === 0 ? (
          <EmptyState>{t.constructors.none}</EmptyState>
        ) : (
          <DataTable
            caption={caption}
            captionHidden
            rows={teams}
            rowKey={(c) => c.constructor_id}
            columns={[
              {
                header: t.common.constructor,
                rowHeader: true,
                cell: (c) => <Link href={`/${locale}/constructors/${c.constructor_id}`}>{c.name}</Link>,
              },
              {
                header: t.drivers.career,
                className: "tabular",
                cell: (c) =>
                  c.first_season === c.last_season ? (c.first_season ?? "—") : `${c.first_season}–${c.last_season}`,
              },
              { header: t.records.races, align: "right", className: "tabular", cell: (c) => c.race_entries },
              { header: t.common.wins, align: "right", className: "tabular", cell: (c) => c.wins },
              { header: t.common.championships, align: "right", className: "tabular", cell: (c) => c.championships },
            ]}
          />
        )}
      </Section>
    </>
  );
}
