import { apiGet, type Schemas } from "@/lib/api/client";
import { date } from "@/lib/format";
import type { Dictionary, Locale } from "@/lib/i18n";
import { fill } from "@/lib/text";

export async function SiteFooter({ locale, t }: { locale: Locale; t: Dictionary }) {
  // El pie no debe romper la página si la API no responde.
  const health = await apiGet<Schemas["Health"]>("/health").catch(() => null);
  const data = health?.data;
  return (
    <footer className="border-t border-line bg-surface text-sm text-muted">
      <div className="mx-auto grid max-w-6xl gap-2 px-4 py-6 sm:px-6">
        <p>{t.site.footer.sources}</p>
        {data?.generated_at && (
          <p>
            {fill(t.site.footer.updated, {
              date: date(data.generated_at.slice(0, 10), locale),
              release: data.f1db_release ?? "—",
            })}
          </p>
        )}
        <p>
          {t.site.footer.project} {t.site.footer.unofficial}
        </p>
      </div>
    </footer>
  );
}
