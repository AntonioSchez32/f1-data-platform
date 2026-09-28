import type { Metadata } from "next";
import Link from "next/link";

import { SearchForm } from "@/components/search-form";
import { DataTable, EmptyState, PageHeader, Section } from "@/components/ui";
import { apiGetRequired, type Schemas } from "@/lib/api/client";
import { getDictionary } from "@/lib/i18n";
import { fill } from "@/lib/text";

export async function generateMetadata({ params }: PageProps<"/[lang]/drivers">): Promise<Metadata> {
  const { t } = await getDictionary((await params).lang);
  return { title: t.drivers.title };
}

export default async function DriversPage({ params, searchParams }: PageProps<"/[lang]/drivers">) {
  const { locale, t } = await getDictionary((await params).lang);
  const raw = (await searchParams).q;
  const query = typeof raw === "string" && raw.trim().length >= 2 ? raw.trim() : undefined;
  const drivers = await apiGetRequired<Schemas["DriverSummary"][]>("/drivers", {
    search: query,
    limit: query ? 100 : 50,
  });

  return (
    <>
      <PageHeader title={t.drivers.title} lede={t.drivers.lede}>
        <SearchForm
          action={`/${locale}/drivers`}
          label={t.drivers.searchLabel}
          placeholder={t.home.searchPlaceholder}
          buttonLabel={t.common.search}
          defaultValue={query}
        />
      </PageHeader>
      <Section title={query ? fill(t.drivers.resultsFor, { query }) : t.drivers.topByWins} id="lista">
        {drivers.length === 0 ? (
          <EmptyState>{t.drivers.none}</EmptyState>
        ) : (
          <DataTable
            caption={query ? fill(t.drivers.resultsFor, { query }) : t.drivers.topByWins}
            captionHidden
            rows={drivers}
            rowKey={(d) => d.driver_id}
            columns={[
              {
                header: t.common.driver,
                rowHeader: true,
                cell: (d) => <Link href={`/${locale}/drivers/${d.driver_id}`}>{d.name}</Link>,
              },
              {
                header: t.drivers.career,
                className: "tabular",
                cell: (d) =>
                  d.first_season === d.last_season
                    ? (d.first_season ?? "—")
                    : fill(t.drivers.careerYears, { first: d.first_season ?? "", last: d.last_season ?? "" }),
              },
              { header: t.common.starts, align: "right", className: "tabular", cell: (d) => d.race_starts },
              { header: t.common.wins, align: "right", className: "tabular", cell: (d) => d.wins },
              { header: t.common.podiums, align: "right", className: "tabular", cell: (d) => d.podiums },
              { header: t.common.championships, align: "right", className: "tabular", cell: (d) => d.championships },
            ]}
          />
        )}
      </Section>
    </>
  );
}
