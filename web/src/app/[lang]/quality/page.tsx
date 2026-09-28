import type { Metadata } from "next";

import { DataTable, PageHeader, Pill, Section } from "@/components/ui";
import { apiGetRequired, type Schemas } from "@/lib/api/client";
import { number } from "@/lib/format";
import { getDictionary } from "@/lib/i18n";
import { fill } from "@/lib/text";

export async function generateMetadata({ params }: PageProps<"/[lang]/quality">): Promise<Metadata> {
  const { t } = await getDictionary((await params).lang);
  return { title: t.quality.title };
}

const TONES = { PASS: "good", FAIL: "bad", INFO: "neutral", NO_DATA: "neutral" } as const;

export default async function QualityPage({ params }: PageProps<"/[lang]/quality">) {
  const { locale, t } = await getDictionary((await params).lang);
  const checks = await apiGetRequired<Schemas["QualityCheck"][]>("/quality");
  const statuses = t.quality.statuses as Record<string, string>;
  const gated = checks.filter((c) => c.min_match_pct !== null);
  const informative = checks.filter((c) => c.min_match_pct === null);
  const pct = (value: number | null | undefined) => (value === null || value === undefined ? "—" : `${number(value, locale, 2)} %`);

  const columns = (withThreshold: boolean) => [
    { header: t.quality.check, rowHeader: true, cell: (c: Schemas["QualityCheck"]) => c.description },
    {
      header: t.quality.compared,
      align: "right" as const,
      className: "tabular",
      cell: (c: Schemas["QualityCheck"]) => number(c.compared, locale),
    },
    {
      header: t.quality.matched,
      align: "right" as const,
      className: "tabular",
      cell: (c: Schemas["QualityCheck"]) => number(c.matched, locale),
    },
    { header: t.quality.match, align: "right" as const, className: "tabular", cell: (c: Schemas["QualityCheck"]) => pct(c.match_pct) },
    ...(withThreshold
      ? [
          {
            header: t.quality.threshold,
            align: "right" as const,
            className: "tabular",
            cell: (c: Schemas["QualityCheck"]) => pct(c.min_match_pct),
          },
          {
            header: t.common.status,
            cell: (c: Schemas["QualityCheck"]) => (
              <Pill tone={TONES[c.status as keyof typeof TONES] ?? "neutral"}>{statuses[c.status] ?? c.status}</Pill>
            ),
          },
        ]
      : []),
  ];

  return (
    <>
      <PageHeader
        title={t.quality.title}
        lede={t.quality.lede}
      >
        <p className="font-semibold">
          {fill(t.quality.summary, {
            pass: gated.filter((c) => c.status === "PASS").length,
            fail: gated.filter((c) => c.status === "FAIL").length,
          })}
        </p>
      </PageHeader>
      <Section title={t.quality.gatedTitle} id="controles">
        <DataTable caption={t.quality.gatedTitle} captionHidden rows={gated} rowKey={(c) => c.check_id} compact columns={columns(true)} />
      </Section>
      <Section title={t.quality.infoTitle} id="informativos" lede={t.quality.infoLede}>
        <DataTable
          caption={t.quality.infoTitle}
          captionHidden
          rows={informative}
          rowKey={(c) => c.check_id}
          compact
          columns={columns(false)}
        />
      </Section>
      <Section title={t.quality.sourcesTitle} id="fuentes">
        <ul className="grid max-w-[68ch] list-disc gap-2 pl-5">
          {t.quality.sources.map((source) => (
            <li key={source}>{source}</li>
          ))}
        </ul>
      </Section>
    </>
  );
}
